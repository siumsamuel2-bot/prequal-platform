# Incident Response Plan - Prequal Platform

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-14 | DevOps Engineer | Initial incident response plan |

---

## Overview

This document defines the incident response procedures for the Prequal Platform. It covers detection, response, communication, and post-mortem processes.

---

## Incident Severity Levels

| Severity | Description | Response Time | Examples |
|----------|-------------|---------------|----------|
| **P0 - Critical** | Complete service outage, data breach, security incident | 5 minutes | - API completely down<br>- Database unreachable<br>- Security breach confirmed<br>- Data loss |
| **P1 - High** | Major functionality impaired, significant user impact | 15 minutes | - Authentication failures<br>- Payment processing down<br>- >50% error rate<br>- Performance degradation >10s |
| **P2 - Medium** | Partial functionality impaired, workaround exists | 1 hour | - Non-critical feature down<br>- Intermittent errors<br>- Performance degradation 2-10s |
| **P3 - Low** | Minor issue, minimal user impact | 4 hours | - UI cosmetic issues<br>- Minor bugs<br>- Documentation errors |

---

## Incident Response Lifecycle

### Phase 1: Detection

**Automated Detection:**
- CloudWatch alarms trigger on metrics (CPU, memory, errors, latency)
- UptimeRobot external health checks fail
- Sentry error rate spikes
- Database backup failures

**Manual Detection:**
- User reports via support channel
- Team member notices anomaly
- Customer success escalation

**Detection Sources:**

| Source | Monitors | Alert Channel |
|--------|----------|---------------|
| CloudWatch | Infrastructure metrics | SNS → Email/SMS |
| UptimeRobot | External health checks | Email/SMS/Push |
| Sentry | Application errors | Email/Slack |
| GitHub Actions | CI/CD failures | GitHub notifications |
| Users | Functional issues | Support channel |

---

### Phase 2: Triage

**Immediate Actions (First 5 minutes):**

1. **Acknowledge the alert**
   - On-call engineer acknowledges in monitoring system
   - Post initial message in incident Slack channel: `#incidents`

2. **Assess severity**
   - Check CloudWatch dashboard: https://us-east-1.console.aws.amazon.com/cloudwatch
   - Check Sentry dashboard: https://sentry.io
   - Check UptimeRobot status: https://uptimerobot.com

3. **Declare incident level**
   - Based on severity matrix above
   - Escalate to CTO if P0/P1

**Triage Checklist:**
- [ ] Alert acknowledged
- [ ] Severity level assigned
- [ ] Incident channel created/joined
- [ ] Initial assessment posted
- [ ] Right people notified

---

### Phase 3: Response

**Incident Commander Role:**
- First responder becomes incident commander until handoff
- Coordinates response efforts
- Manages communication
- Documents timeline

**Response Actions by Severity:**

**P0 - Critical:**
1. Immediately page on-call engineer + CTO
2. Create war room (Slack huddle or call)
3. Start incident timeline document
4. Begin diagnosis and mitigation
5. Prepare customer communication if >15min

**P1 - High:**
1. Page on-call engineer
2. Notify CTO via Slack
3. Start diagnosis
4. Update every 30 minutes

**P2 - Medium:**
1. Assign to on-call engineer
2. Investigate during business hours
3. Update every 2 hours

**P3 - Low:**
1. Create ticket
2. Assign to appropriate team member
3. Resolve in normal sprint cadence

---

### Phase 4: Mitigation

**Common Mitigation Strategies:**

| Issue | Mitigation |
|-------|------------|
| High error rate | Rollback to previous deployment |
| Database overload | Enable read replicas, kill long queries |
| Memory exhaustion | Restart containers, scale horizontally |
| DDoS attack | Enable WAF rate limiting, CloudFront shield |
| Security breach | Rotate credentials, isolate affected systems |
| Data corruption | Restore from backup |

**Rollback Decision Tree:**
```
Is error rate > 50% after deployment?
├─ Yes → Rollback immediately
└─ No → Investigate root cause
    ├─ Found configuration issue? → Fix forward
    └─ Unknown cause after 30min → Rollback
```

---

### Phase 5: Communication

**Internal Communication:**

| Time | Action | Audience |
|------|--------|----------|
| T+5min | Initial alert | On-call, CTO |
| T+15min | Status update | Engineering team |
| T+30min | Status update | All staff (if P0/P1) |
| Resolution | Resolution notice | All staff |

**External Communication (P0/P1 only):**

| Time | Action | Channel |
|------|--------|---------|
| T+30min | Acknowledge issue | Status page |
| T+60min | Update with findings | Status page + Email |
| Resolution | Resolution notice | Status page + Email |
| T+24hr | Post-mortem summary | Email to affected customers |

**Communication Templates:**

**Initial Acknowledgment:**
```
Subject: [INCIDENT] Prequal Platform Service Disruption

We are currently investigating reports of service disruption affecting [specific functionality]. 
Our team is actively working to resolve this issue.

Next update: [time]

Status page: [link]
```

**Resolution Notice:**
```
Subject: [RESOLVED] Prequal Platform Service Restored

The service disruption affecting [functionality] has been resolved as of [time].

Impact: [duration] users affected
Root cause: [brief description]
Remediation: [actions taken]

A full post-mortem will be shared within 48 hours.
```

---

### Phase 6: Post-Mortem

**Timing:** Within 48 hours of incident resolution

**Attendees:**
- Incident commander
- All responders
- CTO (for P0/P1)
- Affected team members

**Post-Mortem Document Structure:**

1. **Summary**
   - What happened
   - Duration
   - Severity level
   - User impact

2. **Timeline**
   - Detection time
   - Response milestones
   - Resolution time

3. **Root Cause Analysis (5 Whys)**
   - Why did this happen?
   - Why did that happen?
   - Continue until root cause found

4. **Impact Assessment**
   - Users affected
   - Data impact
   - Revenue impact (if any)
   - Reputation impact

5. **Action Items**
   - Preventive measures
   - Detection improvements
   - Process improvements
   - Owner and due date for each

6. **Lessons Learned**
   - What went well
   - What could be improved
   - Surprises encountered

**Post-Mortem Storage:**
- All post-mortems stored in: `docs/post-mortems/`
- Naming: `POSTMORTEM-YYYY-MM-DD-[brief-description].md`
- Accessible to all engineering team members

---

## On-Call Rotation

### Schedule

**Primary On-Call:**
- Weekly rotation starting Monday 9:00 AM
- Schedule published quarterly
- Minimum 2 engineers in rotation

**Secondary On-Call (Backup):**
- CTO or designated senior engineer
- Escalated to if primary unreachable

### On-Call Responsibilities

**During On-Call Week:**
- Monitor alerts via phone/email
- Respond within SLA for severity level
- Triage and assign incidents
- Document all incidents in log
- Hand off any ongoing incidents at rotation change

**On-Call Handoff Checklist:**
- [ ] Review open incidents
- [ ] Transfer alert routing to new on-call
- [ ] Update on-call calendar
- [ ] Communicate handoff in team channel

### Escalation Path

```
Alert → Primary On-Call (5 min response)
    ↓ (no response)
Secondary On-Call / CTO (10 min response)
    ↓ (no response)
CEO / Board notification
```

**Escalation Contacts:**

| Level | Contact | Method |
|-------|---------|--------|
| Primary | On-call engineer | PagerDuty/Phone |
| Secondary | CTO | Phone |
| Executive | CEO | Phone |

---

## Runbooks for Common Incidents

### Runbook 1: Service Down

**Symptoms:**
- Health checks failing
- 502/503 errors
- CloudWatch alarm: UnHealthyHostCount > 0

**Diagnosis:**
```bash
# Check ECS service status
aws ecs describe-services --cluster prequal-cluster --services prequal-service

# Check task health
aws ecs list-tasks --cluster prequal-cluster --service prequal-service

# Check recent events
aws ecs describe-services --cluster prequal-cluster --services prequal-service --query 'services[0].events'
```

**Resolution:**
1. If deployment-related → Rollback immediately
2. If infrastructure → Check Terraform state
3. If application → Check CloudWatch Logs

---

### Runbook 2: Database Issues

**Symptoms:**
- Connection timeouts
- Query failures
- RDS CPU > 80%

**Diagnosis:**
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier prequal-db

# Check connections
aws cloudwatch get-metric-statistics --namespace AWS/RDS --metric-name DatabaseConnections --dimensions Name=DBInstanceIdentifier,Value=prequal-db --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) --period 300 --statistics Average

# Check slow queries (if accessible)
# Via RDS Performance Insights or direct connection
```

**Resolution:**
1. Kill long-running queries if identified
2. Restart RDS if unresponsive (last resort)
3. Restore from snapshot if data corruption

---

### Runbook 3: High Error Rate

**Symptoms:**
- Sentry error spike
- CloudWatch 5XXError alarm
- User reports of failures

**Diagnosis:**
```bash
# Check recent deployments
aws ecs describe-services --cluster prequal-cluster --services prequal-service

# Check application logs
aws logs tail /ecs/prequal-app --filter-pattern "ERROR" --limit 100

# Check Sentry for error patterns
# https://sentry.io
```

**Resolution:**
1. Identify error pattern in Sentry
2. If deployment-related → Rollback
3. If configuration → Fix and redeploy
4. If external dependency → Implement circuit breaker

---

### Runbook 4: Authentication Failures

**Symptoms:**
- Users cannot log in
- 401/403 errors increasing
- Auth service errors in logs

**Diagnosis:**
```bash
# Check auth service logs
aws logs tail /ecs/prequal-app --filter-pattern "auth" --limit 50

# Check Stripe connectivity (if payment-related)
curl -v https://api.stripe.com/v1/health

# Check session store (Redis)
# Via ElastiCache console or CLI
```

**Resolution:**
1. Check Stripe API status
2. Verify Redis connectivity
3. Check JWT secret/rotation
4. Restart auth service if needed

---

### Runbook 5: Data Issue

**Symptoms:**
- Data inconsistency reports
- Missing records
- Duplicate entries

**Diagnosis:**
1. Identify affected data scope
2. Check recent migrations/deploys
3. Review application logs for errors
4. Check database logs

**Resolution:**
1. Stop affected functionality if spreading
2. Restore from backup if corruption
3. Run data repair script if available
4. Manual fix as last resort

---

## Backup and Disaster Recovery

### Backup Schedule

| Backup Type | Frequency | Retention | Location |
|-------------|-----------|-----------|----------|
| RDS Automated | Daily | 7 days | AWS RDS |
| RDS Snapshot | Pre-deployment | 30 days | AWS RDS |
| S3 Export | Weekly | 90 days | S3 bucket |
| Terraform State | On change | 30 versions | S3 backend |

### Disaster Recovery Procedures

**RTO (Recovery Time Objective):** 4 hours
**RPO (Recovery Point Objective):** 24 hours

**DR Steps:**
1. Assess damage and scope
2. Activate DR team
3. Restore database from latest backup
4. Deploy infrastructure from Terraform
5. Verify data integrity
6. Resume operations
7. Post-incident review

---

## Testing and Maintenance

### Quarterly Tests

1. **Backup Restoration Test**
   - Restore database to test environment
   - Verify data integrity
   - Document restoration time

2. **Rollback Test**
   - Deploy to staging
   - Execute rollback procedure
   - Verify service recovery

3. **Alert Test**
   - Trigger test alarms
   - Verify all alert channels
   - Update contact list

### Annual Exercises

1. **Full DR Drill**
   - Simulate major outage
   - Execute full DR procedure
   - Document lessons learned

2. **Security Incident Tabletop**
   - Walk through breach scenario
   - Test communication paths
   - Update security procedures

---

## Appendix: Contact List

| Role | Name | Phone | Email |
|------|------|-------|-------|
| On-Call Primary | [Rotation] | [PagerDuty] | [Email] |
| CTO | [Name] | [Phone] | [Email] |
| CEO | [Name] | [Phone] | [Email] |
| AWS Support | - | - | support.aws.com |
| Sentry Support | - | - | support.sentry.io |

---

## Appendix: Dashboard Links

| Dashboard | URL |
|-----------|-----|
| AWS CloudWatch | https://us-east-1.console.aws.amazon.com/cloudwatch |
| ECS Console | https://us-east-1.console.aws.amazon.com/ecs |
| RDS Console | https://us-east-1.console.aws.amazon.com/rds |
| Sentry | https://sentry.io |
| UptimeRobot | https://uptimerobot.com |
| GitHub Actions | https://github.com/[org]/[repo]/actions |

---

**Last Updated**: 2026-06-14
**Maintained By**: DevOps Engineer
**Review Schedule**: Quarterly