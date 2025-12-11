#!/usr/bin/env bash

set -e -o pipefail

# Script to archive a Jira component
# Usage: ./jira-archive-component.sh <component-name>

COMPONENT_NAME=$1

if [ -z "$COMPONENT_NAME" ]; then
  echo "Error: Component name not specified"
  echo "Usage: $0 <component-name>"
  exit 1
fi

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  source "$SCRIPT_DIR/.env"
fi

# Validate required environment variables
if [ -z "$JIRA_MIGRATION_JIRA_URL" ] || [ -z "$JIRA_MIGRATION_JIRA_TOKEN" ] || [ -z "$JIRA_MIGRATION_JIRA_PROJECT_NAME" ]; then
  echo "Error: Required environment variables not set"
  echo "Please set JIRA_MIGRATION_JIRA_URL, JIRA_MIGRATION_JIRA_TOKEN, and JIRA_MIGRATION_JIRA_PROJECT_NAME"
  exit 1
fi

JIRA_BASE_URL="$JIRA_MIGRATION_JIRA_URL"
JIRA_PROJECT="$JIRA_MIGRATION_JIRA_PROJECT_NAME"

echo "Looking up component ID for: $COMPONENT_NAME in project: $JIRA_PROJECT"

# Get component ID by name
COMPONENT_JSON=$(curl -s \
  -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
  -H "Content-Type: application/json" \
  "${JIRA_BASE_URL}/rest/api/2/project/${JIRA_PROJECT}/components")

COMPONENT_ID=$(echo "$COMPONENT_JSON" | jq -r ".[] | select(.name == \"${COMPONENT_NAME}\") | .id")

if [ -z "$COMPONENT_ID" ] || [ "$COMPONENT_ID" = "null" ]; then
  echo "Error: Component '${COMPONENT_NAME}' not found in project ${JIRA_PROJECT}"
  echo "Available components:"
  echo "$COMPONENT_JSON" | jq -r '.[].name'
  exit 1
fi

echo "Found component ID: $COMPONENT_ID"
echo "Archiving component: $COMPONENT_NAME (ID: $COMPONENT_ID)"

# Archive the component
curl -s \
  -X PUT \
  -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
  -H "Content-Type: application/json" \
  "${JIRA_BASE_URL}/rest/api/2/component/${COMPONENT_ID}" \
  --data '{"archived": true}'

echo ""
echo "✓ Component '${COMPONENT_NAME}' has been archived"
