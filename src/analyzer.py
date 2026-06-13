"""
============================================================
PerfectParser Lead Intelligence Platform
Lead Analysis & Scoring Module
============================================================
Scores and evaluates leads using:
  - NVIDIA NIM (Llama-3.3-70B) when NVIDIA_API_KEY is set
    → Real AI reasoning about each company's document needs
  - Keyword-based fallback when no API key is available
    → Fast, offline scoring using domain signals

The NVIDIA path produces much more accurate, company-specific
explanations compared to the generic keyword approach.
============================================================
"""

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
    return bool(os.getenv("NVIDIA_API_KEY", "").strip())


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
    if total >= 7 and not is_vague:
        lead_score = "High"
    elif total >= 4:
        lead_score = "Medium"
    else:
        lead_score = "Low"

    # Build reason
    reasons = []
    if ind_reason:
        reasons.append(ind_reason + ".")
    if high_matches:
        reasons.append(f"Key signals: {', '.join(high_matches[:3])}.")
    if size_reason:
        reasons.append(size_reason + ".")
    if is_vague:
        reasons.append("Generic company name — document pain point unclear.")
    if not reasons:
        reasons.append("Standard business profile — limited document processing evidence.")

    result = dict(lead)
    result["lead_score"] = lead_score
    result["ai_reason"] = " ".join(reasons)
    return result


# ── NVIDIA AI Scoring ─────────────────────────────────────────

def _nvidia_score(lead: dict) -> dict:
    """Use NVIDIA Llama-3.3-70B for intelligent lead scoring."""
    try:
        try:
            from src.nvidia_researcher import score_lead_with_ai
        except ImportError:
            from nvidia_researcher import score_lead_with_ai  # type: ignore
        return score_lead_with_ai(lead)
    except Exception as exc:
        logger.warning("NVIDIA scoring error for %s: %s", lead.get("company_name"), exc)
        return _keyword_score(lead)


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
        logger.info("Scoring '%s' with keyword algorithm (no NVIDIA key)", company)
        result = _keyword_score(lead)

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