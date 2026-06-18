#Requires -Version 5.1
<#
.SYNOPSIS
    Create the Azure resources needed to host the Traveller World Gen app on Azure Functions.

.DESCRIPTION
    Creates: resource group, storage account, managed identity, App Insights,
    Function App (Consumption/Linux/Python 3.11), app settings, and daily quota.

    Prerequisites:
      - Azure CLI installed and signed in (az login)

    After running:
      1. Download the publish profile from Azure Portal:
           Function App -> Overview -> Get publish profile
      2. Store the XML contents as GitHub secret AZURE_FUNCTIONAPP_PUBLISH_PROFILE
      3. Run the Deploy to Azure Functions workflow from GitHub Actions

.EXAMPLE
    az login
    .\scripts\create_azure_function_app.ps1
#>

$ErrorActionPreference = 'Stop'

# ── Configuration ────────────────────────────────────────────────────────────
$ResourceGroup    = 'traveller-world-gen'
$Location         = 'australiaeast'
$FunctionAppName  = 'traveller-world-gen'
$StorageAccount   = 'travellerworldgen'
$UamiName         = 'traveller-world-gen-uami'
$AppInsightsName  = 'traveller-world-gen'
# 1,000 GB-seconds/day expressed in MB-milliseconds (1000 x 1024 x 1000).
$DailyQuotaMbMs   = 1024000000
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "==> Creating resource group: $ResourceGroup"
az group create --name $ResourceGroup --location $Location --output none

Write-Host "==> Creating storage account: $StorageAccount"
az storage account create `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --allow-blob-public-access false `
    --output none

Write-Host "==> Creating user-assigned managed identity: $UamiName"
az identity create --name $UamiName --resource-group $ResourceGroup --location $Location --output none

$UamiId          = az identity show --name $UamiName --resource-group $ResourceGroup --query id          --output tsv
$UamiPrincipalId = az identity show --name $UamiName --resource-group $ResourceGroup --query principalId --output tsv
$StorageId       = az storage account show --name $StorageAccount --resource-group $ResourceGroup --query id --output tsv

Write-Host "==> Assigning Storage Blob Data Owner role to managed identity"
az role assignment create `
    --assignee-object-id    $UamiPrincipalId `
    --assignee-principal-type ServicePrincipal `
    --role "Storage Blob Data Owner" `
    --scope $StorageId `
    --output none

Write-Host "==> Creating Application Insights: $AppInsightsName"
az monitor app-insights component create `
    --app $AppInsightsName `
    --resource-group $ResourceGroup `
    --location $Location `
    --output none

$AppInsightsConnectionString = az monitor app-insights component show `
    --app $AppInsightsName `
    --resource-group $ResourceGroup `
    --query connectionString --output tsv

Write-Host "==> Creating Function App: $FunctionAppName"
az functionapp create `
    --name $FunctionAppName `
    --resource-group $ResourceGroup `
    --consumption-plan-location $Location `
    --runtime python `
    --runtime-version 3.11 `
    --functions-version 4 `
    --storage-account $StorageAccount `
    --os-type Linux `
    --assign-identity $UamiId `
    --output none

Write-Host "==> Configuring app settings"
az functionapp config appsettings set `
    --name $FunctionAppName `
    --resource-group $ResourceGroup `
    --settings `
        "RATE_LIMIT_PER_MINUTE=100/minute" `
        "TRAVELLER_MAX_BATCH_SIZE=20" `
        "APPLICATIONINSIGHTS_CONNECTION_STRING=$AppInsightsConnectionString" `
        "WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT=1" `
    --output none

Write-Host "==> Setting daily execution quota: 1,000 GB-s/day"
az functionapp update `
    --name $FunctionAppName `
    --resource-group $ResourceGroup `
    --set dailyMemoryTimeQuota="$DailyQuotaMbMs" `
    --output none

Write-Host "==> Enabling basic auth (required for publish profile deployment)"
az resource update `
    --resource-group $ResourceGroup `
    --name scm `
    --namespace Microsoft.Web `
    --resource-type basicPublishingCredentialsPolicies `
    --parent "sites/$FunctionAppName" `
    --set properties.allow=true `
    --output none

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Download the publish profile:"
Write-Host "       az webapp deployment list-publishing-profiles ``"
Write-Host "         --name $FunctionAppName ``"
Write-Host "         --resource-group $ResourceGroup ``"
Write-Host "         --xml"
Write-Host "  2. Store the output as GitHub secret AZURE_FUNCTIONAPP_PUBLISH_PROFILE"
Write-Host "  3. Run: Actions -> Deploy to Azure Functions -> Run workflow"
