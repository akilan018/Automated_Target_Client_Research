
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

CREATE INDEX IF NOT EXISTS idx_leads_company_name ON leads (company_name);


CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads (industry);


CREATE INDEX IF NOT EXISTS idx_leads_lead_score ON leads (lead_score);


