#!/usr/bin/env bash

set -e -o pipefail

# Run this over repository to add GitHub autolink: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/configuring-autolinks-to-reference-external-resources

: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing Jira project name (e.g., JENKINS)}"
: "${JIRA_MIGRATION_REDIRECTION_SERVICE? Missing URL of the redirection service (e.g., https://issue-redirect.jenkins.io)}"
: "${JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK:=false}"

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}

# Check for required commands
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: 'gh' is required but not installed on this system." >&2
    echo "Install it first. On macOS: brew install gh" >&2
    exit 1
fi

github_repo="${OWNER}/${REPO}"

if [[ "${JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK}" == "true" ]]; then
  gh repo autolink create "${JIRA_MIGRATION_JIRA_PROJECT_NAME}-" "${JIRA_MIGRATION_REDIRECTION_SERVICE}/${JIRA_MIGRATION_JIRA_PROJECT_NAME}-<num>" --numeric --repo "${github_repo}"
else
  echo "JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK set to 'false', no GitHub autolink created."
fi
