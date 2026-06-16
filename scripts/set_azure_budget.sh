#!/usr/bin/env bash
# Creates or updates a monthly Cost Management budget for the Traveller World Gen
# resource group and sends email alerts at 80 % and 100 % of the limit.
#
# Usage:
#   az login
#   bash scripts/set_azure_budget.sh
#
# To change the limit or alert email, edit the Configuration block below.

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
RESOURCE_GROUP="traveller-world-gen"
BUDGET_NAME="traveller-world-gen-monthly"
BUDGET_AMOUNT=10                          # USD per month
ALERT_EMAIL="michael.t.bailey@gmail.com"  # receives threshold notifications
# ─────────────────────────────────────────────────────────────────────────────

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Budget start date must be the first of the current month (UTC).
START_DATE=$(date -u +"%Y-%m-01")

# End date: five years from now (Azure requires an explicit end date).
END_YEAR=$(( $(date -u +"%Y") + 5 ))
END_DATE="${END_YEAR}-$(date -u +"%m")-01"

SCOPE="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
ENDPOINT="https://management.azure.com${SCOPE}/providers/Microsoft.Consumption/budgets/${BUDGET_NAME}?api-version=2023-05-01"

BODY=$(cat <<EOF
{
  "properties": {
    "category": "Cost",
    "amount": ${BUDGET_AMOUNT},
    "timeGrain": "Monthly",
    "timePeriod": {
      "startDate": "${START_DATE}",
      "endDate": "${END_DATE}"
    },
    "notifications": {
      "Actual_GreaterThan_80_Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 80,
        "thresholdType": "Actual",
        "contactEmails": ["${ALERT_EMAIL}"]
      },
      "Actual_GreaterThan_100_Percent": {
        "enabled": true,
        "operator": "GreaterThan",
        "threshold": 100,
        "thresholdType": "Actual",
        "contactEmails": ["${ALERT_EMAIL}"]
      }
    }
  }
}
EOF
)

echo "==> Setting \$${BUDGET_AMOUNT}/month budget on resource group: ${RESOURCE_GROUP}"
echo "    Alerts to: ${ALERT_EMAIL} at 80 % and 100 %"
echo "    Period: ${START_DATE} → ${END_DATE}"

az rest \
  --method PUT \
  --url "${ENDPOINT}" \
  --body "${BODY}" \
  --output none

echo ""
echo "Done. View in Azure Portal:"
echo "  Cost Management + Billing → Budgets (scope: ${RESOURCE_GROUP})"
