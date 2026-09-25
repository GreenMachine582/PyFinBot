#!/usr/bin/env bash
# Apply .github/rulesets/*.json to a GitHub repo (default: this checkout's
# origin) — idempotent: a ruleset with the same name is updated, else created.
# Needs an authenticated `gh` with admin rights on the repo.
set -euo pipefail
repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
dir="$(cd "$(dirname "$0")/.." && pwd)/.github/rulesets"
for file in "$dir"/*.json; do
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
