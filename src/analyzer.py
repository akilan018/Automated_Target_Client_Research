import os
import re
import json
import random
import logging
from datetime import datetime, timezone

# ── Logger ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Check if NVIDIA is available ─────────────────────────────
def _has_nvidia_key() -> bool:
    from dotenv import load_dotenv
    load_dotenv()
    try:
        from src.nvidia_researcher import _get_active_keys
    except ImportError:
        from nvidia_researcher import _get_active_keys  # type: ignore
    return len(_get_active_keys()) > 0


# ── Keyword-Based Scoring (Fallback) ─────────────────────────

HIGH_DOC_INDUSTRIES = {
    "healthcare", "legal", "finance", "insurance", "government",
    "banking", "pharmaceutical", "medical", "law", "accounting",
    "compliance", "regulatory", "tax", "audit",
}

MEDIUM_DOC_INDUSTRIES = {
    "real estate", "recruitment", "logistics", "education",
    "manufacturing", "consulting", "engineering", "construction",
    "shipping", "human resources", "staffing",
}

HIGH_SIGNAL_KEYWORDS = [
    "document", "pdf", "invoice", "contract", "report", "compliance",
    "records", "filing", "paperwork", "forms", "certificate",
    "license", "permit", "claims", "billing", "processing",
    "digitization", "scanning", "archive", "medical records",
    "legal documents", "regulatory", "audit", "tax filing",
    "patient records", "case files", "mortgage", "loan",
    "insurance claims", "policy documents",
]

MEDIUM_SIGNAL_KEYWORDS = [
    "enterprise", "solutions", "management", "system", "platform",
    "services", "consulting", "automation", "workflow", "data",
    "analytics", "software", "technology", "digital", "cloud",
    "saas", "b2b", "operations",
]

SIZE_INDICATORS = {
    "large": ["fortune", "global", "international", "multinational",
              "enterprise", "corporation", "1000+", "5000+", "10000+"],
    "medium": ["mid-size", "regional", "national", "500+", "growing"],
    "small": ["startup", "small", "local", "boutique", "solo"],
}


def _keyword_score(lead: dict) -> dict:
    """Fast keyword-based scoring (no API needed). Conservative — avoids over-scoring."""
    combined = " ".join([
        lead.get("company_name", ""),
        lead.get("industry", ""),
        lead.get("website", ""),
        lead.get("reason", ""),
        lead.get("job_title", ""),
    ]).lower()

    company_name = lead.get("company_name", "").lower()

    # Penalty: generic / vague company names get capped at Medium
    vague_signals = ["solutions", "consulting", "services", "group", "associates",
                     "management", "systems", "technologies", "tech", "digital"]
    is_vague = sum(1 for v in vague_signals if v in company_name) >= 2

    # Exclusion/Penalty: Tech, SaaS, databases, software, or analytics providers should not get high scores
    tech_keywords = ["software", "saas", "digital", "platform", "online", "database", "analytics", "app", "tech", "technology"]
    is_tech = any(tk in company_name for tk in tech_keywords) or \
              any(tk in lead.get("reason", "").lower() for tk in ["software company", "saas platform", "database provider", "digital analytics", "software platform"])

    # Industry score — base points only, not enough alone for High
    industry = lead.get("industry", "").lower()
    ind_score = 0
    ind_reason = ""
    for kw in HIGH_DOC_INDUSTRIES:
        if kw in industry:
            ind_score = 2  # was 3 — reduced; needs keyword confirmation
            ind_reason = f"{lead.get('industry', 'This industry')} is document-intensive"
            break
    if ind_score == 0:
        for kw in MEDIUM_DOC_INDUSTRIES:
            if kw in industry:
                ind_score = 1
                ind_reason = f"{lead.get('industry', 'This industry')} has moderate document needs"
                break

    # Keyword score — specific document signals required for High
    high_matches = [kw for kw in HIGH_SIGNAL_KEYWORDS if kw in combined]
    med_matches = [kw for kw in MEDIUM_SIGNAL_KEYWORDS if kw in combined]
    kw_score = min(len(high_matches) * 2, 5) + min(len(med_matches), 2)

    # Size score
    size_score = 0
    size_reason = ""
    company_size = lead.get("company_size", "").lower()
    if company_size in ("large", "enterprise") or any(s in combined for s in SIZE_INDICATORS["large"]):
        size_score = 2
        size_reason = "Large enterprise with high document volume"
    elif company_size == "medium" or any(s in combined for s in SIZE_INDICATORS["medium"]):
        size_score = 1
        size_reason = "Mid-size company with growing document needs"

    total = ind_score + kw_score + size_score

    # Stricter thresholds (was >=5 High, >=3 Medium)
    if total >= 7 and not is_vague and not is_tech:
        lead_score = "High"
    elif total >= 4 and not is_tech:
        lead_score = "Medium"
    else:
        lead_score = "Low"

    # Build a descriptive, dynamic buying rationale based on score
    industry_display = lead.get("industry") or "target"
    size_display = lead.get("company_size") or "unknown size"
    
    # Identify what kind of document types are relevant
    if high_matches:
        doc_signals = f"document operations involving {', '.join(high_matches[:3])}"
    else:
        doc_signals = "manual document and data entry operations"

    if lead_score == "High":
        rationale = (
            f"This High-score {industry_display} enterprise/company is a prime candidate for PerfectParser "
            f"due to intensive {doc_signals}. They would buy PerfectParser to eliminate expensive, "
            f"error-prone manual data extraction, accelerate document processing cycles, and achieve "
            f"immediate ROI by automating their high-volume workflows."
        )
    elif lead_score == "Medium":
        rationale = (
            f"Operating as a {size_display.lower()} firm in the {industry_display} sector, this company likely "
            f"has moderate manual workflow needs ({doc_signals}). They would buy PerfectParser to reduce "
            f"administrative overhead and streamline data ingestion, though the exact ROI will depend on their "
            f"actual daily document volumes."
        )
    else:
        # Low score
        if is_vague:
            rationale = (
                f"This company has a generic profile with unclear document pain points. They would only buy "
                f"PerfectParser to address isolated backend automation needs, resulting in a low immediate ROI."
            )
        else:
            rationale = (
                f"With limited indicators of intensive document processing, this {industry_display} company is a "
                f"low-priority lead. They would buy PerfectParser only for occasional document ingestion or "
                f"minor digitizing tasks, as they lack high-volume manual paperwork bottlenecks."
            )

    result = dict(lead)
    result["lead_score"] = lead_score
    result["ai_reason"] = rationale
    return result


# ── NVIDIA AI Scoring ─────────────────────────────────────────

def _nvidia_score(lead: dict) -> dict:
    """Use NVIDIA Llama-3.3-70B for intelligent lead scoring."""
    try:
        from src.nvidia_researcher import score_lead_with_ai
    except ImportError:
        from nvidia_researcher import score_lead_with_ai  # type: ignore
    return score_lead_with_ai(lead)


# ── Public API ────────────────────────────────────────────────

def analyze_lead(lead: dict) -> dict:
    """
    Analyze a single lead and assign a lead_score + ai_reason.

    Uses NVIDIA Llama-3.3-70B if NVIDIA_API_KEY is configured,
    otherwise falls back to keyword-based scoring.

    Parameters
    ----------
    lead : dict
        Lead data with keys like company_name, industry, website, reason.

    Returns
    -------
    dict
        The same lead dict with lead_score and ai_reason added.
    """
    company = lead.get("company_name", "Unknown")

    if _has_nvidia_key():
        logger.info("Scoring '%s' with NVIDIA Llama-3.3-70B", company)
        result = _nvidia_score(lead)
    else:
        raise ValueError("No active NVIDIA API keys configured in .env file. Lead scoring requires an active NVIDIA API key.")

    logger.info(
        "Lead scored: '%s' → %s",
        company,
        result.get("lead_score", "Unknown"),
    )
    return result


def analyze_leads(leads: list[dict]) -> list[dict]:
    """
    Analyze a list of leads. Returns scored results.
    Uses NVIDIA AI if available, keyword fallback otherwise.
    """
    results = []
    for lead in leads:
        result = analyze_lead(lead)
        results.append(result)
    return results
