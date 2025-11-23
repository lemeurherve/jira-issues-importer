#!/usr/bin/env bash
set -euo pipefail

: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing Jira project name (e.g., JENKINS)}"
: "${JIRA_MIGRATION_JIRA_URL:? Missing Jira base URL (e.g., https://issues.jenkins.io)}"
: "${JIRA_MIGRATION_JIRA_USER:? Missing Jira user}"
: "${JIRA_MIGRATION_JIRA_TOKEN:? Missing Jira token}"
: "${JIRA_MIGRATION_PARALLEL_COUNT:=8}"

input_file="jira_output/combined.xml"
watchers_file="core-cli-issues-watchers-usernames-and-emails.txt"
remotelinks_file="core-cli-issues-remotelinks.txt"

jira_base="${JIRA_MIGRATION_JIRA_URL}/rest/api/2/issue"

echo "Check ${JIRA_MIGRATION_JIRA_URL} connectivity"
response_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
    "${JIRA_MIGRATION_JIRA_URL}/rest/api/2/myself")

if [[ "${response_code}" != 200 ]]; then
    echo "Error: Unable to connect to Jira"
    exit 1
fi

echo "Connected to Jira successfully."

: > "${watchers_file}"
: > "${remotelinks_file}"

issues=$(grep '<key id=' "${input_file}" | sed "s/.*\(${JIRA_MIGRATION_JIRA_PROJECT_NAME}-[0-9][0-9]*\).*/\1/")
total=$(printf "%s\n" "${issues}" | grep -c .)

echo "Total issues: ${total}"

# Export for subshells
export JIRA_MIGRATION_JIRA_TOKEN jira_base watchers_file remotelinks_file total

# Progress counter using a file (atomic append)
progress_file=$(mktemp)
echo 0 > "${progress_file}"

update_progress() {
    # atomic fetch/increment
    local current
    current=$(($(tail -n1 "${progress_file}") + 1))
    echo "${current}" >> "${progress_file}"

    local percent=$((100 * current / total))
    printf "\r[%s/%s | %s%%] Processing..." "${current}" "${total}" "${percent}" >&2
}

export progress_file
export -f update_progress

process_issue() {
    issue="$1"
    watchers_url="${jira_base}/${issue}/watchers"
    remotelinks_url="${jira_base}/${issue}/remotelink"

    # Fetch watchers
    watchers_json=$(curl -s \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
        "${watchers_url}")

    printf "%s\n" "${watchers_json}" | jq -r --arg issue "${issue}" '
        .watchers[]? |
        "\($issue):\(.key):\(.emailAddress):\(.displayName)"
    ' >> "${watchers_file}"

    # Fetch remote links
    remotelinks_json=$(curl -s \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
        "${remotelinks_url}")

    printf "%s\n" "${remotelinks_json}" | jq -r --arg issue "${issue}" '
        .[]? | select(.object.url != null) |
        "\($issue):[\(.object.title)](\(.object.url))"
    ' >> "${remotelinks_file}"

    update_progress
}

export -f process_issue

printf "%s\n" "${issues}" | xargs -n1 -P"${JIRA_MIGRATION_PARALLEL_COUNT}" bash -c 'process_issue "$@"' _

echo -e "\nDone. Output written to ${watchers_file} & ${remotelinks_file}" >&2
rm -f "${progress_file}"
