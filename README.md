# 🔍 AUTOMATED TARGET CLIENT RESEARCHER

A production-ready lead intelligence system that identifies potential customers for **PerfectParser** — an AI-powered document processing tool. Built with Python, Streamlit, Supabase, and Google Gemini AI.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Lead Collection** | Scrapes public company directories using BeautifulSoup to find potential customers |
| **AI Analysis** | Uses Google Gemini 1.5 Flash to score leads (High / Medium / Low) with reasoning |
| **Supabase Storage** | Stores, deduplicates, and filters leads in a PostgreSQL database via Supabase |
| **PDF Reports** | Generates professional branded PDF reports with summary statistics and lead details |
| **Modern Dashboard** | Streamlit UI with sidebar navigation, metric cards, charts, and filters |

---

## 🛠 Tech Stack

- **Frontend / Dashboard:** Streamlit
- **Backend:** Python 3.10+
- **Database:** Supabase (PostgreSQL)
- **AI / LLM:** Google Gemini 1.5 Flash
- **Web Scraping:** BeautifulSoup + Requests
- **Data Processing:** Pandas
- **PDF Generation:** ReportLab

---

## 📁 Folder Structure

```
perfectparser-lead-finder/
├── app.py                  # Main Streamlit application
├── src/
│   ├── __init__.py         # Package initializer
│   ├── scraper.py          # Lead collection module (web scraping)
│   ├── analyzer.py         # Gemini AI analysis module
│   ├── supabase_db.py      # Supabase CRUD operations
│   └── pdf_generator.py    # Professional PDF report generator
├── reports/                # Generated PDF reports (auto-created)
├── requirements.txt        # Python dependencies
├── schema.sql              # Supabase table DDL
├── .env.example            # Environment variables template
├── .env                    # Your actual environment variables (gitignored)
└── README.md               # This file
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

Edit `.env` with your actual values:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key
GEMINI_API_KEY=your-gemini-api-key
```

**Where to get these:**
- **Supabase URL & Key:** [Supabase Dashboard](https://app.supabase.com) → Your Project → Settings → API
- **Gemini API Key:** [Google AI Studio](https://aistudio.google.com/apikey)

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

The app will open at **http://localhost:8501** in your browser.

---

## 📊 Usage Guide

### Dashboard
View overall metrics — total leads, score distribution, industry breakdown, and recent entries.

### Collect Leads
1. Select a target industry from the dropdown
2. Set the maximum number of leads
3. Click **Collect Leads** to scrape public directories
4. Click **Store in Supabase** to save results

### Analyze Leads
1. Choose between session leads or unscored database leads
2. Click **Analyze with Gemini AI** to score each lead
3. Review the High / Medium / Low scores and AI reasoning
4. Click **Save Analysis to Supabase** to persist results

### Stored Leads
1. Filter by industry and/or lead score
2. Click **Load Leads** to fetch from Supabase
3. Browse the full data table

### Reports
1. Choose the data source (all DB leads or session leads)
2. Click **Generate PDF Report**
3. Download the professional PDF

---

## 📝 License

This project is built as an internship demonstration project.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -m "Add new feature"`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Open a Pull Request
