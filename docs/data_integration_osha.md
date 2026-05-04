# OSHA Violation Data Ingestion Pipeline

This document describes the OSHA API integration for pulling violation history into Prequal's compliance tracking platform.

## API Client

**File:** `prequal-platform/data/osha_client.lua`

**Main Functions:**
- `ingest_osha_violations(subcontractor_id)`: Fetches and stores violations for a subcontractor
- `fetch_osha_violations(subcontractor)`: Queries OSHA API by name/EIN/state
- `map_osha_to_violations(data)`: Transforms OSHA response to internal schema
- `validate_osha_response(data)`: Ensures required fields are present

## Expected OSHA API Schema

Based on public OSHA datasets (https://www.osha.gov/enforcement/case-opening-and-closing-conference-data); exact API structure pending access:

```lua
{
  activity_nr        = "OSHA inspection ID",
  estab_name        = "Establishment/company name",
  ein               = "Employer Identification Number",
  inspection_date   = "Date of inspection (YYYY-MM-DD)",
  case_status       = "Open/Closed/Contested",
  current_penalty   = "Current penalty amount ($)",
  standard          = "OSHA standard violated (29 CFR Part)",
  violation_type    = "Serious/Other/Willful/Repeat",
  violation_description = "Details of violation",
  contest_date      = "Date contested (if applicable)"
}
```

## Database Integration

**Destination Table:** `violations`

**Field Mapping:**
| OSHA Field           | Violations Table Field     |
|----------------------|----------------------------|
| standard             | violation_code             |
| violation_type       | violation_type             |
| violation_description| description                |
| inspection_date      | issued_date                |
| current_penalty      | penalty_amount             |
| case_status          | status                     |
| activity_nr          | notes (inspection ref)     |

**Data Flow:**
1. Fetch subcontractor from `subcontractors` table
2. Query OSHA API by name, EIN, or license state
3. Validate response structure
4. Map OSHA fields to internal schema
5. Insert new violations; skip duplicates

## Rate Limit & Error Handling

- **Retry Policy:** 3 attempts for failed requests
- **Error Handling:** Write failures to application log, continue ingestion
- **Duplicate Prevention:** Skip records already in `violations` table

## Authentication

**Environment Variables Required:**
```
OSHA_API_KEY=your_api_key_here
OSHA_API_BASE_URL=https://api.osha.gov/developer/
```

## Example Usage

```lua
local osha = require("prequal-platform.data.osha_client")

-- Process violations for subcontractor
local result = osha.ingest_osha_violations("subcontractor-uuid-1234")
if result.success then
  print(string.format("Added %d new OSHA violations", result.new_violations))
else
  ngx.log(ngx.ERR, "OSHA ingestion failed: ", result.error)
end
```

## Testing

Pending OSHA API credentials, client implements schema validation using standard OSHA data shape.