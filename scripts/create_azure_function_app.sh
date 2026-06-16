#!/usr/bin/env bash
# Creates the Azure resources needed to host the Traveller World Gen FastAPI
# app on Azure Functions (Consumption plan, Linux, Python 3.11).
#
# Usage:
#   az login
#   bash scripts/create_azure_function_app.sh
#
# After running:
#   1. Download the publish profile from Azure Portal:
#      Function App → Overview → Get publish profile
#   2. Store the XML contents as GitHub secret AZURE_FUNCTIONAPP_PUBLISH_PROFILE
#   3. Run the Deploy to Azure Functions workflow from GitHub Actions

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
RESOURCE_GROUP="traveller-world-gen"
LOCATION="uksouth"                      # Change to your preferred region
FUNCTIONAPP_NAME="traveller-world-gen"
STORAGE_ACCOUNT="travellerworldgen"     # 3-24 chars, lowercase alphanumeric
UAMI_NAME="traveller-world-gen-uami"
APPINSIGHTS_NAME="traveller-world-gen"
# ─────────────────────────────────────────────────────────────────────────────

echo "==> Creating resource group: $RESOURCE_GROUP"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

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

echo "==> Creating Application Insights: $APPINSIGHTS_NAME"
az monitor app-insights component create \
  --app "$APPINSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

APPINSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show \
  --app "$APPINSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString --output tsv)

echo "==> Creating Function App: $FUNCTIONAPP_NAME"
az functionapp create \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --consumption-plan-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --storage-account "$STORAGE_ACCOUNT" \
  --os-type Linux \
  --assign-identity "$UAMI_ID" \
  --output none

echo "==> Configuring app settings"
az functionapp config appsettings set \
  --name "$FUNCTIONAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "RATE_LIMIT_PER_MINUTE=100/minute" \
    "TRAVELLER_MAX_BATCH_SIZE=20" \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$APPINSIGHTS_CONNECTION_STRING" \
    "WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=1" \
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
echo "Done. Next steps:"
echo "  1. Download the publish profile:"
echo "     az webapp deployment list-publishing-profiles \\"
echo "       --name $FUNCTIONAPP_NAME \\"
echo "       --resource-group $RESOURCE_GROUP \\"
echo "       --xml"
echo ""
echo "  2. Store the output as GitHub secret AZURE_FUNCTIONAPP_PUBLISH_PROFILE"
echo "  3. Run: Actions → Deploy to Azure Functions → Run workflow"
