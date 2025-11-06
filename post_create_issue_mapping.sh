#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - create a json report mapping Jira keys to GitHub issue numbers
# useful for people to re-create watch lists

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}

SEARCH_LIMIT=20000

echo "Fetching all issues from ${OWNER}/${REPO}"
ALL_ISSUES=$(gh issue list -R ${OWNER}/${REPO} --limit $SEARCH_LIMIT --state=all --json number,title)
echo "Fetched all issues"

# Convert all issues to a mapping of JIRA key to GitHub issue number
# in the format [{ jira: JENKINS-1, github: 123 }, ...]

MAPPING=$(echo "${ALL_ISSUES}" | jq '[.[] | { jira: ( .title | capture("\\[(?<key>JENKINS-[0-9]+)\\]") | .key ), github: .number } ]')

FILE_PATH=issue_jira_github_mapping.json
echo "Writing mapping to $FILE_PATH"
echo $MAPPING  | jq '.' > $FILE_PATH
