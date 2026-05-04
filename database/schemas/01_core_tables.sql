-- Core tables for Prequal Subcontractor Compliance Platform
-- Database schema designed for tracking subcontractor certifications, projects, and compliance

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Subcontractors table
CREATE TABLE subcontractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name VARCHAR(255) NOT NULL,
    contact_first_name VARCHAR(100),
    contact_last_name VARCHAR(100),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'USA',
    ein VARCHAR(20), -- Employer Identification Number
    license_number VARCHAR(100), -- State contractor license
    license_state VARCHAR(50),
    license_expiration DATE,
    status VARCHAR(50) DEFAULT 'active', -- active, inactive, suspended, blacklisted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_name VARCHAR(255) NOT NULL,
    project_number VARCHAR(100) UNIQUE,
    description TEXT,
    client_name VARCHAR(255),
    client_contact VARCHAR(255),
    start_date DATE,
    estimated_end_date DATE,
    actual_end_date DATE,
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),
    country VARCHAR(100) DEFAULT 'USA',
    status VARCHAR(50) DEFAULT 'planning', -- planning, active, on_hold, completed, cancelled
    budget DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Certifications table
CREATE TABLE certifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    certification_type VARCHAR(100) NOT NULL, -- e.g., OSHA 10, OSHA 30, First Aid, etc.
    certification_number VARCHAR(100),
    issuing_authority VARCHAR(255), -- Who issued the certification
    issue_date DATE,
    expiration_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'valid', -- valid, expired, revoked, pending_verification
    document_url TEXT, -- URL to scanned/certified document
    verification_status VARCHAR(50) DEFAULT 'unverified', -- unverified, verified, failed
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID, -- Reference to users table (to be created)
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Project-Subcontractor assignments (many-to-many)
CREATE TABLE project_subcontractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    role VARCHAR(100), -- e.g., general contractor, electrician, plumber, etc.
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'active', -- active, completed, terminated
    insurance_expiration DATE,
    bonds_expiration DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, subcontractor_id) -- Prevent duplicate assignments
);

-- Violations table (for OSHA violations or other compliance issues)
CREATE TABLE violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    violation_type VARCHAR(100) NOT NULL, -- e.g., safety, licensing, insurance, etc.
    violation_code VARCHAR(50), -- Specific code if applicable (OSHA code, etc.)
    description TEXT NOT NULL,
    issued_by VARCHAR(255), -- Agency that issued the violation (OSHA, state, etc.)
    issued_date DATE NOT NULL,
    effective_date DATE,
    resolution_date DATE,
    status VARCHAR(50) DEFAULT 'open', -- open, under_review, resolved, appealed
    penalty_amount DECIMAL(10,2),
    is_criminal BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_subcontractors_status ON subcontractors(status);
CREATE INDEX idx_subcontractors_license_expiration ON subcontractors(license_expiration);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_certifications_subcontractor_id ON certifications(subcontractor_id);
CREATE INDEX idx_certifications_expiration_date ON certifications(expiration_date);
CREATE INDEX idx_certifications_status ON certifications(status);
CREATE INDEX idx_project_subcontractors_project_id ON project_subcontractors(project_id);
CREATE INDEX idx_project_subcontractors_subcontractor_id ON project_subcontractors(subcontractor_id);
CREATE INDEX idx_violations_subcontractor_id ON violations(subcontractor_id);
CREATE INDEX idx_violations_project_id ON violations(project_id);
CREATE INDEX idx_violations_issued_date ON violations(issued_date);
CREATE INDEX idx_violations_status ON violations(status);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_subcontractors_updated_at 
    BEFORE UPDATE ON subcontractors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at 
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_certifications_updated_at 
    BEFORE UPDATE ON certifications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_project_subcontractors_updated_at 
    BEFORE UPDATE ON project_subcontractors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_violations_updated_at 
    BEFORE UPDATE ON violations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();