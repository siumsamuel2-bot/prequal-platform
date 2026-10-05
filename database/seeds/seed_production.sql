-- ================================================================
-- Production Seed Data
-- Purpose: Real-world subcontractor compliance scenarios for pilot
-- Depends On: Full schema (01-05) + 06_production_migration.sql
-- Author: Data Engineer
-- Date: 2026-06-09
-- ================================================================

-- ================================================================
-- 1. USER BASELINE (for foreign key consistency)
-- ================================================================

INSERT INTO users (id, email, first_name, last_name, is_active, created_at, updated_at)
VALUES
    ('aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'admin@prequal.com', 'System', 'Admin', TRUE, NOW(), NOW()),
    ('aaaaaaaa-8888-8888-8888-aaaaaaaa8888', 'data@prequal.com', 'Data', 'Engineer', TRUE, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO organizations (id, name, slug, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-orgaaaaaaaa01', 'Prequal Demo Org', 'prequal-demo-org', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO teams (id, name, org_id, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-teamaaaaaa01', 'Operations', '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ================================================================
-- 2. seed_data.sql IS SOURCE OF TRUTH
-- ================================================================
-- The existing seed_data.sql already contains comprehensive seed data.
-- This script adds production-specific supplemental data only.

-- Additional subcontractors with realistic edge cases
INSERT INTO subcontractors (id, company_name, contact_first_name, contact_last_name, email, phone, address_line1, city, state, zip_code, ein, license_number, license_state, license_expiration, status, org_id, created_at, updated_at)
VALUES
    -- Multi-state contractor (edge case: works in multiple states)
    ('aaaaaaaa-1100-1100-1100-aaaaaaaa1111', 'CrossState Demolition LLC', 'Ricardo', 'Vasquez', 'ricardo@crossstatedemo.com', '555-1100', '900 W. 7th Street', 'Los Angeles', 'CA', '90017', '90-1122334', 'CA-CBL-99881', 'CA', '2027-04-20', 'active', '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW()),
    -- Sub with very long company name (255 boundary)
    ('aaaaaaaa-2200-2200-2200-aaaaaaaa2222', 'North American Industrial Commercial and Residential General Contracting and Construction Management Services Inc', 'Patricia', 'Kim', 'patricia@nairgcs.com', '555-2200', '1 Commerce Plaza', 'New York', 'NY', '10001', '01-2233445', 'NY-GC-77777', 'NY', '2028-05-15', 'active', '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW()),
    -- Sub with minimal/null fields (edge case)
    ('aaaaaaaa-3300-3300-3300-aaaaaaaa3333', 'Bare Bones Concrete', NULL, NULL, 'info@barebonesconcrete.com', NULL, NULL, 'Miami', 'FL', '33101', NULL, NULL, NULL, NULL, 'active', '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW()),
    -- Recently blacklisted (compliance scenario)
    ('aaaaaaaa-4400-4400-4400-aaaaaaaa4444', 'CornerCut Framing LLC', 'Brian', 'Smith', 'brian@cornercutframing.com', '555-4400', '440 Frame Ave', 'Phoenix', 'AZ', '85001', '44-5566778', 'AZ-ABC-99999', 'AZ', '2025-11-30', 'blacklisted', '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW());

-- Additional certifications with edge cases
INSERT INTO certifications (id, subcontractor_id, certification_type, certification_number, issuing_authority, issue_date, expiration_date, status, document_url, verification_status, verified_at, verified_by, notes, created_at, updated_at)
VALUES
    -- CrossState: valid OSHA 30
    ('cccccccc-1100-1100-1100-cccccccc1100', 'aaaaaaaa-1100-1100-1100-aaaaaaaa1111', 'OSHA 30-Hour Construction', 'OSHA-30-2025-00101', 'OSHA Training Institute', '2025-02-10', '2027-02-10', 'valid', 'https://docs.prequal.com/cert/osha00101.pdf', 'verified', '2025-02-15 10:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW()),
    -- CornerCut: expired cert linked to blacklisted sub
    ('cccccccc-4400-4400-4400-cccccccc4400', 'aaaaaaaa-4400-4400-4400-aaaaaaaa4444', 'OSHA 10-Hour Construction', 'OSHA-10-2024-55234', 'OSHA Training Institute', '2024-06-01', '2026-01-01', 'expired', 'https://docs.prequal.com/cert/osha55234.pdf', 'failed', '2025-12-01 09:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Expired before blacklisting', NOW(), NOW()),
    -- Bare Bones: pending verification (null fields)
    ('cccccccc-3300-3300-3300-cccccccc3300', 'aaaaaaaa-3300-3300-3300-aaaaaaaa3333', 'OSHA 10-Hour Construction', 'OSHA-10-2026-66111', 'OSHA Training Institute', '2026-01-15', '2028-01-15', 'valid', NULL, 'pending_verification', NULL, NULL, 'Document uploaded but OCR extraction pending', NOW(), NOW()),
    -- Advanced Integrated: additional cert expiring soon (compliance alert trigger)
    ('cccccccc-7700-7700-7700-cccccccc7700', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Fall Protection Competent Person', 'NCS-FP-2025-82828', 'National Center for Safety', '2025-04-01', NOW() + INTERVAL '15 days', 'valid', 'https://docs.prequal.com/cert/ncsfp82828.pdf', 'verified', '2025-04-05 08:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Expiring in 15 days — compliance alert expected', NOW(), NOW());

-- Additional violations for realistic portfolio
INSERT INTO violations (id, subcontractor_id, project_id, violation_type, violation_code, description, issued_by, issued_date, effective_date, resolution_date, status, penalty_amount, is_criminal, notes, created_at, updated_at)
VALUES
    -- CornerCut: serious violation (led to blacklisting)
    ('eeeeeeee-4400-4400-4400-eeeeeeee4400', 'aaaaaaaa-4400-4400-4400-aaaaaaaa4444', NULL, 'safety', '29 CFR 1926.501(b)(13)', 'Failure to provide fall protection on residential framing. Third repeat violation.', 'OSHA', '2025-08-15', '2025-09-01', '2025-09-30', 'resolved', 22000.00, FALSE, 'Resolved after company blacklisted from all projects', NOW(), NOW()),
    -- CrossState: open violation (multi-state complexity)
    ('eeeeeeee-1100-1100-1100-eeeeeeee1100', 'aaaaaaaa-1100-1100-1100-aaaaaaaa1111', NULL, 'licensing', 'CA-CSLB-2026-4821', 'Performing asbestos abatement work without required asbestos certification classification', 'California Contractors State License Board', '2026-03-10', '2026-04-01', NULL, 'open', 15000.00, FALSE, 'License revocation hearing scheduled. Client notified.', NOW(), NOW());

-- Additional project for portfolio diversity
INSERT INTO projects (id, project_name, project_number, description, client_name, client_contact, start_date, estimated_end_date, actual_end_date, address_line1, city, state, zip_code, status, budget, org_id, created_at, updated_at)
VALUES
    ('bbbbbbbb-7700-7700-7700-bbbbbbbb7700', 'Sunset Healthcare Center', 'PROJ-2026-099', 'Outpatient medical facility', 'Sunset Healthcare Group', 'facilities@sunsethealthcare.com', '2026-05-01', '2027-01-15', NULL, '1000 Sunset Blvd', 'Los Angeles', 'CA', '90028', 'active', 3200000.00, '00000000-0000-0000-0000-orgaaaaaaaa01', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO project_subcontractors (id, project_id, subcontractor_id, role, start_date, end_date, status, insurance_expiration, bonds_expiration, created_at, updated_at)
VALUES
    ('dddddddd-7701-7700-7700-dddddddd7701', 'bbbbbbbb-7700-7700-7700-bbbbbbbb7700', 'aaaaaaaa-1100-1100-1100-aaaaaaaa1111', 'Demolition', '2026-05-15', '2026-07-15', 'active', '2027-04-20', '2027-04-20', NOW(), NOW()),
    ('dddddddd-7702-7700-7700-dddddddd7702', 'bbbbbbbb-7700-7700-7700-bbbbbbbb7700', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'General Contractor', '2026-05-01', NULL, 'active', '2027-09-01', '2027-09-01', NOW(), NOW());

-- ================================================================
-- 3. STATE CREDENTIAL RECORD SEEDS (new data source)
-- ================================================================

INSERT INTO state_credential_records (id, state_code, credential_number, credential_type, issuing_state, holder_name, holder_address, holder_city, holder_state, holder_zip, issue_date, expiration_date, status, external_source_id, external_source_url, last_synced_at, subcontractor_id, created_at, updated_at)
VALUES
    ('scr-0001-0001-0001-scr000000001', 'TX', 'TX-ABC-12345', 'General Contractor', 'Texas', 'Summit Construction LLC', '1200 Industrial Blvd', 'Austin', 'TX', '78701', '2024-01-15', '2027-03-15', 'active', 'TX-EXT-112233', 'https://tdlr.texas.gov/verify/TX-ABC-12345', NOW(), 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', NOW(), NOW()),
    ('scr-0001-0001-0001-scr000000002', 'TX', 'TX-ABC-67890', 'Master Electrician', 'Texas', 'Riverbend Electrical Services', '450 Commerce Way', 'Houston', 'TX', '77002', '2023-05-01', '2026-06-01', 'expired', 'TX-EXT-445566', 'https://tdlr.texas.gov/verify/TX-ABC-67890', NOW(), 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', NOW(), NOW()),
    ('scr-0001-0001-0001-scr000000003', 'TX', 'TX-ABC-11111', 'Roofing Contractor', 'Texas', 'Pinnacle Roofing Corp', '890 Summit Drive', 'Dallas', 'TX', '75201', '2024-02-20', '2028-01-20', 'active', 'TX-EXT-778899', 'https://tdlr.texas.gov/verify/TX-ABC-11111', NOW(), 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', NOW(), NOW()),
    ('scr-0001-0001-0001-scr000000004', 'CA', 'CA-CBL-99881', 'Demolition Contractor', 'California', 'CrossState Demolition LLC', '900 W. 7th Street', 'Los Angeles', 'CA', '90017', '2025-01-10', '2027-04-20', 'active', 'CA-EXT-554433', 'https://cslb.ca.gov/verify/CA-CBL-99881', NOW(), 'aaaaaaaa-1100-1100-1100-aaaaaaaa1111', NOW(), NOW()),
    ('scr-0001-0001-0001-scr000000005', 'NY', 'NY-GC-77777', 'General Contractor', 'New York', 'North American Industrial Commercial and Residential General Contracting and Construction Management Services Inc', '1 Commerce Plaza', 'New York', 'NY', '10001', '2025-06-01', '2028-05-15', 'active', 'NY-EXT-112211', 'https://ny.gov/verify/NY-GC-77777', NOW(), 'aaaaaaaa-2200-2200-2200-aaaaaaaa2222', NOW(), NOW());

-- ================================================================
-- 4. SYNC HEALTH BASELINE
-- ================================================================

INSERT INTO sync_health (id, source_name, source_type, sync_run_log_id, health_status, last_successful_sync_at, last_failed_sync_at, last_failure_reason, sync_frequency, expected_next_sync_at, consecutive_failures, consecutive_successes, average_records_processed, average_processing_time_ms, created_at, updated_at)
VALUES
    ('11111111-5555-5555-5555-111111111555', 'production_init', 'manual', NULL, 'healthy', NOW(), NULL, NULL, 'once', NULL, 0, 1, 0, 0, NOW(), NOW());
