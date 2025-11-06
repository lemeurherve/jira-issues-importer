#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - add epic children to epics

OWNER=${1:-timja-org}
REPO=${2:-jenkins-gh-issues-poc-11-04}
START_FROM=${3:-0}

# jenkins core has around 600
SEARCH_LIMIT=1000

ALL_ISSUES_WITH_EPICS=$(gh search issues --owner $OWNER --repo $REPO --limit $SEARCH_LIMIT --match comments --json number,labels -- 'Epic:')
ALL_ISSUE_NUMBERS=$(echo "${ALL_ISSUES_WITH_EPICS}"| jq '.[].number' | sort -g | uniq)

while IFS= read -r ISSUE_CHECKING; do
  if (( ISSUE_CHECKING < START_FROM )); then
    continue
  fi
  echo "Checking $ISSUE_CHECKING"
  COMMENT_JSON=$(gh issue view -R ${OWNER}/${REPO} "${ISSUE_CHECKING}" --comments --json 'comments' --jq '.comments[] | select(any(.body; contains("[Epic:")))')
  COMMENT=$(echo "$COMMENT_JSON" | jq -r '.body')
  COMMENT_NUMBER=$(echo "$COMMENT_JSON" | jq -r '.url' | awk -F 'issuecomment-' '{print $2}')

  if [ -n "$COMMENT"  ]
  then
    JIRA_ISSUE_KEY=$(echo "$COMMENT" | sed -r 's#^.*<a href="[^"]+">([^<]+)</a>.*$#\1#')
    echo "Found epic $JIRA_ISSUE_KEY"

    EPIC_ISSUES_JSON=$(gh search issues --owner ${OWNER} --repo ${REPO} --match title "${JIRA_ISSUE_KEY}"  --json number,repository)
    EPIC_ISSUE_NUMBER=$(echo "$EPIC_ISSUES_JSON" | jq '.[] | select(.repository.nameWithOwner == '\"${OWNER}/${REPO}\"').number')
    # can be empty if epic is not in core component
    if [ -n "$EPIC_ISSUE_NUMBER"  ]
    then
      echo "Found issue for epic: $EPIC_ISSUE_NUMBER"

      BODY=$(gh issue view -R ${OWNER}/${REPO} "${EPIC_ISSUE_NUMBER}" --json body --jq '.body')
      # gh extension install yahsan2/gh-sub-issue
      # see https://github.com/cli/cli/issues/10298
      gh sub-issue add -R ${OWNER}/${REPO} "${EPIC_ISSUE_NUMBER}" "${ISSUE_CHECKING}" || true
      # no cli support https://github.com/cli/cli/issues/9696
      gh api -X PATCH repos/$OWNER/$REPO/issues/$EPIC_ISSUE_NUMBER --field type=Epic > /dev/null
      gh issue edit --remove-label epic -R ${OWNER}/${REPO} "${EPIC_ISSUE_NUMBER}"

      gh api \
        --method DELETE \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        /repos/$OWNER/$REPO/issues/comments/$COMMENT_NUMBER
    fi
  fi
done <<< "${ALL_ISSUE_NUMBERS}"

echo "Finished epic processing"
