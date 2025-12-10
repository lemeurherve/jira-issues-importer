#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - add epic children to epics

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}
START_FROM=${3:-0}

github_repo="${OWNER}/${REPO}"
github_issues_link="https://github.com/${OWNER}/${REPO}/issues"

MAPPING_FILE=jira-keys-to-github-id-mapping.txt
rm -f ${MAPPING_FILE}
# format is JENKINS-1:jenkinsci/jenkins#13336
wget -q https://raw.githubusercontent.com/jenkins-infra/docker-issue-redirect/refs/heads/main/mappings/jira_keys_to_github_ids.txt -O ${MAPPING_FILE}

# See https://github.com/cli/cli/issues/10298
if ! gh sub-issue --version >/dev/null 2>&1; then
  echo "'sub-issue' gh extension not found. Execute 'gh extension install yahsan2/gh-sub-issue' first"
  exit 1
fi

# jenkins core has around 600
SEARCH_LIMIT=1000

# TODO once search allows to check if there's a parent then skip those that already have a parent
ALL_ISSUES_WITH_EPICS=$(gh search issues --repo "${github_repo}" --limit $SEARCH_LIMIT --match body --json title,number,labels,url -- 'jira_relationships_epic_key=')

if [ "$(echo "${ALL_ISSUES_WITH_EPICS}" | jq 'length')" -eq 0 ]; then
  echo "No issues found with epic relationships"
  exit 0
fi

ALL_ISSUE_NUMBERS=$(echo "${ALL_ISSUES_WITH_EPICS}"| jq '.[].number' | sort -g | uniq)

echo "Found $(echo "${ALL_ISSUE_NUMBERS}" | wc -l | tr -d ' ') issues with epic relationships"

while IFS= read -r ISSUE_CHECKING; do
  if (( ISSUE_CHECKING < START_FROM )); then
    continue
  fi
  echo "---"
  echo "Checking ${github_issues_link}/${ISSUE_CHECKING}"
  BODY=$(gh issue view -R "${github_repo}" "${ISSUE_CHECKING}" --json 'body' --jq '.body')
  
  if [ -n "$BODY" ]
  then
    JIRA_ISSUE_KEY=$(echo "$BODY" | sed -n 's/.*jira_relationships_epic_key=\([^]]*\).*/\1/p')
    echo "Found epic ${JIRA_ISSUE_KEY}"

    if [ -z "${JIRA_ISSUE_KEY}" ]; then
      echo "No epic key found in issue body, exiting"
      exit 1
    fi

    EPIC_ISSUES_JSON=$(gh search issues --repo "${github_repo}" --match body "jira_issue_is_epic_key=${JIRA_ISSUE_KEY}"  --json number,repository)
    EPIC_ISSUE_NUMBER=$(echo "$EPIC_ISSUES_JSON" | jq '.[] | select(.repository.nameWithOwner == '\""${github_repo}"\"').number' | sort -u -r | head -1)

    PARENT_REPO_SLUG="${github_repo}"

    # IF we can't find the issue, try locate it using the mapping file
    if [ -z "${EPIC_ISSUE_NUMBER}" ]
    then
      MAPPING_ENTRY=$(grep "^${JIRA_ISSUE_KEY}:" "${MAPPING_FILE}" | head -1 | cut -d':' -f2 || true)
      
      if [ -z "${MAPPING_ENTRY}" ]; then
        echo "${JIRA_ISSUE_KEY} not found in mapping file, skipping"
        continue
      fi
      
      PARENT_REPO_SLUG=$(echo "${MAPPING_ENTRY}" | awk -F'#' '{print $1}')
      EPIC_ISSUE_NUMBER=$(echo "${MAPPING_ENTRY}" | awk -F'#' '{print $2}')
      echo "Found epic issue number from mapping file: $EPIC_ISSUE_NUMBER, repo: $PARENT_REPO_SLUG"
    fi

    # can be empty if epic is not in current component
    if [ -n "${EPIC_ISSUE_NUMBER}" ]
    then

      PARENT_ISSUE="https://github.com/${PARENT_REPO_SLUG}/issues/${EPIC_ISSUE_NUMBER}"
      CHILD_ISSUE="https://github.com/${github_repo}/issues/${ISSUE_CHECKING}"
      
      echo "Found issue for epic: ${PARENT_ISSUE}"

      # add current issue as epic sub issue

      # if error contains text "Parent cannot have more than 100 sub-issues" ignore the error else fail
      # also skip if error is Issue may not contain duplicate sub-issues and Sub issue may only have one parent
      gh sub-issue add "${PARENT_ISSUE}" "${CHILD_ISSUE}" 2>sub-issue-error.log || {
        if grep -q "Parent cannot have more than 100 sub-issues" sub-issue-error.log; then
          echo "Warning: Parent cannot have more than 100 sub-issues, skipping adding sub-issue"
        elif grep -q "Sub issue may only have one parent" sub-issue-error.log; then
          echo "Warning: Sub issue may only have one parent, skipping adding sub-issue"
        else
          echo "Error adding sub-issue:"
          cat sub-issue-error.log
          rm -f sub-issue-error.log
          exit 1
        fi
      }
      # issue type (no cli support https://github.com/cli/cli/issues/9696)
      gh api -X PATCH "repos/${PARENT_REPO_SLUG}/issues/${EPIC_ISSUE_NUMBER}" --field type=Epic > /dev/null || true
      # delete epic label if any
      if gh issue view -R "${PARENT_REPO_SLUG}" "${EPIC_ISSUE_NUMBER}" --json labels --jq '.labels[].name' | grep -q -w -e 'epic' -e 'jira-type:epic'; then
        gh issue edit --remove-label 'epic' -R "${PARENT_REPO_SLUG}" "${EPIC_ISSUE_NUMBER}" || true
        gh issue edit --remove-label 'jira-type:epic' -R "${PARENT_REPO_SLUG}" "${EPIC_ISSUE_NUMBER}" || true
      else
        echo 'No epic label found'
      fi
      sleep 1
    else
      echo "${JIRA_ISSUE_KEY} not found in imported issues"
    fi
  else
    echo "Something weird happened, no body found"
    exit 1
  fi
done <<< "${ALL_ISSUE_NUMBERS}"

echo "Finished epic processing"
