# Changelog

All notable changes to the Prequal platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Customer feedback widget, support/known-issues page, and admin feedback review (MID-666, MID-667)
- Graceful fail-closed UX for analytics/compliance 403 and no-access states (MID-657)
- Free-tier staging provisioning workflow and Render/Vercel/Neon blueprint config (MID-648, MID-653)
- Release process doc, in-repo roadmap, and changelog automation on `v*` tags (MID-668)

### Changed

- Test harness: seed referenced users/teams and timezone-normalize auth comparisons (MID-661)
- Disable the connection pool under pytest to stop cross-loop asyncpg reuse (MID-662)

### Fixed

- Dialect-safe date/round SQL, `pipeline_performance` redirect, MV refresh fallback (MID-660)
- Enforce MFA on refresh and authenticated requests (MID-652)
- Scope analytics reads to the caller's team, fail closed (MID-650)
- Fail closed on tenant scoping for compliance + credentials (MID-651)
- Normalize `DATABASE_URL` driver + SSL params for Render deploys (MID-653)
- Migration robustness: idempotent DDL, duplicate/missing-column guards, revision-id length (MID-645, MID-655, MID-656)
- Add `organizations.stripe_customer_id` (model/migration drift) (MID-656)
- Remove duplicate ToastContainer import breaking ComplianceDashboard suite (MID-657)

### Security

- Analytics reads scoped to the caller's team and fail closed (MID-650)
- Tenant scoping fail closed for compliance + credentials (MID-651)
- MFA enforced on refresh and authenticated requests (MID-652)
