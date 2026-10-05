# State Contractor Licensing Board API Research

## Overview
Research findings for integrating state-level contractor credential databases into the Prequal compliance platform.

## Ranking by API Accessibility & Data Richness

### 1. TEXAS (TX) — Texas Department of Licensing and Regulation (TDLR)
- **API Type**: Socrata Open Data API (REST JSON)
- **Endpoint Base**: `https://data.texas.gov/resource/`
- **Primary Dataset**: Texas Active License Verification Search
- **Data Available**: License number, name, status, issue/expiration dates, class, discipline
- **Auth**: No API key required for public data (app token recommended for higher rate limits)
- **Rate Limit**: ~1,000 requests/hour without token, higher with token
- **Refresh Frequency**: Weekly updates
- **Docs**: https://dev.socrata.com/
- **Notes**: 
  - Most accessible API of the five states
  - Returns JSON, CSV, or XML
  - Supports `$where` filtering (SoQL)
  - Includes Air Conditioning, Barbering, Cosmetology, Driver Education, Electrician, Massage, Mold, Podiatry, Sanitarian, Speech, Tow, Water Well, and more
- **Recommended for Integration**: YES (primary target)

### 2. CALIFORNIA (CA) — Contractors State License Board (CSLB)
- **API Type**: REST JSON via California Open Data portal + SOAP-based Instant License Check
- **Endpoint Base**: 
  - Open Data: `https://data.ca.gov/api/3/action/`
  - Instant Check: SOAP web service
- **Data Available**: License number, business name, classification, status, workers comp, bond, entity, disciplinary actions
- **Auth**: API key for Open Data; account required for Instant Check
- **Rate Limit**: Not publicly documented; moderate
- **Refresh Frequency**: Monthly for bulk data; real-time for Instant Check
- **Docs**: 
  - CKAN API: https://docs.ckan.org/en/latest/api/
  - Instant Check: https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/
- **Notes**:
  - Dual API approach (bulk + real-time)
  - Rich disciplinary action data
  - Requires more complex integration
- **Recommended for Integration**: YES (secondary target)

### 3. FLORIDA (FL) — Department of Business and Professional Regulation (DBPR)
- **API Type**: SOAP/XML via MyFlorida Marketplace + screen scraping fallback
- **Endpoint**: `https://www.myfloridalicense.com/` (search UI)
- **Data Available**: License number, type, status, issue/expiration, disciplinary history
- **Auth**: Requires account for API access
- **Rate Limit**: Not publicly documented; appears moderate
- **Refresh Frequency**: Daily updates for license status
- **Docs**: Limited public API documentation
- **Notes**:
  - No true public REST API
  - SOAP integration requires WSDL parsing
  - Screen scraping as fallback (fragile)
- **Recommended for Integration**: YES (tertiary target, with scraping fallback)

### 4. NEW YORK (NY) — Department of State, Division of Licensing Services
- **API Type**: None (public REST/SOAP)
- **Available Data**: License lookup via web search only
- **Access**: Manual web search at `https://www.dos.ny.gov/licensing/`
- **Data Available**: License number, name, status, type
- **Auth**: N/A
- **Rate Limit**: N/A
- **Refresh Frequency**: Unknown
- **Notes**:
  - No programmatic API
  - Would require screen scraping or manual data entry
  - Data richness is limited compared to CA and TX
- **Recommended for Integration**: NO (unless screen scraping is desired)

### 5. ILLINOIS (IL) — Department of Financial and Professional Regulation (IDFPR)
- **API Type**: None (public REST/SOAP)
- **Available Data**: License lookup via web search
- **Access**: `https://idfpr.illinois.gov/` (search UI)
- **Data Available**: License number, name, status, expiration
- **Auth**: N/A
- **Rate Limit**: N/A
- **Refresh Frequency**: Unknown
- **Notes**:
  - No programmatic API
  - Would require screen scraping
  - Data is less rich than TX/CA
- **Recommended for Integration**: NO (unless screen scraping is desired)

## Integration Priority

| Priority | State | API Quality | Data Richness | Integration Difficulty |
|----------|-------|-------------|---------------|----------------------|
| 1 | TX | High | High | Low |
| 2 | CA | Medium-High | Very High | Medium |
| 3 | FL | Low | Medium | High |
| 4 | NY | None | Low | Very High |
| 5 | IL | None | Low | Very High |

## Recommendation

**Phase 1**: Integrate Texas (TDLR) as the primary state credential source. It has the most accessible API, returns rich license data, and updates weekly. This gives Prequal a working state-level compliance differentiator immediately.

**Phase 2**: Add California (CSLB) as a secondary source. The dual API approach (bulk + real-time) provides the richest data but requires more engineering effort.

**Phase 3**: Evaluate Florida, New York, and Illinois for screen-scraping or wait for them to release public APIs.

## Unified Data Model Mapping

All state credential sources map to the `state_credential_records` table:

| Prequal Field | TX TDLR Field | CA CSLB Field | Notes |
|---------------|---------------|金光-------------|-------|
| `state_code` | `state` | `state` | Static mapping |
| `credential_number` | `license_number` | `license_number` | Primary license identifier |
| `credential_type` | `license_type` / `program` | `classification` | TX: 'HVAC', 'Electrician', etc. |
| `issuing_state` | 'Texas' | 'California' | Static mapping |
| `holder_name` | `licensee_name` | `business_name` | Entity holding the license |
| `holder_address` | `address` | `address` | May be partial |
| `holder_city` | `city` | `city` | |
| `holder_state` | `state` | `state` | |
| `holder_zip` | `zip` | `zip` | |
| `issue_date` | `issue_date` | `issue_date` | |
| `expiration_date` | `expiration_date` | `expiration_date` | |
| `status` | `status` | `status` | Map to Prequal enum: active, expired, revoked, suspended |
| `external_source_id` | `license_id` | `license_id` | Unique ID from source system |
| `external_source_url` | `https://tdlr.texas.gov/verify/{number}` | `https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx?LicNum={number}` | Deep link to source |
| `raw_data` | Full JSON response | Full JSON response | Preserved for audit/debug |

## Daily Sync Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Scheduler      │────▶│  State Sync Job  │────▶│  Texas TDLR API     │
│  (cron/APScheduler)│     │  (Python Service)│     │  (Socrata/REST)     │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                                │
                                ▼
                         ┌──────────────────┐
                         │  Transform Layer │
                         │  (Map to Prequal │
                         │   Schema)        │
                         └──────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  state_credential_records│
                    │  sync_run_logs (audit)   │
                    │  external_data_freshness │
                    └────────────────────────┘
```

## Auth & Rate Limiting Strategy

- **App Token**: Store in environment variable `TEXAS_TDLR_APP_TOKEN` (optional but recommended)
- **Rate Limit**: Default to 1000 req/hr; implement exponential backoff on 429s
- **User Agent**: Custom string to identify Prequal (`Prequal-ComplianceBot/1.0`)
- **Caching**: Cache results for 24 hours to reduce API load
