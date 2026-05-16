-- Database initialization script for staging environment
-- This script runs on container startup if the database is empty

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create application schema if not exists
CREATE SCHEMA IF NOT EXISTS app;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO postgres;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized for staging environment';
END $$;
