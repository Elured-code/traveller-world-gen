#!/usr/bin/env bash
# DESTRUCTIVE — final cutover from the classic-Consumption app to Flex
# Consumption under the ORIGINAL app name.
#
# Azure function apps can't change plan type in place (that's what failed
# with "hosting constraints" in the first attempt) and the .azurewebsites.net
# hostname is tied to the app name, which can't be renamed. So the only way
# to keep the original hostname (traveller-world-gen.azurewebsites.net) is:
#   1. Delete the old classic-Consumption app (frees up the name).
#   2. Delete the temporary "-flex" validation app.
#   3. Recreate a Flex Consumption app under the ORIGINAL name.
#   4. Re-apply app settings and redeploy code.
#
# This causes a short outage between steps 1 and 4 — there is no zero-downtime
# way to move a Consumption app to Flex Consumption under the same name.
#
# Only run this AFTER validating the "-flex" app thoroughly (see
# scripts/create_flex_function_app.sh and scripts/copy_app_settings_to_flex.sh).
#
# Usage:
#   az login
#   bash scripts/cutover_flex_function_app.sh

set -euo pipefail

RESOURCE_GROUP="traveller-world-gen"
LOCATION="australiaeast"
OLD_APP="traveller-world-gen"
VALIDATION_APP="traveller-world-gen-flex"
VALIDATION_UAMI_NAME="traveller-world-gen-flex-uami"   # Created by create_flex_function_app.sh
FINAL_APP="traveller-world-gen"                 # Same as OLD_APP — recreated after deletion
FINAL_STORAGE_ACCOUNT="travellerworldgenflex"   # Reuse the storage account created for validation
UAMI_NAME="traveller-world-gen-uami"            # Original identity — reused, not recreated
APPINSIGHTS_NAME="traveller-world-gen"
INSTANCE_MEMORY_MB=2048
MAX_INSTANCE_COUNT=100
# Rejects any HTTP request body over this size at the platform level, as a
# defensive backstop underneath the ASGI-level streaming body-size limit in
# fastapi/app.py (issue #167). Doesn't replace it — see issue #168.
MAX_REQUEST_BODY_BYTES=1048576   # 1 MB

echo "This will DELETE '$OLD_APP' and '$VALIDATION_APP', then recreate"
echo "'$FINAL_APP' as a Flex Consumption app. This causes an outage until"
echo "settings and code are redeployed in the steps printed at the end."
echo ""
read -r -p "Type the app name ('$OLD_APP') to confirm: " CONFIRMATION
if [ "$CONFIRMATION" != "$OLD_APP" ]; then
  echo "Confirmation did not match. Aborting — nothing was changed." >&2
  exit 1
fi

echo "==> Capturing app settings from $VALIDATION_APP (validated Flex config)"
VALIDATED_SETTINGS_JSON=$(az functionapp config appsettings list \
  --name "$VALIDATION_APP" \
  --resource-group "$RESOURCE_GROUP" \
  -o json)

EXCLUDE_KEYS=(
  "AzureWebJobsStorage"
  "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING"
  "WEBSITE_CONTENTSHARE"
  "FUNCTIONS_EXTENSION_VERSION"
  "FUNCTIONS_WORKER_RUNTIME"
  "APPLICATIONINSIGHTS_CONNECTION_STRING"
  "FUNCTIONS_REQUEST_BODY_SIZE_LIMIT"
)
TO_COPY=$(echo "$VALIDATED_SETTINGS_JSON" | jq --argjson exclude "$(printf '%s\n' "${EXCLUDE_KEYS[@]}" | jq -R . | jq -s .)" \
  '[.[] | select(.name as $n | $exclude | index($n) | not)]')

echo "==> Deleting old classic-Consumption app: $OLD_APP"
az functionapp delete --name "$OLD_APP" --resource-group "$RESOURCE_GROUP"

echo "==> Deleting temporary validation app: $VALIDATION_APP"
az functionapp delete --name "$VALIDATION_APP" --resource-group "$RESOURCE_GROUP"

echo "==> Reusing Application Insights: $APPINSIGHTS_NAME"
APPINSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
  --app "$APPINSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString --output tsv)

echo "==> Reusing managed identity: $UAMI_NAME"
az identity create --name "$UAMI_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --output none
UAMI_ID=$(az identity show --name "$UAMI_NAME" --resource-group "$RESOURCE_GROUP" --query id --output tsv)
UAMI_PRINCIPAL_ID=$(az identity show --name "$UAMI_NAME" --resource-group "$RESOURCE_GROUP" --query principalId --output tsv)
UAMI_CLIENT_ID=$(az identity show --name "$UAMI_NAME" --resource-group "$RESOURCE_GROUP" --query clientId --output tsv)

echo "==> Granting Storage Blob Data Owner on $FINAL_STORAGE_ACCOUNT to $UAMI_NAME"
STORAGE_ID=$(az storage account show --name "$FINAL_STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query id --output tsv)
az role assignment create \
  --assignee-object-id "$UAMI_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Owner" \
  --scope "$STORAGE_ID" \
  --output none

echo "==> Recreating Function App under original name: $FINAL_APP (Flex Consumption)"
az functionapp create \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$FINAL_STORAGE_ACCOUNT" \
  --flexconsumption-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --instance-memory "$INSTANCE_MEMORY_MB" \
  --maximum-instance-count "$MAX_INSTANCE_COUNT" \
  --assign-identity "$UAMI_ID" \
  --disable-app-insights \
  --output none

echo "==> Restoring validated app settings"
SETTINGS_ARGS=()
while IFS= read -r pair; do
  SETTINGS_ARGS+=("$pair")
done < <(echo "$TO_COPY" | jq -r '.[] | "\(.name)=\(.value)"')
SETTINGS_ARGS+=("APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING")
SETTINGS_ARGS+=("FUNCTIONS_REQUEST_BODY_SIZE_LIMIT=$MAX_REQUEST_BODY_BYTES")

az functionapp config appsettings set \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "${SETTINGS_ARGS[@]}" \
  --output none

# `--assign-identity` above only attaches the identity to the app — it does NOT
# switch AzureWebJobsStorage or the deployment storage container off key-based
# auth by itself. Without this explicit step, `functionapp create` leaves both
# as connection strings with an embedded storage account key.
echo "==> Switching AzureWebJobsStorage to identity-based auth (no stored keys)"
az functionapp config appsettings set \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "AzureWebJobsStorage__accountName=$FINAL_STORAGE_ACCOUNT" \
    "AzureWebJobsStorage__credential=managedidentity" \
    "AzureWebJobsStorage__clientId=$UAMI_CLIENT_ID" \
  --output none
az functionapp config appsettings delete \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --setting-names AzureWebJobsStorage \
  --output none

echo "==> Switching deployment storage auth to identity-based (no stored keys)"
DEPLOYMENT_CONTAINER=$(az functionapp deployment config show \
  --name "$FINAL_APP" --resource-group "$RESOURCE_GROUP" \
  --query "storage.value" --output tsv | sed 's#.*/##')
az functionapp deployment config set \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --deployment-storage-name "$FINAL_STORAGE_ACCOUNT" \
  --deployment-storage-container-name "$DEPLOYMENT_CONTAINER" \
  --deployment-storage-auth-type UserAssignedIdentity \
  --deployment-storage-auth-value "$UAMI_ID" \
  --output none
az functionapp config appsettings delete \
  --name "$FINAL_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --setting-names DEPLOYMENT_STORAGE_CONNECTION_STRING \
  --output none

echo "==> Enabling basic auth (required for publish profile deployment)"
az resource update \
  --resource-group "$RESOURCE_GROUP" \
  --name scm \
  --namespace Microsoft.Web \
  --resource-type basicPublishingCredentialsPolicies \
  --parent "sites/$FINAL_APP" \
  --set properties.allow=true \
  --output none

echo ""
echo "Done. '$FINAL_APP' is now running on Flex Consumption."
echo ""
echo "Remaining manual steps:"
echo "  1. Deploy code: bash scripts/prepare_azure.sh, then redeploy via"
echo "     GitHub Actions (Deploy to Azure Functions workflow) or"
echo "     'func azure functionapp publish $FINAL_APP --python'."
echo "  2. Re-fetch the publish profile if using publish-profile-based CI:"
echo "     az webapp deployment list-publishing-profiles \\"
echo "       --name $FINAL_APP --resource-group $RESOURCE_GROUP --xml"
echo "     and update the AZURE_FUNCTIONAPP_PUBLISH_PROFILE GitHub secret."
echo "  3. Smoke-test https://$FINAL_APP.azurewebsites.net/api/version"
echo "  4. Once confirmed healthy, clean up now-orphaned resources from the"
echo "     temporary validation app: the '$VALIDATION_UAMI_NAME' identity and"
echo "     its role assignments (this script reused '$UAMI_NAME', not it), and"
echo "     any storage account left over from an earlier failed migration"
echo "     attempt — check the resource group before deleting anything."
