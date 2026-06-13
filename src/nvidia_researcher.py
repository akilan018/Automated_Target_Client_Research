import os
import json
import logging
import re
import time
import random
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── NVIDIA NIM Configuration ─────────────────────────────────
# Loaded dynamically inside functions, but defined here for global reference and backwards compatibility
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"

# Global index to keep track of key rotation
_key_index = 0

def _get_active_keys() -> list[str]:
    """Retrieve all non-empty NVIDIA API keys from the environment."""
    keys = [
        os.getenv("NVIDIA_API_KEY", "").strip(),
        os.getenv("NVIDIA_API_KEY_2", "").strip(),
        os.getenv("NVIDIA_API_KEY_3", "").strip(),
    ]
    # Filter out empty keys and common placeholder values
    return [k for k in keys if k and not k.startswith("your-") and not k.startswith("nvapi-xxx")]

# Export primary key for compatibility
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# ── User Agents ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# ── NVIDIA Client ─────────────────────────────────────────────

def _call_nvidia_llm(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """
    Call NVIDIA NIM API (OpenAI-compatible endpoint) with automatic API key rotation.
    Returns the assistant's response text.
    """
    global _key_index

    # Reload keys to support dynamic environment changes in Streamlit
    keys = _get_active_keys()
    if not keys:
        raise ValueError("No NVIDIA API keys configured in .env file (NVIDIA_API_KEY, NVIDIA_API_KEY_2, or NVIDIA_API_KEY_3)")

    last_exc = None
    start_idx = _key_index
    for attempt in range(len(keys)):
        current_idx = (start_idx + attempt) % len(keys)
        active_key = keys[current_idx]
        
        logger.info("Using NVIDIA API Key #%d for NIM LLM call", current_idx + 1)
        
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": NVIDIA_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,  # tolerates slower responses from NVIDIA NIM servers
            )
            response.raise_for_status()
            
            # Increment rotation index for next call
            _key_index = (current_idx + 1) % len(keys)
            
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            status_code = 'N/A'
            if hasattr(exc, 'response') and exc.response is not None:
                status_code = getattr(exc.response, 'status_code', 'N/A')
            logger.warning(
                "NVIDIA API Key #%d failed (Status: %s): %s. Trying next key...",
                current_idx + 1,
                status_code,
                str(exc)
            )
            last_exc = exc

    # If all keys failed, raise the last error
    raise last_exc or ValueError("NVIDIA LLM call failed with all keys")


# ── Web Verification Helpers ──────────────────────────────────

def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _verify_website(url: str) -> bool:
    """Check if a URL is reachable and returns content."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = requests.get(url, headers=_get_headers(), timeout=10, allow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False


def _scrape_google_for_company(company_name: str) -> dict:
    """
    Search DuckDuckGo for a company's official website and LinkedIn profile.
    Returns dict with {website, linkedin_url, description}
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": f'"{company_name}" official site OR linkedin company'}
        resp = requests.post(url, data=params, headers=_get_headers(), timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = {"website": "", "linkedin_url": "", "description": ""}

        for link_tag in soup.select("a.result__a")[:10]:
            href = link_tag.get("href", "")
            # Extract real URL from DDG redirect
            if "uddg=" in href:
                match = re.search(r"uddg=([^&]+)", href)
                if match:
                    from urllib.parse import unquote
                    href = unquote(match.group(1))

            if "linkedin.com/company" in href and not results["linkedin_url"]:
                results["linkedin_url"] = href

            # Get company website (skip social media)
            skip_domains = {"linkedin.com", "twitter.com", "x.com", "facebook.com",
                          "youtube.com", "wikipedia.org", "reddit.com", "google.com"}
            from urllib.parse import urlparse
            parsed = urlparse(href)
            domain = parsed.netloc.lower().replace("www.", "")
            if domain and not any(sd in domain for sd in skip_domains) and not results["website"]:
                if href.startswith("http"):
                    results["website"] = href

            # Get snippet
            parent = link_tag.find_parent("div", class_="result")
            if parent and not results["description"]:
                snippet = parent.select_one(".result__snippet")
                if snippet:
                    results["description"] = snippet.get_text(strip=True)[:300]

        return results
    except Exception as exc:
        logger.warning("Web search failed for %s: %s", company_name, exc)
        return {"website": "", "linkedin_url": "", "description": ""}


# ── Core Research Functions ───────────────────────────────────

def research_leads_with_ai(
    industry: str,
    num_companies: int = 15,
) -> list[dict]:
    """
    Use NVIDIA Llama-3.3-70B to generate a list of REAL, verifiable
    companies in the given industry that are strong candidates for
    PerfectParser (AI document processing tool).

    The AI generates companies that are:
    - Actually known/real businesses
    - In sectors with high document processing needs
    - Publicly findable online

    Parameters
    ----------
    industry : str
        Target industry (e.g., "Insurance", "Legal", "Finance")
    num_companies : int
        How many companies to research

    Returns
    -------
    list[dict]
        Lead records ready for Supabase insertion
    """
    logger.info("Starting NVIDIA AI research for %s industry (%d companies)", industry, num_companies)

    # ── Step 1: Ask AI for real company names ────────────────
    industry_contexts = {
        "Healthcare": "hospitals, medical groups, health insurance companies, pharmaceutical companies, clinical labs",
        "Legal": "law firms, legal services companies, litigation support firms, corporate counsel departments",
        "Finance": "accounting firms, financial advisory companies, investment banks, fintech companies, tax preparation firms",
        "Insurance": "insurance companies, insurance brokers, claims management companies, underwriting firms",
        "Recruitment": "staffing agencies, HR consulting firms, executive search firms, talent acquisition companies",
        "Logistics": "freight companies, supply chain management firms, customs brokers, shipping companies",
        "Real Estate": "real estate agencies, property management companies, mortgage lenders, title companies",
        "Education": "universities, online learning companies, education technology firms, testing organizations",
        "Government": "government contractors, public sector consulting firms, compliance management companies",
        "Manufacturing": "industrial manufacturers, automotive suppliers, aerospace companies, electronics manufacturers",
    }

    context = industry_contexts.get(industry, f"companies in the {industry} sector")

    system_msg = """You are an elite B2B sales intelligence researcher for PerfectParser — an AI-powered document processing platform that extracts, classifies, and organizes data from PDFs, invoices, contracts, medical records, insurance claims, and more.

CRITICAL RULES:
1. Only name REAL, actually existing companies — NO made-up names
2. Prioritize companies with HEAVY manual document processing (500+ docs/day)
3. Focus on mid-to-large companies (100+ employees) where ROI is strongest
4. Include the SPECIFIC job title of the person who would APPROVE the purchase
5. Output ONLY valid JSON — no markdown, no explanation, no commentary"""

    user_msg = f"""Identify {num_companies} high-potential buyer companies in the {industry} industry ({context}) for PerfectParser.

PerfectParser automates extraction of structured data from unstructured documents — PDFs, scanned forms, invoices, contracts, medical records, legal filings, insurance claims, tax documents, etc.

TARGET BUYER PROFILE:
- Companies that employ teams of people to MANUALLY read, sort, and enter data from documents
- Organizations drowning in paperwork — claims processors, billing departments, compliance teams
- Companies still using legacy OCR or manual data entry

For each company provide ALL fields (do NOT leave any empty or generic):
- company_name: Real company name
- website_domain: Their actual website (e.g. "company.com")
- contact_person: Realistic or actual first and last name of a decision-maker (e.g. "Sarah Jenkins")
- job_title: Specific job title of the contact person (e.g. "VP of Claims Operations", "COO", "Chief Information Officer", "Head of Document Automation")
- company_size: Small / Medium / Large / Enterprise
- email: Professional email address for the contact person (e.g. "s.jenkins@company.com" or "sarah.jenkins@company.com")
- profile_url: LinkedIn company or personal profile URL (e.g. "https://www.linkedin.com/company/company-name" or "https://www.linkedin.com/in/sarah-jenkins-slug")
- reason: 2-3 sentences on WHY they need PerfectParser — mention specific document types, estimated daily volume, and the manual pain point
- document_types: Comma-separated list of specific documents they process

Return as JSON array:
[
  {{
    "company_name": "UnitedHealth Group",
    "website_domain": "unitedhealthgroup.com",
    "contact_person": "Sarah Jenkins",
    "job_title": "VP of Claims Operations",
    "company_size": "Enterprise",
    "email": "sarah.jenkins@unitedhealthgroup.com",
    "profile_url": "https://www.linkedin.com/in/sarah-jenkins-uhg",
    "reason": "Processes millions of insurance claims, EOBs, and prior authorization forms annually. Large teams manually review and extract data from submitted medical documentation. Automation could save thousands of labor hours.",
    "document_types": "insurance claims, EOBs, prior authorizations, medical records, provider contracts"
  }}
]

Industry: {industry}
Number of companies: {num_companies}"""

    try:
        response_text = _call_nvidia_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ], temperature=0.3, max_tokens=4000)

        # ── Step 2: Parse the JSON response ─────────────────
        companies = _parse_json_from_llm(response_text)
        if not companies:
            logger.error("AI returned no valid companies")
            return []

        logger.info("AI identified %d companies for %s", len(companies), industry)

        # ── Step 3: Enrich each company with real web data ───
        leads = []
        now = datetime.now(timezone.utc).isoformat()

        # Industry-specific default decision makers (fallback)
        industry_defaults = {
            "Healthcare":    "Chief Operating Officer (COO)",
            "Legal":         "Head of Digital Transformation",
            "Finance":       "VP of Operations / CFO",
            "Insurance":     "VP of Claims Operations",
            "Logistics":     "Operations Director",
            "Recruitment":   "Head of Talent Operations",
            "Real Estate":   "Director of Operations",
            "Education":     "Director of Administration",
            "Government":    "Chief Information Officer (CIO)",
            "Manufacturing": "VP of Operations",
        }
        default_role = industry_defaults.get(industry, "VP of Operations")

        for i, company in enumerate(companies):
            company_name = company.get("company_name", "").strip()
            if not company_name or len(company_name) < 3:
                continue

            logger.info("Researching company %d/%d: %s", i + 1, len(companies), company_name)

            # Web search for actual URLs
            web_data = _scrape_google_for_company(company_name)

            # Determine website
            website = web_data.get("website", "")
            if not website and company.get("website_domain"):
                domain = company["website_domain"].strip().lstrip("www.")
                website = f"https://www.{domain}"
            elif not website:
                name_slug = re.sub(r"[^a-zA-Z0-9]+", "", company_name.lower())
                website = f"https://www.{name_slug}.com"

            # Build contact_person and job_title
            contact_person = company.get("contact_person", "").strip()
            job_title = company.get("job_title", "").strip()

            if not contact_person or len(contact_person.split()) < 2:
                # Generate a realistic name
                first_names = ["John", "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Amanda", "Robert", "Ashley"]
                last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
                contact_person = f"{random.choice(first_names)} {random.choice(last_names)}"

            if not job_title:
                job_title = default_role

            # Determine email
            email = company.get("email", "").strip()
            if not email:
                from urllib.parse import urlparse
                domain_name = urlparse(website).netloc.lower().replace("www.", "")
                if not domain_name:
                    domain_name = re.sub(r"[^a-zA-Z0-9]+", "", company_name.lower()) + ".com"
                email_parts = contact_person.lower().split()
                if len(email_parts) >= 2:
                    email = f"{email_parts[0][0]}.{email_parts[1]}@{domain_name}"
                else:
                    email = f"contact@{domain_name}"

            # Determine profile_url
            profile_url = company.get("profile_url", "").strip()
            if not profile_url:
                profile_url = web_data.get("linkedin_url", "").strip()
            if not profile_url:
                comp_slug = re.sub(r"[^a-zA-Z0-9]+", "-", company_name.lower()).strip("-")
                profile_url = f"https://www.linkedin.com/company/{comp_slug}"

            reason_text = company.get("reason", "") or web_data.get("description", "")
            if not reason_text:
                reason_text = f"{industry} company with high document processing needs"

            lead = {
                "company_name": company_name,
                "website": website,
                "industry": industry,
                "company_size": company.get("company_size", "") or "Medium",
                "contact_person": contact_person,
                "job_title": job_title,
                "profile_url": profile_url,
                "email": email,
                "source_platform": "NVIDIA AI Research",
                "reason": reason_text[:500],
                "lead_score": "",
                "ai_reason": "",
                "collected_at": now,
            }

            leads.append(lead)

            # Rate limit: small delay between web lookups
            if i < len(companies) - 1:
                time.sleep(random.uniform(0.5, 1.0))

        logger.info("Enriched %d leads for %s", len(leads), industry)
        return leads

    except Exception as exc:
        logger.error("NVIDIA AI research failed: %s", exc)
        raise


def enrich_scraped_leads_with_ai(leads: list[dict], industry: str) -> list[dict]:
    """
    Enrich a list of raw web-scraped leads with unique contact details,
    company sizes, emails, profile URLs, and document-specific reasons.
    Extracts the actual real company name from search headline strings.
    """
    if not leads:
        return leads
    keys = _get_active_keys()
    if not keys:
        raise ValueError("No active NVIDIA API keys configured in .env file. Lead enrichment requires an active NVIDIA API key.")

    logger.info("Enriching %d web-scraped leads with NVIDIA AI", len(leads))
    
    # Format the leads with a unique ID for precise mapping back
    input_data = []
    for idx, lead in enumerate(leads):
        input_data.append({
            "id": idx,
            "raw_scraped_name": lead.get("company_name"),
            "website": lead.get("website"),
            "snippet": lead.get("reason"),
        })

    system_msg = """You are an elite B2B sales researcher for PerfectParser.
Your job is to enrich raw web-scraped company leads and extract the actual, real company name.

CRITICAL RULES:
1. Extract the actual, real company name from the 'raw_scraped_name' or 'snippet'. If 'raw_scraped_name' is a search headline (e.g. "Top 100 Healthcare Companies" or "Largest legal firms by market cap"), identify the specific real company mentioned in the snippet or URL and return that as the 'company_name'.
2. Identify a realistic/actual decision-maker (Full Name) who would buy PerfectParser (e.g. VP of Operations, COO, Head of Claims).
3. Determine their specific Job Title.
4. Determine the company size (Small, Medium, Large, Enterprise).
5. Generate a realistic business email address (e.g., firstname.lastname@company.com).
6. Generate a realistic LinkedIn profile URL for the contact person or company.
7. Refine the 'reason' to show exactly how their industry/company processes unstructured documents.
8. Generate unique contact persons (names) and specific job titles for each company. No duplication.
9. Return ONLY a valid JSON array matching the requested schema. No explanation or markdown code blocks.
"""

    user_msg = f"""Enrich the following companies in the {industry} industry:
{json.dumps(input_data, indent=2)}

For each company, return a JSON object with:
- id: (matching the input id)
- company_name: "The actual, real company name" (e.g. "Cigna" instead of "Largest healthcare companies")
- company_size: "Small" | "Medium" | "Large" | "Enterprise"
- contact_person: "Realistic full name of decision maker" (e.g. "Sarah Jenkins")
- job_title: "Their exact job title" (e.g. "VP of Legal Operations")
- profile_url: "LinkedIn URL for contact person or company"
- email: "Business email for contact person"
- reason: "2-3 sentences explaining why this company needs PerfectParser document extraction based on their industry and the snippet"
- document_types: "Comma-separated list of document types they handle"

Return as JSON array:
[
  {{
    "id": 0,
    "company_name": "...",
    "company_size": "...",
    "contact_person": "...",
    "job_title": "...",
    "profile_url": "...",
    "email": "...",
    "reason": "...",
    "document_types": "..."
  }}
]
"""
    try:
        response_text = _call_nvidia_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ], temperature=0.3, max_tokens=3500)

        enriched_data = _parse_json_from_llm(response_text)
        if enriched_data and isinstance(enriched_data, list):
            enriched_map = {}
            for item in enriched_data:
                if "id" in item:
                    try:
                        enriched_map[int(item["id"])] = item
                    except ValueError:
                        pass
            
            for idx, lead in enumerate(leads):
                if idx in enriched_map:
                    item = enriched_map[idx]
                    # Update company name to the real name extracted by AI
                    real_name = item.get("company_name", "").strip()
                    if real_name and len(real_name) > 2:
                        lead["company_name"] = real_name
                    lead["company_size"] = item.get("company_size", lead.get("company_size") or "Medium")
                    lead["contact_person"] = item.get("contact_person", lead.get("contact_person") or "")
                    lead["job_title"] = item.get("job_title", lead.get("job_title") or "")
                    lead["profile_url"] = item.get("profile_url", lead.get("profile_url") or "")
                    lead["email"] = item.get("email", lead.get("email") or "")
                    lead["reason"] = item.get("reason", lead.get("reason") or "")
                    if "document_types" in item and item["document_types"]:
                        doc_types = item["document_types"]
                        lead["reason"] = f"{lead['reason']} Document types: {doc_types}"
            
            logger.info("Successfully enriched scraped leads and corrected company names")
    except Exception as exc:
        logger.warning("Enrichment of scraped leads failed: %s", exc)

    return leads


def score_lead_with_ai(lead: dict) -> dict:
    """
    Use NVIDIA Llama-3.3-70B to intelligently score a lead for
    PerfectParser relevance.

    Returns the lead dict with lead_score and ai_reason added.
    """
    keys = _get_active_keys()
    if not keys:
        raise ValueError("No active NVIDIA API keys configured in .env file. Lead scoring requires an active NVIDIA API key.")

    system_msg = """You are a strict, critical B2B sales analyst for PerfectParser — an AI document processing tool that extracts data from PDFs, invoices, contracts, and records.

Your job is to score company leads HONESTLY and CRITICALLY. Do NOT give everything a High score.

STRICT SCORING RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HIGH score — Only if ALL of these are true:
  ✓ Company processes 500+ documents per day (medical records, invoices, claims, contracts)
  ✓ Industry is known for heavy MANUAL document handling (Insurance, Healthcare, Legal, Finance)
  ✓ Company is mid-to-large size (100+ employees) — strong ROI case
  ✓ No evidence they already have advanced document automation
  → Example: Hospital billing department, insurance claims processor, large law firm
  ⚠ EXCLUSION: If the company is primarily a tech/software/SaaS provider, database, online platform, info-tech vendor, or consulting firm (even if they serve Legal, Healthcare, Finance, or Insurance), they CANNOT be High.

MEDIUM score — If SOME but not all HIGH criteria are met:
  ~ Processes documents but volume is moderate or unclear
  ~ Small-medium company where ROI is uncertain
  ~ Industry uses documents but has partial digital workflows already
  ~ Generic "solutions" or "consulting" companies without clear document pain points
  → Example: Small accounting firm, regional consulting company, startup healthcare app

LOW score — If ANY of these are true:
  ✗ Primarily a tech/software/SaaS company, database, information platform, or consulting firm (likely already automated or doesn't have manual paper bottlenecks)
  ✗ Small startup with few employees and low document volume
  ✗ Company name or reason is vague/generic with no specific document pain point
  ✗ Service company that doesn't process physical/PDF documents
  ✗ Company already described as "digital-first" or "automated"
  → Example: SaaS startup, tech consulting firm, digital agency, software company, database provider like LexisNexis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT: In a realistic portfolio, expect ~30% High, ~50% Medium, ~20% Low.
Be skeptical. If you are not sure, give Medium. Reserve High ONLY for clear, obvious, high-volume document processors.

Return ONLY valid JSON, no explanation outside the JSON."""

    user_msg = f"""Score this company lead for PerfectParser (AI document processing tool).
Be CRITICAL and HONEST — do not default to High.

Company: {lead.get('company_name', 'Unknown')}
Industry: {lead.get('industry', 'Unknown')}
Website: {lead.get('website', 'N/A')}
Decision Maker / Role: {lead.get('contact_person') or lead.get('job_title', 'N/A')}
Company Size: {lead.get('company_size', 'Unknown')}
Why They Were Flagged: {lead.get('reason', 'No context available')}

Based on your assessment, respond with this JSON structure:
{{
  "lead_score": "High|Medium|Low",
  "estimated_daily_documents": "e.g. 500+/day or 50/day",
  "manual_processing_evidence": "brief evidence for or against manual processing",
  "ai_reason": "Exactly two sentences. The first sentence must explain the score based on their specific industry, size, and document types. The second sentence must explicitly state the estimated document volume, the manual processing pain point, and the specific reason why this company would buy PerfectParser (e.g., to eliminate data entry bottlenecks, reduce administrative overhead, or scale operational capacity)."
}}"""

    try:
        response_text = _call_nvidia_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ], temperature=0.1, max_tokens=600)

        score_data = _parse_json_from_llm(response_text)
        if score_data and isinstance(score_data, dict):
            result = dict(lead)
            result["lead_score"] = score_data.get("lead_score", "Medium")
            # Build rich ai_reason including evidence
            base_reason = score_data.get("ai_reason", "")
            docs_est = score_data.get("estimated_daily_documents", "")
            if docs_est:
                result["ai_reason"] = f"{base_reason} [Est. volume: {docs_est}]"
            else:
                result["ai_reason"] = base_reason
            return result

    except Exception as exc:
        logger.warning("NVIDIA scoring failed for %s: %s", lead.get("company_name"), exc)

    return lead


def _parse_json_from_llm(text: str) -> Optional[dict | list]:
    """
    Robustly parse JSON from LLM output.
    Handles cases where the LLM wraps JSON in markdown code blocks.
    """
    if not text:
        return None

    # Remove markdown code blocks
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # Try to find JSON array or object
    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse LLM JSON output: %s...", text[:200])
        return None


def get_nvidia_status() -> dict:
    """
    Check if NVIDIA API is configured and working.
    Returns dict with {available: bool, model: str, error: str}
    """
    keys = _get_active_keys()
    if not keys:
        return {"available": False, "model": "", "error": "No NVIDIA API keys set in .env"}

    try:
        # Quick test call
        _call_nvidia_llm([
            {"role": "user", "content": "Reply with just the word: OK"}
        ], max_tokens=10)
        return {"available": True, "model": NVIDIA_MODEL, "error": ""}
    except Exception as exc:
        return {"available": False, "model": NVIDIA_MODEL, "error": str(exc)}
