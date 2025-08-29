-- SRPK Pro Crypto Payment Schema
-- PostgreSQL database schema for cryptocurrency payments and licenses

-- Create database (run as superuser)
-- CREATE DATABASE srpk_licenses;

-- Crypto payments table
CREATE TABLE IF NOT EXISTS crypto_payments (
    id SERIAL PRIMARY KEY,
    tx_hash VARCHAR(66) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    token VARCHAR(10) NOT NULL, -- BNB, USDT, ETH
    amount DECIMAL(20, 8) NOT NULL,
    usd_value DECIMAL(10, 2),
    license_key VARCHAR(255) NOT NULL,
    block_number BIGINT,
    from_address VARCHAR(42),
    status VARCHAR(20) DEFAULT 'confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Licenses table (updated for crypto)
CREATE TABLE IF NOT EXISTS licenses (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    product_type VARCHAR(255) NOT NULL,
    tx_hash VARCHAR(66) REFERENCES crypto_payments(tx_hash),
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_time TIMESTAMP NOT NULL,
    last_validated TIMESTAMP,
    validation_count INTEGER DEFAULT 0
);

-- Token prices history
CREATE TABLE IF NOT EXISTS token_prices (
    id SERIAL PRIMARY KEY,
    token VARCHAR(10) NOT NULL,
    price_usd DECIMAL(20, 8) NOT NULL,
    source VARCHAR(50), -- coingecko, binance, etc
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Webhook registrations
CREATE TABLE IF NOT EXISTS webhook_registrations (
    id SERIAL PRIMARY KEY,
    webhook_id VARCHAR(32) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    events TEXT[], -- Array of event types
    secret VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Webhook delivery logs
CREATE TABLE IF NOT EXISTS webhook_logs (
    id SERIAL PRIMARY KEY,
    webhook_id VARCHAR(32) REFERENCES webhook_registrations(webhook_id),
    event_type VARCHAR(50),
    payload JSONB,
    response_status INTEGER,
    response_body TEXT,
    success BOOLEAN,
    details TEXT,
    attempts INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(255) REFERENCES licenses(license_key),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Blockchain sync status
CREATE TABLE IF NOT EXISTS blockchain_sync (
    id SERIAL PRIMARY KEY,
    network VARCHAR(20) NOT NULL,
    last_block_number BIGINT NOT NULL,
    last_sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active'
);

-- Failed transactions (for support)
CREATE TABLE IF NOT EXISTS failed_transactions (
    id SERIAL PRIMARY KEY,
    tx_hash VARCHAR(66),
    email VARCHAR(255),
    reason TEXT,
    raw_data JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_crypto_payments_email ON crypto_payments(email);
CREATE INDEX idx_crypto_payments_token ON crypto_payments(token);
CREATE INDEX idx_crypto_payments_created ON crypto_payments(created_at);
CREATE INDEX idx_licenses_email ON licenses(email);
CREATE INDEX idx_licenses_expiry ON licenses(expiry_time);
CREATE INDEX idx_licenses_active ON licenses(is_active);
CREATE INDEX idx_token_prices_token_created ON token_prices(token, created_at DESC);
CREATE INDEX idx_webhook_logs_webhook_id ON webhook_logs(webhook_id);
CREATE INDEX idx_webhook_logs_created ON webhook_logs(created_at);
CREATE INDEX idx_api_usage_license ON api_usage(license_key);
CREATE INDEX idx_api_usage_created ON api_usage(created_at);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
CREATE TRIGGER update_crypto_payments_updated_at BEFORE UPDATE ON crypto_payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_webhook_registrations_updated_at BEFORE UPDATE ON webhook_registrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views for reporting
CREATE VIEW active_licenses AS
SELECT 
    l.license_key,
    l.email,
    l.product_type,
    l.created_at,
    l.expiry_time,
    cp.token,
    cp.amount,
    cp.tx_hash
FROM licenses l
JOIN crypto_payments cp ON l.tx_hash = cp.tx_hash
WHERE l.is_active = TRUE AND l.expiry_time > NOW();

CREATE VIEW payment_stats AS
SELECT 
    DATE_TRUNC('day', created_at) as day,
    token,
    COUNT(*) as payment_count,
    SUM(amount) as total_amount,
    SUM(usd_value) as total_usd,
    AVG(usd_value) as avg_usd
FROM crypto_payments
WHERE status = 'confirmed'
GROUP BY DATE_TRUNC('day', created_at), token
ORDER BY day DESC;

CREATE VIEW webhook_performance AS
SELECT 
    w.webhook_id,
    w.url,
    COUNT(wl.id) as total_calls,
    SUM(CASE WHEN wl.success THEN 1 ELSE 0 END) as successful_calls,
    AVG(CASE WHEN wl.response_status BETWEEN 200 AND 299 THEN wl.response_status END) as avg_response_time,
    MAX(wl.created_at) as last_called
FROM webhook_registrations w
LEFT JOIN webhook_logs wl ON w.webhook_id = wl.webhook_id
WHERE w.is_active = TRUE
GROUP BY w.webhook_id, w.url;

-- Function to calculate license statistics
CREATE OR REPLACE FUNCTION get_license_stats(p_email VARCHAR)
RETURNS TABLE (
    total_licenses BIGINT,
    active_licenses BIGINT,
    total_spent_usd DECIMAL,
    preferred_token VARCHAR,
    last_purchase TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT l.id)::BIGINT as total_licenses,
        COUNT(DISTINCT CASE WHEN l.is_active AND l.expiry_time > NOW() THEN l.id END)::BIGINT as active_licenses,
        COALESCE(SUM(cp.usd_value), 0) as total_spent_usd,
        MODE() WITHIN GROUP (ORDER BY cp.token) as preferred_token,
        MAX(cp.created_at) as last_purchase
    FROM licenses l
    JOIN crypto_payments cp ON l.tx_hash = cp.tx_hash
    WHERE l.email = p_email;
END;
$$ LANGUAGE plpgsql;

-- Function to validate license
CREATE OR REPLACE FUNCTION validate_license(p_license_key VARCHAR)
RETURNS TABLE (
    is_valid BOOLEAN,
    email VARCHAR,
    product_type VARCHAR,
    expires_at TIMESTAMP,
    days_remaining INTEGER
) AS $$
BEGIN
    -- Update validation count
    UPDATE licenses 
    SET last_validated = NOW(), 
        validation_count = validation_count + 1
    WHERE license_key = p_license_key;
    
    -- Return license info
    RETURN QUERY
    SELECT 
        (l.is_active AND l.expiry_time > NOW()) as is_valid,
        l.email,
        l.product_type,
        l.expiry_time as expires_at,
        EXTRACT(DAY FROM l.expiry_time - NOW())::INTEGER as days_remaining
    FROM licenses l
    WHERE l.license_key = p_license_key;
END;
$$ LANGUAGE plpgsql;

-- Permissions (adjust based on your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO srpk_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO srpk_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO srpk_user;