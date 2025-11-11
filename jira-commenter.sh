#!/usr/bin/env bash

# Required variables
: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing JIRA project name (e.g., INFRA)}"
: "${JIRA_MIGRATION_JIRA_PROJECT_DESC:? Missing JIRA project description (e.g., Jenkins Infrastructure project)}"
: "${JIRA_MIGRATION_JIRA_PROJECT_LINK:? Missing JIRA project link (e.g., https://www.jenkins.io/projects/infrastructure/)}"
: "${JIRA_MIGRATION_JIRA_PROJECT_NAME:? Missing JIRA project name to process (e.g., INFRA)}"
: "${JIRA_MIGRATION_JIRA_USER:? Missing JIRA user to be comment author (e.g., jenkins-infra-bot)}"
: "${JIRA_MIGRATION_JIRA_TOKEN:? Missing JIRA token for authentication (e.g., your-jira-token)}"
: "${JIRA_MIGRATION_JIRA_URL:? Missing JIRA base URL (e.g., https://issues.jenkins.io)}"
: "${JIRA_MIGRATION_GITHUB_NAME:? Missing GitHub org name (e.g., jenkins-infra)}"
: "${JIRA_MIGRATION_GITHUB_REPO:? Missing GitHub repo name (e.g., helpdesk)}"

: "${JIRA_GITHUB_MAPPING_FILE:=jira-keys-to-github-id.txt}" # with each line containing <JENKINS-ISSUE-KEY>:<GITHUB-ISSUE-KEY>, ex: "INFRA-545:415"
: "${COMMENTS_FILE:=jira-comments.txt}" # with each line containing <JENKINS-ISSUE-KEY>:<GITHUB-ISSUE-KEY>:<JIRA-COMMENT-ID>:<JIRA-COMMENT-SELF-LINK>, ex: "INFRA-545:415:457400:https://issues.jenkins.io/rest/api/2/issue/224778/comment/457400"

github_issues_link="https://github_issues_link.com/${JIRA_MIGRATION_GITHUB_NAME}/${JIRA_MIGRATION_GITHUB_REPO}/issues/"

echo "Check ${JIRA_MIGRATION_JIRA_URL} connectivity"
response_code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" "${JIRA_MIGRATION_JIRA_URL}/rest/api/2/myself")
if [[ $response_code == 200 ]]; then
    echo "Connected to JIRA successfully."
else
    echo "Error: Unable to connect to JIRA. Please check your credentials and JIRA URL."
    exit 1
fi

while IFS=':' read -ra mapping; do
    echo "Processing:: $github_issues_link${mapping[1]} >> ${JIRA_MIGRATION_JIRA_URL}/browse/${mapping[0]}"
    jira_issue_id=${mapping[1]}
    jira_issue_key=${mapping[0]}
    body="For your information, [all ${JIRA_MIGRATION_JIRA_PROJECT_NAME} issues|${JIRA_MIGRATION_JIRA_URL}/projects/${JIRA_MIGRATION_JIRA_PROJECT_NAME}/issues/] related to the [${JIRA_MIGRATION_JIRA_PROJECT_DESC}|${JIRA_MIGRATION_JIRA_PROJECT_LINK}] have been transferred to Github: ${github_issues_link}\n\nHere is the direct link to this issue in Github: ${github_issues_link}/${jira_issue_id}\nAnd here is the link to a search for related issues: ${github_issues_link}?q=%22${jira_issue_key}%22\n\n(Note: this is an automated bulk comment)"
    # https://developer.atlassian.com/server/jira/platform/jira-rest-api-examples/#adding-a-comment
    result=$(curl \
        --silent \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
        -X POST \
        --data "{\"body\": \"${body}\"}" \
    "${JIRA_MIGRATION_JIRA_URL}/rest/api/2/issue/${jira_issue_key}/comment")

    comment_id=$(echo "${result}" | jq -r '.id')
    comment_self_link=$(echo "${result}" | jq -r '.self')
    echo "Added comment id: ${comment_id}, link: ${comment_self_link}"

    echo "Pin comment id ${comment_id} to the top of the issue ${jira_issue_key}"
    pin_url="${JIRA_MIGRATION_JIRA_URL}/rest/api/2/issue/${jira_issue_key}/comment/${comment_id}/pin"
    curl "${pin_url}" \
        --silent \
        -X PUT \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${JIRA_MIGRATION_JIRA_TOKEN}" \
        --data-raw true

    # Append to comments file
    echo "${jira_issue_key}:${jira_issue_id}:${comment_id}:${comment_self_link}" >> "${COMMENTS_FILE}"

done <"${JIRA_GITHUB_MAPPING_FILE}"
