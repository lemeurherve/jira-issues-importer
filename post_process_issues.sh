#!/usr/bin/env bash

set -e -o pipefail

# Run this over issues to:
# - add epic children to epics

OWNER=${1:-timja}
REPO=${2:-jenkins-gh-issues-poc-06-18}
START_FROM=${3:-0}

ALL_ISSUES=$(gh issue list -R ${OWNER}/${REPO} --limit=20000 --state=all --json number,labels)
ALL_ISSUE_NUMBERS=$(echo "${ALL_ISSUES}"| jq '.[].number' | sort -g | uniq)

while IFS= read -r ISSUE_CHECKING; do
  if (( ISSUE_CHECKING < START_FROM )); then
    continue
  fi
  echo "Checking $ISSUE_CHECKING"
  COMMENT=$(gh issue view -R ${OWNER}/${REPO} "${ISSUE_CHECKING}" --comments --json 'comments' --jq '.comments[].body | select(contains("[Epic:"))')

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

      if [[ "$BODY" == *"Epic children:"* ]]; then
        BODY+="
- #${ISSUE_CHECKING}"
      else
       BODY+=$"
Epic children:

- #${ISSUE_CHECKING}"
      fi
      gh issue edit -R ${OWNER}/${REPO} "${EPIC_ISSUE_NUMBER}" --body "${BODY}"
    fi

  fi

done <<< "${ALL_ISSUE_NUMBERS}"
