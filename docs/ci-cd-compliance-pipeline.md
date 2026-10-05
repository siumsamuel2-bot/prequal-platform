# CI/CD Pipeline for Compliance Integration

## Overview

This document describes the CI/CD pipeline configuration for the compliance data integration work.

## Pipeline Location

- **Main CI/CD Workflow**: `.github/workflows/ci-cd.yml`
- **FastAPI Backend Workflow**: `.github/workflows/fastapi-backend.yml`
- **Staging Deployment**: `.github/workflows/staging-deployment.yml`

## Compliance Integration Tests

The CI pipeline includes dedicated integration testing for compliance data pipelines:

### Test Files

1. **`prequal-platform/tests/test_external_compliance_pipeline.py`**
   - Tests for External Compliance ETL Pipeline
   - Covers data integrity, pipeline correctness, and matching logic
   - Tests utility functions: `normalize_company_name`, `parse_date`, `parse_decimal`, `map_status`
   - Tests `MatchResult`, `PipelineRun`, and `run_state_credential_sync`

2. **`prequal-platform/tests/test_analytics_pipeline.py`**
   - Tests for analytics pipeline (materialized views + aggregate queries)
   - Validates MVs exist and are queryable
   - Tests aggregation shapes match expected API response format
   - Tests data quality (no negative counts, valid date formats)
   - Tests edge cases (empty tables, single rows, null values)

### CI Pipeline Stages

The compliance integration tests run in the `integration-tests` job:

```yaml
integration-tests:
  needs: test
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15
      # ... test database configuration
  
  steps:
    - Run compliance pipeline integration tests
      pytest tests/test_external_compliance_pipeline.py -v \
        --cov=app/services/external_compliance_pipeline \
        --cov-report=xml
    
    - Run analytics pipeline integration tests
      pytest tests/test_analytics_pipeline.py -v \
        --cov=app/services/analytics_pipeline \
        --cov-report=xml
```

### Trigger Conditions

The pipeline runs on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch with environment selection

### Environment Variables

Compliance tests use:
- `DATABASE_URL`: PostgreSQL connection for test database
- `TEST_COMPLIANCE_DATA`: Flag to enable compliance data tests
- `TEST_ANALYTICS_DATA`: Flag to enable analytics data tests

## Coverage Reporting

Integration test coverage is uploaded to Codecov:
- Compliance pipeline coverage flagged as `integration`
- Analytics pipeline coverage flagged as `integration`
- Reports available in GitHub Actions artifacts

## Deployment Flow

1. **Security scans** (gitleaks, semgrep) → must pass
2. **Python linting** (flake8, black, mypy, ruff) → must pass
3. **Unit tests** → must pass with 80% coverage threshold
4. **Integration tests** (compliance + analytics) → must pass
5. **Performance tests** (on develop branch only)
6. **Docker build** with semantic versioning
7. **Deploy to staging** (on develop or manual trigger)
8. **Deploy to production** (on main or tagged releases)

## Manual Testing

To run compliance integration tests locally:

```bash
cd prequal-platform
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov

# Run compliance pipeline tests
pytest tests/test_external_compliance_pipeline.py -v \
  --cov=app/services/external_compliance_pipeline \
  --cov-report=html

# Run analytics pipeline tests
pytest tests/test_analytics_pipeline.py -v \
  --cov=app/services/analytics_pipeline \
  --cov-report=html
```

## Related Issues

- MID-120: Compliance data integration work
- MID-138: Set up CI pipeline for compliance integration (this issue)

## Maintenance Notes

- Pipeline configuration reviewed: 2026-06-16
- All compliance integration tests are passing
- Coverage threshold: 80% for integration tests
- PostgreSQL 15 used for test database