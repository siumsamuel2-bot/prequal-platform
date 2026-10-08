"""Initial schema for prequal compliance platform.

Migration ID: 001
Description: Loads core_tables, expiration_tracking, and osha_integration schemas.
Pre-requisites:
  - Extensions "uuid-ossp" and "postgis" must be installed (requires superuser).
    Run manually if not present:
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS "postgis";
"""

import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Raw SQL files embedded as triple-quoted strings
# ---------------------------------------------------------------------------
CORE_SQL = r"""
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
    ein VARCHAR(20),
    license_number VARCHAR(100),
    license_state VARCHAR(50),
    license_expiration DATE,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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
    status VARCHAR(50) DEFAULT 'planning',
    budget DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE certifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    certification_type VARCHAR(100) NOT NULL,
    certification_number VARCHAR(100),
    issuing_authority VARCHAR(255),
    issue_date DATE,
    expiration_date DATE NOT NULL,
    status VARCHAR(50) DEFAULT 'valid',
    document_url TEXT,
    verification_status VARCHAR(50) DEFAULT 'unverified',
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE project_subcontractors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    role VARCHAR(100),
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    insurance_expiration DATE,
    bonds_expiration DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, subcontractor_id)
);

CREATE TABLE violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subcontractor_id UUID NOT NULL REFERENCES subcontractors(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    violation_type VARCHAR(100) NOT NULL,
    violation_code VARCHAR(50),
    description TEXT NOT NULL,
    issued_by VARCHAR(255),
    issued_date DATE NOT NULL,
    effective_date DATE,
    resolution_date DATE,
    status VARCHAR(50) DEFAULT 'open',
    severity_level VARCHAR(50),
    penalty_amount DECIMAL(10,2),
    is_criminal BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_subcontractors_updated_at BEFORE UPDATE ON subcontractors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_certifications_updated_at BEFORE UPDATE ON certifications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_project_subcontractors_updated_at BEFORE UPDATE ON project_subcontractors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_violations_updated_at BEFORE UPDATE ON violations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

EXPIRATION_SQL = r"""
CREATE TABLE alert_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    certification_types TEXT[],
    advance_notice_days INTEGER DEFAULT 30,
    alert_methods TEXT[] DEFAULT '{email}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alert_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certification_id UUID NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'pending',
    method VARCHAR(50),
    recipient VARCHAR(255),
    subject VARCHAR(255),
    body TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE certification_renewals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certification_id UUID NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    reviewed_by UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    new_expiration_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_preferences_user_id ON alert_preferences(user_id);
CREATE INDEX idx_alert_notifications_certification_id ON alert_notifications(certification_id);
CREATE INDEX idx_alert_notifications_scheduled_for ON alert_notifications(scheduled_for);
CREATE INDEX idx_alert_notifications_status ON alert_notifications(status);
CREATE INDEX idx_certification_renewals_certification_id ON certification_renewals(certification_id);
CREATE INDEX idx_certification_renewals_status ON certification_renewals(status);

CREATE TRIGGER update_alert_preferences_updated_at BEFORE UPDATE ON alert_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_alert_notifications_updated_at BEFORE UPDATE ON alert_notifications FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_certification_renewals_updated_at BEFORE UPDATE ON certification_renewals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

OSHA_SQL = r"""
ALTER TABLE violations ADD COLUMN osha_violation_id VARCHAR(100);
ALTER TABLE violations ADD COLUMN citation_number VARCHAR(100);
ALTER TABLE violations ADD COLUMN violation_description TEXT;
ALTER TABLE violations ADD COLUMN standard_cited VARCHAR(100);
ALTER TABLE violations ADD COLUMN initial_penalty DECIMAL(10,2);
ALTER TABLE violations ADD COLUMN final_penalty DECIMAL(10,2);
ALTER TABLE violations ADD COLUMN abatement_date DATE;
ALTER TABLE violations ADD COLUMN date_corrected DATE;
ALTER TABLE violations ADD COLUMN contest_status VARCHAR(50);
ALTER TABLE violations ADD COLUMN inspection_number VARCHAR(100);
ALTER TABLE violations ADD COLUMN activity_number VARCHAR(100);
ALTER TABLE violations ADD COLUMN site_city VARCHAR(100);
ALTER TABLE violations ADD COLUMN site_state VARCHAR(50);
ALTER TABLE violations ADD COLUMN site_zip_code VARCHAR(20);
ALTER TABLE violations ADD COLUMN site_address TEXT;
ALTER TABLE violations ADD COLUMN naics_code VARCHAR(20);
ALTER TABLE violations ADD COLUMN inspection_type VARCHAR(100);
ALTER TABLE violations ADD COLUMN owner_type VARCHAR(50);
ALTER TABLE violations ADD COLUMN gravity_score DECIMAL(5,2);
ALTER TABLE violations ADD COLUMN probability_score DECIMAL(5,2);
ALTER TABLE violations ADD COLUMN risk_category VARCHAR(50);
ALTER TABLE violations ADD COLUMN is_osha_violation BOOLEAN DEFAULT TRUE;

CREATE INDEX idx_violations_osha_violation_id ON violations(osha_violation_id);
CREATE UNIQUE INDEX uq_violations_osha_violation_id ON violations(osha_violation_id) WHERE osha_violation_id IS NOT NULL;
CREATE INDEX idx_violations_inspection_number ON violations(inspection_number);
CREATE INDEX idx_violations_navigation ON violations(naics_code);
CREATE INDEX idx_violations_citation_number ON violations(citation_number);

CREATE TABLE osha_inspections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_number VARCHAR(100) UNIQUE NOT NULL,
    activity_number VARCHAR(100),
    inspection_date DATE NOT NULL,
    completion_date DATE,
    type VARCHAR(100) NOT NULL,
    scope VARCHAR(100),
    site_city VARCHAR(100),
    site_state VARCHAR(50),
    site_zip_code VARCHAR(20),
    site_address TEXT,
    naics_code VARCHAR(20),
    reported_by VARCHAR(255),
    owner_type VARCHAR(50),
    safety_man_hour INTEGER,
    health_man_hour INTEGER,
    total_penalty DECIMAL(10,2),
    abatement_completed DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE osha_api_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_type VARCHAR(50) NOT NULL,
    request_parameters JSONB NOT NULL,
    request_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    response_status INTEGER,
    response_body JSONB,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE osha_data_freshness (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    data_type VARCHAR(50) NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE,
    next_scheduled_update TIMESTAMP WITH TIME ZONE,
    update_frequency VARCHAR(50) DEFAULT 'daily',
    status VARCHAR(50) DEFAULT 'current',
    last_run_log_id UUID REFERENCES osha_api_logs(id),
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TRIGGER update_osha_inspections_updated_at BEFORE UPDATE ON osha_inspections FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_osha_data_freshness_updated_at BEFORE UPDATE ON osha_data_freshness FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

def _split_statements(sql: str):
    """Split raw SQL into individual statements, respecting $$ quoting."""
    statements = []  
    pos = 0
    length = len(sql)

    while pos < length:
        # skip whitespace and comments before next statement
        while pos < length and sql[pos].isspace():
            pos += 1
        if pos >= length:
            break
        if sql[pos:pos+2] == '--':
            while pos < length and sql[pos] != '\n':
                pos += 1
            continue

        # accumulate statement, tracking $$ state
        stmt_start = pos
        in_dollar = False
        in_quote = False  # single quotes
        in_c_style = False

        while pos < length:
            ch = sql[pos]
            next_ch = sql[pos + 1] if pos + 1 < length else ''
            
            if in_dollar:
                if ch == '$' and next_ch == '$':
                    in_dollar = False
                    pos += 2
                    continue
                pos += 1
                continue
            else:
                if ch == '$' and next_ch == '$':
                    in_dollar = True
                    pos += 2
                    continue
                if ch == "'" and not in_c_style:
                    in_quote = not in_quote
                    pos += 1
                    continue
                if ch == ';' and not in_quote:
                    pos += 1
                    break
                pos += 1
                continue

        stmt = sql[stmt_start:pos].strip()
        if stmt:
            statements.append(stmt)

    return [s for s in statements if s]

def _execute_sql(connection, raw_sql: str, context_label: str):
    """Execute a block of raw SQL on the given connection, parsing with _split_statements.

    Statements are rewritten to be idempotent (MID-645) so re-running
    ``alembic upgrade head`` against a database that already holds the base
    schema cannot hard-fail the whole suite with ``DuplicateTable``. Only
    existence guards are added; column and type semantics are untouched.
    """
    statements = _split_statements(raw_sql)
    for idx, statement in enumerate(statements):
        # skip empty/whitespace-only lines safely
        if not statement.strip():
            continue
        # PostgreSQL has no CREATE TRIGGER IF NOT EXISTS (before v14), so a
        # re-run is guarded with an explicit DROP first.
        trigger_match = _CREATE_TRIGGER_RE.match(statement)
        if trigger_match:
            trigger_name, table_name = trigger_match.group(1), trigger_match.group(2)
            op.execute(text(
                f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"
            ))
            op.execute(text(statement))
            continue
        op.execute(text(_make_idempotent(statement)))


# Rewrites ``CREATE <object>`` prefixes to their idempotent form. Order
# matters: the more specific prefixes (UNIQUE INDEX, MATERIALIZED VIEW) are
# attempted before their shorter cousins.
_DDL_IDEMPOTENT_PATTERNS = (
    (re.compile(r"(?is)^\s*CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)"),
     "CREATE TABLE IF NOT EXISTS "),
    (re.compile(r"(?is)^\s*CREATE\s+UNIQUE\s+INDEX\s+(?!IF\s+NOT\s+EXISTS)"),
     "CREATE UNIQUE INDEX IF NOT EXISTS "),
    (re.compile(r"(?is)^\s*CREATE\s+INDEX\s+(?!IF\s+NOT\s+EXISTS)"),
     "CREATE INDEX IF NOT EXISTS "),
    (re.compile(r"(?is)^\s*CREATE\s+MATERIALIZED\s+VIEW\s+(?!IF\s+NOT\s+EXISTS)"),
     "CREATE MATERIALIZED VIEW IF NOT EXISTS "),
    (re.compile(r"(?is)^\s*CREATE\s+VIEW\s+(?!IF\s+NOT\s+EXISTS|OR\s+REPLACE)"),
     "CREATE OR REPLACE VIEW "),
    (re.compile(r"(?is)^\s*CREATE\s+FUNCTION\s+(?!OR\s+REPLACE)"),
     "CREATE OR REPLACE FUNCTION "),
    (re.compile(r"(?is)^\s*ALTER\s+TABLE\s+(\S+)\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS)"),
     r"ALTER TABLE \1 ADD COLUMN IF NOT EXISTS "),
)

_CREATE_TRIGGER_RE = re.compile(
    r"(?is)^\s*CREATE\s+TRIGGER\s+(\w+)\s+.*?\bON\s+(\w+)"
)


def _make_idempotent(statement: str) -> str:
    """Return an existence-guarded form of a raw DDL statement."""
    for pattern, replacement in _DDL_IDEMPOTENT_PATTERNS:
        if pattern.match(statement):
            return pattern.sub(replacement, statement, count=1)
    return statement

def upgrade() -> None:
    """Create all tables, indexes, views, and triggers."""
    # NOTE: Extensions should be pre-installed as superuser:
    # CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    # CREATE EXTENSION IF NOT EXISTS "postgis";
    # We run them inside autocommit to avoid transaction issues.
    op.execute("COMMIT")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"postgis\"")

    # Core tables
    _execute_sql(op.get_bind(), CORE_SQL, "core")
    # Expiration tracking
    _execute_sql(op.get_bind(), EXPIRATION_SQL, "expiration")
    # OSHA integration
    _execute_sql(op.get_bind(), OSHA_SQL, "osha")


def downgrade() -> None:
    """Drop all created objects in reverse dependency order."""
    # Views
    op.execute("DROP VIEW IF EXISTS recent_violations")
    op.execute("DROP VIEW IF EXISTS expiring_certifications")
    op.execute("DROP VIEW IF EXISTS osha_violation_trends")
    op.execute("DROP VIEW IF EXISTS compliance_status_by_subcontractor")

    # Tables (reverse order of creation)
    op.execute("DROP TABLE IF EXISTS osha_data_freshness CASCADE")
    op.execute("DROP TABLE IF EXISTS osha_api_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS osha_inspections CASCADE")
    op.execute("DROP TABLE IF EXISTS certification_renewals CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_preferences CASCADE")
    op.execute("DROP TABLE IF EXISTS violations CASCADE")
    op.execute("DROP TABLE IF EXISTS project_subcontractors CASCADE")
    op.execute("DROP TABLE IF EXISTS certifications CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")
    op.execute("DROP TABLE IF EXISTS subcontractors CASCADE")

    # Function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Extensions
    op.execute("DROP EXTENSION IF EXISTS \"postgis\"")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
