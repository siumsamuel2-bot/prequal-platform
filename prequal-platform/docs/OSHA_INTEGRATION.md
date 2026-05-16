# OSHA Data Ingestion Pipeline

## Overview

This pipeline fetches OSHA violation data via the [OSHA Whistleblower Enforcement API](https://www.whistleblower.gov/api/cases), transforms the JSON into our violation/inspection schema, and loads them into the Prequal database.

## Files

| File | Description |
|------|-------------|
| `app/services/osha_client.py` | Async HTTP client with rate limiting |
| `scripts/etl_osha.py` | ETL pipeline entry point |
| `tests/test_osha_pipeline.py` | Unit tests for extract logic and client |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│ OSHA Client │────▶│  Transform   │────▶│ Upsert to DB     │
│  (aiohttp)  │     │ _extract_*   │     │ violations       │
└─────────────┘     └──────────────┘     │ osha_inspections │
                                         │ osha_api_logs    │
                                         │ osha_data_f.     │
                                         └──────────────────┘
```

## API Capabilities

- **Endpoint**: `GET https://www.whistleblower.gov/api/cases`
- **Authentication**: ApiKey header (`OSHA_API_KEY` env)
- **Rate Limit**: 1 req/sec default; configurable via `OSHA_RATE_LIMIT`
- **Pagination**: Progressive page fetch via `page` parameter + `page_size`
- **Filters**: `search`, `state`, `status`, `date_opened_from`, `date_opened_to`

## Configuration

Set these environment variables before running:

```bash
# Postgres
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/prequal_compliance"

# OSHA
export OSHA_API_KEY="your_api_key"
export OSHA_API_URL="https://www.whistleblower.gov/api/cases"  # default
export OSHA_RATE_LIMIT="1.0"  # req/sec
export OSHA_SEARCH_TERM=""     # default search
export OSHA_STATE_FILTER=""    # default state filter
```

## Usage

### Run ETL Manually

```bash
python scripts/etl_osha.py --search "Acme Construction" --state OH --max-pages 5
```

### Run Tests

```bash
pytest tests/test_osha_pipeline.py -v
```

### Schedule (Rec)

Wrap `scripts/etl_osha.py` in a cron or Paperclip routine. The pipeline is idempotent: records are upserted by `osha_violation_id` and `inspection_number`.

## Transform Mapping

| OSHA Source Field | Our Schema Field |
|-------------------|------------------|
| `id` / `case_number` | `osha_violation_id` |
| `allegation` / `summary` | `description` |
| `date_opened` | `issued_date` |
| `date_closed` | `resolution_date` |
| `status` | `status` (open → open, else resolved) |
| `inspection_number` | `inspection_number` |
| `statute` / `cfr` | `standard_cited` |
| `city` | `site_city` |
| `state` | `site_state` |
| `address` | `site_address` |
| `naics` | `naics_code` |

## Data Quality

- **Date parsing**: ISO-8601 strings converted to Python `date` objects
- **Duplicate handling**: SELECT-then-INSERT/UPDATE upsert via `osha_violation_id`
- **Missing fields**: Gracefully set to None for optional columns
- **Logging**: Every run writes to `osha_api_logs` with counts and error messages
- **Freshness tracking**: `osha_data_freshness` records last successful update

## Dependencies

Listed in `requirements.txt`:
- SQLAlchemy (async/sync)
- aiohttp (async HTTP)
- cachetools (caching, reserved for future use)
- pytest, pytest-asyncio (testing)

## Notes for DevOps

- SQLAlchemy and aiohttp are required at runtime.
- PostgreSQL must have the schema from `001_initial_schema` applied.
- Rate limit defaults are conservative: 1 req/sec.
