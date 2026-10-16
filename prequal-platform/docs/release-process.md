# Release Process

Single repeatable path for shipping Prequal: **branch → PR → CI green → deploy → changelog**.
Source of truth for this process is the ongoing-updates plan document in Paperclip
(`/MID/issues/MID-665#document-plan`, issue MID-665); this file keeps the operational
checklist with the code.

## Branching and pull requests

1. Branch from `task/mid-18`, implement, push. If `task/mid-18` has fallen behind
   `develop`, branch from the tip of `develop` instead — never force-push either branch.
2. Open a PR with **base `develop`**. Keep PRs scoped; rebase-free merges only.

## CI gate (merge requirements)

A PR may merge to `develop` only when on the merge commit:

| Job | Requirement |
| --- | --- |
| `test` | **Must be green** — pytest with `--cov-fail-under=80`, frontend jest, lint, typecheck |
| `integration-tests` | **Must be green** — compliance + analytics pipeline suites |
| `test-postgres` | Advisory (`continue-on-error`) today; becomes a **hard gate** when PG-parity work (MID-656) closes |
| `secrets-scan`, `security-lint`, `python-lint` | Advisory until the first-green-pass work (MID-640) completes |

**Gate rule:** nothing ships to staging or production unless `test` +
`integration-tests` are green on the exact commit being deployed.

## Merge and staging

3. Review and merge to `develop` (no force-push).
4. `deploy-staging` runs automatically on every `develop` push (health check +
   smoke test). Verify the free-tier staging URL per
   `docs/staging-free-tier.md` (MID-625 / smoke test MID-644).

## Cutting a release

5. Cut a release: tag `v*` (semver, e.g. `v1.2.0`) from `main`.
6. On the tag, CI runs `build` → `deploy-production` (blue-green with
   CodeDeploy), then the `generate-changelog` job produces release notes.

## Changelog

Every release updates `prequal-platform/CHANGELOG.md`
([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format:
Added / Changed / Fixed / Security, newest first).

Automation (wired into the existing `generate-changelog` job — no separate pipeline):

- On a `v*` tag, `scripts/release_notes.py` collects merged PRs since the
  previous tag, groups them by label into Keep-a-Changelog sections, and
  prepends a `## [vX.Y.Z] - date` section to `prequal-platform/CHANGELOG.md`,
  then commits the result back to `develop` (commit message carries
  `[skip ci]` so the changelog sync never re-triggers the pipeline).
- The GitHub Actions release-notes artifact (`changelog.md`) is still produced
  by `mikepenz/release-changelog-builder-action` for the release summary.

Manual one-command regeneration (works locally):

```bash
python3 scripts/release_notes.py --tag v1.2.0 \
  --repo <owner>/<repo> --prepend prequal-platform/CHANGELOG.md
```

7. Publish the "What's New" surface in-app and announce via the support
   channel (see the MID-665 plan document).

## Rollback

Emergency rollback is a manual `workflow_dispatch` on `ci-cd.yml` with
`rollback=true` (and `environment=staging|production`). The workflow redeploys
the previous ECS task definition and verifies the health endpoint. Details:
`docs/DEPLOYMENT_RUNBOOK.md`.

## Checklist (copy-paste per release)

```text
[ ] PR merged to develop with test + integration-tests green
[ ] deploy-staging healthy (free-tier staging URL /health + smoke)
[ ] tag vX.Y.Z cut from main
[ ] build + deploy-production (blue-green) succeeded
[ ] generate-changelog produced notes and CHANGELOG.md synced to develop
[ ] What's New published + support channel announced
```
