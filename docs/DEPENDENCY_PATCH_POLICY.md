# Dependency Vulnerability & Patching Policy

**Owner:** Security Engineer · **Approver:** CTO · **Last updated:** 2026-10-04
**Related:** [MID-595] · [`.github/workflows/dependency-security.yml`](../.github/workflows/dependency-security.yml) · [`.github/dependabot.yml`](../.github/dependabot.yml)

## 1. Policy Statement

All third-party dependencies (Python, Node/npm, Docker base images, GitHub Actions)
must be continuously scanned for known vulnerabilities. Critical and High findings in
**production** dependencies are remediated within the SLA below; findings that cannot be
patched are formally accepted in the Exception Register with compensating controls.

## 2. Patch SLA

| Severity | Scope | Remediation target |
| --- | --- | --- |
| Critical | Production | **7 days** |
| High | Production | **30 days** |
| High | Dev / build-only | 30 days where non-breaking; otherwise scheduled major upgrade |
| Medium | Production | Next release / sprint |
| Low | Any | Best effort |
| Any | No upstream fix available | Exception Register + compensating controls; re-evaluate each release |

**Escalation:** A Critical production finding is escalated to the CTO immediately
(per Security Engineer working rules).

## 3. Automated Enforcement

- **`.github/workflows/dependency-security.yml`**
  - `pip-audit` on every service's `requirements.txt` — fails the build on any advisory.
    Accepted-risk IDs go in `.pip-audit-ignore` (one ID per line).
  - `pnpm audit --prod --audit-level=high` — fails the build on High/Critical in
    **production** dependencies. A full (dev-inclusive) audit runs advisory-only.
  - Weekly scheduled re-scan to catch newly published advisories.
- **`.github/dependabot.yml`** — weekly automated update PRs for all pip and npm
  directories, GitHub Actions, and Docker images (security + version updates).
- **SBOM** — CycloneDX JSON SBOMs for the repository and the Python backend are generated
  on `main` and release tags and retained for 90 days as build artifacts.
- The legacy `dependency-check` job in `ci-cd.yml` remains advisory-only.

### Local reproduction

```bash
# Python (per service)
python -m pip install pip-audit
pip-audit -r prequal-platform/requirements.txt

# Node production deps
cd prequal-platform && pnpm audit --prod --audit-level=high
```

## 4. Exception Register

Accepted risks. Each entry must name a compensating control and a review date; entries are
re-validated at every dependency review and at least quarterly.

| ID | Package | Sev | Scope | Advisory / reason | Compensating control | Review by |
| --- | --- | --- | --- | --- | --- | --- |
| EXC-001 | `braces@3.0.3` | High | Dev-only (jest → micromatch) | Advisory lists fix `>=3.0.4`, but **3.0.4 is not published to npm** (latest is 3.0.3). Forcing an override breaks `pnpm install`. | Used only for local test-file glob matching; no untrusted input; not shipped to production. | Next dependency review / on npm publish of 3.0.4 |
| EXC-002 | `vite` (5.x) | High | Dev-only (dev server) | Dev-server advisories (`server.fs.deny` bypass, path traversal, `launch-editor` NTLM disclosure). Fix requires major 6.4.3+ upgrade. | Dev server binds localhost; production serves pre-built static assets. Major upgrade owned by app team. | Next sprint |

## 5. Scheduled Major Upgrades (breaking — require app-team review)

| Package | Current | Fix | Scope | Notes |
| --- | --- | --- | --- | --- |
| `react-router` / `react-router-dom` | 6.x | ≥7.18.0 | Production (moderate) | Open redirect / constructor-injection advisories. Major API changes. |
| `vite` | 5.x | ≥6.4.3 | Dev-only (high) | See EXC-002. |

## 6. History

| Date | Change |
| --- | --- |
| 2026-10-04 | Policy created. Removed dead `python-jose`; remediated 121 Python vulns (prequal-platform venv) and all Python service advisories; added CI scanning, Dependabot, SBOM. |
