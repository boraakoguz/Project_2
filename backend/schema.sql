-- Marketing Automation Module Database Schema
-- Event-Driven Architecture with Customer Segmentation, Campaign Management, and Analytics

-- ============================================================================
-- CORE ENTITIES
-- ============================================================================

-- Customer base table (minimal - assumes integration with main CRM Customer database)
CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP,
    marketing_consent BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMP
);

-- Customer demographic and behavioral data for segmentation
CREATE TABLE IF NOT EXISTS customer_profiles (
    profile_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    purchase_history_value DECIMAL(12,2) DEFAULT 0.00,
    total_purchases INTEGER DEFAULT 0,
    last_purchase_date TIMESTAMP,
    avg_order_value DECIMAL(10,2),
    engagement_score INTEGER CHECK (engagement_score >= 0 AND engagement_score <= 100),
    location VARCHAR(100),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id)
);

-- Product/Interest tracking for personalization
CREATE TABLE IF NOT EXISTS customer_interests (
    interest_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    product_category VARCHAR(100),
    interest_level VARCHAR(20) CHECK (interest_level IN ('high', 'medium', 'low')),
    last_interaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    interaction_count INTEGER DEFAULT 1
);

-- ============================================================================
-- SEGMENTATION MANAGER
-- ============================================================================

-- Segment definitions (e.g., "High Value", "At Risk", "New Leads")
CREATE TABLE IF NOT EXISTS segments (
    segment_id SERIAL PRIMARY KEY,
    segment_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    criteria_json JSONB, -- Stores complex segmentation rules
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: customers belong to multiple segments
CREATE TABLE IF NOT EXISTS customer_segments (
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    segment_id INTEGER REFERENCES segments(segment_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_assigned BOOLEAN DEFAULT TRUE, -- TRUE if assigned by behavior trigger
    PRIMARY KEY (customer_id, segment_id)
);

-- Behavior triggers that automatically move customers between segments
CREATE TABLE IF NOT EXISTS segment_triggers (
    trigger_id SERIAL PRIMARY KEY,
    segment_id INTEGER REFERENCES segments(segment_id) ON DELETE CASCADE,
    trigger_type VARCHAR(50) NOT NULL, -- e.g., 'PURCHASE', 'PAGE_VIEW', 'EMAIL_OPEN'
    condition_json JSONB, -- Trigger conditions
    action VARCHAR(20) CHECK (action IN ('ADD', 'REMOVE')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CAMPAIGN MANAGER
-- ============================================================================

-- Campaign definitions
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id SERIAL PRIMARY KEY,
    campaign_name VARCHAR(200) NOT NULL,
    description TEXT,
    campaign_type VARCHAR(50) CHECK (campaign_type IN ('email', 'social', 'sms', 'ad')),
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'active', 'paused', 'completed')),
    target_segment_id INTEGER REFERENCES segments(segment_id),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    budget DECIMAL(12,2),
    created_by VARCHAR(100), -- Admin user ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Campaign content templates
CREATE TABLE IF NOT EXISTS campaign_templates (
    template_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL, -- 'email', 'social_media', 'sms'
    subject_line VARCHAR(200),
    body_content TEXT,
    personalization_fields JSONB, -- Dynamic fields like {{first_name}}, {{product}}
    external_asset_url VARCHAR(500), -- Link to Cloud Storage for images/videos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Workflow automation rules for campaigns
CREATE TABLE IF NOT EXISTS campaign_workflows (
    workflow_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    trigger_event VARCHAR(100), -- e.g., 'EMAIL_OPEN', 'LINK_CLICK', 'TIME_DELAY'
    delay_hours INTEGER DEFAULT 0,
    action_type VARCHAR(50), -- 'SEND_EMAIL', 'POST_SOCIAL', 'SEND_SMS'
    action_config_json JSONB, -- Configuration for the action
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(campaign_id, step_number)
);

-- Individual campaign executions sent to customers
CREATE TABLE IF NOT EXISTS campaign_executions (
    execution_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    channel VARCHAR(50),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_status VARCHAR(20) DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'sent', 'delivered', 'failed', 'bounced')),
    external_message_id VARCHAR(200), -- ID from email/SMS provider
    personalized_content TEXT, -- Rendered content with personalization
    error_message TEXT
);

-- ============================================================================
-- MARKETING ANALYTICS
-- ============================================================================

-- Campaign performance metrics aggregated by campaign
CREATE TABLE IF NOT EXISTS campaign_metrics (
    metric_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    metric_date DATE DEFAULT CURRENT_DATE,
    emails_sent INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    links_clicked INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0, -- Leads converted to sales
    revenue_generated DECIMAL(12,2) DEFAULT 0.00,
    cost_incurred DECIMAL(12,2) DEFAULT 0.00,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, metric_date)
);

-- Customer interaction tracking for analytics
CREATE TABLE IF NOT EXISTS customer_interactions (
    interaction_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL, -- 'email_open', 'click', 'conversion', 'unsubscribe'
    interaction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json JSONB, -- Additional context (e.g., clicked link URL)
    conversion_value DECIMAL(10,2) -- Revenue if interaction resulted in purchase
);

-- ROI tracking per campaign
CREATE TABLE IF NOT EXISTS campaign_roi (
    roi_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    total_cost DECIMAL(12,2) NOT NULL,
    total_revenue DECIMAL(12,2) NOT NULL,
    roi_percentage DECIMAL(8,2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_cost > 0 THEN ((total_revenue - total_cost) / total_cost * 100)
            ELSE 0 
        END
    ) STORED,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id)
);

-- ============================================================================
-- EVENT-DRIVEN INTEGRATION (Pub/Sub)
-- ============================================================================

-- Event log for publish-subscribe integration
CREATE TABLE IF NOT EXISTS marketing_events (
    event_id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL, -- e.g., 'CAMPAIGN_STARTED', 'EMAIL_SENT', 'CUSTOMER_PURCHASE'
    event_source VARCHAR(100), -- Module that published the event
    payload_json JSONB, -- Event data
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE SET NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE SET NULL,
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- External service integration tracking
CREATE TABLE IF NOT EXISTS external_service_logs (
    log_id SERIAL PRIMARY KEY,
    service_type VARCHAR(50) NOT NULL, -- 'email_provider', 'social_media_api', 'sms_gateway'
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE SET NULL,
    request_payload JSONB,
    response_payload JSONB,
    status_code INTEGER,
    success BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX idx_customer_email ON customers(email);
CREATE INDEX idx_customer_consent ON customers(marketing_consent);
CREATE INDEX idx_customer_segments_customer ON customer_segments(customer_id);
CREATE INDEX idx_customer_segments_segment ON customer_segments(segment_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_segment ON campaigns(target_segment_id);
CREATE INDEX idx_campaign_executions_campaign ON campaign_executions(campaign_id);
CREATE INDEX idx_campaign_executions_customer ON campaign_executions(customer_id);
CREATE INDEX idx_interactions_customer ON customer_interactions(customer_id);
CREATE INDEX idx_interactions_campaign ON customer_interactions(campaign_id);
CREATE INDEX idx_interactions_type ON customer_interactions(interaction_type);
CREATE INDEX idx_events_type ON marketing_events(event_type);
CREATE INDEX idx_events_processed ON marketing_events(processed);
CREATE INDEX idx_events_timestamp ON marketing_events(published_at);

-- ============================================================================
-- SEED DATA (Example Data for All Tables)
-- ============================================================================

-- Insert example customers
INSERT INTO customers (email, first_name, last_name, phone, marketing_consent, consent_date, last_activity_at) VALUES
('john.doe@example.com', 'John', 'Doe', '+1-555-0101', TRUE, CURRENT_TIMESTAMP - INTERVAL '90 days', CURRENT_TIMESTAMP - INTERVAL '5 days'),
('jane.smith@example.com', 'Jane', 'Smith', '+1-555-0102', TRUE, CURRENT_TIMESTAMP - INTERVAL '60 days', CURRENT_TIMESTAMP - INTERVAL '2 days'),
('bob.johnson@example.com', 'Bob', 'Johnson', '+1-555-0103', TRUE, CURRENT_TIMESTAMP - INTERVAL '120 days', CURRENT_TIMESTAMP - INTERVAL '95 days'),
('alice.williams@example.com', 'Alice', 'Williams', '+1-555-0104', TRUE, CURRENT_TIMESTAMP - INTERVAL '30 days', CURRENT_TIMESTAMP - INTERVAL '1 day'),
('charlie.brown@example.com', 'Charlie', 'Brown', '+1-555-0105', FALSE, NULL, CURRENT_TIMESTAMP - INTERVAL '15 days'),
('diana.garcia@example.com', 'Diana', 'Garcia', '+1-555-0106', TRUE, CURRENT_TIMESTAMP - INTERVAL '45 days', CURRENT_TIMESTAMP - INTERVAL '3 hours'),
('edward.martinez@example.com', 'Edward', 'Martinez', '+1-555-0107', TRUE, CURRENT_TIMESTAMP - INTERVAL '10 days', CURRENT_TIMESTAMP - INTERVAL '1 hour'),
('fiona.davis@example.com', 'Fiona', 'Davis', '+1-555-0108', TRUE, CURRENT_TIMESTAMP - INTERVAL '75 days', CURRENT_TIMESTAMP - INTERVAL '10 days');

-- Insert customer profiles
INSERT INTO customer_profiles (customer_id, purchase_history_value, total_purchases, last_purchase_date, avg_order_value, engagement_score, location, industry, company_size) VALUES
(1, 15000.00, 25, CURRENT_TIMESTAMP - INTERVAL '10 days', 600.00, 85, 'New York, NY', 'Technology', '50-200'),
(2, 8500.00, 12, CURRENT_TIMESTAMP - INTERVAL '5 days', 708.33, 90, 'San Francisco, CA', 'Finance', '200-500'),
(3, 12000.00, 18, CURRENT_TIMESTAMP - INTERVAL '100 days', 666.67, 45, 'Austin, TX', 'Healthcare', '10-50'),
(4, 2500.00, 3, CURRENT_TIMESTAMP - INTERVAL '2 days', 833.33, 75, 'Seattle, WA', 'Retail', '1-10'),
(5, 0.00, 0, NULL, 0.00, 60, 'Boston, MA', 'Education', '500+'),
(6, 22000.00, 35, CURRENT_TIMESTAMP - INTERVAL '1 day', 628.57, 95, 'Chicago, IL', 'Manufacturing', '200-500'),
(7, 1200.00, 2, CURRENT_TIMESTAMP - INTERVAL '3 days', 600.00, 80, 'Denver, CO', 'Technology', '10-50'),
(8, 9500.00, 15, CURRENT_TIMESTAMP - INTERVAL '15 days', 633.33, 55, 'Miami, FL', 'Hospitality', '50-200');

-- Insert customer interests
INSERT INTO customer_interests (customer_id, product_category, interest_level, last_interaction_date, interaction_count) VALUES
(1, 'Enterprise Software', 'high', CURRENT_TIMESTAMP - INTERVAL '2 days', 15),
(1, 'Cloud Services', 'medium', CURRENT_TIMESTAMP - INTERVAL '5 days', 8),
(2, 'Financial Analytics', 'high', CURRENT_TIMESTAMP - INTERVAL '1 day', 22),
(2, 'Security Solutions', 'high', CURRENT_TIMESTAMP - INTERVAL '3 days', 12),
(3, 'Healthcare IT', 'medium', CURRENT_TIMESTAMP - INTERVAL '105 days', 5),
(4, 'E-commerce Platforms', 'high', CURRENT_TIMESTAMP - INTERVAL '1 day', 18),
(6, 'Supply Chain Management', 'high', CURRENT_TIMESTAMP - INTERVAL '6 hours', 25),
(6, 'IoT Solutions', 'medium', CURRENT_TIMESTAMP - INTERVAL '2 days', 10),
(7, 'Mobile Development', 'medium', CURRENT_TIMESTAMP - INTERVAL '4 days', 6),
(8, 'CRM Systems', 'low', CURRENT_TIMESTAMP - INTERVAL '20 days', 3);

-- Insert segments
INSERT INTO segments (segment_name, description, criteria_json) VALUES
('High Value', 'Customers with purchase history > $10,000', '{"min_purchase_value": 10000, "min_engagement_score": 70}'),
('At Risk', 'Previously active customers with no recent activity', '{"days_since_last_activity": 90, "previous_purchase_count": ">= 1"}'),
('New Leads', 'Recently acquired contacts with no purchases', '{"total_purchases": 0, "created_within_days": 30}'),
('Engaged Subscribers', 'High email engagement, regular opens and clicks', '{"min_engagement_score": 80, "email_open_rate": ">= 0.4"}'),
('VIP Customers', 'Top tier customers with exceptional value', '{"min_purchase_value": 20000, "min_engagement_score": 90}');

-- Insert customer-segment relationships
INSERT INTO customer_segments (customer_id, segment_id, auto_assigned) VALUES
(1, 1, TRUE),  -- John Doe -> High Value
(1, 4, TRUE),  -- John Doe -> Engaged Subscribers
(2, 1, TRUE),  -- Jane Smith -> High Value
(2, 4, TRUE),  -- Jane Smith -> Engaged Subscribers
(3, 1, TRUE),  -- Bob Johnson -> High Value
(3, 2, TRUE),  -- Bob Johnson -> At Risk
(4, 3, TRUE),  -- Alice Williams -> New Leads
(4, 4, TRUE),  -- Alice Williams -> Engaged Subscribers
(5, 3, TRUE),  -- Charlie Brown -> New Leads
(6, 1, TRUE),  -- Diana Garcia -> High Value
(6, 4, TRUE),  -- Diana Garcia -> Engaged Subscribers
(6, 5, TRUE),  -- Diana Garcia -> VIP Customers
(7, 3, TRUE),  -- Edward Martinez -> New Leads
(8, 1, TRUE),  -- Fiona Davis -> High Value
(8, 2, FALSE); -- Fiona Davis -> At Risk (manually assigned)

-- Insert segment triggers
INSERT INTO segment_triggers (segment_id, trigger_type, condition_json, action, is_active) VALUES
(1, 'PURCHASE', '{"min_purchase_value": 10000}', 'ADD', TRUE),
(2, 'INACTIVITY', '{"days_since_last_activity": 90}', 'ADD', TRUE),
(3, 'REGISTRATION', '{"days_since_registration": 30, "total_purchases": 0}', 'ADD', TRUE),
(4, 'EMAIL_OPEN', '{"open_rate": 0.4, "min_emails_received": 5}', 'ADD', TRUE),
(5, 'PURCHASE', '{"min_purchase_value": 20000}', 'ADD', TRUE);

-- Insert campaigns
INSERT INTO campaigns (campaign_name, description, campaign_type, status, target_segment_id, start_date, end_date, budget, created_by) VALUES
('Spring Sale 2024', 'Promote spring product discounts to high-value customers', 'email', 'completed', 1, CURRENT_TIMESTAMP - INTERVAL '60 days', CURRENT_TIMESTAMP - INTERVAL '30 days', 5000.00, 'admin@marketing.com'),
('Re-engagement Campaign', 'Win back at-risk customers with special offers', 'email', 'active', 2, CURRENT_TIMESTAMP - INTERVAL '10 days', CURRENT_TIMESTAMP + INTERVAL '20 days', 3000.00, 'admin@marketing.com'),
('Welcome Series', 'Onboard new leads with educational content', 'email', 'active', 3, CURRENT_TIMESTAMP - INTERVAL '5 days', CURRENT_TIMESTAMP + INTERVAL '60 days', 2000.00, 'marketing.team@marketing.com'),
('VIP Exclusive Offer', 'Exclusive product launch for VIP customers', 'email', 'scheduled', 5, CURRENT_TIMESTAMP + INTERVAL '5 days', CURRENT_TIMESTAMP + INTERVAL '15 days', 8000.00, 'admin@marketing.com'),
('Holiday Social Campaign', 'Social media engagement for engaged subscribers', 'social', 'draft', 4, CURRENT_TIMESTAMP + INTERVAL '30 days', CURRENT_TIMESTAMP + INTERVAL '45 days', 4500.00, 'social.team@marketing.com');

-- Insert campaign templates
INSERT INTO campaign_templates (campaign_id, channel, subject_line, body_content, personalization_fields, external_asset_url) VALUES
(1, 'email', 'Spring into Savings - 30% Off!', 'Hi {{first_name}}, Spring is here and so are our best deals! Get 30% off on {{recommended_product}}. Shop now!', '{"first_name": "customer.first_name", "recommended_product": "segmentation.top_interest"}', 'https://cdn.example.com/spring-sale-banner.jpg'),
(2, 'email', 'We Miss You, {{first_name}}!', 'It has been a while since we last saw you. Here is a special 40% discount code just for you: {{discount_code}}', '{"first_name": "customer.first_name", "discount_code": "AUTO_GENERATED"}', 'https://cdn.example.com/we-miss-you.jpg'),
(3, 'email', 'Welcome to Our Community!', 'Hello {{first_name}}, Welcome aboard! We are excited to have you. Here are some resources to get you started...', '{"first_name": "customer.first_name"}', 'https://cdn.example.com/welcome-banner.jpg'),
(4, 'email', 'Exclusive VIP Access - Product Launch', 'Dear {{first_name}}, As a VIP customer, you get early access to our newest product line. Launch date: {{launch_date}}', '{"first_name": "customer.first_name", "launch_date": "2024-12-20"}', 'https://cdn.example.com/vip-launch.jpg'),
(5, 'social_media', NULL, 'Join us this holiday season! Share your favorite moments with #HolidayWith{{company_name}}', '{"company_name": "OurBrand"}', 'https://cdn.example.com/holiday-social.jpg');

-- Insert campaign workflows
INSERT INTO campaign_workflows (campaign_id, step_number, trigger_event, delay_hours, action_type, action_config_json, is_active) VALUES
(2, 1, 'CAMPAIGN_START', 0, 'SEND_EMAIL', '{"template_id": 2, "send_time": "09:00"}', TRUE),
(2, 2, 'EMAIL_OPEN', 48, 'SEND_EMAIL', '{"template_id": 2, "follow_up": true}', TRUE),
(3, 1, 'CUSTOMER_REGISTERED', 0, 'SEND_EMAIL', '{"template_id": 3, "send_time": "immediate"}', TRUE),
(3, 2, 'TIME_DELAY', 72, 'SEND_EMAIL', '{"template_id": 3, "content": "tips_and_tricks"}', TRUE),
(3, 3, 'TIME_DELAY', 168, 'SEND_EMAIL', '{"template_id": 3, "content": "feature_highlights"}', TRUE);

-- Insert campaign executions
INSERT INTO campaign_executions (campaign_id, customer_id, channel, sent_at, delivery_status, external_message_id, personalized_content) VALUES
(1, 1, 'email', CURRENT_TIMESTAMP - INTERVAL '55 days', 'delivered', 'msg_001_abc123', 'Hi John, Spring is here and so are our best deals! Get 30% off on Enterprise Software. Shop now!'),
(1, 2, 'email', CURRENT_TIMESTAMP - INTERVAL '55 days', 'delivered', 'msg_002_def456', 'Hi Jane, Spring is here and so are our best deals! Get 30% off on Financial Analytics. Shop now!'),
(1, 6, 'email', CURRENT_TIMESTAMP - INTERVAL '55 days', 'delivered', 'msg_003_ghi789', 'Hi Diana, Spring is here and so are our best deals! Get 30% off on Supply Chain Management. Shop now!'),
(2, 3, 'email', CURRENT_TIMESTAMP - INTERVAL '8 days', 'delivered', 'msg_004_jkl012', 'It has been a while since we last saw you. Here is a special 40% discount code just for you: WELCOME40'),
(2, 8, 'email', CURRENT_TIMESTAMP - INTERVAL '8 days', 'delivered', 'msg_005_mno345', 'It has been a while since we last saw you. Here is a special 40% discount code just for you: BACK40'),
(3, 4, 'email', CURRENT_TIMESTAMP - INTERVAL '4 days', 'delivered', 'msg_006_pqr678', 'Hello Alice, Welcome aboard! We are excited to have you. Here are some resources to get you started...'),
(3, 5, 'email', CURRENT_TIMESTAMP - INTERVAL '3 days', 'sent', 'msg_007_stu901', 'Hello Charlie, Welcome aboard! We are excited to have you. Here are some resources to get you started...'),
(3, 7, 'email', CURRENT_TIMESTAMP - INTERVAL '2 days', 'delivered', 'msg_008_vwx234', 'Hello Edward, Welcome aboard! We are excited to have you. Here are some resources to get you started...');

-- Insert campaign metrics
INSERT INTO campaign_metrics (campaign_id, metric_date, emails_sent, emails_opened, links_clicked, conversions, revenue_generated, cost_incurred) VALUES
(1, CURRENT_DATE - INTERVAL '55 days', 150, 105, 68, 22, 18500.00, 1200.00),
(1, CURRENT_DATE - INTERVAL '50 days', 0, 12, 8, 5, 4200.00, 0.00),
(1, CURRENT_DATE - INTERVAL '45 days', 0, 8, 5, 3, 2800.00, 0.00),
(2, CURRENT_DATE - INTERVAL '8 days', 85, 42, 28, 8, 6400.00, 800.00),
(2, CURRENT_DATE - INTERVAL '5 days', 0, 15, 10, 4, 3200.00, 0.00),
(3, CURRENT_DATE - INTERVAL '4 days', 120, 95, 52, 12, 8500.00, 600.00),
(3, CURRENT_DATE - INTERVAL '2 days', 45, 38, 20, 6, 4200.00, 200.00);

-- Insert customer interactions
INSERT INTO customer_interactions (customer_id, campaign_id, interaction_type, interaction_timestamp, metadata_json, conversion_value) VALUES
(1, 1, 'email_open', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"device": "desktop", "location": "New York"}', NULL),
(1, 1, 'click', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"link": "https://shop.example.com/spring-sale", "device": "desktop"}', NULL),
(1, 1, 'conversion', CURRENT_TIMESTAMP - INTERVAL '53 days', '{"product": "Enterprise Software", "order_id": "ORD-001"}', 1200.00),
(2, 1, 'email_open', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"device": "mobile", "location": "San Francisco"}', NULL),
(2, 1, 'click', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"link": "https://shop.example.com/spring-sale", "device": "mobile"}', NULL),
(2, 1, 'conversion', CURRENT_TIMESTAMP - INTERVAL '52 days', '{"product": "Financial Analytics", "order_id": "ORD-002"}', 2500.00),
(3, 2, 'email_open', CURRENT_TIMESTAMP - INTERVAL '7 days', '{"device": "desktop", "location": "Austin"}', NULL),
(3, 2, 'click', CURRENT_TIMESTAMP - INTERVAL '7 days', '{"link": "https://shop.example.com/comeback-offer", "device": "desktop"}', NULL),
(4, 3, 'email_open', CURRENT_TIMESTAMP - INTERVAL '3 days', '{"device": "mobile", "location": "Seattle"}', NULL),
(4, 3, 'click', CURRENT_TIMESTAMP - INTERVAL '3 days', '{"link": "https://learn.example.com/getting-started", "device": "mobile"}', NULL),
(6, 1, 'email_open', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"device": "desktop", "location": "Chicago"}', NULL),
(6, 1, 'click', CURRENT_TIMESTAMP - INTERVAL '54 days', '{"link": "https://shop.example.com/spring-sale", "device": "desktop"}', NULL),
(6, 1, 'conversion', CURRENT_TIMESTAMP - INTERVAL '53 days', '{"product": "Supply Chain Management", "order_id": "ORD-003"}', 3500.00);

-- Insert campaign ROI
INSERT INTO campaign_roi (campaign_id, total_cost, total_revenue) VALUES
(1, 5000.00, 25500.00),
(2, 3000.00, 9600.00),
(3, 2000.00, 12700.00);

-- Insert marketing events
INSERT INTO marketing_events (event_type, event_source, payload_json, customer_id, campaign_id, published_at, processed) VALUES
('CAMPAIGN_STARTED', 'marketing_automation', '{"campaign_name": "Spring Sale 2024", "target_segment": "High Value"}', NULL, 1, CURRENT_TIMESTAMP - INTERVAL '60 days', TRUE),
('EMAIL_SENT', 'marketing_automation', '{"recipient": "john.doe@example.com", "template_id": 1}', 1, 1, CURRENT_TIMESTAMP - INTERVAL '55 days', TRUE),
('EMAIL_OPENED', 'email_service', '{"message_id": "msg_001_abc123", "open_time": "2024-10-15 09:23:00"}', 1, 1, CURRENT_TIMESTAMP - INTERVAL '54 days', TRUE),
('LINK_CLICKED', 'email_service', '{"message_id": "msg_001_abc123", "link_url": "https://shop.example.com/spring-sale"}', 1, 1, CURRENT_TIMESTAMP - INTERVAL '54 days', TRUE),
('CUSTOMER_PURCHASE', 'sales_module', '{"order_id": "ORD-001", "amount": 1200.00, "product": "Enterprise Software"}', 1, 1, CURRENT_TIMESTAMP - INTERVAL '53 days', TRUE),
('CAMPAIGN_STARTED', 'marketing_automation', '{"campaign_name": "Re-engagement Campaign", "target_segment": "At Risk"}', NULL, 2, CURRENT_TIMESTAMP - INTERVAL '10 days', TRUE),
('EMAIL_SENT', 'marketing_automation', '{"recipient": "bob.johnson@example.com", "template_id": 2}', 3, 2, CURRENT_TIMESTAMP - INTERVAL '8 days', TRUE),
('CUSTOMER_REGISTERED', 'crm_module', '{"email": "edward.martinez@example.com", "source": "website"}', 7, NULL, CURRENT_TIMESTAMP - INTERVAL '10 days', TRUE),
('SEGMENT_CHANGED', 'segmentation_manager', '{"customer_id": 7, "new_segment": "New Leads", "trigger": "registration"}', 7, NULL, CURRENT_TIMESTAMP - INTERVAL '10 days', TRUE);

-- Insert external service logs
INSERT INTO external_service_logs (service_type, campaign_id, request_payload, response_payload, status_code, success) VALUES
('email_provider', 1, '{"to": "john.doe@example.com", "subject": "Spring into Savings - 30% Off!", "template_id": 1}', '{"message_id": "msg_001_abc123", "status": "sent"}', 200, TRUE),
('email_provider', 1, '{"to": "jane.smith@example.com", "subject": "Spring into Savings - 30% Off!", "template_id": 1}', '{"message_id": "msg_002_def456", "status": "sent"}', 200, TRUE),
('email_provider', 2, '{"to": "bob.johnson@example.com", "subject": "We Miss You, Bob!", "template_id": 2}', '{"message_id": "msg_004_jkl012", "status": "sent"}', 200, TRUE),
('email_provider', 3, '{"to": "alice.williams@example.com", "subject": "Welcome to Our Community!", "template_id": 3}', '{"message_id": "msg_006_pqr678", "status": "sent"}', 200, TRUE),
('social_media_api', 5, '{"platform": "twitter", "content": "Join us this holiday season! #HolidayWithOurBrand"}', '{"post_id": "tw_12345", "status": "draft"}', 200, TRUE);
