#!/usr/bin/env bash
# Local GTH mode: run this repo against the sibling greentechhub-* checkouts
# (editable installs in .venv) instead of their pinned releases. Changes only
# the venv. See greentechhub-core's CONTRIBUTING.md, "Developing against local
# GTH repos".
#
#   ./scripts/use-local-gth.sh            link the siblings
#   ./scripts/use-local-gth.sh --status   local or released, per dependency
#   ./scripts/use-local-gth.sh --undo     back to the pinned releases
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
py="$root/.venv/Scripts/python.exe"
[ -x "$py" ] || py="$root/.venv/bin/python"
[ -x "$py" ] || { echo "No .venv in $root: create it first." >&2; exit 1; }
tool="$root/../greentechhub-core/scripts/local_gth.py"
[ -f "$tool" ] || { echo "Needs greentechhub-core checked out next to this repo ($tool)." >&2; exit 1; }
exec "$py" "$tool" --project "$root" "$@"
