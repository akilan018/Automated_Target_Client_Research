# 🔍 PerfectParser Lead Intelligence Platform

A production-ready **automated lead intelligence system** that programmatically identifies potential customers for **[PerfectParser](https://perfectparser.com)** — an AI-powered document processing tool.

Built with Python, Streamlit, NVIDIA NIM (Llama-3.3-70B), Supabase, and multi-source web scraping.

---

## 🧠 What is PerfectParser?

PerfectParser is an AI document-processing tool that helps businesses:
- **Extract** data from PDFs, invoices, contracts, and scanned forms automatically
- **Organize** unstructured document data into structured formats
- **Eliminate** manual data entry from paper-based workflows

**Target customers:** Any company that processes high volumes of paper/PDF documents — insurance claims, legal contracts, medical records, financial reports, shipping manifests, and more.

---

## ✨ System Features

| Feature | Description |
|---------|-------------|
| **🤖 NVIDIA AI Research** | Uses meta/llama-3.3-70b-instruct to identify REAL, named companies that need document automation |
| **🔑 Multi-Key Rotation** | Dynamically rotates queries across up to 3 NVIDIA NIM API keys with automated error failover and retries |
| **🧠 AI Lead Enrichment** | Automatically enriches web-scraped leads (LinkedIn, Directories) to extract real company names, emails, and profiles |
| **🔗 LinkedIn Scraping** | Finds company profiles on LinkedIn via programmatic search |
| **📒 Business Directories** | Scrapes Manta, D&B, and other public business directories |
| **💼 Crunchbase** | Finds startup and company profiles from Crunchbase |
| **🤖 Reddit Research** | Extracts company mentions from industry discussion threads |
| **🌐 Company Websites** | Direct company website discovery via search |
| **🧠 AI Lead Scoring** | meta/llama-3.3-70b-instruct scores each lead High/Medium/Low with a perfect 2-sentence sales rationale |
| **💾 Supabase Storage** | PostgreSQL via Supabase — deduplication, filtering, date tracking |
| **📄 PDF Reports** | Professional branded lead intelligence reports |
| **📊 Dashboard** | Real-time metrics, industry breakdown, recent leads overview |

---

## 🛠 Tech Stack

- **Frontend / Dashboard:** Streamlit
- **Backend:** Python 3.10+
- **AI / LLM:** NVIDIA NIM — Llama-3.3-70B (OpenAI-compatible API)
- **Database:** Supabase (PostgreSQL)
- **Web Scraping:** BeautifulSoup + Requests (DuckDuckGo HTML search)
- **Data Processing:** Pandas
- **PDF Generation:** ReportLab

---

## 📁 Folder Structure

```
perfectparser-lead-finder/
├── app.py                      # Main Streamlit application
├── src/
│   ├── __init__.py             # Package initializer
│   ├── scraper.py              # Multi-platform lead collection module
│   ├── nvidia_researcher.py    # NVIDIA NIM AI researcher (Llama-3.3-70B)
│   ├── analyzer.py             # Lead scoring module (AI + keyword fallback)
│   ├── supabase_db.py          # Supabase CRUD operations
│   ├── pdf_generator.py        # Professional PDF report generator
│   └── pdf_parser.py           # PDF upload and lead extraction
├── reports/                    # Generated PDF reports (auto-created)
├── requirements.txt            # Python dependencies
├── schema.sql                  # Supabase table DDL
├── .env.example                # Environment variables template
├── .env                        # Your actual credentials (git-ignored)
└── README.md                   # This file
```

---

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd perfectparser-lead-finder
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values. You can configure up to 3 keys for sequential round-robin rotation and failover:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Up to 3 NVIDIA NIM API keys for rotation
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
NVIDIA_API_KEY_2=nvapi-yyyyyyyyyyyyyyyyyyyy
NVIDIA_API_KEY_3=nvapi-zzzzzzzzzzzzzzzzzzzz
```

**Where to get these:**
- **Supabase URL & Key:** [Supabase Dashboard](https://app.supabase.com) → Your Project → Settings → API
- **NVIDIA API Key (Free):** [NVIDIA Build](https://build.nvidia.com) → Sign up → Get API Key
  - Gives access to Llama-3.3-70B and other models
  - Free tier available with usage credits

### 5. Create the Database Table

Go to your Supabase project → **SQL Editor** → paste and run the contents of `schema.sql`:

```sql
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
```

### 6. Run the Application

```bash
streamlit run app.py
```

The app will open at **http://localhost:8501**.

---

## 📊 Usage Guide

### Dashboard
View overall metrics — total leads, High/Medium/Low score distribution, and recent entries.

### Collect Leads
1. Select a target industry (Healthcare, Legal, Finance, Insurance, etc.)
2. Set the maximum number of leads to collect
3. Select which platforms to search:
   - ✅ **NVIDIA AI Research** (recommended — uses Llama-3.3-70B to find REAL named companies)
   - ✅ LinkedIn, Reddit, Business Directories, Company Websites, Crunchbase
4. Click **Collect Leads** — the system finds real companies programmatically
5. Click **Store in Supabase** to save results

### Analyze Leads
1. Choose between session leads or unscored database leads
2. Click **Score Leads** — NVIDIA Llama-3.3-70B assigns High/Medium/Low scores
3. View AI-generated reasoning for each company
4. Click **Save Analysis to Supabase** to persist scores

### Stored Leads
Filter by industry and/or lead score, then click **Load Leads** to fetch from Supabase.

### Reports
Generate and download professional PDF lead intelligence reports.

---

## 🎯 Lead Scoring Method

Leads are scored using **NVIDIA Llama-3.3-70B** (when API key is set):

| Score | Criteria |
|-------|----------|
| **High** | Strong, immediate need for document processing — company clearly handles high-volume documents manually |
| **Medium** | Likely uses documents frequently but may have partial automation already |
| **Low** | Minimal document processing needs or already automated |

The AI analyzes: company name, industry, website context, company size, and job role of the decision-maker.

**Scoring Output Format**: The AI output features a strict, exactly 2-sentence rationale in the `ai_reason` column (sentence one explains industry relevance/size/docs; sentence two outlines estimated daily volume and ROI justification).

**Fallback:** If no NVIDIA API key is set, the system uses a keyword-based scoring algorithm that analyzes industry signals, document-related terms, and company size indicators.

---

## 🔐 Security Notes

- Never commit `.env` to GitHub (it's in `.gitignore`)
- Store all API keys in environment variables only
- Only publicly available, non-personal information is collected
- No purchased lead lists are used

---

## 📝 License

This project is built as an internship screening task demonstration.
