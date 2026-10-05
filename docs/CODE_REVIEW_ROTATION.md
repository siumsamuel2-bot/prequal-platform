# Code Review Rotation Schedule - Prequal Platform

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-06-29 | Senior Engineer | Initial code review rotation schedule |

---

## Overview

This document defines the code reviewer rotation schedule and procedures for the Prequal Platform engineering team. Following a structured rotation ensures equitable distribution of review workload, knowledge sharing, and consistent code quality across all pull requests.

---

## Rotation Schedule

### Q3 2026 Rotation (July - September)

| Week | Primary Reviewer | Secondary Reviewer | Start Date | End Date |
|------|------------------|-------------------|------------|----------|
| 1 | Backend Engineer | Senior Engineer | 2026-07-01 | 2026-07-07 |
| 2 | Frontend Engineer | Backend Engineer | 2026-07-08 | 2026-07-14 |
| 3 | Senior Engineer | Frontend Engineer | 2026-07-15 | 2026-07-21 |
| 4 | Backend Engineer | Senior Engineer | 2026-07-22 | 2026-07-28 |
| 5 | Frontend Engineer | Backend Engineer | 2026-07-29 | 2026-08-04 |

### Q4 2026 Rotation (October - December)

| Week | Primary Reviewer | Secondary Reviewer | Start Date | End Date |
|------|------------------|-------------------|------------|----------|
| 1 | Senior Engineer | Frontend Engineer | 2026-10-01 | 2026-10-07 |
| 2 | Backend Engineer | Senior Engineer | 2026-10-08 | 2026-10-14 |
| 3 | Frontend Engineer | Backend Engineer | 2026-10-15 | 2026-10-21 |
| 4 | Senior Engineer | Frontend Engineer | 2026-10-22 | 2026-10-28 |
| 5 | Backend Engineer | Senior Engineer | 2026-10-29 | 2026-11-04 |

**Note:** Update this schedule quarterly. All engineers must complete code review training before joining rotation.

---

## Reviewer Expectations

### Availability

**Primary Reviewer:**
- Available during business hours (9 AM - 6 PM local time)
- Must acknowledge PR review requests within 4 hours
- Complete initial review within 24 hours of acknowledgment
- Be responsive in PR threads within business hours

**Secondary Reviewer:**
- Available as backup if primary is unavailable
- Must respond within 8 hours if primary cannot review
- Step in for extended absences (>1 day)
- Typically CTO or lead engineer

### Response Time SLAs

| PR Priority | Response Time | Action |
|-------------|---------------|--------|
| Hotfix/P0 | 2 hours | Immediate review, notify team |
| High Priority | 4 hours | Expedited review |
| Normal | 24 hours | Standard review cycle |
| Low Priority | 48 hours | Review when capacity available |

---

## Review Assignment Process

### Automatic Assignment

PRs are assigned using CODEOWNERS file patterns:
- Backend PRs: Backend Engineer
- Frontend PRs: Frontend Engineer  
- Infrastructure/DevOps: Senior Engineer
- Security-related: Security Engineer (if applicable)

### Manual Override

For specialized review needs:
1. Author requests specific reviewer via PR comment
2. Tag requested reviewer in comment
3. Reason for specific assignment must be documented
4. Await confirmation of availability

### Rotation Bypass

**Expedited Review (no rotation):**
- Security fixes requiring immediate review
- P0/hotfix PRs
- CTO-directive priority items

---

## Code Review Handbook

### Before Your Review Week

**Preparation Checklist:**
- [ ] Review current team PR queue
- [ ] Check CODEOWNERS patterns are correct
- [ ] Confirm secondary reviewer availability
- [ ] Review any pending reviews from previous week
- [ ] Update rotation calendar if coverage needed

### During Your Review Week

**Daily Tasks:**
- [ ] Check for new PR review requests morning and afternoon
- [ ] Prioritize reviews by urgency
- [ ] Update PR status labels as review progresses
- [ ] Document any blockers or concerns in PR thread

**Review Process:**
1. Acknowledge review request (react with eyes emoji or comment)
2. Review PR description and linked issue
3. Check code changes systematically
4. Leave constructive feedback
5. Approve, request changes, or escalate if needed
6. Notify author of decision

### End of Week Handoff

**Handoff Checklist:**
- [ ] Complete any pending reviews
- [ ] Document open PRs requiring follow-up
- [ ] Brief incoming reviewer on any complex ongoing reviews
- [ ] Update rotation calendar

**Handoff Message Template:**
```
Code Review Handoff

Outgoing: [Your name]
Incoming: [Next reviewer name]
Week: [Date range]

Open PRs Needing Attention:
- [PR #] - [Title] - [Status]
- [PR #] - [Title] - [Status]

Notes:
- [Any special considerations for incoming reviewer]
```

---

## Review Guidelines

### What to Look For

**Correctness:**
- Logic errors and edge cases
- Error handling completeness
- Input validation
- Boundary condition handling

**Security:**
- No secrets or credentials in code
- Proper authentication/authorization
- SQL injection prevention
- XSS prevention
- Secure dependency updates

**Performance:**
- Database query efficiency
- N+1 query patterns
- Unnecessary re-renders (frontend)
- Memory leaks

**Maintainability:**
- Code follows project conventions
- Appropriate abstraction level
- Clear naming
- Minimal technical debt

**Testing:**
- Adequate test coverage
- Tests are meaningful
- Edge cases covered

### Review Response Templates

**Approval:**
```
LGTM! Nice work on [specific positive feedback].

Minor suggestions (non-blocking):
- [Optional suggestion 1]
- [Optional suggestion 2]

Approved. Merge when ready.
```

**Request Changes:**
```
Changes requested.

Issue: [Brief description of problem]
Suggestion: [How to fix it]

Code location: [File:Line or specific section]

Please address the above and re-request review.
```

**Escalation:**
```
Needs additional review from [reason].

This PR involves [security changes / complex logic / external API integration] 
that requires specialized review. Tagging @[Specialist] for additional review.

I'll continue review once concerns are addressed.
```

---

## Coverage and Time Off

### Review Coverage Swaps

**Process:**
1. Find willing swap partner (same rotation tier)
2. Notify team at least 24 hours in advance
3. Update rotation calendar
4. Confirm swap in #engineering channel
5. Document swap in PR if active reviews affected

### Vacation/Leave During Rotation

**Allowed:**
- Normal PTO with coverage arrangement
- Coverage swap with willing partner
- CTO approval for extended leave

**Not Allowed:**
- Leaving reviews unattended
- No-show without notification
- Unilateral swap without team notification

---

## Training Requirements

### Before Joining Rotation

**Required Training:**
- [ ] Complete code review training module
- [ ] Shadow 3 reviews with senior engineer
- [ ] Complete 2 supervised reviews with feedback
- [ ] Review CONTRIBUTING.md code standards
- [ ] Understand CODEOWNERS patterns

**Knowledge Requirements:**
- [ ] Project architecture overview
- [ ] Security review checklist
- [ ] Performance review checklist
- [ ] Testing standards and coverage requirements

---

## Metrics and Tracking

### Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Mean Review Time | <24 hours | [Track] |
| Review Coverage | >90% PRs reviewed | [Track] |
| Reviewer Satisfaction | >8/10 | [Track] |
| Re-request Rate | <20% | [Track] |

### Quarterly Reviews

**Review Topics:**
- Review time trends
- Common feedback patterns
- Training gaps
- Rotation fairness
- Tool effectiveness

**Action Items:**
- Update review guidelines
- Address training needs
- Adjust rotation if needed
- Improve tooling

---

## Escalation Contacts

### Escalation Path

```
PR Request → Primary Reviewer (24h)
    → Secondary Reviewer (8h if primary unavailable)
    → Senior Engineer (escalation)
    → CTO (unresolved >48h)
```

### Contact Information

| Role | Name | Slack | Email |
|------|------|-------|-------|
| Senior Engineer | [Rotation] | @senior-eng | senior@prequal.com |
| Backend Engineer | [Rotation] | @backend-eng | backend@prequal.com |
| Frontend Engineer | [Rotation] | @frontend-eng | frontend@prequal.com |
| CTO | [Name] | @cto | cto@prequal.com |

### When to Escalate

**Escalate to Senior Engineer:**
- Complex architectural decisions
- Security-sensitive changes
- Disagreements on approach
- Reviewer unavailable >24 hours

**Escalate to CTO:**
- Unresolved disputes
- Team blocked on review
- Repeated quality issues

---

## FAQs

**Q: What if a PR requires a specific expert who isn't in rotation?**
A: Request specific reviewer manually and notify rotation backup. The CODEOWNERS pattern still applies for default assignment.

**Q: Can I review multiple PRs simultaneously?**
A: Yes, but prioritize by urgency. If queue exceeds capacity, notify team and request assistance.

**Q: What if I need to decline a review due to conflict of interest?**
A: Decline politely, suggest alternative reviewer, document reason in PR thread.

**Q: How do I handle large PRs that can't be reviewed in one sitting?**
A: Break into smaller logical PRs when possible. For necessary large PRs, request multi-session review and coordinate with author.

**Q: Do I need to re-review after every change?**
A: No. Only request re-review when changes address your feedback. Minor fixes (typos, formatting) do not require re-review.

---

## Related Documents

- CONTRIBUTING.md - General contribution guidelines
- ON_CALL_ROTATION.md - On-call rotation schedule
- INCIDENT_RESPONSE_PLAN.md - Incident handling procedures
- DEPLOYMENT_RUNBOOK.md - Deployment procedures

---

**Last Updated**: 2026-06-29
**Maintained By**: Senior Engineer
**Review Schedule**: Quarterly
**Next Review**: 2026-09-29