-- OSHA violation data integration and analytics extensions
-- Extends the violations table and adds supporting structures for OSHA API ingestion

-- Enable PostGIS for geospatial queries if needed
CREATE EXTENSION IF NOT EXISTS postgis;

-- Extend violations table for OSHA-specific fields
ALTER TABLE violations ADD COLUMN IF NOT EXISTS 
    osha_violation_id VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    citation_number VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    violation_description TEXT;

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    standard_cited VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    initial_penalty DECIMAL(10,2);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    final_penalty DECIMAL(10,2);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    abatement_date DATE;

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    date_corrected DATE;

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    contest_status VARCHAR(50);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    inspection_number VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    activity_number VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    site_city VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    site_state VARCHAR(50);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    site_zip_code VARCHAR(20);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    site_address TEXT;

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    naics_code VARCHAR(20);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    inspection_type VARCHAR(100);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    owner_type VARCHAR(50);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    gravity_score DECIMAL(5,2);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    probability_score DECIMAL(5,2);

ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    risk_category VARCHAR(50);

-- Add OSHA-specific status and flags
ALTER TABLE violations ADD COLUMN IF NOT EXISTS
    is_osha_violation BOOLEAN DEFAULT TRUE;

-- Add index for OSHA-specific fields
CREATE INDEX IF NOT EXISTS idx_violations_osha_violation_id ON violations(osha_violation_id);
CREATE INDEX IF NOT EXISTS idx_violations_inspection_number ON violations(inspection_number);
CREATE INDEX IF NOT EXISTS idx_violations_navigation ON violations(naics_code);
CREATE INDEX IF NOT EXISTS idx_violations_citation_number ON violations(citation_number);

-- Table for OSHA inspection metadata
CREATE TABLE osha_inspections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_number VARCHAR(100) UNIQUE NOT NULL,
    activity_number VARCHAR(100),
    inspection_date DATE NOT NULL,
    completion_date DATE,
    type VARCHAR(100) NOT NULL,  -- Complaint, Fatality, Referral, etc.
    scope VARCHAR(100),           -- Partial, Full, etc.
    site_city VARCHAR(100),
    site_state VARCHAR(50),
    site_zip_code VARCHAR(20),
    site_address TEXT,
    naics_code VARCHAR(20),
    reported_by VARCHAR(255),     -- Who reported the inspection
    owner_type VARCHAR(50),
    safety_man_hour INTEGER,
    health_man_hour INTEGER,
    total_penalty DECIMAL(10,2),
    abatement_completed DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for OSHA API ingestion logs
CREATE TABLE osha_api_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_type VARCHAR(50) NOT NULL,  -- inspection, violation, establishment
    request_parameters JSONB NOT NULL,
    request_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    response_status INTEGER,
    response_body JSONB,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for OSHA data freshness tracking
CREATE TABLE osha_data_freshness (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_type VARCHAR(50) NOT NULL,  -- inspections, violations, establishments
    last_updated TIMESTAMP WITH TIME ZONE,
    next_scheduled_update TIMESTAMP WITH TIME ZONE,
    update_frequency VARCHAR(50) DEFAULT 'daily',
    status VARCHAR(50) DEFAULT 'current', -- current, stale, failed_update
    last_run_log_id UUID REFERENCES osha_api_logs(id),
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analytics views for compliance reporting

-- Compliance status by subcontractor
CREATE OR REPLACE VIEW compliance_status_by_subcontractor AS
SELECT 
    s.id AS subcontractor_id,
    s.company_name,
    COUNT(DISTINCT CASE WHEN c.status = 'valid' THEN c.id END) AS valid_certifications,
    COUNT(DISTINCT CASE WHEN c.status = 'expired' THEN c.id END) AS expired_certifications,
    COUNT(DISTINCT CASE WHEN c.status = 'pending_verification' THEN c.id END) AS pending_verification,
    COUNT(DISTINCT CASE WHEN v.status = 'open' AND v.is_osha_violation = TRUE THEN v.id END) AS open_osha_violations,
    COUNT(DISTINCT CASE WHEN v.status = 'resolved' AND v.is_osha_violation = TRUE THEN v.id END) AS resolved_osha_violations,
    SUM(CASE WHEN v.penalty_amount IS NOT NULL AND v.is_osha_violation = TRUE THEN v.penalty_amount ELSE 0 END) AS total_penalties,
    MAX(CASE WHEN c.expiration_date > CURRENT_DATE AND c.status != 'valid' THEN NULL ELSE c.expiration_date END) AS earliest_expiration_date,
    CURRENT_DATE - MAX(CASE WHEN v.issued_date IS NOT NULL AND v.is_osha_violation = TRUE 
          AND v.status = 'open' THEN v.issued_date ELSE NULL END) AS days_with_open_violations
FROM 
    subcontractors s
LEFT JOIN 
    certifications c ON s.id = c.subcontractor_id
LEFT JOIN 
    violations v ON s.id = v.subcontractor_id AND v.is_osha_violation = TRUE
GROUP BY 
    s.id, s.company_name;

-- OSHA violation trends
CREATE OR REPLACE VIEW osha_violation_trends AS
SELECT
    v.subcontractor_id,
    s.company_name,
    DATE_TRUNC('month', v.issued_date) AS violation_month,
    COUNT(*) AS violation_count,
    SUM(v.penalty_amount) AS total_penalties,
    AVG(v.gravity_score) AS avg_gravity_score,
    COUNT(DISTINCT v.inspection_number) AS inspections_count,
    COUNT(DISTINCT CASE WHEN v.status = 'open' THEN v.id END) AS open_violations,
    MAX(v.issued_date) AS latest_violation_date
FROM
    violations v
JOIN
    subcontractors s ON v.subcontractor_id = s.id
WHERE
    v.is_osha_violation = TRUE
GROUP BY
    v.subcontractor_id, s.company_name, DATE_TRUNC('month', v.issued_date);

-- Expiring certifications report
CREATE OR REPLACE VIEW expiring_certifications AS
SELECT
    c.id AS certification_id,
    c.subcontractor_id,
    s.company_name,
    c.certification_type,
    c.expiration_date,
    CURRENT_DATE - c.expiration_date AS days_until_expiration,
    c.status AS certification_status,
    c.verification_status
FROM
    certifications c
JOIN
    subcontractors s ON c.subcontractor_id = s.id
WHERE
    c.expiration_date <= (CURRENT_DATE + INTERVAL '90 days')
    AND c.expiration_date >= CURRENT_DATE
    AND c.status != 'revoked'
ORDER BY
    c.expiration_date ASC;

-- Recently added violations
CREATE OR REPLACE VIEW recent_violations AS
SELECT
    v.id AS violation_id,
    v.subcontractor_id,
    s.company_name,
    v.violation_type,
    v.description,
    v.issued_date,
    v.status,
    v.penalty_amount,
    v.gravity_score,
    v.inspection_number
FROM
    violations v
JOIN
    subcontractors s ON v.subcontractor_id = s.id
WHERE
    v.issued_date >= (CURRENT_DATE - INTERVAL '60 days')
ORDER BY
    v.issued_date DESC;

-- Trigger updates
CREATE TRIGGER update_osha_inspections_updated_at
BEFORE UPDATE ON osha_inspections
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_osha_data_freshness_updated_at
BEFORE UPDATE ON osha_data_freshness
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();