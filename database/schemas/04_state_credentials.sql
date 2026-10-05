-- State Credential Database Integration Schema
-- Extends the compliance platform to support external state licensing board data
-- Created for: MID-64 — Integrate External Compliance Data Sources

-- Table for raw state credential records fetched from state licensing APIs
CREATE TABLE state_credential_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_code VARCHAR(2) NOT NULL,                    -- e.g., 'TX', 'CA', 'FL'
    credential_number VARCHAR(100) NOT NULL,          -- License/credential number from state
    credential_type VARCHAR(100) NOT NULL,            -- e.g., 'General Contractor', 'Electrical'
    issuing_state VARCHAR(100) NOT NULL,                -- Full state name or code
    holder_name VARCHAR(255),                         -- Name of credential holder
    holder_address TEXT,
    holder_city VARCHAR(100),
    holder_state VARCHAR(50),
    holder_zip VARCHAR(20),
    issue_date DATE,
    expiration_date DATE,
    status VARCHAR(50) DEFAULT 'active',              -- active, expired, revoked, suspended
    external_source_id VARCHAR(255),                  -- ID from the state's system
    external_source_url TEXT,                          -- Link back to state record
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sync_version INTEGER DEFAULT 1,                     -- Incremented on each update
    raw_data JSONB,                                     -- Full raw response for debugging
    subcontractor_id UUID REFERENCES subcontractors(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Unique constraint to prevent duplicate state+credential_number+credential_type combos
CREATE UNIQUE INDEX idx_state_credential_unique 
    ON state_credential_records(state_code, credential_number, credential_type);

-- Indexes for matching and querying
CREATE INDEX idx_state_credential_state_code ON state_credential_records(state_code);
CREATE INDEX idx_state_credential_subcontractor_id ON state_credential_records(subcontractor_id);
CREATE INDEX idx_state_credential_status ON state_credential_records(status);
CREATE INDEX idx_state_credential_expiration ON state_credential_records(expiration_date);
CREATE INDEX idx_state_credential_last_synced ON state_credential_records(last_synced_at);

-- Full-text search on holder_name for fuzzy matching
CREATE INDEX idx_state_credential_holder_name 
    ON state_credential_records USING gin(to_tsvector('english', COALESCE(holder_name, '')));

-- Trigger to update updated_at
CREATE TRIGGER update_state_credential_records_updated_at
    BEFORE UPDATE ON state_credential_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Table for pipeline run audit logs
CREATE TABLE sync_run_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(255) NOT NULL,                     -- e.g., 'osha_daily_sync'
    job_type VARCHAR(100) NOT NULL,                   -- e.g., 'osha_sync', 'state_credential_sync'
    status VARCHAR(50) DEFAULT 'running',              -- running, completed, partial, failed, skipped
    triggered_by VARCHAR(100) DEFAULT 'schedule',       -- schedule, manual, webhook
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    records_matched INTEGER DEFAULT 0,
    error_message TEXT,
    run_metadata JSONB,                                 -- Additional structured info
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for sync_run_logs
CREATE INDEX idx_sync_run_logs_job_name ON sync_run_logs(job_name);
CREATE INDEX idx_sync_run_logs_status ON sync_run_logs(status);
CREATE INDEX idx_sync_run_logs_started_at ON sync_run_logs(started_at);
CREATE INDEX idx_sync_run_logs_job_type ON sync_run_logs(job_type);

-- Trigger for sync_run_logs updated_at
CREATE TRIGGER update_sync_run_logs_updated_at
    BEFORE UPDATE ON sync_run_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Table for tracking external data source health / freshness
CREATE TABLE external_data_freshness (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(100) NOT NULL,                  -- 'osha', 'tx_credentials', etc.
    source_type VARCHAR(50) NOT NULL,                   -- 'api', 'ftp', 'sftp'
    last_updated TIMESTAMP WITH TIME ZONE,
    next_scheduled_update TIMESTAMP WITH TIME ZONE,
    update_frequency VARCHAR(50) DEFAULT 'daily',       -- hourly, daily, weekly
    status VARCHAR(50) DEFAULT 'current',             -- current, stale, failed_update
    last_run_log_id UUID REFERENCES sync_run_logs(id) ON DELETE SET NULL,
    error_count INTEGER DEFAULT 0,
    last_error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_external_data_freshness_source 
    ON external_data_freshness(source_name, source_type);

CREATE TRIGGER update_external_data_freshness_updated_at
    BEFORE UPDATE ON external_data_freshness
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
