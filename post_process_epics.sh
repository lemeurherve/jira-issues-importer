#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - add epic children to epics

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}
START_FROM=${3:-0}

github_repo="${OWNER}/${REPO}"
github_issues_link="https://github.com/${OWNER}/${REPO}/issues"

# See https://github.com/cli/cli/issues/10298
if ! gh sub-issue --version >/dev/null 2>&1; then
  echo "'sub-issue' gh extension not found. Execute 'gh extension install yahsan2/gh-sub-issue' first"
  exit 1
fi

# jenkins core has around 600
SEARCH_LIMIT=1000

ALL_ISSUES_WITH_EPICS=$(gh search issues --repo "${github_repo}" --limit $SEARCH_LIMIT --match body --json title,number,labels,url -- 'jira_relationships_epic_key=')
ALL_ISSUE_NUMBERS=$(echo "${ALL_ISSUES_WITH_EPICS}"| jq '.[].number' | sort -g | uniq)

echo "${ALL_ISSUES_WITH_EPICS}" | jq '.[] | [.title, .url]'

while IFS= read -r ISSUE_CHECKING; do
  if (( ISSUE_CHECKING < START_FROM )); then
    continue
  fi
  echo "---"
  echo "Checking ${github_issues_link}/${ISSUE_CHECKING}"
  COMMENT_JSON=$(gh issue view -R "${github_repo}" "${ISSUE_CHECKING}" --comments --json 'comments' --jq '.comments[] | select(any(.body; contains("jira_relationship_type=epic")))')
  COMMENT=$(echo "$COMMENT_JSON" | jq -r '.body')
  COMMENT_NUMBER=$(echo "$COMMENT_JSON" | jq -r '.url' | awk -F 'issuecomment-' '{print $2}')

  if [ -n "$COMMENT"  ]
  then
    JIRA_ISSUE_KEY=$(echo "$COMMENT" | sed -n 's/.*jira_relationship_key=\([^]]*\).*/\1/p')
    echo "Found epic ${JIRA_ISSUE_KEY}"
    if [[ -z "${JIRA_ISSUE_KEY}" ]]; then
      echo "Not found"
      exit 13
    fi

    EPIC_ISSUES_JSON=$(gh search issues --repo "${github_repo}" --match body "jira_issue_key=${JIRA_ISSUE_KEY}"  --json number,repository)
    EPIC_ISSUE_NUMBER=$(echo "$EPIC_ISSUES_JSON" | jq '.[] | select(.repository.nameWithOwner == '\""${github_repo}"\"').number' | sort -u -r | head -1)
    # can be empty if epic is not in core component
    if [ -n "${EPIC_ISSUE_NUMBER}"  ]
    then
      echo "Found issue for epic: ${github_issues_link}/${EPIC_ISSUE_NUMBER}"

      BODY=$(gh issue view -R "${github_repo}" "${EPIC_ISSUE_NUMBER}" --json body --jq '.body')
      gh sub-issue add -R "${github_repo}" "${EPIC_ISSUE_NUMBER}" "${ISSUE_CHECKING}" || true
      set -x
      # no cli support https://github.com/cli/cli/issues/9696
      gh api -X PATCH "repos/${github_repo}/issues/${EPIC_ISSUE_NUMBER}" --field type=Epic > /dev/null || true
      gh issue edit --remove-label epic -R "${github_repo}" "${EPIC_ISSUE_NUMBER}" || true
      set +x

      gh api \
        --method DELETE \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "/repos/${github_repo}/issues/comments/${COMMENT_NUMBER}"
      sleep 1
    else
      echo "${JIRA_ISSUE_KEY} not found in imported issues"
    fi
  else
    echo "COMMENT empty"
  fi
done <<< "${ALL_ISSUE_NUMBERS}"

echo "Finished epic processing"
