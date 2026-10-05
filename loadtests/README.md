# Staging Load Testing (MID-625)

Baseline load testing against the staging environment for the Analytics
Dashboard ([MID-592](/MID/issues/MID-592)) and Analytics Service
([MID-588](/MID/issues/MID-588)).

## Environment

Provisioned by `terraform/staging.tf`:

- ECS cluster: `prequal-cluster-staging`
- Platform service: `prequal-service-staging` (task family `prequal-task-staging`)
- Analytics service: `analytics-service-staging` (task family `analytics-service-task-staging`)
- Dedicated staging ALB (`prequal-alb-staging`) — load tests never touch production traffic
- CodeDeploy blue/green group: `staging-deployment-group` (see `terraform/codedeploy.tf`)

Deploy path: the `deploy-staging` jobs in `.github/workflows/ci-cd.yml` and
`.github/workflows/analytics-service.yml` deploy on merge to `develop`.

## One-time setup before first load test

1. Apply terraform staging module (CI `validate-infrastructure` + apply, or
   `terraform apply` from a workstation with AWS creds).
2. Populate the staging SSM parameters (placeholder values by design):
   - `/prequal/staging/database-url`
   - `/prequal/staging/analytics/database-url`
3. Validate the staging ACM cert (`staging.prequal.yourcompany.com`) via DNS.
4. Verify staging health: `curl -f https://staging.prequal.yourcompany.com/api/health`
   and `curl -f https://staging.prequal.yourcompany.com/analytics/health`.

## Running baseline tests

k6 (primary):

```bash
k6 run -e BASE_URL=https://staging.prequal.yourcompany.com loadtests/k6-analytics.js
```

Locust (secondary, API-heavy profile):

```bash
cd prequal-platform
locust -f tests/locustfile.py --host=https://staging.prequal.yourcompany.com --headless -u 50 -r 10 --run-time 180s
```

## Thresholds

Mirrors the CloudWatch alarms in terraform:

| Metric        | Threshold        |
| ------------- | ---------------- |
| p95 latency   | < 2000 ms        |
| Error rate    | < 1%             |
| Test profile  | ramp 20 -> 50 VUs over 9 min |

## Baseline benchmark record

Capture from each run (k6 summary or CloudWatch): p50/p95/p99 latency,
throughput (req/s), error rate, ECS CPU/memory, RDS connections.

| Run | Date | Profile | p50 (ms) | p95 (ms) | p99 (ms) | req/s | Error rate | Notes |
| --- | ---- | ------- | -------- | -------- | -------- | ----- | ---------- | ----- |
| (pending — first run after staging is live) | | | | | | | | |
