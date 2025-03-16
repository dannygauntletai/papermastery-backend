-- **Table: researchers**
-- Stores profiles of researchers available for consultations
CREATE TABLE researchers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    bio TEXT,
    expertise JSONB,  -- e.g., ["machine learning", "physics"]
    achievements JSONB,  -- e.g., ["machine learning", "physics"]
    availability JSONB,  -- e.g., {"monday": ["9:00-10:00"], "tuesday": ["14:00-15:00"]}
    rate DECIMAL(10, 2) NOT NULL,  -- Hourly rate (e.g., 50.00)
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- **Table: subscriptions**
-- Manages user subscriptions for the consulting feature
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'expired', 'canceled')),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- **Table: outreach_requests**
-- Tracks requests to onboard new researchers
CREATE TABLE outreach_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    researcher_email VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- **Table: sessions**
-- Manages consultation sessions between users and researchers
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    researcher_id UUID REFERENCES researchers(id) ON DELETE CASCADE,
    paper_id UUID REFERENCES papers(id) ON DELETE SET NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('scheduled', 'completed', 'canceled')),
    zoom_link VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- **Table: payments**
-- Records payment transactions for subscriptions and sessions
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
    transaction_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- **Table: reviews**
-- Stores user reviews and ratings for researchers post-session
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    researcher_id UUID REFERENCES researchers(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Part 3: Index Creations for Performance
-- ============================================

-- **Indexes for 'researchers' table**
CREATE INDEX idx_researchers_email ON researchers(email);
CREATE INDEX idx_researchers_verified ON researchers(verified);

-- **Index for 'subscriptions' table**
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);

-- **Index for 'outreach_requests' table**
CREATE INDEX idx_outreach_requests_researcher_email ON outreach_requests(researcher_email);

-- **Indexes for 'sessions' table**
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_researcher_id ON sessions(researcher_id);
CREATE INDEX idx_sessions_status ON sessions(status);

-- **Indexes for 'payments' table**
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);

-- **Indexes for 'reviews' table**
CREATE INDEX idx_reviews_researcher_id ON reviews(researcher_id);
CREATE INDEX idx_reviews_session_id ON reviews(session_id);

-- ============================================
-- End of Script
-- ============================================