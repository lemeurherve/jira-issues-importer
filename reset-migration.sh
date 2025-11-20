#!/usr/bin/env bash

: "${JIRA_MIGRATION_GITHUB_NAME:? Missing GitHub org name (e.g., jenkins-infra)}"
: "${JIRA_MIGRATION_GITHUB_REPO:? Missing GitHub repo name (e.g., helpdesk)}"

repo="${JIRA_MIGRATION_GITHUB_NAME}/${JIRA_MIGRATION_GITHUB_REPO}"

# caution make sure anything you want to keep is managed in code
# i.e. existing labels that may be used for pull requests
read -p "Are you sure to delete all issues and labels from https://github.com/${repo}? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo 'You might need to type "reset" to restore your terminal afterward'

    # TODO: loop if more than 1000 issues imported
    gh issue list -R "${repo}" --limit=1000 --state=all --json number --jq '.[].number' | xargs -n 1 -P 10 gh issue -R "${repo}" delete --yes
    gh label list -R "${repo}" --limit=500 --json name --jq '.[].name' | xargs -L 1 -I {} gh label delete --yes -R "${repo}" '{}'
fi
