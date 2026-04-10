-- =============================================
-- @Reb7yBot - PostgreSQL Database Schema
-- =============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Settings Table (dynamic admin config)
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default settings
INSERT INTO settings (key, value) VALUES
    ('referral_reward', '5.00'),
    ('first_withdraw_min', '50.00'),
    ('next_withdraw_min', '20.00'),
    ('daily_reward', '2.00'),
    ('daily_reward_streak_bonus', '0.50'),
    ('ads_enabled', 'true'),
    ('maintenance_mode', 'false'),
    ('bronze_threshold', '5'),
    ('silver_threshold', '20'),
    ('gold_threshold', '50'),
    ('bronze_multiplier', '1.0'),
    ('silver_multiplier', '1.2'),
    ('gold_multiplier', '1.5'),
    ('spin_min_reward', '0.50'),
    ('spin_max_reward', '5.00'),
    ('spin_cooldown_hours', '24'),
    ('guess_reward', '1.00'),
    ('guess_max_attempts', '3'),
    ('boost_active', 'false'),
    ('boost_multiplier', '2.0'),
    ('boost_ends_at', NULL)
ON CONFLICT (key) DO NOTHING;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(100),
    full_name VARCHAR(255),
    balance DECIMAL(15,2) DEFAULT 0.00,
    total_earned DECIMAL(15,2) DEFAULT 0.00,
    total_withdrawn DECIMAL(15,2) DEFAULT 0.00,
    referral_count INTEGER DEFAULT 0,
    referred_by BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    rank VARCHAR(20) DEFAULT 'bronze',
    rank_multiplier DECIMAL(5,2) DEFAULT 1.0,
    is_banned BOOLEAN DEFAULT FALSE,
    ban_reason TEXT,
    ban_expires_at TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE,
    warning_count INTEGER DEFAULT 0,
    join_date TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW(),
    last_daily_claim TIMESTAMP,
    daily_streak INTEGER DEFAULT 0,
    last_spin TIMESTAMP,
    last_guess TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    referral_speed_score DECIMAL(10,4) DEFAULT 0,
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,
    captcha_verified BOOLEAN DEFAULT FALSE,
    captcha_code VARCHAR(20),
    captcha_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Referrals Table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id BIGINT NOT NULL REFERENCES users(user_id),
    referred_id BIGINT NOT NULL REFERENCES users(user_id),
    reward_amount DECIMAL(15,2) NOT NULL,
    reward_paid BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(referred_id)
);

-- Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    type VARCHAR(50) NOT NULL, -- 'referral_reward', 'daily_reward', 'game_reward', 'withdrawal', 'promo_code', 'admin_add', 'admin_deduct'
    amount DECIMAL(15,2) NOT NULL,
    description TEXT,
    reference_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Withdrawals Table
CREATE TABLE IF NOT EXISTS withdrawals (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(20) UNIQUE NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    amount DECIMAL(15,2) NOT NULL,
    payment_method VARCHAR(100) NOT NULL,
    account_details TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
    admin_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

-- Channels (Forced Subscription)
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    channel_id VARCHAR(100) UNIQUE NOT NULL,
    channel_name VARCHAR(255) NOT NULL,
    channel_link VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMP DEFAULT NOW()
);

-- Promo Codes Table
CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    reward DECIMAL(15,2) NOT NULL,
    usage_limit INTEGER, -- NULL = unlimited
    usage_per_user INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Promo Code Usage
CREATE TABLE IF NOT EXISTS promo_usage (
    id SERIAL PRIMARY KEY,
    code_id INTEGER NOT NULL REFERENCES promo_codes(id),
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    used_at TIMESTAMP DEFAULT NOW()
);

-- Ads Table
CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    ad_type VARCHAR(20) DEFAULT 'text', -- text, link, button
    link_url VARCHAR(500),
    button_text VARCHAR(100),
    reward_for_view DECIMAL(15,2) DEFAULT 0,
    trigger_event VARCHAR(50), -- 'after_daily', 'after_game', 'main_menu'
    click_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ad Views
CREATE TABLE IF NOT EXISTS ad_views (
    id SERIAL PRIMARY KEY,
    ad_id INTEGER NOT NULL REFERENCES ads(id),
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    viewed_at TIMESTAMP DEFAULT NOW()
);

-- User Activity Log
CREATE TABLE IF NOT EXISTS user_activity (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    ip_hash VARCHAR(64),
    session_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Payment Methods (Admin configurable)
CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    placeholder TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO payment_methods (name, description, placeholder) VALUES
    ('فودافون كاش', 'رقم فودافون كاش', 'أدخل رقم الهاتف'),
    ('باينانس', 'معرف حساب Binance', 'أدخل UID أو البريد الإلكتروني'),
    ('انستاباي', 'رقم انستاباي', 'أدخل رقم الهاتف')
ON CONFLICT DO NOTHING;

-- Broadcast Log
CREATE TABLE IF NOT EXISTS broadcasts (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    sent_by BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_rank ON users(rank);
CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_withdrawals_user ON withdrawals(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals(status);
CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_promo_usage_code ON promo_usage(code_id);
CREATE INDEX IF NOT EXISTS idx_promo_usage_user ON promo_usage(user_id);
