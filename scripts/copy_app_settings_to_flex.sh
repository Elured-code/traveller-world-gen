#!/usr/bin/env bash
# Copies application settings from the existing classic-Consumption function
# app onto the new Flex Consumption validation app created by
# scripts/create_flex_function_app.sh.
#
# Deliberately excludes settings tied to the OLD app's identity and storage
# model, since the new app must keep its own:
#   - AzureWebJobsStorage                    (points at the new app's own storage account)
#   - WEBSITE_CONTENTAZUREFILECONNECTIONSTRING (Azure Files content-share model — Flex doesn't use it)
#   - WEBSITE_CONTENTSHARE                     (same — Flex uses a blob deployment container instead)
#   - FUNCTIONS_EXTENSION_VERSION / FUNCTIONS_WORKER_RUNTIME (set by `functionapp create`)
#   - APPLICATIONINSIGHTS_CONNECTION_STRING    (already set by create_flex_function_app.sh)
#   - WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT (Consumption-plan-only scale-out cap;
#                                                 Flex uses --maximum-instance-count instead)
#   - FUNCTIONS_REQUEST_BODY_SIZE_LIMIT         (already set by create_flex_function_app.sh;
#                                                 not present on the old app anyway — issue #167/#168)
#
# Usage:
#   az login
#   bash scripts/copy_app_settings_to_flex.sh

set -euo pipefail

RESOURCE_GROUP="traveller-world-gen"
SOURCE_APP="traveller-world-gen"
DEST_APP="traveller-world-gen-flex"

EXCLUDE_KEYS=(
  "AzureWebJobsStorage"
  "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING"
  "WEBSITE_CONTENTSHARE"
  "FUNCTIONS_EXTENSION_VERSION"
  "FUNCTIONS_WORKER_RUNTIME"
  "APPLICATIONINSIGHTS_CONNECTION_STRING"
  "WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT"
  "FUNCTIONS_REQUEST_BODY_SIZE_LIMIT"
)

echo "==> Reading app settings from $SOURCE_APP"
ALL_SETTINGS_JSON=$(az functionapp config appsettings list \
  --name "$SOURCE_APP" \
  --resource-group "$RESOURCE_GROUP" \
  -o json)

TO_COPY=$(echo "$ALL_SETTINGS_JSON" | jq --argjson exclude "$(printf '%s\n' "${EXCLUDE_KEYS[@]}" | jq -R . | jq -s .)" \
  '[.[] | select(.name as $n | $exclude | index($n) | not)]')

COUNT=$(echo "$TO_COPY" | jq 'length')
echo "==> Copying $COUNT setting(s) to $DEST_APP (excluding ${#EXCLUDE_KEYS[@]} storage/runtime-specific keys)"

SETTINGS_ARGS=()
while IFS= read -r pair; do
  SETTINGS_ARGS+=("$pair")
done < <(echo "$TO_COPY" | jq -r '.[] | "\(.name)=\(.value)"')

if [ "${#SETTINGS_ARGS[@]}" -eq 0 ]; then
  echo "Nothing to copy."
  exit 0
fi

az functionapp config appsettings set \
  --name "$DEST_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "${SETTINGS_ARGS[@]}" \
  --output none

echo "Done. Copied settings:"
echo "$TO_COPY" | jq -r '.[].name'
