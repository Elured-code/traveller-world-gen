#!/usr/bin/env bash
# Provisions a NEW Flex Consumption function app alongside the existing
# classic-Consumption app, for validation before cutover.
#
# Background: in-place migration (`az functionapp flex-migration start`)
# failed with "Cannot change the site ... due to hosting constraints" against
# the existing traveller-world-gen app. Root cause was not conclusively
# identified (region, OS, runtime, plan sharing, slots, VNet, custom domains,
# and storage account settings were all checked and are compatible), so the
# safer path is to stand up a brand-new Flex Consumption app, validate it,
# then cut over — rather than continue fighting the in-place migration tool.
#
# This script creates the new app under a temporary name
# ("$FUNCTIONAPP_NAME-flex") in the SAME resource group, with its OWN storage
# account (Flex Consumption uses a blob-container deployment model, not the
# Azure Files content-share model the old app's storage account is already
# configured for — reusing it risks colliding with WEBSITE_CONTENTSHARE /
# WEBSITE_CONTENTAZUREFILECONNECTIONSTRING settings left on the old account).
# It reuses the EXISTING Application Insights resource so telemetry stays in
# one place.
#
# Usage:
#   az login
#   bash scripts/create_flex_function_app.sh
#
# After running:
#   1. bash scripts/copy_app_settings_to_flex.sh
#   2. bash scripts/prepare_azure.sh && cd azure-api && func azure functionapp
#      publish traveller-world-gen-flex --python
#      (or trigger the GitHub Actions workflow against the new app name)
#   3. Smoke-test https://traveller-world-gen-flex.azurewebsites.net
#   4. Once validated, run scripts/cutover_flex_function_app.sh (destructive —
#      deletes the old app and recreates the Flex app under the original name)

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
RESOURCE_GROUP="traveller-world-gen"
LOCATION="australiaeast"
EXISTING_FUNCTIONAPP_NAME="traveller-world-gen"
FUNCTIONAPP_NAME="traveller-world-gen-flex"     # Temporary validation app name
STORAGE_ACCOUNT="travellerworldgenflex"         # 3-24 chars, lowercase alphanumeric
UAMI_NAME="traveller-world-gen-flex-uami"
APPINSIGHTS_NAME="traveller-world-gen"          # Reuse the existing resource
INSTANCE_MEMORY_MB=2048
MAX_INSTANCE_COUNT=100
# Rejects any HTTP request body over this size at the platform level, as a
# defensive backstop underneath the ASGI-level streaming body-size limit in
# fastapi/app.py (issue #167). Doesn't replace it — see issue #168.
MAX_REQUEST_BODY_BYTES=1048576   # 1 MB
# ─────────────────────────────────────────────────────────────────────────────

echo "==> Confirming Flex Consumption is available in: $LOCATION"
az functionapp list-flexconsumption-locations --query "[?name=='$LOCATION'].name" -o tsv | grep -q "$LOCATION" \
  || { echo "ERROR: $LOCATION does not support Flex Consumption." >&2; exit 1; }

echo "==> Creating storage account: $STORAGE_ACCOUNT"
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access false \
  --output none

echo "==> Creating user-assigned managed identity: $UAMI_NAME"
az identity create \
  --name "$UAMI_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

UAMI_ID=$(az identity show \
  --name "$UAMI_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

UAMI_PRINCIPAL_ID=$(az identity show \
  --name "$UAMI_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query principalId --output tsv)

STORAGE_ID=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

echo "==> Assigning Storage Blob Data Owner role to managed identity"
az role assignment create \
  --assignee-object-id "$UAMI_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Owner" \
  --scope "$STORAGE_ID" \
  --output none

echo "==> Reusing existing Application Insights: $APPINSIGHTS_NAME"
APPINSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
  --app "$APPINSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString --output tsv)

echo "==> Creating Flex Consumption Function App: $FUNCTIONAPP_NAME"
az functionapp create \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$STORAGE_ACCOUNT" \
  --flexconsumption-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --instance-memory "$INSTANCE_MEMORY_MB" \
  --maximum-instance-count "$MAX_INSTANCE_COUNT" \
  --assign-identity "$UAMI_ID" \
  --disable-app-insights \
  --output none

echo "==> Configuring app settings"
az functionapp config appsettings set \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "RATE_LIMIT_PER_MINUTE=100/minute" \
    "TRAVELLER_MAX_BATCH_SIZE=20" \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING" \
    "FUNCTIONS_REQUEST_BODY_SIZE_LIMIT=$MAX_REQUEST_BODY_BYTES" \
  --output none

# `--assign-identity` above only attaches the identity to the app — it does NOT
# switch AzureWebJobsStorage or the deployment storage container off key-based
# auth by itself. Without this explicit step, `functionapp create` leaves both
# as connection strings with an embedded storage account key.
UAMI_CLIENT_ID=$(az identity show --name "$UAMI_NAME" --resource-group "$RESOURCE_GROUP" --query clientId --output tsv)

echo "==> Switching AzureWebJobsStorage to identity-based auth (no stored keys)"
az functionapp config appsettings set \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "AzureWebJobsStorage__accountName=$STORAGE_ACCOUNT" \
    "AzureWebJobsStorage__credential=managedidentity" \
    "AzureWebJobsStorage__clientId=$UAMI_CLIENT_ID" \
  --output none
az functionapp config appsettings delete \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --setting-names AzureWebJobsStorage \
  --output none

echo "==> Switching deployment storage auth to identity-based (no stored keys)"
DEPLOYMENT_CONTAINER=$(az functionapp deployment config show \
  --name "$FUNCTIONAPP_NAME" --resource-group "$RESOURCE_GROUP" \
  --query "storage.value" --output tsv | sed 's#.*/##')
az functionapp deployment config set \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --deployment-storage-name "$STORAGE_ACCOUNT" \
  --deployment-storage-container-name "$DEPLOYMENT_CONTAINER" \
  --deployment-storage-auth-type UserAssignedIdentity \
  --deployment-storage-auth-value "$UAMI_ID" \
  --output none
az functionapp config appsettings delete \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --setting-names DEPLOYMENT_STORAGE_CONNECTION_STRING \
  --output none

echo "==> Enabling basic auth (required for publish profile deployment)"
az resource update \
  --resource-group "$RESOURCE_GROUP" \
  --name scm \
  --namespace Microsoft.Web \
  --resource-type basicPublishingCredentialsPolicies \
  --parent "sites/$FUNCTIONAPP_NAME" \
  --set properties.allow=true \
  --output none

echo ""
echo "Done. Validation app created: $FUNCTIONAPP_NAME"
echo ""
echo "Next steps:"
echo "  1. bash scripts/copy_app_settings_to_flex.sh"
echo "  2. Deploy code to the new app (func azure functionapp publish"
echo "     $FUNCTIONAPP_NAME --python, or a one-off GitHub Actions run"
echo "     targeting $FUNCTIONAPP_NAME)"
echo "  3. Smoke-test https://$FUNCTIONAPP_NAME.azurewebsites.net"
echo "  4. Once satisfied, run scripts/cutover_flex_function_app.sh to retire"
echo "     $EXISTING_FUNCTIONAPP_NAME and move the original name onto Flex"
echo "     Consumption."
