# API Rate Limiting & DDoS Protection

Owner: Backend Engineer · Ticket: MID-593 · Component: `app/middleware/rate_limit.py`

All public API endpoints are rate limited and protected against abusive traffic.
Limits are **dynamic**: administrators can change them at runtime through the admin
API without a code change or redeploy.

## Policies

| Scope | Tier | Default limit | Key |
| --- | --- | --- | --- |
| Authenticated reads (GET/HEAD/OPTIONS) | `authenticated_read` | 200/min | `user:{user_id}` |
| Authenticated writes (POST/PUT/PATCH/DELETE) | `authenticated_write` | 50/min | `user:{user_id}` |
| Authenticated fallback | `authenticated_default` | 100/min | `user:{user_id}` |
| Unauthenticated reads | `unauthenticated_read` | 30/min | `ip:{client_ip}` |
| Unauthenticated default | `unauthenticated_default` | 20/min | `ip:{client_ip}` |
| Login / token / MFA validate | `unauthenticated_login` | 10/min | `ip:{client_ip}` |
| Registration | `unauthenticated_register` | 20/min | `ip:{client_ip}` |
| DDoS burst ceiling | `ddos_burst` | 100/sec | `ip:{client_ip}` |
| DDoS sustained ceiling | `ddos_sustained` | 1000/min | `ip:{client_ip}` |

Authenticated requests are limited per user (derived from the JWT `user_id`);
unauthenticated requests are limited per client IP, honoring `X-Forwarded-For`.

Health and observability endpoints (`/health*`, `/metrics`, `/docs`, `/redoc`,
`/openapi.json`) are exempt.

## Response headers

Every rate-limited response includes:

| Header | Meaning |
| --- | --- |
| `X-RateLimit-Limit` | Maximum requests allowed in the current window |
| `X-RateLimit-Remaining` | Requests remaining in the current window |
| `X-RateLimit-Reset` | Unix timestamp when the window resets |
| `Retry-After` | Seconds to wait before retrying (429 responses only) |

Exceeding a limit returns `HTTP 429` with a JSON body: `{"detail": "Rate limit exceeded: <limit>"}`.

## DDoS protection

In addition to per-route limits, `DDoSProtectionMiddleware` enforces:

- **Request size limit** — bodies larger than `DDOS_MAX_BODY_BYTES` (default 10 MB) → `413`.
- **Query guards** — query strings longer than `DDOS_MAX_QUERY_LENGTH` (2048) or
  with more than `DDOS_MAX_QUERY_PARAMS` (50) parameters → `400`.
- **Header guard** — more than `DDOS_MAX_HEADER_COUNT` (100) headers → `400`.
- **Suspicious pattern detection** — path traversal, null bytes, common SQL
  injection and XSS signatures, oversized/malformed `User-Agent` → `400`.
- **Connection throttling** — more than `DDOS_MAX_CONCURRENT_PER_IP` (50)
  in-flight requests from one IP → `429`.
- **Automatic IP bans** — after `DDOS_VIOLATION_THRESHOLD` (20) DDoS violations
  an IP is banned for `DDOS_BAN_SECONDS` (300). Banned IPs receive `429`.

### Configuration (environment)

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_URL` | unset | Shared storage + config persistence. Without it, per-process memory is used. |
| `RATE_LIMIT_CONFIG_FILE` | unset | JSON file used to persist dynamic tier/rule changes. |
| `RATE_LIMIT_ALERT_WEBHOOK` | unset | Optional webhook POSTed when an IP is auto-banned. |
| `RATELIMIT_ENABLED` | `true` | Set to `false` to disable request rate limiting. |
| `DDOS_MAX_BODY_BYTES` | `10485760` | Maximum request body size. |
| `DDOS_MAX_QUERY_LENGTH` | `2048` | Maximum raw query string length. |
| `DDOS_MAX_QUERY_PARAMS` | `50` | Maximum number of query parameters. |
| `DDOS_MAX_HEADER_COUNT` | `100` | Maximum number of request headers. |
| `DDOS_MAX_CONCURRENT_PER_IP` | `50` | Maximum concurrent in-flight requests per IP. |
| `DDOS_VIOLATION_THRESHOLD` | `20` | Violations before an automatic ban. |
| `DDOS_BAN_SECONDS` | `300` | Duration of an automatic IP ban. |

> **Production note:** configure `REDIS_URL` so limits are shared across all API
> replicas and survive restarts.

## Admin API

All endpoints require an `admin` JWT and live under `/api/admin/rate-limits`.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/tiers` | List tier defaults and current values |
| PUT | `/tiers/{name}` | Update a tier, body `{"limit": "5/minute"}` |
| POST | `/tiers/reset` | Restore shipped defaults |
| GET | `/rules` | List per-route rules |
| POST | `/rules` | Create/update a route rule |
| DELETE | `/rules/{rule_id}` | Delete a route rule |
| POST | `/resolve` | Preview the effective limit for a request shape |
| GET | `/stats` | Live rate limit / DDoS metrics |
| GET | `/blocked` | List banned IPs |
| POST | `/blocked` | Manually ban an IP, body `{"ip": "...", "seconds": 300}` |
| DELETE | `/blocked/{ip}` | Unban an IP |
| POST | `/reset-metrics` | Clear in-memory counters |

Route rules take precedence over tier defaults:

```json
{
  "path_prefix": "/api/analytics",
  "methods": ["POST"],
  "tier": "authenticated_write",
  "applies_to": "any",
  "enabled": true,
  "description": "Analytics ingest is write-heavy"
}
```

## Monitoring

Metrics are exposed for Prometheus at `/metrics`:

- `rate_limit_hits_total{endpoint}`
- `rate_limit_blocked_ips`
- `ddos_violations_total{reason}`
- `ddos_concurrent_requests`

Auto-bans also emit an `ERROR` log line (`SECURITY ALERT: auto-banned ...`) and,
when `RATE_LIMIT_ALERT_WEBHOOK` is set, a JSON webhook.

## Load testing

`scripts/load_test_rate_limit.py` simulates burst traffic and asserts that the
protection engages (429 + headers). Example:

```
python scripts/load_test_rate_limit.py --url http://localhost:8000/api/analytics/summary --requests 300 --concurrency 50
```
