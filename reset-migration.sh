#!/usr/bin/env bash

REPO=$1

# caution make sure anything you want to keep is managed in code
# i.e. existing labels that may be used for pull requests

gh issue list -R "${REPO}" -L=1000 -s=all  --json=number | jq -r '.[].number' | xargs -n 1 -P 10 gh issue -R "${REPO}" delete
gh label list -R "${REPO}" --limit=500 --json name | jq -r '.[].name' | xargs -L 1  -P 10 -I {} gh label delete --confirm -R "${REPO}" '{}'
