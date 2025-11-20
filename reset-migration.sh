#!/usr/bin/env bash

REPO=$1

# caution make sure anything you want to keep is managed in code
# i.e. existing labels that may be used for pull requests
# export NO_COLOR=true
# export GH_FORCE_TTY=never

# TODO: loop if more than 1000 issues imported
gh issue list -R "${REPO}" --limit=1000 --state=all --json number | jq -r '.[].number' | xargs -n 1 -P 10 gh issue -R "${REPO}" delete --yes
gh label list -R "${REPO}" --limit=500 --json name | jq -r '.[].name' | xargs -L 1 -I {} gh label delete --yes -R "${REPO}" '{}'
