-- OSHA API Client for Prequal Subcontractor Compliance Platform
-- Implements data ingestion pipeline for OSHA violation data

-- Usage:
-- 1. Set environment variables: OSHA_API_KEY, OSHA_API_BASE_URL
-- 2. Call ingest_osha_violations() with subcontractor details
-- 3. Response maps to violations table in database schema

local http = require('resty.http')
local cjson = require('cjson')

-- Expected OSHA Violation Data Structure
-- Based on OSHA public datasets and industry standards
local function get_expected_osha_schema()
  return {
    activity_nr = "Unique identifier for the inspection/violation",
    estab_name = "Name of the establishment/company (subcontractor)",
    trade_name = "Trade name/DBA of the company",
    sito_flag = "Single establishment flag (Y/N)",
    naics_code = "Industry classification code",
    owner_type = "Type of ownership (Private, Government, etc.)",
    nbr_employees = "Number of employees",
    current_penalty = "Current penalty amount",
    initial_penalty = "Initial penalty amount",
    inspection_date = "Date of inspection",
    inspection_type = "Type of inspection (Complaint, Planned, etc.)",
    case_status = "Status of the case (Open, Closed, etc.)",
    citation_id = "Citation identifier",
    standard = "OSHA standard violated (29 CFR Part)",
    standard_description = "Description of the violated standard",
    violation_type = "Type of violation (Serious, Other, etc.)",
    serious_violation = "Serious violation flag (Y/N)",
    repeated_violation = "Repeated violation flag (Y/N)",
    willful_violation = "Willful violation flag (Y/N)",
    final_order_date = "Final order/adjudication date",
    contest_date = "Date case was contested",
    violations = {
      {
        citation_number = "Citation number",
        item_number = "Item number",
        violation_description = "Description of the specific violation",
        initial_penalty = "Initial penalty for this violation",
        current_penalty = "Current penalty for this violation"
      }
    }
  }
end

-- Validate OSHA API response against expected schema
local function validate_osha_response(data)
  local required_fields = {
    "activity_nr", "estab_name", "inspection_date", 
    "case_status", "current_penalty"
  }
  
  for _, field in ipairs(required_fields) do
    if not data[field] or data[field] == "" then
      return false, "Missing required field: " .. field
    end
  end
  
  return true, nil
end

-- Map OSHA response to internal violations schema
local function map_osha_to_violations(osha_data)
  return {
    subcontractor_id = nil,  -- To be filled during ingestion with matching logic
    violation_type = osha_data.violation_type or "Safety Violation",
    violation_code = osha_data.standard,  -- OSHA standard code
    description = osha_data.standard_description or osha_data.violation_description,
    issued_by = "OSHA",  -- Federal/state agency that issued the violation
    issued_date = osha_data.inspection_date,
    effective_date = osha_data.final_order_date,
    resolution_date = osha_data.contest_date,
    status = osha_data.case_status == "Closed" and "resolved" or "open",
    penalty_amount = tonumber(osha_data.current_penalty) or 0,
    is_criminal = osha_data.willful_violation == "Y",
    notes = string.format("Inspection: %s | Type: %s | Standard: %s", 
                osha_data.activity_nr,
                osha_data.inspection_type,
                osha_data.standard)
  }
end

-- Fetch OSHA violations for subcontractor based on name/EIN
local function fetch_osha_violations(subcontractor)
  local httpc = http.new()
  local api_key = os.getenv("OSHA_API_KEY")
  local base_url = os.getenv("OSHA_API_BASE_URL") or "https://www.osha.gov/api/"
  
  local query_params = {
    key = api_key,
    format = "json",
    establishment_name = subcontractor.company_name,
    ein = subcontractor.ein,  -- Employer Identification Number
    state = subcontractor.license_state,
    limit = 100  -- Max initial results
  }
  
  local query_string = {
    "key=" .. query_params.key,
    "format=" .. query_params.format,
    "establishment_name=" .. ngx.escape_uri(query_params.establishment_name),
    "ein=" .. ngx.escape_uri(query_params.ein),
    "state=" .. ngx.escape_uri(query_params.state),
    "limit=" .. query_params.limit
  }
  
  local url = base_url .. "/violations?" .. table.concat(query_string, "&")
  
  local res, err = httpc:request_uri(url, {
    method = "GET",
    headers = {
      ["Accept"] = "application/json",
      ["User-Agent"] = "Prequal Compliance Platform"
    }
  })
  
  if not res then
    ngx.log(ngx.ERR, "Failed to request OSHA API: ", err)
    return nil, err
  end
  
  if res.status ~= 200 then
    ngx.log(ngx.ERR, "OSHA API returned non-200 status: ", res.status)
    return nil, "API request failed with status: " .. res.status
  end
  
  local ok, data = pcall(cjson.decode, res.body)
  if not ok then
    return nil, "Failed to parse JSON response"
  end
  
  -- Assume OSHA API returns data array directly
  -- In practice, may need to navigate data.results or similar
  return data, nil
end

-- Main ingestion pipeline
local function ingest_osha_violations(subcontractor_id)
  -- Step 1: Fetch subcontractor details from database
  local subcontractor = db.fetch_subcontractor(subcontractor_id)
  if not subcontractor then
    return nil, "Subcontractor not found"
  end
  
  -- Step 2: Pull violation history from OSHA API
  local osha_data, err = fetch_osha_violations(subcontractor)
  if not osha_data then
    -- Fallback: log locally but continue without violations
    ngx.log(ngx.WARN, "OSHA API fetch failed for ", subcontractor.company_name, ": ", err)
    return {success = true, new_violations = 0, error = err}
  end
  
  -- Step 3: Validate and process each violation
  local new_violations = 0
  for _, violation_data in ipairs(osha_data) do
    local is_valid, validation_err = validate_osha_response(violation_data)
    if not is_valid then
      ngx.log(ngx.WARN, "Invalid OSHA data ignored: ", validation_err)
      goto continue
    end
    
    local violation = map_osha_to_violations(violation_data)
    violation.subcontractor_id = subcontractor_id
    
    -- Step 4: Insert into violations table if not already present
    local existing = db.check_violation_exists(violation.subcontractor_id,
                                     violation.violation_code,
                                     violation.issued_date)
    
    if not existing then
      local success, db_err = db.insert_violation(violation)
      if success then
        new_violations = new_violations + 1
      else
        ngx.log(ngx.ERR, "Failed to insert violation: ", db_err)
      end
    end
    
    ::continue::
  end
  
  return {success = true, new_violations = new_violations}
end

return {
  ingest_osha_violations = ingest_osha_violations,
  get_expected_osha_schema = get_expected_osha_schema,
  validate_osha_response = validate_osha_response,
  map_osha_to_violations = map_osha_to_violations
}