#Requires -Version 5.1
<#
.SYNOPSIS
    Create or update a monthly Cost Management budget for the Traveller World Gen resource group.

.DESCRIPTION
    Sends email alerts at 80% and 100% of the monthly spend limit.
    To change the limit or alert email, edit the Configuration block below.

    Prerequisites:
      - Azure CLI installed and signed in (az login)

.EXAMPLE
    az login
    .\scripts\set_azure_budget.ps1
#>

$ErrorActionPreference = 'Stop'

# ── Configuration ────────────────────────────────────────────────────────────
$ResourceGroup = 'traveller-world-gen'
$BudgetName    = 'traveller-world-gen-monthly'
$BudgetAmount  = 10                            # USD per month
$AlertEmail    = 'michael.t.bailey@gmail.com'  # receives threshold notifications
# ─────────────────────────────────────────────────────────────────────────────

$SubscriptionId = (az account show --query id --output tsv).Trim()

# Budget start: first of the current month (UTC)
$Now       = [System.DateTime]::UtcNow
$StartDate = (New-Object System.DateTime($Now.Year, $Now.Month, 1)).ToString('yyyy-MM-dd')
$EndDate   = (New-Object System.DateTime($Now.Year + 5, $Now.Month, 1)).ToString('yyyy-MM-dd')

$Scope    = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
$Endpoint = "https://management.azure.com$Scope/providers/Microsoft.Consumption/budgets/${BudgetName}?api-version=2023-05-01"

$Body = @"
{
  "properties": {
    "category": "Cost",
    "amount": $BudgetAmount,
    "timeGrain": "Monthly",
    "timePeriod": {
      "startDate": "$StartDate",
      "endDate":   "$EndDate"
    },
    "notifications": {
      "Actual_GreaterThan_80_Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 80,
        "thresholdType": "Actual",
        "contactEmails": ["$AlertEmail"]
      },
      "Actual_GreaterThan_100_Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 100,
        "thresholdType": "Actual",
        "contactEmails": ["$AlertEmail"]
      }
    }
  }
}
"@

Write-Host "==> Setting `$$BudgetAmount/month budget on resource group: $ResourceGroup"
Write-Host "    Alerts to: $AlertEmail at 80% and 100%"
Write-Host "    Period: $StartDate -> $EndDate"

az rest --method PUT --url $Endpoint --body $Body --output none

Write-Host ""
Write-Host "Done. View in Azure Portal:"
Write-Host "  Cost Management + Billing -> Budgets (scope: $ResourceGroup)"
