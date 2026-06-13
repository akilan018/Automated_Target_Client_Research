"""
============================================================
PerfectParser Lead Intelligence Platform
PDF Parser Module (Regex/Heuristic Based — No API Key Required)
============================================================
Extracts text from uploaded PDF files and uses regex/heuristics
to identify potential leads (company names, contacts, emails)
from the document content.
============================================================
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional

# ── Logger ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# Common company suffixes for heuristic detection
COMPANY_SUFFIXES = (
    "Inc", "LLC", "Corp", "Corporation", "Ltd", "Limited",
    "Company", "Co", "Partners", "Group", "Solutions", "Services"
)

# Common industry keywords
INDUSTRY_KEYWORDS = {
    "Healthcare": ["medical", "health", "hospital", "clinic", "pharma"],
    "Legal": ["law", "legal", "attorney", "firm", "litigation"],
    "Finance": ["finance", "bank", "investment", "capital", "wealth"],
    "Technology": ["tech", "software", "digital", "data", "cloud", "it"],
    "Real Estate": ["real estate", "property", "realty", "mortgage"],
}


def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract all text from an uploaded PDF file.
    """
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(pdf_file)
        pages_text: list[str] = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
            logger.info("Extracted text from page %d (%d chars)", i + 1, len(text or ""))

        full_text = "\n\n".join(pages_text)
        logger.info(
            "PDF extraction complete: %d pages, %d total chars",
            len(reader.pages),
            len(full_text),
        )
        return full_text

    except ImportError:
        logger.error("PyPDF2 not installed. Run: pip install PyPDF2")
        raise RuntimeError("PyPDF2 is required for PDF parsing. Install it with: pip install PyPDF2")
    except Exception as exc:
        logger.error("PDF extraction failed: %s", exc)
        raise RuntimeError(f"Failed to extract text from PDF: {exc}")


def _infer_industry(text: str, context: str) -> str:
    """Infer industry based on keyword counts in the text and context."""
    combined = (text + " " + context).lower()
    best_industry = "Unknown"
    max_count = 0

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        count = sum(combined.count(kw) for kw in keywords)
        if count > max_count:
            max_count = count
            best_industry = industry

    return best_industry if max_count > 0 else "General Business"


def extract_leads_from_text(text: str, context: str = "") -> list[dict]:
    """
    Use heuristics and regex to identify potential leads from extracted PDF text.
    """
    leads: list[dict] = []
    seen_companies: set[str] = set()

    now = datetime.now(timezone.utc).isoformat()
    industry = _infer_industry(text, context)

    # 1. Extract Emails
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = list(set(re.findall(email_pattern, text)))

    # 2. Extract potential company names (Capitalized words followed by suffixes)
    # E.g. "Acme Corp", "Tech Solutions LLC"
    suffix_pattern = r"\b(?:" + "|".join(COMPANY_SUFFIXES) + r")\b\.?"
    company_pattern = r"([A-Z][a-zA-Z0-9&]* (?:\s*[A-Z][a-zA-Z0-9&]*)*\s*" + suffix_pattern + ")"
    
    potential_companies = re.findall(company_pattern, text)
    
    # 3. Extract potential URLs
    url_pattern = r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b"
    urls = list(set(re.findall(url_pattern, text)))

    # If we found explicit companies, create a lead for each
    for comp in potential_companies:
        comp_clean = comp.strip().replace("\n", " ")
        if comp_clean.lower() in seen_companies or len(comp_clean) < 4:
            continue
            
        seen_companies.add(comp_clean.lower())
        
        # Try to match an email with the company domain if possible
        matched_email = ""
        comp_first_word = comp_clean.split()[0].lower()
        for e in emails:
            if comp_first_word in e:
                matched_email = e
                break
        if not matched_email and emails:
            matched_email = emails.pop(0) # Assign random email if no match

        # Try to match URL
        matched_url = ""
        for u in urls:
            if comp_first_word in u.lower():
                matched_url = u
                break
        if not matched_url and urls:
            matched_url = urls.pop(0)

        leads.append({
            "company_name": comp_clean,
            "website": matched_url,
            "industry": industry,
            "company_size": "Unknown",
            "contact_person": "Extracted Contact", 
            "job_title": "",
            "profile_url": "",
            "email": matched_email,
            "source_platform": "PDF Upload",
            "reason": f"Extracted via document analysis. Context: {context}",
            "collected_at": now,
        })

    # If no explicit companies found with suffixes, but we have emails, create leads from email domains
    if not leads and emails:
        for email in emails:
            domain = email.split('@')[1]
            company_guess = domain.split('.')[0].capitalize()
            if company_guess.lower() in ["gmail", "yahoo", "hotmail", "outlook"]:
                continue # Skip generic email providers
                
            if company_guess.lower() in seen_companies:
                continue
                
            seen_companies.add(company_guess.lower())
            
            leads.append({
                "company_name": company_guess + " (Inferred from email)",
                "website": f"https://www.{domain}",
                "industry": industry,
                "company_size": "Unknown",
                "contact_person": email.split('@')[0].capitalize(),
                "job_title": "",
                "profile_url": "",
                "email": email,
                "source_platform": "PDF Upload",
                "reason": f"Extracted via document analysis. Context: {context}",
                "collected_at": now,
            })

    logger.info("Extracted %d leads from PDF text via regex/heuristics", len(leads))
    return leads


def parse_pdf_for_leads(pdf_file, context: str = "") -> list[dict]:
    """
    End-to-end: extract text from PDF, then use regex/heuristics to find leads.
    """
    text = extract_text_from_pdf(pdf_file)

    if not text.strip():
        logger.warning("PDF contains no extractable text")
        return []

    leads = extract_leads_from_text(text, context=context)
    return leads
