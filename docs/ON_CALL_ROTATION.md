# On-Call Rotation Schedule - Prequal Platform

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-14 | DevOps Engineer | Initial on-call schedule |

---

## Overview

This document defines the on-call rotation schedule and procedures for the Prequal Platform engineering team.

---

## Rotation Schedule

### Q2 2026 Rotation (April - June)

| Week | Primary On-Call | Secondary (Backup) | Start Date | End Date |
|------|-----------------|-------------------|------------|----------|
| 1 | [Engineer A] | CTO | 2026-04-01 | 2026-04-07 |
| 2 | [Engineer B] | CTO | 2026-04-08 | 2026-04-14 |
| 3 | [Engineer C] | CTO | 2026-04-15 | 2026-04-21 |
| 4 | [Engineer A] | CTO | 2026-04-22 | 2026-04-28 |

### Q3 2026 Rotation (July - September)

| Week | Primary On-Call | Secondary (Backup) | Start Date | End Date |
|------|-----------------|-------------------|------------|----------|
| 1 | [Engineer B] | CTO | 2026-07-01 | 2026-07-07 |
| 2 | [Engineer C] | CTO | 2026-07-08 | 2026-07-14 |
| 3 | [Engineer A] | CTO | 2026-07-15 | 2026-07-21 |
| 4 | [Engineer B] | CTO | 2026-07-22 | 2026-07-28 |

**Note:** Update this schedule quarterly. All engineers must be trained on incident response before joining rotation.

---

## On-Call Expectations

### Availability

**Primary On-Call:**
- Available 24/7 during on-call week
- Must respond to alerts within SLA (see Incident Response Plan)
- Keep phone charged and audible
- Avoid activities that would prevent response (e.g., flights, surgery)

**Secondary On-Call:**
- Available as backup if primary unreachable
- Typically CTO or senior engineer
- Must respond within 10 minutes of escalation

### Response Time SLAs

| Severity | Response Time | Action |
|----------|---------------|--------|
| P0 - Critical | 5 minutes | Immediate response, war room |
| P1 - High | 15 minutes | Active investigation |
| P2 - Medium | 1 hour | Triage and assign |
| P3 - Low | 4 hours | Create ticket, normal workflow |

---

## Alert Configuration

### Alert Routing

**Primary Alerts (P0/P1):**
- Phone call via PagerDuty
- SMS message
- Email notification
- Slack mention in #incidents

**Secondary Alerts (P2/P3):**
- Email notification
- Slack message in #incidents

### Alert Channels Configuration

**PagerDuty Setup:**
```
Service: Prequal Platform
Escalation Policy:
  - Level 1: Primary On-Call (5 min)
  - Level 2: Secondary On-Call (10 min)
  - Level 3: CTO/CEO (15 min)
```

**Slack Configuration:**
- Channel: #incidents
- Bot: @PagerDuty Bot
- Notifications: All severities

**Email Distribution:**
- Primary: oncall@company.com (forwards to current on-call)
- Secondary: engineering@company.com
- Executive: cto@company.com, ceo@company.com (P0/P1 only)

---

## On-Call Handbook

### Before Your Shift

**Preparation Checklist:**
- [ ] Review incident response plan
- [ ] Test alert routing (phone, SMS, email)
- [ ] Confirm access to all systems:
  - AWS Console
  - CloudWatch dashboards
  - Sentry dashboard
  - GitHub Actions
  - Terraform state
  - Runbooks
- [ ] Check calendar for conflicts
- [ ] Brief handoff with previous on-call
- [ ] Verify secondary on-call availability

### During Your Shift

**Daily Checks:**
- [ ] Review CloudWatch dashboard
- [ ] Check Sentry error trends
- [ ] Verify backup success (if overnight)
- [ ] Monitor UptimeRobot status

**When Alert Fires:**
1. Acknowledge within SLA
2. Assess severity
3. Follow appropriate runbook
4. Document in incident log
5. Escalate if needed
6. Communicate status updates

### Handoff Procedure

**End of Shift Checklist:**
- [ ] Document any open incidents
- [ ] Transfer alert routing to next on-call
- [ ] Update on-call calendar
- [ ] Post handoff message in #engineering
- [ ] Brief incoming on-call on any ongoing issues

**Handoff Message Template:**
```
🔄 On-Call Handoff

Outgoing: [Your name]
Incoming: [Next on-call name]
Week: [Date range]

Open Incidents:
- [List any ongoing incidents or follow-ups]

Recent Activity:
- [Summary of incidents handled this week]

Notes:
- [Any special considerations for incoming on-call]
```

---

## Compensation and Time Off

### On-Call Compensation

**Weekly Stipend:** $500/week for primary on-call
**Incident Pay:** 1.5x hourly rate for time spent on incidents
**P0 Bonus:** Additional $200 for P0 incidents resolved within SLA

### Time Off During On-Call

**Not Allowed:**
- International travel without backup coverage
- Activities preventing alert response (flights, surgery, etc.)
- Full days off without arranging coverage

**Allowed:**
- Normal evenings and personal time
- Exercise and appointments (with phone accessible)
- Local activities (with alert response capability)

### Coverage Swaps

**Process:**
1. Find willing swap partner (same training level)
2. Notify CTO at least 48 hours in advance
3. Update on-call calendar
4. Transfer alert routing
5. Document swap in #engineering channel

---

## Training Requirements

### Before Joining Rotation

**Required Training:**
- [ ] Incident response plan review
- [ ] Runbook walkthrough with senior engineer
- [ ] Shadow on-call for 1 week
- [ ] Mock incident drill (P0 scenario)
- [ ] AWS console access and navigation
- [ ] Terraform basics
- [ ] Database backup/restore procedure

**Access Requirements:**
- [ ] AWS IAM user with appropriate permissions
- [ ] Sentry access
- [ ] GitHub admin access
- [ ] PagerDuty user account
- [ ] Slack #incidents channel access

### Ongoing Training

**Quarterly:**
- [ ] Runbook refresher
- [ ] New feature overview
- [ ] Incident post-mortem review
- [ ] Tool updates training

**Annual:**
- [ ] Full DR drill participation
- [ ] Security incident tabletop
- [ ] Certification renewal (if applicable)

---

## Incident Log

### Log Template

| Date | Time | Severity | Description | Responder | Duration | Status |
|------|------|----------|-------------|-----------|----------|--------|
| YYYY-MM-DD | HH:MM | P0/P1/P2/P3 | Brief description | Name | X hours | Resolved |

### Recent Incidents

**2026 Incidents:**

| Date | Severity | Description | Responder | Duration | Status |
|------|----------|-------------|-----------|----------|--------|
| [Add as incidents occur] | | | | | |

---

## Escalation Contacts

### Primary Escalation Path

```
Alert → Primary On-Call (5 min)
    ↓ (no response)
Secondary On-Call (10 min)
    ↓ (no response)
CTO (15 min)
    ↓ (no response)
CEO (20 min)
```

### Contact Information

| Role | Name | Phone | Email | Slack |
|------|------|-------|-------|-------|
| Primary On-Call | [Rotation] | [PagerDuty] | oncall@company.com | @oncall |
| Secondary On-Call | CTO | [Phone] | cto@company.com | @cto |
| CEO | [Name] | [Phone] | ceo@company.com | @ceo |
| AWS Support | - | 1-800-XXX-XXXX | support.aws.com | - |

### Emergency Escalation Criteria

**Escalate to CTO Immediately:**
- Any P0 incident
- Security breach suspected
- Data loss confirmed
- Customer-impacting incident >30 minutes
- Legal/compliance implications

**Escalate to CEO:**
- P0 incident >1 hour
- Major customer escalation
- PR/reputation risk
- CTO unreachable during P0

---

## Tools and Access

### Monitoring Tools

| Tool | Purpose | URL | Access Required |
|------|---------|-----|-----------------|
| CloudWatch | Infrastructure metrics | aws.amazon.com/cloudwatch | AWS IAM |
| Sentry | Error tracking | sentry.io | Sentry account |
| UptimeRobot | External monitoring | uptimerobot.com | UptimeRobot account |
| GitHub Actions | CI/CD status | github.com | GitHub org member |

### Runbook Access

All runbooks stored in: `docs/` directory
- Incident Response Plan: `docs/INCIDENT_RESPONSE_PLAN.md`
- Deployment Runbook: `docs/DEPLOYMENT_RUNBOOK.md`
- Monitoring Setup: `docs/MONITORING_SETUP_SUMMARY.md`
- Backup Procedures: `scripts/backup-database.sh`

---

## FAQs

**Q: What if I miss an alert?**
A: Immediately acknowledge, escalate to secondary, and document in incident log. Review alert configuration to prevent recurrence.

**Q: Can I drink alcohol while on-call?**
A: Moderate consumption only. You must be able to respond effectively to incidents.

**Q: What if I'm sick during my on-call week?**
A: Arrange coverage swap as early as possible. Health comes first—notify CTO and find backup.

**Q: How many incidents per week is normal?**
A: Varies by system maturity. Target: <5 P2+ incidents/week. If higher, prioritize reliability improvements.

**Q: Do I need to write post-mortems for all incidents?**
A: Required for P0/P1. Recommended for recurring P2. Optional for P3.

---

## Continuous Improvement

### Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Mean Time to Acknowledge (MTTA) | <5 min (P0) | [Track] |
| Mean Time to Resolve (MTTR) | <1 hour (P0) | [Track] |
| Alert Fatigue Score | <10 alerts/week | [Track] |
| On-Call Satisfaction | >8/10 | [Track] |

### Quarterly Reviews

**Review Topics:**
- Incident trends and patterns
- Alert noise vs. signal
- On-call satisfaction
- Tool effectiveness
- Training gaps
- Runbook updates

**Action Items:**
- Update runbooks based on learnings
- Adjust alert thresholds
- Improve tooling
- Address training needs

---

**Last Updated**: 2026-06-14
**Maintained By**: DevOps Engineer
**Review Schedule**: Quarterly
**Next Review**: 2026-09-14