#!/usr/bin/env bash
# Delete branches whose work is done. Dry run by default, --apply to delete.
#   Local:  a branch whose PR merged, with no open PR, and with no commits
#           beyond what that PR merged. Anything else is kept, since it may hold
#           unpushed work.
#   Remote: an origin branch whose PR merged or was closed, with no open PR and
#           no commits beyond that PR's head (including stale
#           release-please--branches--* branches).
# dev, main and the checked-out branch are never touched. Needs an
# authenticated `gh`. Run from anywhere inside the checkout.
set -euo pipefail
apply=false
[ "${1:-}" = "--apply" ] && apply=true
cd "$(git rev-parse --show-toplevel)"
current="$(git rev-parse --abbrev-ref HEAD)"
git fetch --prune --quiet origin

# pr_state <branch> <tip>: "open", "merged", "closed", "none", or "newer" when
# the tip has commits past every finished PR's head.
pr_state() {
  local prs state oid
  prs="$(gh pr list --head "$1" --state all --json state,headRefOid --jq '.[] | "\(.state) \(.headRefOid)"')"
  [ -z "$prs" ] && { echo none; return; }
  grep -q '^OPEN ' <<<"$prs" && { echo open; return; }
  for state in MERGED CLOSED; do
    while read -r _ oid; do
      if git merge-base --is-ancestor "$2" "$oid" 2>/dev/null; then
        tr '[:upper:]' '[:lower:]' <<<"$state"; return
      fi
    done < <(grep "^$state " <<<"$prs")
  done
  echo newer
}

act() { # act <description> <command...>
  if $apply; then "${@:2}" > /dev/null 2>&1 && echo "deleted  $1" || echo "FAILED   $1"
  else echo "would delete  $1"
  fi
}

echo "== local"
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  case "$b" in dev|main|"$current") echo "kept     $b (protected or checked out)"; continue ;; esac
  state="$(pr_state "$b" "refs/heads/$b")"
  if [ "$state" = merged ]; then act "$b (PR merged)" git branch -D "$b"
  else echo "kept     $b (PR $state)"
  fi
done

echo "== origin"
for ref in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin); do
  b="${ref#origin/}"
  case "$b" in dev|main|HEAD|origin) continue ;; esac
  state="$(pr_state "$b" "$ref")"
  case "$state" in
    merged|closed) act "origin/$b (PR $state)" git push --quiet origin --delete "$b" ;;
    *) echo "kept     origin/$b (PR $state)" ;;
  esac
done
$apply || echo "Dry run. Rerun with --apply to delete."
