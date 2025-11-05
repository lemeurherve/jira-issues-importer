#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - add epic children to epics

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}
START_FROM=${3:-0}

echo "Fetching all issues from ${OWNER}/${REPO}"
ALL_ISSUES=$(gh issue list -R ${OWNER}/${REPO} --limit 20000 --state=all --json number,labels)
echo "Fetched all issues"

# Function to process issues with a specific label and type
process_issue_type() {
  local label=$1
  local type=$2
  
  echo "Processing issues with label '$label' as type '$type'"
  
  ALL_ISSUES_OF_TYPE=$(echo "${ALL_ISSUES}" | jq --arg LABEL "$label" '[.[] | select(.labels[].name == $LABEL)]')
  ALL_ISSUE_NUMBERS=$(echo "${ALL_ISSUES_OF_TYPE}"| jq '.[].number' | sort -g | uniq)

  if [ -z "${ALL_ISSUE_NUMBERS}" ]; then
    echo "No issues found with label '$label'"
    return
  fi

  COUNT=$(echo "${ALL_ISSUE_NUMBERS}" | wc -l | tr -d ' ')
  echo "Found $COUNT issues with label '$label'"

  while IFS= read -r ISSUE_CHECKING; do
    if (( ISSUE_CHECKING < START_FROM )); then
      continue
    fi
    echo "Checking $ISSUE_CHECKING"
    gh api -X PATCH repos/$OWNER/$REPO/issues/$ISSUE_CHECKING --field type="$type" > /dev/null
    gh issue edit --remove-label "$label" -R ${OWNER}/${REPO} "${ISSUE_CHECKING}"

  done <<< "${ALL_ISSUE_NUMBERS}"
}

process_issue_type "rfe" "Enhancement"
process_issue_type "bug" "Bug"

# handles an edge case where there are some epics with no issues
process_issue_type "epic" "Epic"
