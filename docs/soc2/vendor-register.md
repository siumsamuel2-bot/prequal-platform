# Vendor / Sub-processor Assessment Register (CC9.1)

**Owner:** CTO · **Maintained by:** Data Engineer
**Last updated:** 2026-10-05 · **Review cadence:** annually, on contract renewal, or on vendor incident
**Data classifications** (per [information-security-policy.md](./information-security-policy.md) §5): Public / Internal / Confidential.

| Vendor | Role / data touched | Classification | Assurance requested | Assessment date | Status |
|---|---|---|---|---|---|
| Amazon Web Services | Hosting (RDS, ECS, Secrets Manager, CloudWatch); primary data store | Confidential | SOC 2 Type II (AWS Artifact) | pending | Pending collection |
| Stripe | Payment processing; customer billing data | Confidential (PCI) | PCI DSS AoC + SOC 2 Type II | pending | Pending collection |
| GitHub (Microsoft) | Source code hosting; CI/CD secrets (repo-scoped) | Confidential | GitHub SOC 2 Type II / ISO 27001 | pending | Pending collection |
| Sentry (Functional Software) | Error telemetry; may contain request metadata | Internal | Sentry SOC 2 Type II | pending | Pending collection |
| OpenAI | LLM assistance (code only; no customer data by policy) | Internal | SOC 2 Type II (API data-privacy terms) | pending | Pending collection |

## Procedure

1. For each vendor above, download latest SOC 2 Type II (or PCI AoC for Stripe)
   report to `docs/soc2/evidence/vendors/<vendor>-<year>.pdf` (or link if
   export-restricted, with an NDA note) and record the assessment date above.
2. Review complementary-user-entity controls (CUECs) and record which we own
   (e.g., AWS: "encrypt data at rest" → our PII field encryption).
3. On vendor security incident: log against this register, assess impact, open a
   follow-up task; never remove the entry, append the outcome.
4. On offboarding a vendor: mark `Closed` with deletion certificate/reference.

## Notes

- Package registries (PyPI, npm) are supply-chain sources, not data
  sub-processors; covered by the dependency policy, not this register.
- Email sending provider: TBD at pilot onboarding; add row when selected.
- Public state-board data sources (TDLR etc.) carry no customer data — excluded.
