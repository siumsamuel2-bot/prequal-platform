-- Seed data for Prequal Subcontractor Compliance Platform
-- Designed for realistic compliance scenarios with edge cases
-- Author: Data Engineer
-- Run against a PostgreSQL 15+ database with uuid-ossp extension enabled

-- Clear existing seed data (use with caution in production)
-- Uncomment below lines only during development reset
-- DELETE FROM alert_notifications;
-- DELETE FROM alert_preferences;
-- DELETE FROM certification_renewals;
-- DELETE FROM certifications;
-- DELETE FROM project_subcontractors;
-- DELETE FROM violations;
-- DELETE FROM osha_inspections;
-- DELETE FROM osha_api_logs;
-- DELETE FROM osha_data_freshness;
-- DELETE FROM projects;
-- DELETE FROM subcontractors;
-- DELETE FROM sync_health;
-- DELETE FROM data_quality_results;
-- DELETE FROM data_quality_checks;
-- DELETE FROM match_rate_tracking;
-- DELETE FROM data_quality_alert_log;
-- DELETE FROM data_quality_alert_rules;
-- DELETE FROM pipeline_performance;
-- DELETE FROM api_latency_tracking;
-- DELETE FROM archived_records;
-- DELETE FROM data_retention_policies;

-- ================================================================
-- SUBCONTRACTORS: Mix of compliance profiles
-- ================================================================

INSERT INTO subcontractors (id, company_name, contact_first_name, contact_last_name, email, phone, address_line1, city, state, zip_code, ein, license_number, license_state, license_expiration, status, created_at, updated_at)
VALUES
    -- Active, fully compliant
    ('aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'Summit Construction LLC', 'Michael', 'Thompson', 'm.thompson@summit-construction.com', '555-0101', '1200 Industrial Blvd', 'Austin', 'TX', '78701', '12-3456789', 'TX-ABC-12345', 'TX', '2027-03-15', 'active', NOW(), NOW()),
    -- Active, expiring license soon
    ('aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'Riverbend Electrical Services', 'Ana', 'Gutierrez', 'ana@riverbend-electric.com', '555-0202', '450 Commerce Way', 'Houston', 'TX', '77002', '23-4567890', 'TX-ABC-67890', 'TX', '2026-06-30', 'active', NOW(), NOW()),
    -- Active, with OSHA violations history
    ('aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'Pinnacle Roofing Corp', 'David', 'Chen', 'david@pinnacleroofing.com', '555-0303', '890 Summit Drive', 'Dallas', 'TX', '75201', '34-5678901', 'TX-ABC-11111', 'TX', '2028-01-20', 'active', NOW(), NOW()),
    -- Suspended status
    ('aaaaaaaa-4444-4444-4444-aaaaaaaa4444', 'Metro Plumbing Services Inc', 'James', 'Wilson', 'j.wilson@metroplumbing.com', '555-0404', '320 Main Street', 'San Antonio', 'TX', '78205', '45-6789012', 'TX-ABC-22222', 'TX', '2026-12-01', 'suspended', NOW(), NOW()),
    -- Inactive, with expired license
    ('aaaaaaaa-5555-5555-5555-aaaaaaaa5555', 'Heritage Drywall & Finishing', 'Linda', 'Rodriguez', 'info@heritagedrywall.com', '555-0505', '55 Heritage Lane', 'Austin', 'TX', '78745', '56-7890123', 'TX-ABC-33333', 'TX', '2025-01-10', 'inactive', NOW(), NOW()),
    -- Blacklisted
    ('aaaaaaaa-6666-6666-6666-aaaaaaaa6666', 'QuickFix General Contractors', 'Robert', 'Davis', 'quickfixgc@gmail.com', '555-0606', '207 Quick Street', 'Houston', 'TX', '77004', '67-8901234', 'TX-ABC-44444', 'TX', '2025-08-15', 'blacklisted', NOW(), NOW()),
    -- Active with very long company name (edge case: 255 char boundary)
    ('aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Advanced Integrated Building Systems and Infrastructure Solutions LLC', 'Sarah', 'Johnson', 'sarah@advancedintegratedbuilding.com', '555-0707', '1000 Innovation Parkway', 'Fort Worth', 'TX', '76102', '78-9012345', 'TX-ABC-55555', 'TX', '2027-09-01', 'active', NOW(), NOW()),
    -- NULL optional fields
    ('aaaaaaaa-8888-8888-8888-aaaaaaaa8888', 'Texan Framing & Carpentry', NULL, NULL, 'contact@texanframing.com', NULL, NULL, 'El Paso', 'TX', '79901', '89-0123456', NULL, 'TX', NULL, 'active', NOW(), NOW()),
    -- Company with special characters in address (edge case: null address)
    ('aaaaaaaa-9999-9999-9999-aaaaaaaa9999', 'Apex HVAC Specialists', 'Christopher', 'Lee', 'chris@apexhvac.com', '555-0909', NULL, NULL, 'TX', NULL, NULL, 'TX-ABC-77777', 'TX', '2029-02-28', 'active', NOW(), NOW()),
    -- Very new subcontractor with minimal fields
    ('aaaaaaaa-1010-1010-1010-aaaaaaaa1010', 'Foundation First Concrete', 'Maria', 'Gonzalez', 'maria@foundationfirst.com', '555-1010', '1 Main Avenue', 'Corpus Christi', 'TX', '78401', NULL, NULL, NULL, NULL, 'active', NOW(), NOW());


-- ================================================================
-- PROJECTS: Various project statuses and dates
-- ================================================================

INSERT INTO projects (id, project_name, project_number, description, client_name, client_contact, start_date, estimated_end_date, actual_end_date, address_line1, city, state, zip_code, status, budget, created_at, updated_at)
VALUES
    -- Active project, mid-budget
    ('bbbbbbbb-1111-1111-1111-bbbbbbbb1111', 'Riverside Office Complex', 'PROJ-2026-001', '4-story commercial office building', 'Meridian Realty Partners', 'contact@meridianrealty.com', '2026-01-15', '2026-12-31', NULL, '500 Riverside Drive', 'Austin', 'TX', '78701', 'active', 4500000.00, NOW(), NOW()),
    -- Active project, high budget
    ('bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'Metro Transit Station', 'PROJ-2026-002', 'Light rail station with retail', 'Central Texas Transit Authority', 'contracts@ctta.gov', '2025-11-01', '2027-08-30', NULL, '800 Transit Blvd', 'Houston', 'TX', '77006', 'active', 12500000.00, NOW(), NOW()),
    -- Planning phase
    ('bbbbbbbb-3333-3333-3333-bbbbbbbb3333', 'Harbor View Residences', 'PROJ-2026-003', '12-unit luxury residential development', 'Harbor View Development LLC', 'pm@harborviewdev.com', '2026-06-01', '2027-09-15', NULL, '12 Harbor View Lane', 'Corpus Christi', 'TX', '78401', 'planning', 2800000.00, NOW(), NOW()),
    -- Completed project
    ('bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'Northside Elementary Addition', 'PROJ-2025-015', '2-story school addition with gymnasium', 'Oakwood ISD', 'facilities@oakwoodisd.edu', '2025-03-01', '2025-08-15', '2025-09-01', '300 Northside Drive', 'Fort Worth', 'TX', '76103', 'completed', 2100000.00, NOW(), NOW()),
    -- On hold
    ('bbbbbbbb-5555-5555-5555-bbbbbbbb5555', 'Downtown Parking Structure', 'PROJ-2026-010', '3-level parking garage, 500 spaces', 'City of Austin', 'contracts@austintx.gov', '2026-03-01', '2027-06-30', NULL, '1000 Commerce Street', 'Austin', 'TX', '78701', 'on_hold', 6500000.00, NOW(), NOW()),
    -- Cancelled project (archived, not deleted per company rules)
    ('bbbbbbbb-6666-6666-6666-bbbbbbbb6666', 'Westside Mall Renovation', 'PROJ-2025-008', 'Interior renovation of 2-story mall', 'Westgate Properties', 'facilities@westgateprop.com', '2025-01-01', '2025-10-31', '2025-06-15', '2500 Westside Mall Blvd', 'Houston', 'TX', '77027', 'cancelled', 3500000.00, NOW(), NOW());


-- ================================================================
-- CERTIFICATIONS: Various lifecycle stages
-- ================================================================

INSERT INTO certifications (id, subcontractor_id, certification_type, certification_number, issuing_authority, issue_date, expiration_date, status, document_url, verification_status, verified_at, verified_by, notes, created_at, updated_at)
VALUES
    -- Summit Construction: Valid OSHA 30, far from expiration
    ('cccccccc-1111-1111-1111-cccccccc1111', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'OSHA 30-Hour Construction', 'OSHA-30-2024-56789', 'OSHA Training Institute', '2024-04-10', '2026-04-10', 'valid', 'https://docs.prequal.com/cert/osha56789.pdf', 'verified', '2024-04-15 09:30:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Renewed early via online refresher', NOW(), NOW()),
    -- Summit Construction: Valid First Aid, recent
    ('cccccccc-1112-1111-1111-cccccccc1112', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'National Safety Council First Aid/CPR/AED', 'NSC-FA-2026-112233', 'National Safety Council', '2026-01-15', '2028-01-15', 'valid', 'https://docs.prequal.com/cert/nsc112233.pdf', 'verified', '2026-01-20 14:15:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW()),
    -- Riverbend: Valid but EXPIRING IN 30 DAYS (alert fire test)
    ('cccccccc-2222-2222-2222-cccccccc2222', 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'Electrical License - Master', 'TX-ELE-MA-78901', 'Texas Department of Licensing and Regulation', '2023-06-30', NOW() + INTERVAL '29 days', 'valid', 'https://docs.prequal.com/cert/txele78901.pdf', 'verified', '2023-07-05 10:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Renewal application submitted', NOW(), NOW()),
    -- Riverbend: OSHA 30, expired RECENTLY (grace period scenario)
    ('cccccccc-2223-2222-2222-cccccccc2223', 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'OSHA 30-Hour Construction', 'OSHA-30-2023-44556', 'OSHA Training Institute', '2023-05-20', NOW() - INTERVAL '5 days', 'expired', 'https://docs.prequal.com/cert/osha44556.pdf', 'verified', '2023-05-25 11:30:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Crew lead cert expired; renewal in progress', NOW(), NOW()),
    -- Pinnacle Roofing: OSHA 10, valid
    ('cccccccc-3333-3333-3333-cccccccc3333', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'OSHA 10-Hour Construction', 'OSHA-10-2025-33211', 'OSHA Training Institute', '2025-02-15', '2027-02-15', 'valid', 'https://docs.prequal.com/cert/osha33211.pdf', 'verified', '2025-02-20 08:45:00-05', NULL, NULL, NOW(), NOW()),
    -- Pinnacle Roofing: Roofing Safety, expired long ago
    ('cccccccc-3334-3333-3333-cccccccc3334', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'Certified Roofing Technician', 'NRCA-CRT-2023-99877', 'National Roofing Contractors Association', '2023-04-01', '2025-03-31', 'expired', 'https://docs.prequal.com/cert/nrca99877.pdf', 'verified', '2023-04-10 13:20:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Expired; renewal reminder sent 60/30/7 days', NOW(), NOW()),
    -- Metro Plumbing: Suspended state; cert still technically valid (edge case)
    ('cccccccc-4444-4444-4444-cccccccc4444', 'aaaaaaaa-4444-4444-4444-aaaaaaaa4444', 'Master Plumber License', 'TX-PLM-45678', 'Texas State Board of Plumbing Examiners', '2024-09-01', '2026-08-31', 'valid', 'https://docs.prequal.com/cert/txplm45678.pdf', 'verified', '2024-09-10 09:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Subcontractor suspended due to payment disputes; cert still valid', NOW(), NOW()),
    -- Heritage Drywall: Certification revoked (forgery detected)
    ('cccccccc-5555-5555-5555-cccccccc5555', 'aaaaaaaa-5555-5555-5555-aaaaaaaa5555', 'OSHA 10-Hour Construction', 'OSHA-10-2024-99001', 'OSHA Training Institute', '2024-07-01', '2026-07-01', 'revoked', 'https://docs.prequal.com/cert/osha99001.pdf', 'failed', '2025-03-20 10:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Revoked: scanned document was fraudulent. Verified against OSHA records.', NOW(), NOW()),
    -- QuickFix: Multiple certs, all expired and blacklisted sub
    ('cccccccc-6666-6666-6666-cccccccc6666', 'aaaaaaaa-6666-6666-6666-aaaaaaaa6666', 'OSHA 30-Hour Construction', 'OSHA-30-2022-10101', 'OSHA Training Institute', '2022-08-10', '2024-08-10', 'expired', 'https://docs.prequal.com/cert/osha10101.pdf', 'verified', '2022-08-15 11:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Blacklisted: repeated OSHA violations, unaddressed', NOW(), NOW()),
    -- Advanced Integrated: Valid, many certs (highly compliant sub)
    ('cccccccc-7771-7777-7777-cccccccc7771', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'OSHA 30-Hour Construction', 'OSHA-30-2025-81818', 'OSHA Training Institute', '2025-07-01', '2027-07-01', 'valid', 'https://docs.prequal.com/cert/osha81818.pdf', 'verified', '2025-07-05 09:30:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW()),
    ('cccccccc-7772-7777-7777-cccccccc7772', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Confined Space Entry', 'NSC-CSE-2025-91919', 'National Safety Council', '2025-03-10', '2026-03-10', 'valid', 'https://docs.prequal.com/cert/nsc91919.pdf', 'verified', '2025-03-15 10:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW()),
    ('cccccccc-7773-7777-7777-cccccccc7773', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'Scaffold Competent Person', 'SAIA-SCP-2025-02020', 'Scaffold Industry Association', '2025-05-01', '2026-05-01', 'valid', 'https://docs.prequal.com/cert/saia02020.pdf', 'verified', '2025-05-05 08:30:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW()),
    -- Texan Framing: Pending verification (document uploaded but not yet verified)
    ('cccccccc-8888-8888-8888-cccccccc8888', 'aaaaaaaa-8888-8888-8888-aaaaaaaa8888', 'OSHA 10-Hour Construction', 'OSHA-10-2026-12121', 'OSHA Training Institute', '2026-02-01', '2028-02-01', 'valid', 'https://docs.prequal.com/cert/osha12121.pdf', 'pending_verification', NULL, NULL, 'Document uploaded 2026-02-03, awaiting TDLR verification batch run', NOW(), NOW()),
    -- Apex HVAC: Null optional fields (edge case testing)
    ('cccccccc-9999-9999-9999-cccccccc9999', 'aaaaaaaa-9999-9999-9999-aaaaaaaa9999', 'EPA Section 608 Universal Technician', 'EPA-608-U-2025-34343', 'EPA', '2025-01-20', '2028-01-20', 'valid', NULL, 'unverified', NULL, NULL, 'Certificate image uploaded; OCR extraction pending. No issuing authority contact info on record.', NOW(), NOW()),
    -- Foundation First: Valid cert
    ('cccccccc-1011-1011-1011-cccccccc1011', 'aaaaaaaa-1010-1010-1010-aaaaaaaa1010', 'OSHA 10-Hour Construction', 'OSHA-10-2026-45454', 'OSHA Training Institute', '2026-03-15', '2028-03-15', 'valid', 'https://docs.prequal.com/cert/osha45454.pdf', 'verified', '2026-03-20 11:00:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, NOW(), NOW());


-- ================================================================
-- PROJECT_SUBCONTRACTORS: Assignment relationships
-- ================================================================

INSERT INTO project_subcontractors (id, project_id, subcontractor_id, role, start_date, end_date, status, insurance_expiration, bonds_expiration, created_at, updated_at)
VALUES
    -- Riverside Office: Summit (GC), Riverbend (Electrical), Heritage (Drywall before it went inactive)
    ('dddddddd-1111-1111-1111-dddddddd1111', 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'General Contractor', '2026-01-15', NULL, 'active', '2027-01-15', '2027-01-15', NOW(), NOW()),
    ('dddddddd-1112-1111-1111-dddddddd1112', 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111', 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'Electrical', '2026-03-01', NULL, 'active', '2026-09-30', '2027-02-28', NOW(), NOW()),
    ('dddddddd-1113-1111-1111-dddddddd1113', 'bbbbbbbb-1111-1111-1111-bbbbbbbb1111', 'aaaaaaaa-5555-5555-5555-aaaaaaaa5555', 'Drywall & Framing', '2026-01-15', '2026-03-10', 'completed', '2025-06-15', '2025-04-01', NOW(), NOW()),
    
    -- Metro Transit: Summit (Structural), Riverbend (Electrical), Pinnacle (Roofing), Advanced (MEP)
    ('dddddddd-2221-2222-2222-dddddddd2221', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'Structural Steel', '2025-11-01', NULL, 'active', '2026-11-01', '2026-11-01', NOW(), NOW()),
    ('dddddddd-2222-2222-2222-dddddddd2222', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'Electrical', '2026-01-15', NULL, 'active', '2026-09-30', '2027-02-28', NOW(), NOW()),
    ('dddddddd-2223-2222-2222-dddddddd2223', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'Roofing', '2026-05-01', NULL, 'active', '2026-12-31', NULL, NOW(), NOW()),
    ('dddddddd-2224-2222-2222-dddddddd2224', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'MEP Coordination', '2026-02-15', NULL, 'active', '2027-02-15', '2027-02-15', NOW(), NOW()),
    
    -- Harbor View: Foundation First (initial earthwork)
    ('dddddddd-3333-3333-3333-dddddddd3333', 'bbbbbbbb-3333-3333-3333-bbbbbbbb3333', 'aaaaaaaa-1010-1010-1010-aaaaaaaa1010', 'Foundation & Concrete', '2026-06-01', NULL, 'active', '2027-05-30', '2027-06-01', NOW(), NOW()),
    
    -- Northside School: Summit (GC), Pinnacle (Roofing), Heritage (Drywall - inactive sub on past job)
    ('dddddddd-4441-4444-4444-dddddddd4441', 'bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'aaaaaaaa-1111-1111-1111-aaaaaaaa1111', 'General Contractor', '2025-03-01', '2025-09-01', 'completed', '2026-03-01', '2026-03-01', NOW(), NOW()),
    ('dddddddd-4442-4444-4444-dddddddd4442', 'bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'Roofing', '2025-05-01', '2025-08-15', 'completed', '2026-01-31', '2025-12-05', NOW(), NOW()),
    ('dddddddd-4443-4444-4444-dddddddd4443', 'bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'aaaaaaaa-5555-5555-5555-aaaaaaaa5555', 'Drywall', '2025-04-15', '2025-09-15', 'completed', NULL, NULL, NOW(), NOW()),
    
    -- Downtown Parking: Metrog Plumbing (suspended sub on current job - risk scenario)
    ('dddddddd-5555-5555-5555-dddddddd5555', 'bbbbbbbb-5555-5555-5555-bbbbbbbb5555', 'aaaaaaaa-4444-4444-4444-aaaaaaaa4444', 'Plumbing', '2026-03-01', NULL, 'terminated', '2026-06-30', '2026-06-15', NOW(), NOW());


-- ================================================================
-- VIOLATIONS: OSHA and other compliance issues
-- ================================================================

INSERT INTO violations (id, subcontractor_id, project_id, violation_type, violation_code, description, issued_by, issued_date, effective_date, resolution_date, status, penalty_amount, is_criminal, notes, created_at, updated_at)
VALUES
    -- Pinnacle Roofing: Open OSHA violation on Metro Transit (active project)
    ('eeeeeeee-1111-1111-1111-eeeeeeee1111', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'safety', '29 CFR 1926.501(b)(10)', 'Failure to provide fall protection on roofing operations above 6 feet. Workers observed without harnesses.', 'OSHA', '2026-04-05', '2026-04-20', NULL, 'open', 7500.00, FALSE, 'Abatement deadline extended once. Must abate by 2026-04-20.', NOW(), NOW()),
    -- Pinnacle Roofing: Resolved OSHA violation (past project)
    ('eeeeeeee-1112-1111-1111-eeeeeeee1112', 'aaaaaaaa-3333-3333-3333-aaaaaaaa3333', 'bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'safety', '29 CFR 1926.503(b)(10)', 'Inadequate ladder access to elevated work surface. 3 ladders with insufficient extension.', 'OSHA', '2025-06-10', '2025-06-25', '2025-07-05', 'resolved', 3200.00, FALSE, 'Corrected: replaced with adequate extension ladders. Abatement verified 2025-07-05.', NOW(), NOW()),
    -- QuickFix: Serious violation (sub now blacklisted)
    ('eeeeeeee-6666-6666-6666-eeeeeeee6666', 'aaaaaaaa-6666-6666-6666-aaaaaaaa6666', NULL, 'safety', '29 CFR 1926.501(b)(1)', 'Repeated failure to install guardrails on elevated scaffolds. 4th violation in 18 months.', 'OSHA', '2025-09-15', '2025-09-30', '2025-10-15', 'resolved', 15000.00, FALSE, 'Subcontractor did not contest. Prequal recommended terminating all active assignments.', NOW(), NOW()),
    -- Metro Plumbing: Insurance lapse violation (insurance-related)
    ('eeeeeeee-4444-4444-4444-eeeeeeee4444', 'aaaaaaaa-4444-4444-4444-aaaaaaaa4444', NULL, 'insurance', 'CLAIM-2026-001', 'General liability insurance coverage lapsed during active project. Incident occurred during gap period.', 'Claims Department', '2026-02-20', '2026-03-01', NULL, 'under_review', 0.00, FALSE, 'Legal review pending. Subcontractor has since reinstated coverage but gap remains problematic.', NOW(), NOW()),
    -- Heritage Drywall: Resolved fine for licensing issue
    ('eeeeeeee-5555-5555-5555-eeeeeeee5555', 'aaaaaaaa-5555-5555-5555-aaaaaaaa5555', 'bbbbbbbb-4444-4444-4444-bbbbbbbb4444', 'licensing', 'TX-LIC-4021', 'Employee performed work outside scope of current license classification (performed plumbing work as drywall contractor)', 'Texas Department of Licensing and Regulation', '2025-03-10', '2025-03-20', '2025-03-25', 'resolved', 1250.00, FALSE, 'Paid in full. Subcontractor has since gone inactive.', NOW(), NOW()),
    -- Summit Construction: Clean record (no violations) -- used for testing empty LEFT JOIN
    -- Riverbend Electrical: Minor citation, resolved
    ('eeeeeeee-2222-2222-2222-eeeeeeee2222', 'aaaaaaaa-2222-2222-2222-aaaaaaaa2222', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'safety', '29 CFR 1926.405(a)(2)', 'Improper connection of flexible cords. 2 violations.', 'OSHA', '2026-02-20', '2026-03-05', '2026-03-02', 'resolved', 1800.00, FALSE, 'Corrected same day. Inspector verified correction on follow-up 2026-03-02.', NOW(), NOW()),
    -- Advanced Integrated: Open compliance issue (not OSHA - insurance gap), very high penalty
    ('eeeeeeee-7777-7777-7777-eeeeeeee7777', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', 'bbbbbbbb-2222-2222-2222-bbbbbbbb2222', 'insurance', 'INS-2026-033', 'Umbrella policy expired during project. Gap of 15 days detected during mid-project audit.', 'Prequal Internal Audit', '2026-04-01', '2026-04-15', NULL, 'open', 50000.00, FALSE, 'Subcontractor has submitted updated policy. Verification in progress.', NOW(), NOW());


-- ================================================================
-- OSHA INSPECTIONS: Metadata for detailed reports
-- ================================================================

INSERT INTO osha_inspections (inspection_number, activity_number, inspection_date, completion_date, type, scope, site_city, site_state, naics_code, reported_by, owner_type, safety_man_hour, health_man_hour, total_penalty, abatement_completed, created_at, updated_at)
VALUES
    ('3428094.015', '3428094', '2026-04-05', NULL, 'Complaint', 'Partial', 'Houston', 'TX', '236220', 'Anonymous Worker', 'Private', 4, 2, 7500.00, NULL, NOW(), NOW()),
    ('3398877.015', '3398877', '2025-06-10', '2025-06-10', 'Planned', 'Partial', 'Fort Worth', 'TX', '236220', 'OSHA Area Office', 'Private', 2, 1, 3200.00, '2025-07-05', NOW(), NOW()),
    ('3501122.045', '3501122', '2025-09-15', '2025-09-15', 'Complaint', 'Partial', 'Houston', 'TX', '236115', 'Union Representative', 'Private', 3, 2, 15000.00, '2025-10-15', NOW(), NOW());


-- ================================================================
-- ALERT_PREFERENCES: Notification rules per user
-- ================================================================

INSERT INTO alert_preferences (id, user_id, certification_types, advance_notice_days, alert_methods, is_active, created_at, updated_at)
VALUES
    ('ffffffff-1111-1111-1111-ffffffff1111', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '{OSHA 30-Hour Construction}', 30, '{email,in_app}', TRUE, NOW(), NOW()),
    ('ffffffff-2222-2222-2222-ffffffff2222', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', NULL, 60, '{email,sms}', TRUE, NOW(), NOW());


-- ================================================================
-- ALERT_NOTIFICATIONS: Pending and sent alerts
-- ================================================================

INSERT INTO alert_notifications (id, certification_id, alert_type, scheduled_for, sent_at, status, method, recipient, subject, body, created_at, updated_at)
VALUES
    -- Pending alert for Riverbend cert expiring in 29 days (Should trigger 30-day notice)
    ('ffffffff-3333-3333-3333-ffffffff3333', 'cccccccc-2222-2222-2222-cccccccc2222', 'expiration_approaching', NOW() + INTERVAL '1 day', NULL, 'pending', 'email', 'ana@riverbend-electric.com', 'Action Required: Electrical License Expiring in 29 Days', 'Your Master Electrical License expires soon. Please renew before expiration.', NOW(), NOW()),
    -- Sent alert for Pinnacle cert expiring (historical)
    ('ffffffff-4444-4444-4444-ffffffff4444', 'cccccccc-3334-3333-3333-cccccccc3334', 'expiration_approaching', '2025-03-01 09:00:00-05', '2025-03-01 09:05:22-05', 'sent', 'email', 'david@pinnacleroofing.com', 'Reminder: Certified Roofing Technician Expiring in 30 Days', 'Your NRCA certification expires on 2025-03-31.', NOW(), NOW()),
    -- Failed alert (network issue)
    ('ffffffff-5555-5555-5555-ffffffff5555', 'cccccccc-4444-4444-4444-cccccccc4444', 'expired', '2026-02-01 09:00:00-05', NULL, 'failed', 'email', 'j.wilson@metroplumbing.com', 'URGENT: Master Plumber License Expired', 'Your Master Plumber License expired on 2026-08-31.', NOW(), NOW());


-- ================================================================
-- CERTIFICATION_RENEWALS: Renewal workflow
-- ================================================================

INSERT INTO certification_renewals (id, certification_id, requested_by, requested_at, status, reviewed_by, reviewed_at, notes, new_expiration_date, created_at, updated_at)
VALUES
    -- Riverbend: Renewal for expiring cert, pending
    ('99999999-1111-1111-1111-999999991111', 'cccccccc-2222-2222-2222-cccccccc2222', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '2026-04-20 10:00:00-05', 'pending', NULL, NULL, 'Renewal application submitted by Ana; check status with TDLR', '2028-06-30', NOW(), NOW()),
    -- QuickFix cert renewal rejected (sub is blacklisted)
    ('99999999-6666-6666-6666-999999996666', 'cccccccc-6666-6666-6666-cccccccc6666', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '2024-07-01 09:00:00-05', 'rejected', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '2024-07-10 14:20:00-05', 'REJECTED: Subcontractor is blacklisted. Do NOT process renewal request. Company status review recommended.', NULL, NOW(), NOW());


-- ================================================================
-- SYNC RUN LOGS: Pipeline execution history
-- ================================================================

INSERT INTO sync_run_logs (id, job_name, job_type, status, triggered_by, started_at, completed_at, records_processed, records_inserted, records_updated, records_failed, records_matched, error_message, run_metadata, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0001-000000000001', 'osha_daily_sync', 'osha_sync', 'completed', 'schedule', '2026-06-08 01:00:00-05', '2026-06-08 01:05:22-05', 347, 12, 45, 0, 305, NULL, '{"batch_size": 50, "api_version": "v1"}', NOW(), NOW()),
    ('00000000-0000-0000-0002-000000000002', 'tx_credentials_sync', 'state_credential_sync', 'completed', 'schedule', '2026-06-08 02:00:00-05', '2026-06-08 02:03:15-05', 892, 23, 67, 2, 889, NULL, '{"batch_size": 100, "api_version": "v2"}', NOW(), NOW()),
    ('00000000-0000-0000-0003-000000000003', 'osha_daily_sync', 'osha_sync', 'failed', 'schedule', '2026-06-07 01:00:00-05', '2026-06-07 01:01:10-05', 0, 0, 0, 0, 0, 'Connection timeout to OSHA API', '{"retry_count": 3}', NOW(), NOW()),
    ('00000000-0000-0000-0004-000000000004', 'osha_daily_sync', 'osha_sync', 'completed', 'schedule', '2026-06-06 01:00:00-05', '2026-06-06 01:04:45-05', 298, 8, 33, 1, 270, NULL, '{"batch_size": 50}', NOW(), NOW()),
    ('00000000-0000-0000-0005-000000000005', 'ca_credentials_sync', 'state_credential_sync', 'partial', 'schedule', '2026-06-08 03:00:00-05', '2026-06-08 03:05:00-05', 1500, 50, 200, 5, 1450, 'Rate limit exceeded mid-run', '{"batch_size": 100}', NOW(), NOW());


-- ================================================================
-- SYNC HEALTH: Current sync health for each data source
-- ================================================================

INSERT INTO sync_health (id, source_name, source_type, sync_run_log_id, health_status, last_successful_sync_at, last_failed_sync_at, last_failure_reason, sync_frequency, expected_next_sync_at, consecutive_failures, consecutive_successes, average_records_processed, average_processing_time_ms, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111111', 'osha_api', 'api', '00000000-0000-0000-0001-000000000001', 'healthy', '2026-06-08 01:05:22-05', '2026-06-07 01:01:10-05', 'Connection timeout to OSHA API', 'daily', '2026-06-09 01:00:00-05', 0, 2, 322, 285000, NOW(), NOW()),
    ('11111111-2222-2222-2222-111111111222', 'tx_credentials', 'api', '00000000-0000-0000-0002-000000000002', 'healthy', '2026-06-08 02:03:15-05', NULL, NULL, 'daily', '2026-06-09 02:00:00-05', 0, 5, 890, 185000, NOW(), NOW()),
    ('11111111-3333-3333-3333-111111111333', 'ca_credentials', 'api', '00000000-0000-0000-0005-000000000005', 'degraded', '2026-06-07 03:00:00-05', '2026-06-08 03:05:00-05', 'Rate limit exceeded mid-run', 'daily', '2026-06-09 03:00:00-05', 1, 4, 1450, 300000, NOW(), NOW()),
    ('11111111-4444-4444-4444-111111111444', 'ftp_vendors', 'ftp', NULL, 'unknown', NULL, NULL, NULL, 'weekly', '2026-06-14 00:00:00-05', 0, 0, 0, 0, NOW(), NOW());


-- ================================================================
-- DATA QUALITY CHECKS: Active checks for production tables
-- ================================================================

INSERT INTO data_quality_checks (id, check_name, check_type, table_name, column_name, description, check_query, expected_result, alert_threshold, is_active, priority, created_at, updated_at)
VALUES
    ('dqc-0001-0001-0001-000000000001', 'subcontractors_email_unique', 'uniqueness', 'subcontractors', 'email', 'Email addresses must be unique across all subcontractors', 'SELECT COUNT(*) FROM (SELECT email FROM subcontractors GROUP BY email HAVING COUNT(*) > 1) t', '0', 1.0, TRUE, 'critical', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000002', 'subcontractors_email_not_null', 'completeness', 'subcontractors', 'email', 'Email must not be null or empty', 'SELECT COUNT(*) FROM subcontractors WHERE email IS NULL OR TRIM(email) = ''''', '0', 1.0, TRUE, 'critical', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000003', 'certifications_expiration_not_null', 'completeness', 'certifications', 'expiration_date', 'Certification expiration dates must not be null', 'SELECT COUNT(*) FROM certifications WHERE expiration_date IS NULL', '0', 1.0, TRUE, 'high', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000004', 'violations_description_not_null', 'completeness', 'violations', 'description', 'Violation descriptions must not be null or empty', 'SELECT COUNT(*) FROM violations WHERE description IS NULL OR TRIM(description) = ''''', '0', 1.0, TRUE, 'high', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000005', 'state_credential_records_freshness', 'freshness', 'state_credential_records', 'last_synced_at', 'State credentials should sync at least once per day', 'SELECT COUNT(*) FROM state_credential_records WHERE last_synced_at < NOW() - INTERVAL ''1 day''', '0', 0.95, TRUE, 'high', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000006', 'osha_api_logs_format', 'format', 'osha_api_logs', 'response_status', 'OSHA API response status should be valid integer', 'SELECT COUNT(*) FROM osha_api_logs WHERE response_status IS NOT NULL AND response_status::text !~ ''^[0-9]+$''', '0', 1.0, TRUE, 'medium', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000007', 'subcontractors_license_expiration_future', 'format', 'subcontractors', 'license_expiration', 'License expiration should normally be in the future or null', 'SELECT COUNT(*) FROM subcontractors WHERE license_expiration IS NOT NULL AND license_expiration < CURRENT_DATE - INTERVAL ''1 year''', '0', 0.90, TRUE, 'medium', NOW(), NOW()),
    ('dqc-0001-0001-0001-000000000008', 'project_subcontractors_referential', 'referential', 'project_subcontractors', 'project_id', 'All project_subcontractors must reference valid projects', 'SELECT COUNT(*) FROM project_subcontractors ps LEFT JOIN projects p ON ps.project_id = p.id WHERE p.id IS NULL', '0', 1.0, TRUE, 'critical', NOW(), NOW());


-- ================================================================
-- DATA QUALITY RESULTS: Recent results for active checks
-- ================================================================

INSERT INTO data_quality_results (id, check_id, run_at, status, actual_result, record_count, failed_record_count, details, execution_time_ms, created_at)
VALUES
    ('dqr-0001-0001-0001-000000000001', 'dqc-0001-0001-0001-000000000001', '2026-06-08 06:00:00-05', 'pass', '0', 10, 0, '{"note": "All emails unique"}', 12, NOW()),
    ('dqr-0001-0001-0001-000000000002', 'dqc-0001-0001-0001-000000000002', '2026-06-08 06:00:00-05', 'pass', '0', 10, 0, '{"note": "No null emails"}', 8, NOW()),
    ('dqr-0001-0001-0001-000000000003', 'dqc-0001-0001-0001-000000000003', '2026-06-08 06:00:00-05', 'pass', '0', 12, 0, '{"note": "All certifications have expiration dates"}', 15, NOW()),
    ('dqr-0001-0001-0001-000000000004', 'dqc-0001-0001-0001-000000000004', '2026-06-08 06:00:00-05', 'pass', '0', 7, 0, '{"note": "All violations have descriptions"}', 10, NOW()),
    ('dqr-0001-0001-0001-000000000005', 'dqc-0001-0001-0001-000000000005', '2026-06-08 06:00:00-05', 'pass', '0', 0, 0, '{"note": "No state credential records to check"}', 5, NOW()),
    ('dqr-0001-0001-0001-000000000006', 'dqc-0001-0001-0001-000000000006', '2026-06-08 06:00:00-05', 'pass', '0', 3, 0, '{"note": "All response statuses valid integers"}', 7, NOW()),
    ('dqr-0001-0001-0001-000000000007', 'dqc-0001-0001-0001-000000000007', '2026-06-08 06:00:00-05', 'warning', '1', 10, 1, '{"note": "Heritage Drywall expired over 1 year ago"}', 18, NOW()),
    ('dqr-0001-0001-0001-000000000008', 'dqc-0001-0001-0001-000000000008', '2026-06-08 06:00:00-05', 'pass', '0', 10, 0, '{"note": "All project references valid"}', 11, NOW());


-- ================================================================
-- MATCH RATE TRACKING: External data match rates over time
-- ================================================================

INSERT INTO match_rate_tracking (id, source_name, match_date, source_records_total, source_records_new, source_records_updated, matched_records, unmatched_records, fuzzy_matched_records, match_rate_percent, fuzzy_match_percent, match_confidence_avg, reprocess_needed, match_method, notes, created_at)
VALUES
    ('mrt-0001-0001-0001-000000000001', 'osha_api', '2026-06-08', 347, 12, 45, 305, 42, 5, 87.90, 11.90, 0.94, FALSE, 'exact', 'Strong match rate; 5 records flagged for manual review', NOW()),
    ('mrt-0001-0001-0001-000000000002', 'osha_api', '2026-06-07', 298, 8, 33, 270, 28, 3, 90.60, 10.71, 0.95, FALSE, 'exact', 'Consistent with historical trends', NOW()),
    ('mrt-0001-0001-0001-000000000003', 'tx_credentials', '2026-06-08', 892, 23, 67, 889, 3, 0, 99.66, 0.00, 0.99, FALSE, 'exact', 'Near-perfect match; 3 unmatched need manual review', NOW()),
    ('mrt-0001-0001-0001-000000000004', 'tx_credentials', '2026-06-07', 850, 15, 50, 845, 5, 1, 99.41, 20.00, 0.98, FALSE, 'exact', 'Stable match rate', NOW()),
    ('mrt-0001-0001-0001-000000000005', 'ca_credentials', '2026-06-08', 1500, 50, 200, 1450, 50, 10, 96.67, 20.00, 0.92, TRUE, 'exact', '50 unmatched due to rate limit mid-run; will reprocess', NOW()),
    ('mrt-0001-0001-0001-000000000006', 'ca_credentials', '2026-06-07', 1400, 30, 180, 1380, 20, 4, 98.57, 20.00, 0.93, FALSE, 'exact', 'Normal run', NOW());


-- ================================================================
-- DATA QUALITY ALERT RULES: Active alert rules
-- ================================================================

INSERT INTO data_quality_alert_rules (id, rule_name, rule_type, source_name, check_id, condition_operator, condition_value, severity, notification_channels, recipients, is_active, cooldown_minutes, last_triggered_at, created_at, updated_at)
VALUES
    ('dqa-0001-0001-0001-000000000001', 'OSHA Sync Failure', 'sync_fail', 'osha_api', NULL, '>', '0', 'critical', '{email, slack}', '{ops@prequal.com, #data-alerts}', TRUE, 15, NULL, NOW(), NOW()),
    ('dqa-0001-0001-0001-000000000002', 'TX Credential Match Rate Drop', 'match_rate_drop', 'tx_credentials', NULL, '<', '95', 'warning', '{email}', '{ops@prequal.com}', TRUE, 30, NULL, NOW(), NOW()),
    ('dqa-0001-0001-0001-000000000003', 'Data Quality Check Fail', 'quality_fail', NULL, 'dqc-0001-0001-0001-000000000001', '!=', 'pass', 'critical', '{email, slack}', '{ops@prequal.com, #data-alerts}', TRUE, 60, NULL, NOW(), NOW()),
    ('dqa-0001-0001-0001-000000000004', 'Stale OSHA Data', 'stale_data', 'osha_api', NULL, '>', '86400', 'warning', '{email}', '{ops@prequal.com}', TRUE, 60, '2026-06-07 02:00:00-05', NOW(), NOW()),
    ('dqa-0001-0001-0001-000000000005', 'Pipeline Performance Degradation', 'performance', 'osha_daily_sync', NULL, '>', '300000', 'warning', '{slack}', '{#data-alerts}', TRUE, 120, NULL, NOW(), NOW());


-- ================================================================
-- DATA QUALITY ALERT LOG: Recent triggered alerts
-- ================================================================

INSERT INTO data_quality_alert_log (id, rule_id, alert_status, triggered_at, acknowledged_at, acknowledged_by, resolved_at, severity, alert_message, context, created_at)
VALUES
    ('dal-0001-0001-0001-000000000001', 'dqa-0001-0001-0001-000000000004', 'acknowledged', '2026-06-07 02:15:00-05', '2026-06-07 02:30:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '2026-06-07 03:00:00-05', 'warning', 'OSHA data has not been updated in over 24 hours.', '{"last_sync": "2026-06-06 01:05:22", "hours_stale": 25}', NOW()),
    ('dal-0001-0001-0001-000000000002', 'dqa-0001-0001-0001-000000000001', 'resolved', '2026-06-07 01:05:00-05', '2026-06-07 01:10:00-05', 'aaaaaaaa-7777-7777-7777-aaaaaaaa7777', '2026-06-08 01:05:00-05', 'critical', 'OSHA sync failed with connection timeout.', '{"error": "Connection timeout to OSHA API", "retry_count": 3}', NOW()),
    ('dal-0001-0001-0001-000000000003', 'dqa-0001-0001-0001-000000000005', 'pending', '2026-06-08 06:10:00-05', NULL, NULL, NULL, 'warning', 'OSHA daily sync processing time exceeded 5 minutes.', '{"duration_ms": 285000, "threshold_ms": 300000}', NOW());


-- ================================================================
-- PIPELINE PERFORMANCE: Execution metrics
-- ================================================================

INSERT INTO pipeline_performance (id, pipeline_name, run_id, run_start_at, run_end_at, duration_ms, records_processed, records_inserted, records_updated, records_failed, cpu_time_ms, memory_peak_mb, cache_hits, cache_misses, cache_hit_rate_percent, api_calls_made, total_api_latency_ms, avg_api_latency_ms, status, error_message, created_at)
VALUES
    ('pp-0001-0001-0001-000000000001', 'osha_daily_sync', '00000000-0000-0000-0001-000000000001', '2026-06-08 01:00:00-05', '2026-06-08 01:05:22-05', 322000, 347, 12, 45, 0, 4000, 512, 280, 67, 80.70, 8, 24000, 3000.00, 'completed', NULL, NOW()),
    ('pp-0001-0001-0001-000000000002', 'tx_credentials_sync', '00000000-0000-0000-0002-000000000002', '2026-06-08 02:00:00-05', '2026-06-08 02:03:15-05', 195000, 892, 23, 67, 2, 2100, 384, 450, 12, 97.41, 10, 15000, 1500.00, 'completed', NULL, NOW()),
    ('pp-0001-0001-0001-000000000003', 'osha_daily_sync', NULL, '2026-06-07 01:00:00-05', '2026-06-07 01:01:10-05', 70000, 0, 0, 0, 0, 500, 128, 0, 0, 0.00, 3, 60000, 20000.00, 'failed', 'Connection timeout to OSHA API', NOW()),
    ('pp-0001-0001-0001-000000000004', 'ca_credentials_sync', '00000000-0000-0000-0005-000000000005', '2026-06-08 03:00:00-05', '2026-06-08 03:05:00-05', 300000, 1500, 50, 200, 5, 8000, 768, 120, 30, 80.00, 20, 120000, 6000.00, 'partial', 'Rate limit exceeded mid-run', NOW());


-- ================================================================
-- API LATENCY TRACKING: Per-endpoint timing
-- ================================================================

INSERT INTO api_latency_tracking (id, endpoint, method, request_at, latency_ms, status_code, response_size_bytes, is_cache_hit, pipeline_name, error_message, created_at)
VALUES
    ('lat-0001-0001-0001-000000000001', 'https://api.osha.gov/violations', 'GET', '2026-06-08 01:00:00-05', 2500, 200, 45000, TRUE, 'osha_daily_sync', NULL, NOW()),
    ('lat-0001-0001-0001-000000000002', 'https://api.osha.gov/violations', 'GET', '2026-06-08 01:00:01-05', 3500, 200, 52000, FALSE, 'osha_daily_sync', NULL, NOW()),
    ('lat-0001-0001-0001-000000000003', 'https://api.tdlr.texas.gov/credentials', 'GET', '2026-06-08 02:00:00-05', 1200, 200, 89000, TRUE, 'tx_credentials_sync', NULL, NOW()),
    ('lat-0001-0001-0001-000000000004', 'https://api.osha.gov/violations', 'GET', '2026-06-07 01:00:00-05', 60000, 504, 0, FALSE, 'osha_daily_sync', 'Connection timeout to OSHA API', NOW()),
    ('lat-0001-0001-0001-000000000005', 'https://api.ca.gov/credentials', 'GET', '2026-06-08 03:02:30-05', 8000, 429, 0, FALSE, 'ca_credentials_sync', 'Rate limit exceeded', NOW());


-- ================================================================
-- DATA RETENTION POLICIES
-- ================================================================

INSERT INTO data_quality_results (id, check_id, run_at, status, actual_result, record_count, failed_record_count, details, execution_time_ms, created_at)
VALUES
    ('dqr-0001-0001-0001-000000000009', 'dqc-0001-0001-0001-000000000001', '2026-06-07 06:00:00-05', 'pass', '0', 10, 0, '{"note": "All emails unique"}', 14, NOW()),
    ('dqr-0001-0001-0001-000000000010', 'dqc-0001-0001-0001-000000000002', '2026-06-07 06:00:00-05', 'pass', '0', 10, 0, '{"note": "No null emails"}', 9, NOW()),
    ('dqr-0001-0001-0001-000000000011', 'dqc-0001-0001-0001-000000000003', '2026-06-07 06:00:00-05', 'pass', '0', 12, 0, '{"note": "All certifications have expiration dates"}', 16, NOW()),
    ('dqr-0001-0001-0001-000000000012', 'dqc-0001-0001-0001-000000000004', '2026-06-07 06:00:00-05', 'pass', '0', 7, 0, '{"note": "All violations have descriptions"}', 12, NOW()),
    ('dqr-0001-0001-0001-000000000013', 'dqc-0001-0001-0001-000000000005', '2026-06-07 06:00:00-05', 'pass', '0', 0, 0, '{"note": "No state credential records to check"}', 6, NOW()),
    ('dqr-0001-0001-0001-000000000014', 'dqc-0001-0001-0001-000000000006', '2026-06-07 06:00:00-05', 'pass', '0', 3, 0, '{"note": "All response statuses valid integers"}', 8, NOW());


-- ================================================================
-- DATA RETENTION POLICIES
-- ================================================================

INSERT INTO data_retention_policies (id, policy_name, table_name, retention_days, archival_after_days, action, is_active, last_applied_at, records_archived, notes, created_at, updated_at)
VALUES
    ('drp-0001-0001-0001-000000000001', 'osha_api_logs_90d', 'osha_api_logs', 90, 30, 'archive', TRUE, '2026-06-01 00:00:00-05', 4200, 'Archive OSHA API logs after 90 days, archive bucket after 30', NOW(), NOW()),
    ('drp-0001-0001-0001-000000000002', 'sync_run_logs_180d', 'sync_run_logs', 180, 90, 'archive', TRUE, '2026-06-01 00:00:00-05', 12500, 'Archive sync run logs after 180 days', NOW(), NOW()),
    ('drp-0001-0001-0001-000000000003', 'api_latency_30d', 'api_latency_tracking', 30, 7, 'archive', TRUE, '2026-06-01 00:00:00-05', 89000, 'Archive API latency records after 30 days', NOW(), NOW()),
    ('drp-0001-0001-0001-000000000004', 'alert_log_365d', 'data_quality_alert_log', 365, 180, 'flag', TRUE, '2026-06-01 00:00:00-05', 0, 'Flag alert logs older than 365 days instead of deleting', NOW(), NOW());


-- ================================================================
-- ARCHIVED RECORDS: Sample archival entry (flagged, not deleted)
-- ================================================================

INSERT INTO archived_records (id, source_table, source_record_id, archived_at, archive_reason, retention_policy_id, original_data, restored_at, created_at)
VALUES
    ('arc-0001-0001-0001-000000000001', 'osha_api_logs', '00000000-0000-0000-0003-000000000003', '2026-06-08 00:00:00-05', 'Data retention policy: 90-day retention for OSHA API logs', 'drp-0001-0001-0001-000000000001', '{"request_type": "inspection", "request_parameters": {"date_range": "2026-03-01/2026-03-31"}, "response_status": 200, "records_processed": 150}', NULL, NOW());

