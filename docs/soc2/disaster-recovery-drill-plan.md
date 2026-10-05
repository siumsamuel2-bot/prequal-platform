# Disaster Recovery Drill Plan — Data Tier (CC9.2 / CC7.4)

**Owner:** Data Engineer (drill coordinator) · **Approver:** CTO · DevOps executes restores
**Last updated:** 2026-10-05 · **Status:** Planned — first drill scheduled for pilot-rehearsal week
**Companion:** [disaster-recovery-plan.md](./disaster-recovery-plan.md) (policy/RTO-RPO), [DEPLOYMENT_RUNBOOK.md](../DEPLOYMENT_RUNBOOK.md)

## Objective

Prove we can restore the production data tier (PostgreSQL/RDS + Secrets Manager
state) to a good state within documented RTO/RPO, and that the data-quality
pipeline recovers consistency afterward.

## Targets (from DR plan)

| Metric | Target | Scope |
|---|---|---|
| RPO | ≤ 24 h (nightly snapshot) — stretch: ≤ 15 min (WAL/PITR) | RDS/prequal DB |
| RTO | ≤ 4 h | full stack to "login + read dashboards" |

## Drill type

**First drill: tabletop + live snapshot-restore of the data tier**
(not full failover; that is the annual drill).

## Steps

1. **Preparation (D-2)**
   - Snapshot schedule confirmed current; note latest restorable time.
   - Freeze notice posted (no schema migrations during drill).
2. **Execute restore drill**
   - Restore latest RDS snapshot to an isolated instance (`prequal-dr-restore-*`).
   - Record timestamps at each stage: start → snapshot copied → instance available → Alembic head applied → health check green.
   - Verify a known row count: `SELECT COUNT(*) FROM organizations;` vs. production value captured at drill start (tolerance = rows added since snapshot).
3. **Application smoke**
   - Point a staging task definition at the restored DB; verify login, one read endpoint, one analytics endpoint return 200.
4. **Fail back / cleanup (same day)**
   - Tear down restored instance; confirm no data flowed both ways.
5. **Report within 5 business days**
   - Record: actual RTO/RPO vs. target, gaps, corrective actions with owner + due date; file under `docs/soc2/evidence/dr-drill-2026.md`.

## Data-integrity validation checklist

- [ ] Alembic migrations apply cleanly from zero on restored snapshot
- [ ] `validate_schema.sql` (see `database/`) passes on restored copy
- [ ] Materialized views refresh without error
- [ ] PII decryption smoke: one encrypted subcontractor record round-trips
- [ ] Audit log (`data_access_audit_logs`) shows the drill accesses, correctly attributed to the drill service identity

## Failure criteria (stop and escalate to CTO)

- Snapshot older than RPO at drill start
- Restore fails twice
- Any restored data readable without auth

## Cadence

- Tabletop + snapshot-restore: **quarterly** (next: during pilot rehearsal)
- Full failover exercise: **annually**
