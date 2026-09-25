[← Back to README](README.md)

# Contributing

## Branches

```
feat/x ─┐                                    release-please (on main)
fix/y  ─┼─PR (squash, conventional title)──▶ dev ──PR (merge commit)──▶ main ──▶ release PR
docs/z ─┘                                                                          │ merge
                                             dev ◀── back-merge ────── tag vX.Y.Z + GitHub Release
```

- **`main`** only ever holds released code; deployments build from a `vX.Y.Z` tag, never a branch.
- **`dev`** is the integration branch and the default branch: open feature PRs against it.
- **Feature branches**: `feat/…`, `fix/…`, `docs/…`, `refactor/…`, `chore/…`, `ci/…` — short-lived, one topic each.

## Pull requests

- Into **`dev`**: squash-merged. The **PR title** must be a [conventional commit](https://www.conventionalcommits.org/)
  (checked by `pr-title`) — it becomes the single commit on `dev` and the line in the changelog:
  `feat(reports): franking credits`, `fix(sync): retry on timeout`, `docs: …`. Breaking: `feat!: …` plus a
  `BREAKING CHANGE:` note in the description.
- Into **`main`**: a release PR from `dev`, merged with a **merge commit** (not squash) so each conventional
  commit reaches release-please.
- Required checks: `test (3.12)`, `test (3.14)`, `lint`, plus `pr-title` on PRs into dev.
  Approvals aren't required (solo maintainer — GitHub doesn't count self-approval).

## Releasing

1. Open a PR `dev` → `main` ("release: …"), wait for CI, merge (merge commit).
2. release-please opens or updates **`chore(main): release X.Y.Z`** on `main`: the version bump
   (`src/pyfinbot/version.py`) and the new `CHANGELOG.md` section, computed from the commits — `feat` → minor, `fix` /
   `perf` / `build` → patch (docs, refactor, tests, CI and chores alone never cut a release); while below 1.0
   a breaking change bumps the minor.
3. Review the notes, merge it (it's opened by the `gth-release-bot` GitHub App, so CI runs on it). That tags `vX.Y.Z`, publishes the [GitHub Release](../../releases) with the same
   notes, and merges `main` back into `dev`.

Never bump versions or edit released `CHANGELOG.md` sections by hand, and never move a `v*` tag (the tag ruleset
blocks it).

## Rules

Repository rulesets (source of truth: [`.github/rulesets/`](.github/rulesets/), applied with
`scripts/apply-rulesets.sh`): `main` and `dev` need a PR and green checks, no force-push or deletion; `v*` tags
can't be moved or deleted, and only release-please (the `gth-release-bot` app) creates them. In an emergency the admin can merge a PR past failing checks (a logged bypass) — but
nobody, admin included, can push straight to `main` or `dev`. Use the bypass for fixing a broken pipeline, not
for skipping one.
