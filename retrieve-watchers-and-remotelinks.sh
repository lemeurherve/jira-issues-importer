#!/usr/bin/env bash
set -euo pipefail

: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? MissingJira project name (e.g., JENKINS)}"
: "${JIRA_MIGRATION_JIRA_URL:? Missing Jira base URL (e.g., https://issues.jenkins.io)}"
: "${JIRA_MIGRATION_JIRA_USER:? Missing Jira user to be comment author (e.g., jenkins-infra-bot)}"
: "${JIRA_MIGRATION_JIRA_TOKEN:? Missing Jira token for authentication (e.g., your-jira-token)}"

input_file="jira_output/combined.xml"
watchers_file="core-cli-issues-watchers-usernames-and-emails.txt"
remotelinks_file="core-cli-issues-remotelinks.txt"


jira_base="${JIRA_MIGRATION_JIRA_URL}/rest/api/2/issue"


echo "Check ${JIRA_MIGRATION_JIRA_URL} connectivity"
response_code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" "${JIRA_MIGRATION_JIRA_URL}/rest/api/2/myself")
if [[ $response_code == 200 ]]; then
    echo "Connected to Jira successfully."
else
    echo "Error: Unable to connect to JIRA. Please check your credentials and Jira URL."
    exit 1
fi

# Clean output files
: > "${watchers_file}"
: > "${remotelinks_file}"

issues=$(grep '<key id=' "${input_file}" | sed "s/.*\(${JIRA_MIGRATION_JIRA_PROJECT_NAME}-[0-9][0-9]*\).*/\1/")

total=$(printf "%s\n" "$issues" | grep -c .)
count=0

for issue in $issues; do
    count=$(( count + 1 ))
    percent=$(( 100 * count / total ))

    watchers_url="${jira_base}/${issue}/watchers"
    remotelinks_url="${jira_base}/${issue}/remotelink"

    echo "[$count/$total | ${percent}%] Issue ${issue} ..." >&2

    # Retrieve watchers JSON
    json=$(curl -s \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
         "${watchers_url}")

    # Extract watchers
    echo "${json}" | jq -r --arg issue "${issue}" '
        .watchers[]? |
        "\($issue):\(.key):\(.emailAddress):\(.displayName)"
    ' >> "${watchers_file}"

    # Retrieve remote links JSON
    json=$(curl -s \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
         "${remotelinks_url}")

    # Extract remote links
    echo "${json}" | jq -r --arg issue "${issue}" '
        .[]? | select(.object.url != null) |
        "\($issue):[\(.object.title)](\(.object.url))"
    ' >> "${remotelinks_file}"

done

echo "Done. Output written to ${watchers_file} & ${remotelinks_file}" >&2
