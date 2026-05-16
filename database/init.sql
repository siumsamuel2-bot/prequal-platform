-- Prequal Platform Database Initialization Script
-- This script initializes the database for the staging environment
-- Run automatically by Docker Compose on first startup

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create application schema if not exists
CREATE SCHEMA IF NOT EXISTS app;

-- Grant permissions (adjust as needed for your setup)
-- This is for staging, so we're permissive
GRANT ALL PRIVILEGES ON SCHEMA app TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA public TO postgres;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Prequal Platform database initialized successfully';
    RAISE NOTICE 'Extensions: uuid-ossp enabled';
    RAISE NOTICE 'Schema: app schema created';
END $$;
