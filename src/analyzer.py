"""
============================================================
PerfectParser Lead Intelligence Platform
Lead Analysis Module (Keyword-Based — No API Key Required)
============================================================
Scores and evaluates leads using a keyword-based algorithm
that checks industry fit, company indicators, and document-
processing need signals. No external API keys needed.
============================================================
"""

import re
import random
import logging
from datetime import datetime, timezone

# ── Logger ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Scoring Configuration ───────────────────────────────────

# Industries with HIGH document processing needs
HIGH_DOC_INDUSTRIES = {
    "healthcare", "legal", "finance", "insurance", "government",
    "banking", "pharmaceutical", "medical", "law", "accounting",
    "compliance", "regulatory", "tax", "audit",
}

# Industries with MEDIUM document processing needs
MEDIUM_DOC_INDUSTRIES = {
    "real estate", "recruitment", "logistics", "education",
    "manufacturing", "consulting", "engineering", "construction",
    "shipping", "human resources", "staffing",
}

# Keywords that signal high document processing needs
HIGH_SIGNAL_KEYWORDS = [
    "document", "pdf", "invoice", "contract", "report", "compliance",
    "records", "filing", "paperwork", "forms", "certificate",
    "license", "permit", "claims", "billing", "processing",
    "digitization", "scanning", "archive", "medical records",
    "legal documents", "regulatory", "audit", "tax filing",
    "patient records", "case files", "mortgage", "loan",
    "insurance claims", "policy documents",
]

# Keywords that signal medium document processing needs
MEDIUM_SIGNAL_KEYWORDS = [
    "enterprise", "solutions", "management", "system", "platform",
    "services", "consulting", "automation", "workflow", "data",
    "analytics", "software", "technology", "digital", "cloud",
    "saas", "b2b", "operations",
]

# Company size indicators (larger companies = more documents)
SIZE_INDICATORS = {
    "large": ["fortune", "global", "international", "multinational",
              "enterprise", "corporation", "1000+", "5000+", "10000+"],
    "medium": ["mid-size", "regional", "national", "500+", "growing"],
    "small": ["startup", "small", "local", "boutique", "solo"],
}


def _calculate_industry_score(industry: str) -> tuple[int, str]:
    """Score based on industry relevance to document processing."""
    industry_lower = industry.lower().strip()

    for keyword in HIGH_DOC_INDUSTRIES:
        if keyword in industry_lower:
            return 3, f"{industry} is a document-intensive industry"

    for keyword in MEDIUM_DOC_INDUSTRIES:
        if keyword in industry_lower:
            return 2, f"{industry} has moderate document processing needs"

    return 1, f"{industry} has standard document processing needs"


def _calculate_keyword_score(text: str) -> tuple[int, list[str]]:
    """Score based on keyword matches in company info."""
    text_lower = text.lower()
    high_matches = [kw for kw in HIGH_SIGNAL_KEYWORDS if kw in text_lower]
    medium_matches = [kw for kw in MEDIUM_SIGNAL_KEYWORDS if kw in text_lower]

    score = 0
    score += min(len(high_matches) * 2, 6)  # Max 6 from high keywords
    score += min(len(medium_matches), 3)     # Max 3 from medium keywords

    return score, high_matches + medium_matches


def _calculate_size_score(text: str) -> tuple[int, str]:
    """Score based on company size (larger = more document needs)."""
    text_lower = text.lower()

    for indicator in SIZE_INDICATORS["large"]:
        if indicator in text_lower:
            return 2, "Large enterprise with high document volume"

    for indicator in SIZE_INDICATORS["medium"]:
        if indicator in text_lower:
            return 1, "Mid-size company with growing document needs"

    return 0, ""


def _determine_score(total_points: int) -> str:
    """Convert numerical points to High/Medium/Low label."""
    if total_points >= 5:
        return "High"
    elif total_points >= 3:
        return "Medium"
    else:
        return "Low"


def analyze_lead(lead: dict) -> dict:
    """
    Analyze a single lead and assign a lead_score + ai_reason.
    Uses keyword-based scoring — no external API required.

    Parameters
    ----------
    lead : dict
        Lead data with keys like company_name, industry, website, reason.

    Returns
    -------
    dict
        The same lead dict with lead_score and ai_reason added.
    """
    # Build a combined text blob for keyword analysis
    combined_text = " ".join([
        lead.get("company_name", ""),
        lead.get("industry", ""),
        lead.get("website", ""),
        lead.get("reason", ""),
        lead.get("job_title", ""),
    ])

    # Calculate scores from multiple signals
    industry_score, industry_reason = _calculate_industry_score(
        lead.get("industry", "")
    )
    keyword_score, matched_keywords = _calculate_keyword_score(combined_text)
    size_score, size_reason = _calculate_size_score(combined_text)

    # Total score
    total = industry_score + keyword_score + size_score
    lead_score = _determine_score(total)

    # Build dynamic natural-sounding reason
    industry_templates = [
        "As a company in the {industry} sector, they likely deal with high volumes of documents.",
        "Operating in {industry} usually requires significant paperwork and compliance.",
        "The {industry} space is traditionally document-heavy, making them a strong candidate.",
        "Given their focus on {industry}, they could benefit greatly from automated processing."
    ]
    
    keyword_templates = [
        "We noticed signals indicating {keywords} needs.",
        "Their profile mentions {keywords}, which aligns with PerfectParser's capabilities.",
        "Keywords like {keywords} suggest an immediate need for digitization.",
        "Signals such as {keywords} highlight potential workflow bottlenecks we can solve."
    ]
    
    reasons = []
    
    # Add industry reason if relevant (score > 1)
    if industry_score > 1:
        ind_name = lead.get("industry", "this industry") or "this industry"
        reasons.append(random.choice(industry_templates).format(industry=ind_name))
    elif industry_reason:
        reasons.append(industry_reason)
        
    # Add keyword reason if relevant
    if matched_keywords:
        kw_str = ", ".join(matched_keywords[:3])
        reasons.append(random.choice(keyword_templates).format(keywords=kw_str))
        
    # Add size reason if relevant
    if size_reason:
        reasons.append(size_reason)
        
    # Fallback if no strong signals
    if not reasons:
        reasons.append("Standard business profile with potential general document needs.")

    ai_reason = " ".join(reasons)

    # Update the lead dict
    result = dict(lead)
    result["lead_score"] = lead_score
    result["ai_reason"] = ai_reason

    logger.info(
        "Scored '%s': %s (points=%d)",
        lead.get("company_name", "Unknown"),
        lead_score,
        total,
    )

    return result


def analyze_leads(leads: list[dict]) -> list[dict]:
    """
    Analyze a list of leads and return scored results.

    Parameters
    ----------
    leads : list[dict]
        List of lead dictionaries.

    Returns
    -------
    list[dict]
        Same leads with lead_score and ai_reason fields added.
    """
    results = []
    for lead in leads:
        result = analyze_lead(lead)
        results.append(result)
    return results