# Contributing to Prequal

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL (via Docker)

### Local Setup
```bash
# Backend
cd prequal-platform
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
npm install

# Start services
docker-compose up -d
```

## Branch Strategy

- `main` - Production-ready code
- `staging` - Pre-production testing
- `feat/*` / `fix/*` / `refactor/*` - Feature branches

## Code Standards

### Python (Backend)
- Follow PEP 8
- Type hints required (enforced by mypy)
- Use `black` for formatting
- Use `ruff` for linting
- Docstrings for public functions

### TypeScript/React (Frontend)
- Strict TypeScript (`strict: true` in tsconfig)
- Functional components with hooks
- Use hooks from `src/hooks/`
- Test components with `@testing-library/react`

## Testing Requirements

- Minimum 80% test coverage
- Unit tests for business logic
- Integration tests for API endpoints
- E2E tests for critical user flows

```bash
# Run tests
pytest tests/ -v --cov=prequal-platform
npm test
```

## Code Review Process

### Opening a Pull Request
1. Fill out the PR template completely
2. Link the related issue (e.g., `Fixes MID-123`)
3. Ensure all CI checks pass
4. Request reviewers via CODEOWNERS or manual mention
5. Assign to rotation-based reviewer or request specific reviewer with justification

### Reviewer Rotation

The team follows a structured code reviewer rotation schedule defined in `docs/CODE_REVIEW_ROTATION.md`. The rotation ensures equitable distribution of review workload and timely PR processing.

**Quick Reference (from CODE_REVIEW_ROTATION.md):**
- Primary reviewer assigned via CODEOWNERS or rotation
- Response SLA: 24 hours (normal priority)
- Escalation: Secondary reviewer → Senior Engineer → CTO
- See `docs/CODE_REVIEW_ROTATION.md` for full rotation schedule and procedures

### Review Guidelines for Reviewers

**Before approving, verify:**
- [ ] Code follows project conventions
- [ ] No security vulnerabilities introduced
- [ ] Tests are adequate and passing
- [ ] No secrets or credentials in code
- [ ] Documentation updated if needed
- [ ] UI changes have screenshots

**Review focus areas:**
- Logic errors and edge cases
- Error handling completeness
- Performance implications
- Maintainability
- Security concerns

### Review Response Time
- Initial review: within 24 hours
- Re-review after changes: within 4 hours
- Hotfix/P0: 2 hours (see CODE_REVIEW_ROTATION.md for escalation)

**For full rotation details, SLAs by priority, and escalation paths, see `docs/CODE_REVIEW_ROTATION.md`.**

## Commit Messages

Format: `<type>(<scope>): <description>`

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(auth): add JWT refresh token`
- `fix(compliance): handle null certification date`
- `docs(api): update endpoint documentation`

## Security

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive config
- Report security issues to security@prequal.com

## Questions?

Reach out in `#engineering` on Slack or tag @CTO for guidance.