# Sentry Error Tracking Configuration

## Overview

This guide covers the setup and configuration of Sentry.io for error tracking in the Prequal Platform.

## Architecture

```
Frontend (React)  --> Sentry SDK --> Sentry.io
Backend (FastAPI) --> Sentry SDK --> Sentry.io
                                      |
                                      v
                              Alerts & Notifications
```

## Setup Instructions

### 1. Create Sentry Project

1. Go to [sentry.io](https://sentry.io)
2. Create new organization: `prequal`
3. Create new project: `prequal-platform`
4. Select framework: `JavaScript` for frontend, `Python` for backend
5. Copy the DSN (Data Source Name) for both projects

### 2. Backend Configuration (FastAPI)

Add Sentry SDK to requirements.txt:

```txt
# requirements.txt
sentry-sdk[fastapi]>=1.45.0
```

Configure in main.py:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        FastApiIntegration(),
    ],
    # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
    traces_sample_rate=0.1,
    # Environment
    environment=os.getenv("ENVIRONMENT", "development"),
    # Release version
    release=os.getenv("RELEASE_VERSION", "dev"),
)
```

### 3. Frontend Configuration (React)

Install Sentry SDK:

```bash
npm install @sentry/react @sentry/tracing
```

Configure in App.tsx:

```typescript
import * as Sentry from "@sentry/react";
import { BrowserTracing } from "@sentry/tracing";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  integrations: [
    new BrowserTracing({
      routingInstrumentation: Sentry.reactRouterV6Instrumentation(
        useEffect,
        useLocation,
        useNavigationType
      ),
    }),
  ],
  tracesSampleRate: 0.1,
  environment: import.meta.env.VITE_ENVIRONMENT,
  release: import.meta.env.VITE_RELEASE_VERSION,
});
```

### 4. Environment Variables

Add to `.env` or `.env.production`:

```bash
# Sentry Configuration
SENTRY_DSN=https://xxxxx@o123456.ingest.sentry.io/1234567
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0

# Frontend
VITE_SENTRY_DSN=https://xxxxx@o123456.ingest.sentry.io/1234567
VITE_ENVIRONMENT=production
VITE_RELEASE_VERSION=1.0.0
```

### 5. GitHub Integration

Connect Sentry to GitHub for better context:

1. Go to Settings > GitHub in Sentry
2. Install Sentry GitHub App
3. Connect repository: `prequal-platform`
4. Enable commit annotations

### 6. Alert Configuration

Configure alert notifications in Sentry:

1. Go to Alerts > Create Alert Rule
2. Select project: `prequal-platform`
3. Condition: `An issue is created`
4. Action: `Send notification to Slack/Email`
5. Frequency: `Only once per issue`

Recommended alert rules:

- **Critical Errors**: Any error with `level=critical`
- **High Error Rate**: Error rate > 5% in 5 minutes
- **New Issue**: First time an issue appears
- **Performance**: P95 latency > 2s

### 7. Release Tracking

Add release information to deployments:

```bash
# In CI/CD pipeline
export SENTRY_RELEASE=$(git describe --tags --always --dirty)

# Create release in Sentry
curl -X POST \
  -H 'Authorization: Bearer '$SENTRY_AUTH_TOKEN \
  https://sentry.io/api/0/projects/prequal/prequal-platform/releases/ \
  -d '{"version":"'$SENTRY_RELEASE'"}'

# Associate commits
curl -X POST \
  -H 'Authorization: Bearer '$SENTRY_AUTH_TOKEN \
  https://sentry.io/api/0/projects/prequal/prequal-platform/releases/$SENTRY_RELEASE/commits/ \
  -d '{"previousCommit":"'$PREVIOUS_RELEASE'"}'
```

## Monitoring Dashboard

### Key Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Error Rate | % of requests resulting in errors | < 1% |
| Crash Free Sessions | % of sessions without crashes | > 99% |
| P95 Latency | 95th percentile response time | < 2s |
| Apdex Score | Application performance index | > 0.9 |

### Daily Checks

- [ ] Review new issues in Sentry dashboard
- [ ] Check error trend (should be stable or decreasing)
- [ ] Verify critical errors are resolved
- [ ] Review performance metrics

## Troubleshooting

### Issues Not Appearing in Sentry

1. Verify DSN is correct
2. Check network connectivity to `o123456.ingest.sentry.io`
3. Verify SDK initialization in code
4. Check browser console for SDK errors

### Too Many False Positives

1. Adjust error filters in Sentry settings
2. Configure ignore rules for known issues
3. Set up release health to filter by version
4. Use environment tags to separate prod/dev

### Performance Impact

Sentry SDK has minimal performance impact:
- Backend: ~2-5ms overhead per request
- Frontend: ~10-20KB bundle size increase
- Network: Asynchronous, non-blocking

## Cost Management

Sentry pricing tiers:

- **Free**: 5,000 errors/month, 10,000 transactions/month
- **Team**: $26/month, 50,000 errors, 100,000 transactions
- **Business**: Custom, unlimited errors

To manage costs:
- Set transaction sample rate to 0.1 (10%)
- Filter out health check endpoints
- Use error sampling for high-traffic endpoints

## Security

- Never commit DSN with credentials
- Use environment variables for all secrets
- Configure allowed domains for JavaScript SDK
- Enable two-factor authentication on Sentry account

---

**Last Updated**: 2026-05-25
**Maintained By**: DevOps Engineer
