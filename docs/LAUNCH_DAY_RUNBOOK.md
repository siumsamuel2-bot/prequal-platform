# Launch Day Runbook - Prequal Platform

**Issue**: MID-86  
**Date**: 2026-07-03  
**Version**: 1.0  
**Status**: Ready for Execution

---

## Launch Timeline

| Time (ET) | Phase | Task | Owner | Duration |
|-----------|-------|------|-------|----------|
| 08:00 | Pre-Launch | Final infrastructure check | DevOps | 30 min |
| 08:30 | Pre-Launch | Database backup | DevOps | 15 min |
| 08:45 | Pre-Launch | Notify team | CTO | 5 min |
| 09:00 | Deployment | Trigger production deploy | DevOps | 15 min |
| 09:15 | Deployment | Monitor rollout | DevOps | 30 min |
| 09:45 | Verification | Run smoke tests | Senior Eng | 45 min |
| 10:30 | Verification | SSL/HTTPS verification | Senior Eng | 15 min |
| 10:45 | Verification | Stripe integration test | Senior Eng | 30 min |
| 11:15 | Verification | Monitoring dashboards | DevOps | 15 min |
| 11:30 | Go/No-Go | Launch decision | CTO | 15 min |
| 11:45 | Launch | Enable traffic | DevOps | 5 min |
| 12:00 | Post-Launch | Status page update | Senior Eng | 5 min |

---

## Phase 1: Pre-Launch Checks

### 1.1 Infrastructure Verification

```bash
# SSH to production server
ssh prod@prequal.yourcompany.com

# Check disk space (need 50%+ free)
df -h

# Check memory (need 40%+ available)
free -m

# Check Docker is running
docker --version
docker compose version

# Verify no stale containers
docker ps -a
```

**Checklist**:
- [ ] Disk space > 50%
- [ ] Memory > 40% available
- [ ] Docker daemon running
- [ ] No stale containers from previous deploy

### 1.2 Database Pre-Backup

```bash
cd /opt/prequal-platform

# Create pre-deployment snapshot
docker compose -f docker-compose.production.yml exec db pg_dump -U postgres prequal_prod | gzip > /backups/pre_deploy_$(date +%Y%m%d_%H%M%S).sql.gz

# Verify backup exists
ls -la /backups/
```

**Checklist**:
- [ ] Database backup created
- [ ] Backup file > 1MB (sanity check)
- [ ] Backup verified in AWS/s3 if applicable

### 1.3 Team Notification

Post to team channels:
```
:rocket: Prequal Platform Launch - T-minus 30 minutes

Timeline:
- 09:00 ET - Deployment begins
- 09:45 ET - Smoke tests start
- 11:30 ET - Go/No-Go decision

Rollback criteria:
- Error rate > 5%
- Response time > 3s
- Any critical functionality broken

Contact: @oncall
```

**Checklist**:
- [ ] Team notified in #engineering
- [ ] Team notified in #general
- [ ] On-call engineer available

---

## Phase 2: Deployment

### 2.1 Trigger Production Deployment

**Option A: Git Tag (Automated)**
```bash
# From local machine
git tag -a v1.0.0-$(date +%Y%m%d) -m "Production launch $(date)"
git push origin v1.0.0-$(date +%Y%m%d)
```

**Option B: GitHub Actions Manual Trigger**
1. Go to https://github.com/your-org/prequal-platform/actions
2. Select "Production Deployment" workflow
3. Click "Run workflow"
4. Select `main` branch
5. Click "Run workflow"

### 2.2 Monitor Deployment

```bash
# Watch GitHub Actions
# Monitor ECS/Docker service status
docker compose -f docker-compose.production.yml ps

# Watch backend logs
docker compose -f docker-compose.production.yml logs -f backend

# Verify containers are healthy
docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}"
```

**Expected Results**:
- traefik: running (healthy)
- backend: running (healthy)
- frontend: running (healthy)
- db: running (healthy)
- redis: running (healthy)

**Checklist**:
- [ ] All containers started
- [ ] No crash loops
- [ ] Health checks passing

---

## Phase 3: Verification

### 3.1 Smoke Tests

Run the smoke test suite (see `smoke_tests.sh`):

```bash
# From local machine or jump server
./smoke_tests.sh https://prequal.yourcompany.com
```

**Test Coverage**:
- [ ] GET /health - Health check
- [ ] POST /api/auth/login - Authentication
- [ ] GET /api/dashboard - Dashboard access
- [ ] GET /api/subcontractors - Subcontractor list
- [ ] POST /api/credentials/upload - File upload
- [ ] GET /api/alerts - Alerts retrieval
- [ ] GET /api/billing/plans - Billing plans

**Success Criteria**: All tests return 200/201 with valid JSON

### 3.2 SSL/TLS Verification

```bash
# Check SSL certificate
openssl s_client -connect prequal.yourcompany.com:443 -servername prequal.yourcompany.com </dev/null 2>/dev/null | openssl x509 -noout -dates

# Verify HTTPS redirect
curl -I http://prequal.yourcompany.com/
# Should return 301 to HTTPS

# Check SSL grade (Qualys)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=prequal.yourcompany.com
```

**Checklist**:
- [ ] Certificate valid (not expired)
- [ ] Certificate issued by Let's Encrypt
- [ ] HTTPS redirect working (301)
- [ ] TLS 1.2+ enabled
- [ ] HSTS headers present

### 3.3 Stripe Billing Integration

```bash
# Test checkout session creation (requires test mode)
curl -X POST https://prequal.yourcompany.com/api/billing/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <test_token>" \
  -d '{"plan":"starter"}'
# Should return checkout_url

# Verify webhook endpoint reachable
curl -I https://prequal.yourcompany.com/api/billing/webhook
# Should return 200 (even without signature)
```

**Checklist**:
- [ ] /api/billing/plans returns plan info
- [ ] /api/billing/checkout creates session (test mode)
- [ ] /api/billing/webhook reachable
- [ ] Stripe test mode configured

### 3.4 Monitoring Verification

Access dashboards:
- **Grafana**: https://prequal.yourcompany.com:3000
- **Prometheus**: https://prequal.yourcompany.com:9090

```bash
# Check Prometheus targets
curl -s http://prequal.yourcompany.com:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health=="up")'

# Verify metrics are flowing
curl -s http://prequal.yourcompany.com:9090/api/v1/query?query=up | jq '.data.result'
```

**Checklist**:
- [ ] Grafana accessible
- [ ] Prometheus accessible
- [ ] All targets showing "up"
- [ ] CPU/Memory metrics visible
- [ ] Request rate metrics visible
- [ ] Error rate metrics visible

---

## Phase 4: Go/No-Go Decision

### Success Criteria

| Metric | Threshold | Measurement |
|--------|-----------|-------------|
| Error rate | < 1% | Grafana dashboard |
| P95 latency | < 2s | Grafana dashboard |
| Availability | 100% | Health checks |
| SSL grade | A or A+ | Qualys SSL test |

### Rollback Criteria

Trigger rollback if ANY of:
- Error rate > 5% for 5 minutes
- P95 latency > 5s for 5 minutes
- Health checks failing continuously
- Database connections exhausted
- Critical functionality broken (auth, dashboard, alerts)

### Decision Checklist

- [ ] All smoke tests passed
- [ ] Error rate < 1%
- [ ] Response time < 2s (P95)
- [ ] No critical errors in logs
- [ ] Monitoring shows green
- [ ] SSL certificate valid
- [ ] CTO approves launch

---

## Phase 5: Post-Launch

### 5.1 Status Page Update

Update status page at `status.prequal.yourcompany.com`:

```
Status: Operational
Updated: 2026-07-03 12:00 ET

Services:
- API: Operational
- Frontend: Operational
- Database: Operational
- SSL: Valid

No incidents reported.
```

### 5.2 Documentation

- [ ] Save deployment logs
- [ ] Document any issues encountered
- [ ] Update runbook with lessons learned

### 5.3 Post-Launch Monitoring (First Hour)

```bash
# Watch error rates
docker compose -f docker-compose.production.yml logs backend | grep -i error | tail -20

# Watch response times
curl -w "%{time_total}\n" -o /dev/null -s https://prequal.yourcompany.com/api/health

# Watch database connections
docker compose -f docker-compose.production.yml exec db psql -U postgres -d prequal_prod -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## Rollback Procedure

If rollback is needed:

### Step 1: Stop Deployment
```bash
# Prevent new deployments
# Disable GitHub Actions or cancel workflow
```

### Step 2: Restore Database (If Needed)
```bash
# Find pre-deployment backup
ls -la /backups/pre_deploy_*.sql.gz

# Restore database
gunzip -c /backups/pre_deploy_YYYYMMDD_HHMMSS.sql.gz | docker compose -f docker-compose.production.yml exec -T db psql -U postgres -d prequal_prod
```

### Step 3: Restore Previous Version
```bash
# Get previous image tags
docker images | grep prequal

# Tag previous version as latest
docker tag ghcr.io/your-org/prequal-platform-backend:previous ghcr.io/your-org/prequal-platform-backend:latest
docker tag ghcr.io/your-org/prequal-platform-frontend:previous ghcr.io/your-org/prequal-platform-frontend:latest

# Redeploy
docker compose -f docker-compose.production.yml up -d
```

### Step 4: Verify Rollback
```bash
# Health check
curl -f https://prequal.yourcompany.com/health

# Verify previous version
docker compose -f docker-compose.production.yml ps
```

### Step 5: Notify Team
```
:warning: ROLLBACK INITIATED

Reason: [describe issue]
Time: [timestamp]
Status: Rollback complete

Next steps: [describe recovery plan]
```

---

## Emergency Contacts

| Role | Contact | Slack |
|------|---------|-------|
| DevOps Engineer | @devops | @devops |
| CTO | @cto | @cto |
| On-Call Engineer | @oncall | @oncall |
| Stripe Support | support@stripe.com | - |

---

## Appendix: Smoke Test Script

Location: `scripts/smoke_tests.sh`

Run with:
```bash
./smoke_tests.sh https://prequal.yourcompany.com [auth_token]
```

---

**Document Control**
- Version 1.0 - 2026-07-03 - Initial launch day runbook
- Created by: Senior Engineer
- Approved by: CTO