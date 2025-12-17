#!/usr/bin/env bash

set -e -o pipefail

# Run this over repository to add GitHub autolink: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/configuring-autolinks-to-reference-external-resources

: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing Jira project name (e.g., JENKINS)}"
: "${JIRA_MIGRATION_REDIRECTION_SERVICE? Missing URL of the redirection service (e.g., https://issue-redirect.jenkins.io)}"
: "${JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK:=false}"
: "${JIRA_MIGRATION_REPLACE_EXISTING_GITHUB_AUTOLINK:=false}"

if [[ "${JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK}" == "false" ]]; then
  echo "JIRA_MIGRATION_CREATE_GITHUB_AUTOLINK set to 'false', no GitHub autolink created."
  exit 0
fi

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}

# Check for required commands
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: 'gh' is required but not installed on this system." >&2
    echo "Install it first. On macOS: brew install gh" >&2
    exit 1
fi

github_repo="${OWNER}/${REPO}"
key_prefix="${JIRA_MIGRATION_JIRA_PROJECT_NAME}-"

all_autolinks="$(gh repo autolink list --repo "${github_repo}" --json id,isAlphanumeric,keyPrefix,urlTemplate)"
all_key_prefixes="$(echo "${all_autolinks}" | jq '.[].keyPrefix')"
existing_autolink_id=""
if [[ "${all_key_prefixes}" == *"${key_prefix}"* ]]; then
  existing_autolink="$(echo "${all_autolinks}" | jq --arg kp "$key_prefix" '.[] | select(.keyPrefix == $kp)')"
  existing_autolink_id="$(echo "${existing_autolink}" | jq -r '.id')"
  echo "There is already an autolink in ${github_repo} using '${key_prefix}' prefix:"
  echo "${existing_autolink}" | jq
fi

if [[ "${JIRA_MIGRATION_REPLACE_EXISTING_GITHUB_AUTOLINK}" == "false" && -n "${existing_autolink_id}" ]]; then
  echo "JIRA_MIGRATION_REPLACE_EXISTING_GITHUB_AUTOLINK set to 'false', not replacing the existing autolink"
  exit 0
fi

if [[ -n "${existing_autolink_id}" ]]; then
  gh repo autolink delete "${existing_autolink_id}" --repo "${github_repo}" --yes
fi

gh repo autolink create "${key_prefix}" "${JIRA_MIGRATION_REDIRECTION_SERVICE}/${key_prefix}<num>" --numeric --repo "${github_repo}"
