#!/usr/bin/env bash
# Creates or updates Application Insights alerts on the Function App's
# exception and restart frequency, notifying by email (issue #170).
#
# This is vigilance, not a control: it won't prevent the OOM DoS risk the ASGI
# body-size limit (issue #167) and its platform-level backstop (issue #168)
# already guard against, and it doesn't validate anything the World-JSON
# length checks (issue #169) don't already reject before it reaches app code.
# It surfaces whatever slips past those fixes, and gives visibility into
# whether crash/restart frequency (from repeated OOM kills) is a driver of
# Storage Account transaction costs.
#
# Two alerts are created, both notifying the same Action Group:
#   1. Exception-frequency: a standard Azure Monitor metric alert on the App
#      Insights component's exceptions/server metric.
#   2. Restart-frequency: Flex Consumption does NOT expose a platform "restart
#      count" metric (confirmed via `az monitor metrics list-definitions`
#      against the live Function App resource — only MemoryWorkingSet,
#      InstanceCount, CpuPercentage, and the FunctionExecutionCount/Units
#      family are available). The closest reliable proxy is a log-query
#      (scheduled query) alert counting "Worker process started and
#      initialized." trace lines in AppTraces — this message is logged
#      exactly once per host/worker start, whether that start was normal
#      Flex Consumption scale-to-zero-and-back behaviour or a crash loop.
#
# Threshold rationale (both empirically measured against the live resource,
# not guessed — see Configuration block below to retune):
#   - Exceptions: 7-day baseline was 9 total, max 4 in any single hour.
#     Alerting at >5 in 5 minutes is well above any observed normal noise.
#   - Restarts: 2-day baseline was 119 worker starts (~2.5/hour, entirely
#     normal Flex Consumption scaling). Alerting at >15 in 15 minutes is
#     roughly 25x that baseline — well clear of routine scale-out/scale-to-
#     zero churn, but still catches a genuine crash loop quickly.
#
# Usage:
#   az login
#   bash scripts/set_azure_exception_restart_alert.sh
#
# To change thresholds, the alert email, or resource names, edit the
# Configuration block below.

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
RESOURCE_GROUP="traveller-world-gen"
APPINSIGHTS_NAME="traveller-world-gen"
ACTION_GROUP_NAME="traveller-world-gen-alerts"
ACTION_GROUP_SHORT_NAME="twg-alerts"          # Max 12 chars
ALERT_EMAIL="michael.t.bailey@gmail.com"

EXCEPTION_ALERT_NAME="traveller-world-gen-exception-frequency"
EXCEPTION_THRESHOLD=5                          # exceptions/server count
EXCEPTION_WINDOW="5m"                          # evaluation window
EXCEPTION_FREQUENCY="5m"                       # how often it's evaluated

RESTART_ALERT_NAME="traveller-world-gen-restart-frequency"
RESTART_THRESHOLD=15                           # "Worker process started" count
RESTART_WINDOW_MINUTES=15
RESTART_FREQUENCY_MINUTES=15
# ─────────────────────────────────────────────────────────────────────────────

SUBSCRIPTION_ID=$(az account show --query id --output tsv)
APPINSIGHTS_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/microsoft.insights/components/${APPINSIGHTS_NAME}"

# The scheduled-query (log) alert below queries AppTraces directly, which
# only resolves when scoped to the underlying Log Analytics workspace, not
# the App Insights component itself (this App Insights resource is
# workspace-based — confirmed via `az monitor app-insights component show`
# --query workspaceResourceId). Scoping the log alert to the component ID
# instead fails with "Failed to resolve table or column expression named
# 'AppTraces'".
WORKSPACE_ID=$(az monitor app-insights component show \
  --app "${APPINSIGHTS_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query workspaceResourceId --output tsv)

echo "==> Creating/updating action group: ${ACTION_GROUP_NAME}"
az monitor action-group create \
  --name "${ACTION_GROUP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --short-name "${ACTION_GROUP_SHORT_NAME}" \
  --action email primary "${ALERT_EMAIL}" \
  --output none

ACTION_GROUP_ID=$(az monitor action-group show \
  --name "${ACTION_GROUP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query id --output tsv)

echo "==> Creating/updating exception-frequency metric alert: ${EXCEPTION_ALERT_NAME}"
az monitor metrics alert create \
  --name "${EXCEPTION_ALERT_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --scopes "${APPINSIGHTS_ID}" \
  --condition "count exceptions/server > ${EXCEPTION_THRESHOLD}" \
  --window-size "${EXCEPTION_WINDOW}" \
  --evaluation-frequency "${EXCEPTION_FREQUENCY}" \
  --severity 2 \
  --action "${ACTION_GROUP_ID}" \
  --description "Server exceptions exceeded ${EXCEPTION_THRESHOLD} in ${EXCEPTION_WINDOW} (issue #170)." \
  --output none

echo "==> Creating/updating restart-frequency log alert: ${RESTART_ALERT_NAME}"
az monitor scheduled-query create \
  --name "${RESTART_ALERT_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --scopes "${WORKSPACE_ID}" \
  --condition "count 'WorkerStarts' > ${RESTART_THRESHOLD}" \
  --condition-query WorkerStarts="AppTraces | where Message == \"Worker process started and initialized.\" | summarize count()" \
  --window-size "${RESTART_WINDOW_MINUTES}m" \
  --evaluation-frequency "${RESTART_FREQUENCY_MINUTES}m" \
  --severity 2 \
  --action-groups "${ACTION_GROUP_ID}" \
  --description "Worker process restarts exceeded ${RESTART_THRESHOLD} in ${RESTART_WINDOW_MINUTES} minutes (issue #170) — closest available proxy for restart frequency, since Flex Consumption exposes no platform restart-count metric." \
  --output none

echo ""
echo "Done. View in Azure Portal:"
echo "  Monitor → Alerts → Alert rules (resource group: ${RESOURCE_GROUP})"
echo "  Alerts notify: ${ALERT_EMAIL}"
