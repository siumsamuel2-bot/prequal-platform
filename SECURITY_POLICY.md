# Dependency Vulnerability Policy

**Effective Date**: 2026-06-09  
**Owner**: DevOps Engineer  
**Review Cadence**: Monthly

## Overview

This document defines the policy and procedures for managing dependency vulnerabilities in the Prequal platform codebase.

## Scanning Tools

### Node.js Dependencies
- **Primary**: `npm audit` (built-in)
- **Secondary**: `eslint-plugin-security`, `semgrep`
- **CI/CD Integration**: GitHub Actions (ci-cd.yml)

### Python Dependencies
- **Primary**: `pip-audit`
- **Secondary**: `safety`, `bandit` (for code security)
- **CI/CD Integration**: GitHub Actions (production-deployment.yml)

### Container Images
- **Primary**: Trivy vulnerability scanner
- **CI/CD Integration**: GitHub Actions (production-deployment.yml)

### Secrets Scanning
- **Primary**: Gitleaks
- **CI/CD Integration**: GitHub Actions (ci-cd.yml, production-deployment.yml)

## Vulnerability Severity Levels

| Severity | Definition | Response Time |
|----------|-----------|---------------|
| Critical | Remote code execution, authentication bypass, data exposure | Immediate (24 hours) |
| High | Significant security impact, privilege escalation | 7 days |
| Medium | Moderate security impact | 30 days |
| Low | Minimal security impact | 90 days |

## Automated Scanning

### CI/CD Pipeline Gates

**Pre-merge checks** (pull requests):
- `npm audit` - must pass (no critical/high vulnerabilities)
- `eslint-plugin-security` - must pass
- `semgrep --config auto --error` - must pass
- `gitleaks` - must pass (no secrets detected)

**Pre-deployment checks** (production):
- `pip-audit` - must pass (no critical/high vulnerabilities)
- Trivy container scan - must pass (no critical/high vulnerabilities)
- All pre-merge checks must pass

### GitHub Actions Configuration

```yaml
# Secrets scanning
- name: Run gitleaks secrets scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

# Node.js security
- name: Run ESLint security plugin
  run: npx eslint --plugin security .

- name: Run Semgrep security scan
  run: npx semgrep --config auto --error

# Python security (production-deployment.yml)
- name: Run pip-audit
  run: |
    pip install pip-audit
    python -m pip_audit --requirement requirements.txt

# Container security
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.AWS_REGION }}.amazonaws.com/${{ env.ECR_REPOSITORY_BACKEND }}:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'
```

## Manual Review Process

### Monthly Dependency Audit

1. **Run comprehensive scans**:
   ```bash
   # Node.js
   npm audit --audit-level=moderate
   
   # Python
   python -m pip_audit --requirement requirements.txt
   
   # Container images
   trivy image prequal-platform:latest
   ```

2. **Review and categorize findings**:
   - Document all critical/high vulnerabilities
   - Assess exploitability and impact
   - Determine remediation path

3. **Update dependencies**:
   - Patch version updates (automatic)
   - Minor version updates (test required)
   - Major version updates (breaking changes review)

4. **Risk acceptance** (if patching not possible):
   - Document vulnerability
   - Assess mitigating controls
   - Set review date (max 90 days)
   - Requires CTO approval for critical/high

## Remediation Workflow

### Critical/High Vulnerabilities

1. **Detection** (automated via CI/CD)
2. **Triage** (DevOps Engineer, within 24 hours)
   - Verify vulnerability
   - Assess impact
   - Identify affected services
3. **Patch** (Development team)
   - Update dependency
   - Run tests
   - Deploy to staging
4. **Verify** (DevOps Engineer)
   - Re-scan to confirm fix
   - Validate in staging
5. **Deploy** (CI/CD pipeline)
   - Production deployment
   - Monitor for issues

### Medium/Low Vulnerabilities

1. **Detection** (automated or manual audit)
2. **Triage** (monthly review)
3. **Schedule** (next sprint planning)
4. **Patch** (standard development workflow)
5. **Deploy** (regular release cycle)

## Exception Process

Exceptions may be granted when:
- No patch is available
- Patching requires breaking changes
- Mitigating controls reduce risk to acceptable level

**Exception Requirements**:
- Written justification
- Risk assessment
- Mitigation plan
- Review date (max 90 days)
- CTO approval for critical/high severity

## Documentation

All vulnerability findings, remediation actions, and exceptions must be documented in:
- GitHub Issues (tracking)
- Security audit log (compliance)
- This policy document (process improvements)

## Tools Configuration

### Gitleaks Configuration

See `.gitleaks.toml` for:
- Secret patterns (AWS, Stripe, API keys, etc.)
- Allowlist rules
- Path exclusions

### ESLint Security Plugin

```json
{
  "plugins": ["security"],
  "extends": ["plugin:security/recommended"],
  "rules": {
    "security/detect-object-injection": "warn",
    "security/detect-non-literal-fs-filename": "warn",
    "security/detect-eval-with-expression": "error"
  }
}
```

### Semgrep Configuration

```yaml
# .semgrep.yml
rules:
  - p:security
  - p:owasp-top-ten
  - p:cwe-top-25
```

## Compliance

This policy supports:
- SOC 2 Type II requirements
- OWASP Top 10 compliance
- CIS Benchmark standards

## Review and Updates

This policy must be reviewed:
- Quarterly by DevOps Engineer
- After any security incident
- When new tools or processes are adopted

---

**Last Updated**: 2026-06-09  
**Next Review**: 2026-09-09  
**Approved By**: CTO