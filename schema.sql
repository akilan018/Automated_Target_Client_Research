-- ============================================================
-- PerfectParser Lead Intelligence Platform
-- Database Schema for Supabase (PostgreSQL)
-- ============================================================

-- Drop the table if it exists (useful for dev resets)
-- DROP TABLE IF EXISTS leads;

CREATE TABLE leads (
    id              BIGSERIAL PRIMARY KEY,
    company_name    TEXT NOT NULL,
    website         TEXT,
    industry        TEXT,
    company_size    TEXT,
    contact_person  TEXT,
    job_title       TEXT,
    profile_url     TEXT,
    email           TEXT,
    source_platform TEXT,
    reason          TEXT,
    lead_score      TEXT,
    ai_reason       TEXT,
    collected_at    TIMESTAMP DEFAULT NOW()
);

-- Index for fast duplicate checks on company_name
CREATE INDEX IF NOT EXISTS idx_leads_company_name ON leads (company_name);

-- Index for filtering by industry
CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads (industry);

-- Index for filtering by lead_score
CREATE INDEX IF NOT EXISTS idx_leads_lead_score ON leads (lead_score);

-- ============================================================
-- MIGRATION: If your table already exists but is missing columns,
-- run these ALTER TABLE statements in the Supabase SQL Editor:
-- ============================================================
-- ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score TEXT;
-- ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_reason TEXT;
-- ALTER TABLE leads ADD COLUMN IF NOT EXISTS reason TEXT;
