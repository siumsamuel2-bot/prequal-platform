-- Expiration tracking system for certifications
-- This schema extends the core tables to support automated expiration tracking

-- Alert preferences table
CREATE TABLE alert_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL, -- Will reference users table when created
    certification_types TEXT[], -- Types of certifications to monitor (null = all)
    advance_notice_days INTEGER DEFAULT 30, -- How many days before expiration to alert
    alert_methods TEXT[] DEFAULT '{email}', -- email, sms, in_app
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Alert notifications table
CREATE TABLE alert_notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certification_id UUID NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL, -- expiration_approaching, expired, etc.
    scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL, -- When the alert should be sent
    sent_at TIMESTAMP WITH TIME ZONE, -- When the alert was actually sent
    status VARCHAR(50) DEFAULT 'pending', -- pending, sent, failed, cancelled
    method VARCHAR(50), -- email, sms, in_app
    recipient VARCHAR(255), -- Email address or phone number
    subject VARCHAR(255),
    body TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Certification renewal requests
CREATE TABLE certification_renewals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certification_id UUID NOT NULL REFERENCES certifications(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL, -- User requesting renewal
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected, completed
    reviewed_by UUID, -- User who reviewed the request
    reviewed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    new_expiration_date DATE, -- If approved, what the new expiration should be
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for expiration tracking
CREATE INDEX idx_alert_preferences_user_id ON alert_preferences(user_id);
CREATE INDEX idx_alert_notifications_certification_id ON alert_notifications(certification_id);
CREATE INDEX idx_alert_notifications_scheduled_for ON alert_notifications(scheduled_for);
CREATE INDEX idx_alert_notifications_status ON alert_notifications(status);
CREATE INDEX idx_certification_renewals_certification_id ON certification_renewals(certification_id);
CREATE INDEX idx_certification_renewals_status ON certification_renewals(status);

-- Trigger to update updated_at timestamp
CREATE TRIGGER update_alert_preferences_updated_at 
    BEFORE UPDATE ON alert_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alert_notifications_updated_at 
    BEFORE UPDATE ON alert_notifications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_certification_renewals_updated_at 
    BEFORE UPDATE ON certification_renewals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();