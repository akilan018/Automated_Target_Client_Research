"""
============================================================
PerfectParser Lead Intelligence Platform
Multi-Platform Lead Collection Module
============================================================
Collects potential leads from multiple public sources:
  - LinkedIn (company profiles)
  - X / Twitter (company accounts)
  - Reddit (company mentions)
  - Public Business Directories
  - Company Websites
All via DuckDuckGo site-scoped searches using BeautifulSoup.
============================================================
"""

import re
import time
import random
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

# ── Logger ──────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────
# Rotate User-Agent strings to reduce blocking risk
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

# Default request timeout (seconds)
REQUEST_TIMEOUT = 15

# Industries the platform supports
SUPPORTED_INDUSTRIES = [
    "Healthcare",
    "Legal",
    "Finance",
    "Real Estate",
    "Recruitment",
    "Logistics",
    "Insurance",
    "Education",
    "Government",
    "Manufacturing",
]

# ── Platform Definitions ────────────────────────────────────
# Each platform defines a name, site filter for DuckDuckGo,
# query templates, and how to label the source.

PLATFORMS = {
    "LinkedIn": {
        "label": "LinkedIn",
        "icon": "🔗",
        "site_filter": "site:linkedin.com/company",
        "queries": [
            "{industry} companies",
            "{industry} firms agencies",
        ],
        "description": "Company profiles from LinkedIn",
    },
    "X (Twitter)": {
        "label": "X (Twitter)",
        "icon": "🐦",
        "site_filter": "site:x.com OR site:twitter.com",
        "queries": [
            "{industry} company",
            "{industry} business official",
        ],
        "description": "Company accounts on X / Twitter",
    },
    "Reddit": {
        "label": "Reddit",
        "icon": "🤖",
        "site_filter": "site:reddit.com",
        "queries": [
            "{industry} companies recommendations",
            "best {industry} companies",
        ],
        "description": "Company discussions and mentions on Reddit",
    },
    "Business Directories": {
        "label": "Business Directories",
        "icon": "📒",
        "site_filter": "",
        "queries": [
            "{industry} companies directory list",
            "top {industry} companies 2024 2025",
            "{industry} business directory USA",
        ],
        "description": "Public business directories and company listings",
    },
    "Company Websites": {
        "label": "Company Websites",
        "icon": "🌐",
        "site_filter": "",
        "queries": [
            "{industry} company official website",
            "{industry} firm services about us",
            "{industry} agency solutions",
        ],
        "description": "Direct company websites",
    },
}

# Convenience list for UI
PLATFORM_NAMES = list(PLATFORMS.keys())


# ── Internal Helpers ────────────────────────────────────────

def _get_headers() -> dict:
    """Return HTTP headers with a randomly selected User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _clean_company_name(raw: str) -> str:
    """
    Strip noise from a raw company-name string scraped from HTML.
    Removes excess whitespace, trailing dashes, and common suffixes.
    """
    name = re.sub(r"\s+", " ", raw).strip()
    # Remove trailing " - Some description" patterns
    name = re.split(r"\s*[-–—|]\s*", name)[0].strip()
    # Remove common prefixes like "r/" for Reddit
    name = re.sub(r"^r/", "", name).strip()
    # Drop empty or very short results
    return name if len(name) > 2 else ""


def _extract_url_from_duckduckgo_href(href: str) -> str:
    """
    DuckDuckGo wraps outbound links through a redirect.
    Extract the actual destination URL.
    """
    if "uddg=" in href:
        match = re.search(r"uddg=([^&]+)", href)
        if match:
            return unquote(match.group(1))
    return href


def _extract_domain(url: str) -> str:
    """Return the domain (netloc) of a URL for dedup purposes."""
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return url


def _detect_platform_from_url(url: str) -> str:
    """Detect which platform a URL belongs to based on its domain."""
    domain = _extract_domain(url)
    if "linkedin.com" in domain:
        return "LinkedIn"
    elif "x.com" in domain or "twitter.com" in domain:
        return "X (Twitter)"
    elif "reddit.com" in domain:
        return "Reddit"
    else:
        return "Website"


def _is_skip_domain(domain: str) -> bool:
    """Check if a domain should be skipped (search engines, generic sites)."""
    skip = {
        "duckduckgo.com", "google.com", "youtube.com",
        "facebook.com", "instagram.com", "wikipedia.org",
        "pinterest.com", "tiktok.com", "bing.com",
        "yahoo.com", "amazon.com", "ebay.com",
    }
    return domain in skip


def _scrape_duckduckgo(query: str, industry: str, source_label: str) -> list[dict]:
    """
    Scrape DuckDuckGo HTML search results for a given query.

    Parameters
    ----------
    query : str
        The full search query (may include site: filters).
    industry : str
        The target industry to tag results with.
    source_label : str
        The source platform label (e.g. "LinkedIn", "Reddit").

    Returns
    -------
    list[dict]
        Lead dicts extracted from search results.
    """
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    headers = _get_headers()

    response = requests.post(
        url,
        data=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    # DuckDuckGo HTML results are in <a class="result__a"> tags
    for link_tag in soup.select("a.result__a"):
        href = link_tag.get("href", "")
        raw_name = link_tag.get_text(strip=True)

        if not href or not raw_name:
            continue

        # Extract actual URL from DuckDuckGo redirect
        actual_url = _extract_url_from_duckduckgo_href(href)

        # Skip non-http links
        if not actual_url.startswith("http"):
            continue

        domain = _extract_domain(actual_url)
        if _is_skip_domain(domain):
            continue

        company_name = _clean_company_name(raw_name)
        if not company_name:
            continue

        # Detect actual platform from URL
        detected_platform = _detect_platform_from_url(actual_url)

        # Build the profile_url for social platforms, website for others
        profile_url = ""
        website = actual_url
        if detected_platform in ("LinkedIn", "X (Twitter)", "Reddit"):
            profile_url = actual_url
            website = ""  # Will be filled by the company's actual site if found

        # Extract snippet/description for context
        snippet_tag = link_tag.find_parent("div", class_="result")
        snippet = ""
        if snippet_tag:
            snippet_el = snippet_tag.select_one(".result__snippet")
            if snippet_el:
                snippet = snippet_el.get_text(strip=True)

        results.append({
            "company_name": company_name,
            "website": website,
            "industry": industry,
            "company_size": "",
            "contact_person": "",
            "job_title": "",
            "profile_url": profile_url,
            "email": "",
            "source_platform": source_label,
            "reason": snippet[:200] if snippet else "",
            "collected_at": now,
        })

    return results


# ── Public API ──────────────────────────────────────────────


def collect_leads(industry: str, max_results: int = 15) -> list[dict]:
    """
    Collect leads for a given industry from all platforms.
    Backward-compatible wrapper around collect_leads_multi().
    """
    return collect_leads_multi(
        industry=industry,
        platforms=list(PLATFORMS.keys()),
        max_results=max_results,
    )


def collect_leads_multi(
    industry: str,
    platforms: list[str],
    max_results: int = 15,
) -> list[dict]:
    """
    Collect leads for a given industry from selected platforms.

    Parameters
    ----------
    industry : str
        The target industry (e.g. "Healthcare", "Legal").
    platforms : list[str]
        List of platform names to search (from PLATFORM_NAMES).
    max_results : int
        Maximum total number of leads to return.

    Returns
    -------
    list[dict]
        A list of lead dictionaries with all available fields.
    """
    leads: list[dict] = []
    seen_domains: set[str] = set()
    seen_names: set[str] = set()

    for platform_name in platforms:
        if len(leads) >= max_results:
            break

        platform = PLATFORMS.get(platform_name)
        if not platform:
            logger.warning("Unknown platform: %s", platform_name)
            continue

        site_filter = platform["site_filter"]
        source_label = platform["label"]

        for query_template in platform["queries"]:
            if len(leads) >= max_results:
                break

            # Build the full query with optional site: filter
            base_query = query_template.format(industry=industry)
            full_query = f"{site_filter} {base_query}".strip() if site_filter else base_query

            try:
                new_leads = _scrape_duckduckgo(full_query, industry, source_label)

                for lead in new_leads:
                    # Deduplicate by domain and by company name
                    domain = _extract_domain(lead["website"] or lead["profile_url"])
                    name_key = lead["company_name"].lower().strip()

                    if domain and domain in seen_domains:
                        continue
                    if name_key in seen_names:
                        continue

                    if domain:
                        seen_domains.add(domain)
                    seen_names.add(name_key)
                    leads.append(lead)

                    if len(leads) >= max_results:
                        break

            except Exception as exc:
                logger.warning(
                    "Query failed [%s]: '%s' — %s",
                    source_label, full_query[:60], exc,
                )

            # Polite delay between requests
            time.sleep(random.uniform(1.0, 2.5))

    logger.info(
        "Collected %d leads for '%s' from %d platform(s)",
        len(leads), industry, len(platforms),
    )
    return leads