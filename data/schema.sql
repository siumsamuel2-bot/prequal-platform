-- schema.sql

-- Example starter schema
CREATE TABLE IF NOT EXISTS osha_violations (
    id SERIAL PRIMARY KEY,
    establishment_name TEXT,
    inspection_date DATE,
    violation_type TEXT,
    penalty NUMERIC
);