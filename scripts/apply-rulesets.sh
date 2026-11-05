#!/usr/bin/env bash
# Apply this repo's GitHub settings to a repo (default: this checkout's origin):
#   1. .github/repo-settings.json: merge methods, delete branches on merge,
#      the "Update branch" button, auto-merge.
#   2. .github/rulesets/*.json: idempotent, so a ruleset with the same name is
#      updated, otherwise it's created.
# Rerun it whenever either changes. It needs an authenticated `gh` with admin
# rights on the repo. See CONTRIBUTING.md#rules.
set -euo pipefail
repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
root="$(cd "$(dirname "$0")/.." && pwd)/.github"

gh api -X PATCH "repos/$repo" --input "$root/repo-settings.json" > /dev/null
echo "updated settings on $repo"

for file in "$root"/rulesets/*.json; do
  name="$(sed -n 's/^  "name": "\(.*\)",$/\1/p' "$file" | head -1)"
  id="$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id")"
  if [ -n "$id" ]; then
    gh api -X PUT "repos/$repo/rulesets/$id" --input "$file" > /dev/null
    echo "updated ruleset '$name' on $repo"
  else
    gh api -X POST "repos/$repo/rulesets" --input "$file" > /dev/null
    echo "created ruleset '$name' on $repo"
  fi
done
