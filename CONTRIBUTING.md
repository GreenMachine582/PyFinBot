[← Back to README](README.md)

# Contributing

## Setup

Use [uv](https://docs.astral.sh/uv/) for the virtual environment and installs:

```bash
uv venv --seed --python 3.14     # .venv; --seed adds pip, which use-local-gth.sh needs
uv pip install -r requirements.txt
```

CI installs the same way (`uv pip install -r requirements.txt`) on Python 3.12 and 3.14. Run checks through the
venv so you get the pinned tool versions, e.g. `.venv/Scripts/python -m ruff check src tests` (`.venv/bin/python`
off Windows), or `uv run --no-sync ruff check src tests`.

## Branches

```
feat/x ──commits──▶ PR to dev (merge commit) ──▶ branch deleted     release-please (on main)
                                  dev ──PR (merge commit)──▶ main ──▶ release PR ──merge──▶ tag vX.Y.Z
                                  dev ◀──────────────── back-merge ─────────────────────────┘
```

- **`main`** only ever holds released code. Deployments build from a `vX.Y.Z` tag, never a branch.
- **`dev`** is the integration branch and the default branch: open PRs against it.
- **Branches** are named `<type>/<short-description>` (`feat/franking-credits`, `docs/todo-sync`), hold one topic
  and live until their PR merges. GitHub then deletes the branch. Delete your local copy with `git branch -D`, or
  run `scripts/prune-branches.sh` (see [Rules](#rules)).

## Pull requests

- A PR to dev is one topic, made of related commits. For example `feat(reports): franking credits`, then
  `test(reports): franking credits on partial years`, then `docs(reports): franking credits`. Code and the docs that
  describe it go in the same PR.
- PRs are merged with a **merge commit**, so every commit lands on dev as written and release-please reads each
  one. That means **every commit** must be a [conventional commit](https://www.conventionalcommits.org/) with a
  first line of at most 100 characters, checked by `commits`. Each `feat`, `fix`, `perf` and `build` commit becomes
  a changelog line. `docs`, `test`, `refactor`, `ci` and `chore` stay out of it. For a breaking change use
  `feat!: …` plus a `BREAKING CHANGE:` footer in that commit's body.
- The PR title is free text and must **not** be a conventional commit (`commits` rejects one). The merge commit is
  GitHub's `Merge pull request #N from …` with the PR title as its body, and release-please reads conventional
  lines in a body as extra changes: a `feat(x): …` title would list that change twice. GitHub suggests a
  one-commit PR's subject as its title, so rewrite it, e.g. `Franking credits`. Release PRs to main use
  `release: …`, which isn't a changelog type.
- Update an open PR by adding commits, or by merging dev into it (the **Update branch** button). Don't rebase or
  force-push a PR that's been reviewed or that another PR is chained on. The one exception: rewording a commit
  `commits` rejected, before review, then `git push --force-with-lease`.
- Required checks: `test (3.12)`, `test (3.14)`, `lint` and `commits`. Approvals aren't required (solo maintainer,
  and GitHub doesn't count self-approval).

### Chained PRs

Small PRs get reviewed and merged faster, and they conflict less. When one piece of work builds on another, chain them
instead of opening one big PR:

1. `feat/a` → PR into `dev`.
2. Branch `feat/b` off `feat/a` → PR with **base `feat/a`**. Its diff shows only B's commits, and `commits` and CI
   run on it as usual.
3. Merge A. GitHub deletes `feat/a` and retargets B's PR to `dev` by itself. B already contains A's real commits
   (merge commits keep them), so nothing conflicts and nothing needs rebasing.
4. Merge B, and so on down the chain. To pick up a fix made in A after B was branched, merge `feat/a` into `feat/b`.

Merge the chain in order, starting from the PR nearest dev. Merging B first lands A's commits along with it.

## Releasing

Release whenever dev is in a state worth shipping. There's no fixed cadence.

1. Open a PR `dev` → `main` ("release: …"), wait for CI, merge (merge commit).
2. release-please opens or updates **`chore(main): release X.Y.Z`** on `main`: the version bump
   (`src/pyfinbot/version.py`) and the new `CHANGELOG.md` section, computed from the commits. `feat` → minor, `fix` /
   `perf` / `build` → patch (docs, refactor, tests, CI and chores alone never cut a release). While below 1.0,
   a breaking change bumps the minor.
3. Review the notes and merge it. It's opened by the `gth-release-bot` GitHub App, so CI runs on it. Merging tags
   `vX.Y.Z`, publishes the [GitHub Release](../../releases) with the same notes, and merges `main` back into `dev`.

Never bump versions or edit released `CHANGELOG.md` sections by hand, and never move a `v*` tag (the tag ruleset
blocks it).

## Developing against local GTH repos

With greentechhub-core, greentechhub-fastapi and greentechhub-ui checked out next to this repo,
`./scripts/use-local-gth.sh` runs this venv against those checkouts instead of the pinned releases. `--status` shows
which is in use, with each checkout's branch and commit, and `--undo` goes back to the pins. It changes only the
venv, never `requirements.txt`, so CI keeps testing the pins. It installs with the venv's pip, so create the venv with
`uv venv --seed`. PyFinBot pins greentechhub-core itself (it imports core and needs its extras), so that tag has to
match the one greentechhub-fastapi's own dependencies name. CI runs `python scripts/check_gth_pins.py` before
installing anything, and it says which pin to bump when they disagree. Run it locally after changing a pin. Details,
invariants and the release order:
[greentechhub-core's CONTRIBUTING.md](https://github.com/GreenMachine582/greentechhub-core/blob/dev/CONTRIBUTING.md#developing-against-local-gth-repos).

## Rules

GitHub settings live in the repo and are applied with `scripts/apply-rulesets.sh`, which needs an authenticated
`gh` with admin rights. Rerun it whenever one of these files changes:

| File | What it sets |
|---|---|
| [`.github/repo-settings.json`](.github/repo-settings.json) | Merge commits only (no squash or rebase), delete the branch on merge, the **Update branch** button, auto-merge |
| [`.github/rulesets/dev.json`](.github/rulesets/dev.json) | `dev`: PR with a merge commit, green required checks, no force-push or deletion |
| [`.github/rulesets/main.json`](.github/rulesets/main.json) | `main`: the same, without `commits` |
| [`.github/rulesets/tags.json`](.github/rulesets/tags.json) | `v*` tags can't be moved or deleted, and only release-please (the `gth-release-bot` app) creates them |

In an emergency the admin can merge a PR past failing checks (a logged bypass), but nobody, admin included, can push
straight to `main` or `dev`. Use the bypass to fix a broken pipeline, not to skip one.

`scripts/prune-branches.sh` cleans up branches after merges. It's a dry run by default, and `--apply` deletes. It
removes local branches whose PR merged, and origin branches whose PR merged or was closed. It never touches `dev`,
`main`, the checked-out branch, a branch with an open PR or no PR, or one with commits beyond what its PR merged
(reported as `newer`, so check it by hand).
