"""
============================================================
PerfectParser Lead Intelligence Platform
Supabase Database Module
============================================================
Handles all CRUD operations against the Supabase 'leads' table.
Supports insert with duplicate avoidance, filtered reads,
analysis updates, and distinct-value lookups for dropdowns.
============================================================
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# ── Configuration ───────────────────────────────────────────
load_dotenv()
logger = logging.getLogger(__name__)

# Lazy-initialized Supabase client
_client: Optional[Client] = None

# Cached set of column names in the leads table (detected once)
_table_columns: Optional[set] = None


def _get_client() -> Client:
    """
    Lazily initialize and return the Supabase client.
    Raises RuntimeError if credentials are missing.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in your .env file. "
            "Get them from your Supabase project dashboard → Settings → API."
        )

    _client = create_client(url, key)
    logger.info("Supabase client initialized for %s", url)
    return _client


def _get_table_columns() -> set:
    """
    Auto-detect the columns available in the 'leads' table.
    This allows the code to work even if the table was created
    with an older schema missing some columns (e.g. lead_score, ai_reason).
    """
    global _table_columns
    if _table_columns is not None:
        return _table_columns

    client = _get_client()
    try:
        # Fetch one row to discover column names
        response = client.table("leads").select("*").limit(1).execute()
        if response.data:
            _table_columns = set(response.data[0].keys())
        else:
            # Table is empty — try inserting a minimal row and reading it back
            # Fallback: assume all columns exist
            _table_columns = {
                "id", "company_name", "website", "industry", "company_size",
                "contact_person", "job_title", "profile_url", "email",
                "source_platform", "reason", "lead_score", "ai_reason",
                "collected_at",
            }
        logger.info("Detected table columns: %s", _table_columns)
    except Exception as exc:
        logger.warning("Could not detect table columns: %s", exc)
        _table_columns = {
            "company_name", "website", "industry", "company_size",
            "contact_person", "job_title", "profile_url", "email",
            "source_platform", "reason",
        }
    return _table_columns


# ── Insert Operations ──────────────────────────────────────


def insert_lead(lead: dict) -> bool:
    """
    Insert a single lead into Supabase.
    Skips the insert if a lead with the same company_name already exists.

    Parameters
    ----------
    lead : dict
        Lead data matching the 'leads' table columns.

    Returns
    -------
    bool
        True if inserted, False if duplicate or error.
    """
    client = _get_client()

    try:
        # Check for existing entry with the same company name
        existing = (
            client.table("leads")
            .select("id")
            .eq("company_name", lead.get("company_name", ""))
            .limit(1)
            .execute()
        )

        if existing.data:
            logger.info("Duplicate skipped: %s", lead.get("company_name"))
            return False

        # Build a clean record with only the columns that exist in the table
        available_cols = _get_table_columns()
        all_fields = {
            "company_name": lead.get("company_name", ""),
            "website": lead.get("website", ""),
            "industry": lead.get("industry", ""),
            "company_size": lead.get("company_size", ""),
            "contact_person": lead.get("contact_person", ""),
            "job_title": lead.get("job_title", ""),
            "profile_url": lead.get("profile_url", ""),
            "email": lead.get("email", ""),
            "source_platform": lead.get("source_platform", ""),
            "reason": lead.get("reason", ""),
            "lead_score": lead.get("lead_score", ""),
            "ai_reason": lead.get("ai_reason", ""),
        }
        # Only include fields that exist as columns in the table
        record = {
            k: v for k, v in all_fields.items()
            if k in available_cols and k != "id"
        }

        client.table("leads").insert(record).execute()
        logger.info("Inserted lead: %s", lead.get("company_name"))
        return True

    except Exception as exc:
        logger.error("Insert error for '%s': %s", lead.get("company_name"), exc)
        return False


def insert_leads(leads: list[dict]) -> int:
    """
    Insert multiple leads, skipping duplicates.

    Returns
    -------
    int
        Number of leads successfully inserted.
    """
    count = 0
    for lead in leads:
        if insert_lead(lead):
            count += 1
    return count


# ── Update Operations ──────────────────────────────────────


def update_lead_analysis(
    company_name: str,
    lead_score: str,
    ai_reason: str,
) -> bool:
    """
    Update the lead_score and ai_reason for an existing lead.

    Parameters
    ----------
    company_name : str
        The company to update (matched exactly).
    lead_score : str
        New score value ("High", "Medium", or "Low").
    ai_reason : str
        AI-generated reasoning.

    Returns
    -------
    bool
        True if updated, False on error.
    """
    client = _get_client()
    available_cols = _get_table_columns()

    # Only update columns that exist in the table
    update_data = {}
    if "lead_score" in available_cols:
        update_data["lead_score"] = lead_score
    if "ai_reason" in available_cols:
        update_data["ai_reason"] = ai_reason

    if not update_data:
        logger.warning(
            "Cannot update analysis for '%s': lead_score/ai_reason columns "
            "not found in table. Run schema.sql to add them.", company_name
        )
        return False

    try:
        client.table("leads").update(
            update_data
        ).eq("company_name", company_name).execute()

        logger.info("Updated analysis for: %s → %s", company_name, lead_score)
        return True

    except Exception as exc:
        logger.error("Update error for '%s': %s", company_name, exc)
        return False


# ── Read Operations ─────────────────────────────────────────


def get_leads(
    industry: Optional[str] = None,
    lead_score: Optional[str] = None,
) -> list[dict]:
    """
    Fetch leads from Supabase with optional filters.

    Parameters
    ----------
    industry : str, optional
        Filter by industry (exact match).
    lead_score : str, optional
        Filter by lead_score (exact match).

    Returns
    -------
    list[dict]
        List of lead records.
    """
    client = _get_client()

    try:
        query = client.table("leads").select("*")

        if industry and industry != "All":
            query = query.eq("industry", industry)

        if lead_score and lead_score != "All":
            available_cols = _get_table_columns()
            if "lead_score" in available_cols:
                query = query.eq("lead_score", lead_score)

        # Order by most recent first
        query = query.order("collected_at", desc=True)

        response = query.execute()
        return response.data or []

    except Exception as exc:
        logger.error("Fetch error: %s", exc)
        return []


def get_industries() -> list[str]:
    """
    Return a sorted list of distinct industries present in the leads table.
    """
    client = _get_client()

    try:
        response = (
            client.table("leads")
            .select("industry")
            .execute()
        )

        industries = sorted({
            row["industry"]
            for row in (response.data or [])
            if row.get("industry")
        })
        return industries

    except Exception as exc:
        logger.error("Error fetching industries: %s", exc)
        return []


def get_lead_scores() -> list[str]:
    """
    Return a sorted list of distinct lead_score values present in the leads table.
    """
    # First check if the column exists at all
    available_cols = _get_table_columns()
    if "lead_score" not in available_cols:
        return []

    client = _get_client()

    try:
        response = (
            client.table("leads")
            .select("lead_score")
            .execute()
        )

        scores = sorted({
            row["lead_score"]
            for row in (response.data or [])
            if row.get("lead_score")
        })
        return scores

    except Exception as exc:
        logger.error("Error fetching lead scores: %s", exc)
        return []


def test_connection() -> bool:
    """
    Test the Supabase connection by running a simple query.
    """
    try:
        client = _get_client()
        client.table("leads").select("id").limit(1).execute()
        logger.info("Supabase connection test: SUCCESS")
        return True
    except Exception as exc:
        logger.error("Supabase connection test FAILED: %s", exc)
        return False