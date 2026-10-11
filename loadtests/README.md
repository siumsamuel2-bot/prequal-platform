# Staging Load Testing (MID-625)

Baseline load testing against the staging environment for the Analytics
Dashboard ([MID-592](/MID/issues/MID-592)) and Analytics Service
([MID-588](/MID/issues/MID-588)).

## Environment (Render free tier - no AWS)

Board decision (MID-71, 2026-10-06): no cloud budget; staging runs on 100%
free tiers. Full provider/env/limit docs live in
`prequal-platform/docs/staging-free-tier.md`.

| Layer     | Provider | Plan | Target                                        |
| --------- | -------- | ---- | --------------------------------------------- |
| API       | Render   | free | `https://prequal-staging-api.onrender.com`    |
| Postgres  | Neon     | free | `DATABASE_URL` secret on the Render service   |
| Frontend  | Vercel   | free | Vercel project (board-managed)                |

Superseded: `terraform/staging.tf` (AWS ECS/ALB/CodeDeploy) is not used for
free-tier staging hosting. `k6-analytics.js` remains as a profile reference
for the analytics-service surface (`/analytics/health`,
`/api/v1/analytics/...`); those paths do not exist on the Render monolith,
use the stdlib harness below against staging.

## Rate limits the harness must respect

From `prequal-platform/app/middleware/rate_limit.py`:

| Scope                          | Limit              |
| ------------------------------ | ------------------ |
| Register (per IP)              | 20/min             |
| Login (per IP)                 | 10/min             |
| Unauthenticated (per IP)       | 20/min (reads 30)  |
| Authenticated reads (per user) | 200/min            |
| DDoS sustained (per IP)        | 1000/min           |
| `/health` (root)               | exempt             |

Note: `/api/health` is NOT exempt (only the root `/health` path is); an
unauthenticated poll of `/api/health` above ~20/min gets 429s.

Auth sessions rotate on every authenticated request: each response carries
`X-New-Access-Token` and the previous token is invalidated
(`get_current_user` in `prequal-platform/app/routers/auth.py`). Load clients
MUST chain that header per virtual user - reusing a token twice returns 401
"Session is invalid or has expired".

## Running baseline tests

Stdlib harness (primary - no installs, rate-limit and token-rotation aware):

```bash
python loadtests/baseline_staging.py \
  --base-url https://prequal-staging-api.onrender.com
```

Profile: register+login 8 users (pacing under register/login limits), then
3 VUs x 120s -> 8 VUs x 180s -> 8 VUs x 60s peak (think 0.5-2s), endpoint mix
1x health / 4x `/api/analytics/summary` / 3x
`/api/analytics/compliance/summary`. Writes `loadtests/baseline_results_<ts>.csv`.

Locust (secondary, API-heavy profile, `pip install locust`):

```bash
cd prequal-platform
locust -f tests/locustfile.py --host=https://prequal-staging-api.onrender.com \
  --headless -u 8 -r 1 --run-time 180s
```

k6 (reference profile only, see note above).

## Thresholds

| Metric        | Threshold |
| ------------- | --------- |
| p95 latency   | < 2000 ms |
| Error rate    | < 1%      |

## Baseline benchmark record

| Run | Date | Profile | p50 (ms) | p95 (ms) | p99 (ms) | req/s | Error rate | Notes |
| --- | ---- | ------- | -------- | -------- | -------- | ----- | ---------- | ----- |
| 1 | 2026-10-11 | 3->8 VUs, 365s, 8 authed users | 1351 | 1750 | 2370 | 2.50 | 0.00% | PASS both thresholds. Render free instance warm; summary p95 1905 / compliance p95 1441. Max 2908 ms. |
