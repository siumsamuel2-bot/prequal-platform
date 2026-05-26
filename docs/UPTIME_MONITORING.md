# Uptime Monitoring Setup

## Overview

This guide covers setting up external uptime monitoring for the Prequal Platform using UptimeRobot (free tier) or Better Stack (formerly Better Uptime).

## Monitoring Requirements

| Check | Frequency | Alert Threshold |
|-------|-----------|-----------------|
| API Health | 1 min | 1 failed check |
| Frontend | 1 min | 1 failed check |
| SSL Certificate | Daily | 30 days before expiry |
| Domain Expiry | Weekly | 14 days before expiry |

## Option 1: UptimeRobot Setup (Free)

### 1. Create Account

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Sign up for free account
3. Verify email

### 2. Add API Monitor

```
Monitor Type: HTTP
Friendly Name: Prequal API
URL: https://prequal.yourcompany.com/api/health
Monitoring Interval: 1 min
Advanced Settings:
  - Request Type: GET
  - Expected Status Codes: 200
  - Timeout: 30 seconds
```

### 3. Add Frontend Monitor

```
Monitor Type: HTTP
Friendly Name: Prequal Frontend
URL: https://prequal.yourcompany.com
Monitoring Interval: 1 min
Advanced Settings:
  - Request Type: GET
  - Expected Status Codes: 200
  - Timeout: 30 seconds
```

### 4. Configure Alerts

```
1. Go to My Settings > Alert Contacts
2. Add email: devops@yourcompany.com
3. Add SMS (optional): +1-XXX-XXX-XXXX
4. Create Alert Contact: "DevOps Team"
5. Add both email and SMS
```

### 5. SSL Certificate Monitoring

```
1. Add New Monitor
2. Type: SSL Certificate
3. Domain: prequal.yourcompany.com
4. Alert: 30 days before expiry
```

## Option 2: Better Stack Setup (Premium)

### 1. Create Account

1. Go to [betterstack.com](https://betterstack.com)
2. Sign up
3. Create new monitor

### 2. Configure Monitors

```yaml
# monitors.yml
monitors:
  - name: "Prequal API"
    url: "https://prequal.yourcompany.com/api/health"
    check_frequency: 60  # seconds
    timeout: 30
    method: GET
    follow_redirects: true
    verify_ssl: true
    assertions:
      - type: status_code
        value: 200
    locations:
      - us_east
      - us_west
      - eu_west

  - name: "Prequal Frontend"
    url: "https://prequal.yourcompany.com"
    check_frequency: 60
    timeout: 30
    method: GET
    assertions:
      - type: status_code
        value: 200
      - type: keyword
        value: "Prequal"

  - name: "Database Health"
    url: "https://prequal.yourcompany.com/api/health/detailed"
    check_frequency: 300  # 5 minutes
    timeout: 30
    method: GET
    assertions:
      - type: status_code
        value: 200
      - type: json_body
        path: "database.status"
        value: "healthy"
```

### 3. Alert Configuration

```yaml
# on_call.yml
on_call_schedule:
  - name: "DevOps Primary"
    rotation: weekly
    members:
      - devops1@company.com
      - devops2@company.com

escalation_policy:
  - level: 1
    wait_time: 5  # minutes
    targets:
      - type: email
        value: primary@company.com
  - level: 2
    wait_time: 10
    targets:
      - type: sms
        value: "+1-XXX-XXX-XXXX"
      - type: phone
        value: "+1-XXX-XXX-XXXX"
```

### 4. Status Page (Optional)

Create public status page:

```
1. Go to Status Pages
2. Create new: "Prequal Status"
3. Domain: status.prequal.yourcompany.com
4. Add monitors to display
5. Customize branding
```

## GitHub Actions Integration

Create automated status checks:

```yaml
# .github/workflows/uptime-check.yml
name: Manual Uptime Check

on:
  workflow_dispatch:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  uptime-check:
    runs-on: ubuntu-latest
    steps:
      - name: Check API Health
        run: |
          curl -f -s https://prequal.yourcompany.com/api/health || exit 1

      - name: Check Frontend
        run: |
          curl -f -s https://prequal.yourcompany.com/ || exit 1

      - name: Notify on Failure
        if: failure()
        run: |
          echo "Uptime check failed!"
          # Add Slack/Teams notification here
```

## Alert Escalation Policy

### Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| Critical | Service down | 5 minutes | Immediate |
| High | Major feature broken | 15 minutes | 15 min |
| Medium | Minor feature broken | 1 hour | 2 hours |
| Low | Degraded performance | 4 hours | 8 hours |

### Notification Channels

- **Email**: All alerts
- **SMS**: Critical and High severity
- **Phone Call**: Critical after 15 minutes
- **Slack**: All alerts (for visibility)

## Maintenance Windows

Schedule maintenance windows to avoid false alerts:

```yaml
# maintenance.yml
maintenance_windows:
  - name: "Weekly Deployment"
    schedule: "0 2 * * 0"  # Sunday 2 AM
    duration: 60  # minutes
    monitors:
      - "Prequal API"
      - "Prequal Frontend"
```

## Runbook Integration

Link monitors to runbooks:

```markdown
## When API Monitor Fires

1. Check Sentry for errors: https://sentry.io/...
2. Check CloudWatch logs: https://console.aws.amazon.com/...
3. Check ECS service status:
   ```bash
   aws ecs describe-services --cluster prequal-cluster
   ```
4. If database issue, check RDS:
   ```bash
   aws rds describe-db-instances --db-instance-identifier prequal-db
   ```
5. Follow deployment runbook for rollback if needed
```

## Testing Alerts

### Test Procedure

1. Manually stop backend service
2. Verify alert fires within 2 minutes
3. Verify correct channel receives alert
4. Verify escalation works
5. Restart service
6. Verify recovery alert

### Test Schedule

- **Weekly**: Test email alerts
- **Monthly**: Test SMS alerts
- **Quarterly**: Full escalation test

---

**Last Updated**: 2026-05-25
**Maintained By**: DevOps Engineer
