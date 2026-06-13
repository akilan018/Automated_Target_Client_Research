"""
============================================================
AUTOMATED TARGET CLIENT RESEARCHER
Main Streamlit Application
============================================================
A modern dashboard for collecting, analyzing, storing, and
reporting on potential leads for PerfectParser — an AI-powered
document processing tool.

Run with:  streamlit run app.py
============================================================
"""

import os
import time
import logging
import streamlit as st
import pandas as pd
from datetime import datetime

from src.scraper import (
    collect_leads_multi,
    SUPPORTED_INDUSTRIES,
    PLATFORMS,
    PLATFORM_NAMES,
)
from src.nvidia_researcher import get_nvidia_status
from src.analyzer import analyze_lead
from src.supabase_db import (
    insert_leads,
    get_leads,
    get_industries,
    get_lead_scores,
    update_lead_analysis,
)
from src.pdf_generator import generate_report
from src.pdf_parser import parse_pdf_for_leads

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-7s  %(message)s",
)

# ── Page Config ─────────────────────────────────────────────
st.set_page_config(
    page_title="AUTOMATED TARGET CLIENT RESEARCHER",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────
st.markdown("""
<style>
/* ── Import Google Font ─────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Global ─────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stText {
    font-family: 'Inter', sans-serif;
}

/* ── Sidebar ────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {
    color: #e8e8e8 !important;
}
section[data-testid="stSidebar"] .stRadio label {
    font-size: 1.05rem;
    padding: 6px 0;
}

/* ── Page Header ─────────────────────────────────────────── */
.main-header {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem;
}
.sub-header {
    opacity: 0.7;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* ── Metric Cards ───────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: rgba(108, 99, 255, 0.05);
    border: 1px solid rgba(108, 99, 255, 0.1);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: transform 0.2s, box-shadow 0.2s;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(108,99,255,0.15);
}

/* ── Score Badges ───────────────────────────────────────── */
.score-high {
    background: #dcfce7; color: #166534;
    padding: 3px 10px; border-radius: 20px;
    font-weight: 600; font-size: 0.85rem;
}
.score-medium {
    background: #fef9c3; color: #854d0e;
    padding: 3px 10px; border-radius: 20px;
    font-weight: 600; font-size: 0.85rem;
}
.score-low {
    background: #fee2e2; color: #991b1b;
    padding: 3px 10px; border-radius: 20px;
    font-weight: 600; font-size: 0.85rem;
}

/* ── Upload Area ────────────────────────────────────────── */
.upload-area {
    border: 2px dashed #3b82f6;
    border-radius: 16px;
    padding: 2rem;
    text-align: center;
    background: rgba(59, 130, 246, 0.05);
    font-size: 1rem;
    margin-bottom: 1rem;
}

/* ── Platform Cards ─────────────────────────────────────── */
.platform-info {
    background: rgba(108, 99, 255, 0.05);
    border: 1px solid rgba(108, 99, 255, 0.1);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 4px 0;
    font-size: 0.9rem;
}

/* ── Buttons ────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(108,99,255,0.25);
}

/* ── DataFrames ─────────────────────────────────────────── */
.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)


# ── Cached helpers ──────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)   # cache 5 min
def _cached_nvidia_status():
    """Cache NVIDIA status so we don't make an LLM call on every rerun."""
    return get_nvidia_status()


@st.cache_data(ttl=60, show_spinner=False)     # cache 1 min
def _cached_get_leads(**kwargs):
    """Cache lead fetches to avoid hitting Supabase on every rerun."""
    return get_leads(**kwargs)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_get_industries():
    return get_industries()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_get_lead_scores():
    return get_lead_scores()


# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 CLIENT RESEARCHER")
    st.markdown("**AUTOMATED TARGET SYSTEM**")
    st.divider()

    page = st.radio(
        "Navigation",
        options=[
            "📊 Dashboard",
            "🌐 Collect Leads",
            "📎 Upload PDF",
            "🤖 Analyze Leads",
            "💾 Stored Leads",
            "📄 Reports",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("© 2026 AUTOMATED TARGET CLIENT RESEARCHER")


# ── Helper: safe column display ─────────────────────────────
def _safe_cols(df: pd.DataFrame, desired: list[str]) -> list[str]:
    """Return only the columns that exist in the DataFrame."""
    return [c for c in desired if c in df.columns]


# ════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown('<p class="main-header">Lead Intelligence Dashboard</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Real-time overview of your lead pipeline</p>', unsafe_allow_html=True)

    all_leads = _cached_get_leads()

    if all_leads:
        total = len(all_leads)
        high = sum(1 for l in all_leads if l.get("lead_score") == "High")
        medium = sum(1 for l in all_leads if l.get("lead_score") == "Medium")
        low = sum(1 for l in all_leads if l.get("lead_score") == "Low")
        unscored = total - high - medium - low

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Leads", total)
        col2.metric("🟢 High Score", high)
        col3.metric("🟡 Medium Score", medium)
        col4.metric("🔴 Low Score", low)
        col5.metric("⚪ Unscored", unscored)

        st.divider()

        df = pd.DataFrame(all_leads)

        st.subheader("🏆 Top Potential Buyers")
        st.caption("Companies most likely to purchase PerfectParser — ranked by score, with the key decision-maker who would approve the purchase")

        buyer_df = df.copy()

        # Build a "Decision Maker" column — never empty
        # Priority: contact_person → job_title → industry-based default
        industry_defaults = {
            "Healthcare":    "Chief Operating Officer (COO)",
            "Legal":         "Head of Digital Transformation",
            "Finance":       "VP of Operations / CFO",
            "Insurance":     "VP of Operations",
            "Logistics":     "Operations Director",
            "Recruitment":   "Head of Talent Operations",
            "Real Estate":   "Director of Operations",
            "Education":     "Director of Administration",
            "Government":    "Chief Information Officer (CIO)",
            "Manufacturing": "VP of Operations",
        }

        def _decision_maker(row):
            # Use str() to safely handle NaN floats from pandas
            cp = str(row.get("contact_person") or "").strip()
            jt = str(row.get("job_title") or "").strip()
            if cp and cp.lower() not in ("nan", "none", ""):
                return cp
            if jt and jt.lower() not in ("nan", "none", ""):
                return jt
            return industry_defaults.get(str(row.get("industry", "")), "VP of Operations")

        def _why_buy(row):
            ai = str(row.get("ai_reason") or "").strip()
            reason = str(row.get("reason") or "").strip()
            if ai and ai.lower() not in ("nan", "none", ""):
                return ai[:200]
            if reason and reason.lower() not in ("nan", "none", ""):
                return reason.split("| Buyer:")[0].strip()[:200]
            return "High document processing volume — strong candidate for automation"

        buyer_df["Decision Maker"] = buyer_df.apply(_decision_maker, axis=1)
        buyer_df["Why Buy PerfectParser?"] = buyer_df.apply(_why_buy, axis=1)

        # Sort High → Medium → Low
        score_order = {"High": 0, "Medium": 1, "Low": 2}
        if "lead_score" in buyer_df.columns:
            buyer_df["_rank"] = buyer_df["lead_score"].map(score_order).fillna(3)
            buyer_df = buyer_df.sort_values("_rank").drop(columns=["_rank"])

        display_buyer = buyer_df[[
            "company_name", "Decision Maker", "industry",
            "lead_score", "Why Buy PerfectParser?", "website",
        ]].rename(columns={
            "company_name": "🏢 Company",
            "industry":     "🏭 Industry",
            "lead_score":   "🎯 Score",
            "website":      "🌐 Website",
        }).head(20)

        st.dataframe(display_buyer, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🕐 Recently Added Leads")
        recent_cols = _safe_cols(df, ["company_name", "contact_person", "job_title", "industry", "lead_score", "ai_reason", "source_platform", "website", "collected_at"])
        st.dataframe(df.head(10)[recent_cols], use_container_width=True, hide_index=True)

    else:
        st.info(
            "👋 No leads found yet. Head to **Collect Leads** or **Upload PDF** to get started!",
            icon="ℹ️",
        )


# ════════════════════════════════════════════════════════════
# PAGE: Collect Leads (Multi-Platform)
# ════════════════════════════════════════════════════════════
elif page == "🌐 Collect Leads":
    st.markdown('<p class="main-header">Collect Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Discover potential customers from multiple platforms</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_industry = st.selectbox(
            "🏭 Select Target Industry",
            options=SUPPORTED_INDUSTRIES,
            index=0,
        )

    with col2:
        max_leads = st.slider("Max leads", min_value=5, max_value=30, value=15)

    st.subheader("🌍 Select Platforms")
    st.caption("Choose which platforms to search for leads")

    platform_cols = st.columns(min(len(PLATFORM_NAMES), 3))
    selected_platforms: list[str] = []

    for i, pname in enumerate(PLATFORM_NAMES):
        pinfo = PLATFORMS[pname]
        col_idx = i % 3
        with platform_cols[col_idx]:
            is_ai = pinfo.get("is_ai", False)
            default_checked = True
            if is_ai and not _cached_nvidia_status()["available"]:
                default_checked = False
            checked = st.checkbox(
                f"{pinfo['icon']} {pinfo['label']}",
                value=default_checked,
                key=f"platform_{pname}",
                help=pinfo.get("description", ""),
            )
            if checked:
                selected_platforms.append(pname)

    st.divider()

    if not selected_platforms:
        st.warning("Please select at least one platform.")
    else:
        platform_labels = ", ".join(selected_platforms)

        if st.button("🔍 Collect Leads", type="primary", use_container_width=True):
            with st.spinner(f"Searching {len(selected_platforms)} platform(s) for {selected_industry} companies..."):
                leads = collect_leads_multi(
                    industry=selected_industry,
                    platforms=selected_platforms,
                    max_results=max_leads,
                )

            if leads:
                st.session_state["collected_leads"] = leads
                st.success(f"✅ Found **{len(leads)}** leads across {platform_labels}!")
            else:
                st.warning("No leads found. Try different platforms or industry.")

    if "collected_leads" in st.session_state and st.session_state["collected_leads"]:
        leads = st.session_state["collected_leads"]
        df = pd.DataFrame(leads)

        st.subheader(f"📋 Collected Leads ({len(leads)})")

        if "source_platform" in df.columns:
            platform_counts = df["source_platform"].value_counts()
            pcols = st.columns(len(platform_counts))
            for i, (platform, count) in enumerate(platform_counts.items()):
                pcols[i].metric(platform, count)

        display_cols = _safe_cols(df, [
            "company_name", "website", "industry", "source_platform",
            "profile_url", "reason", "collected_at",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        st.divider()
        if st.button("💾 Store in Supabase", type="secondary", use_container_width=True):
            with st.spinner("Storing leads in Supabase..."):
                count = insert_leads(leads)
            _cached_get_leads.clear()  # refresh cache after write
            if count > 0:
                st.success(f"✅ **{count}** new leads stored in Supabase!")
            else:
                st.info("No new leads to store (all duplicates or already exist).")


# ════════════════════════════════════════════════════════════
# PAGE: Upload PDF
# ════════════════════════════════════════════════════════════
elif page == "📎 Upload PDF":
    st.markdown('<p class="main-header">Upload PDF</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Extract leads from PDF documents using our local parser</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="upload-area">
        📎 Upload a PDF containing company information, business directories,
        contact lists, or industry reports. Our algorithm will extract potential leads automatically.
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        accept_multiple_files=False,
        help="Upload a PDF file containing business/company information",
    )

    context = st.text_input(
        "🔍 Additional context (optional)",
        placeholder="e.g. 'Healthcare companies in USA', 'Law firms', 'Tech startups'",
        help="Provide context to help better identify leads from the document",
    )

    st.divider()

    if uploaded_file is not None:
        st.info(f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

        col_step1, col_step2 = st.columns(2)

        with col_step1:
            if st.button("📝 Step 1: Extract Text", type="secondary", use_container_width=True):
                try:
                    from src.pdf_parser import extract_text_from_pdf
                    with st.spinner("Extracting text from PDF..."):
                        text = extract_text_from_pdf(uploaded_file)
                    if text.strip():
                        st.session_state["pdf_text"] = text
                        st.success(f"✅ Extracted {len(text):,} characters from {uploaded_file.name}")
                    else:
                        st.warning("No text found in this PDF. It may be image-based (scanned).")
                except Exception as exc:
                    st.error(f"❌ Text extraction failed: {exc}")

        with col_step2:
            if st.button("🤖 Step 2: Find Leads", type="primary", use_container_width=True):
                try:
                    with st.spinner("Analyzing text for leads..."):
                        uploaded_file.seek(0)
                        leads = parse_pdf_for_leads(uploaded_file, context=context)

                    if leads:
                        st.session_state["pdf_leads"] = leads
                        st.success(f"✅ Extracted **{len(leads)}** leads from the PDF!")
                    else:
                        st.warning(
                            "No leads could be identified in this PDF. "
                            "Try providing additional context or uploading a different document."
                        )
                except Exception as exc:
                    st.error(f"❌ Unexpected error: {exc}")

        if "pdf_text" in st.session_state and st.session_state["pdf_text"]:
            st.divider()
            st.subheader("📄 Extracted Text Preview")
            preview = st.session_state["pdf_text"][:3000]
            if len(st.session_state["pdf_text"]) > 3000:
                preview += "\n\n... [text truncated for preview] ..."
            st.text_area("PDF Content", value=preview, height=300, disabled=True)

    else:
        st.info("👆 Upload a PDF file to get started.")

    if "pdf_leads" in st.session_state and st.session_state["pdf_leads"]:
        leads = st.session_state["pdf_leads"]
        df = pd.DataFrame(leads)

        st.subheader(f"📋 Extracted Leads ({len(leads)})")

        if "industry" in df.columns:
            industries = df["industry"].value_counts()
            ind_cols = st.columns(min(len(industries), 5))
            for i, (ind, cnt) in enumerate(industries.head(5).items()):
                ind_cols[i].metric(ind, cnt)

        display_cols = _safe_cols(df, [
            "company_name", "website", "industry", "company_size",
            "contact_person", "job_title", "email",
            "profile_url", "reason", "source_platform",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        st.divider()
        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("💾 Store in Supabase", key="pdf_store", type="secondary", use_container_width=True):
                with st.spinner("Storing PDF leads in Supabase..."):
                    count = insert_leads(leads)
                _cached_get_leads.clear()  # refresh cache after write
                if count > 0:
                    st.success(f"✅ **{count}** leads stored in Supabase!")
                else:
                    st.info("No new leads to store (all duplicates).")

        with action_col2:
            if st.button("🤖 Score Leads", key="pdf_analyze", type="secondary", use_container_width=True):
                st.session_state["collected_leads"] = leads
                st.success("✅ Leads ready for analysis! Go to **Analyze Leads** page.")


# ════════════════════════════════════════════════════════════
# PAGE: Analyze Leads
# ════════════════════════════════════════════════════════════
elif page == "🤖 Analyze Leads":
    st.markdown('<p class="main-header">Score Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Use NVIDIA Llama-3.3-70B to score and evaluate each lead</p>', unsafe_allow_html=True)

    source_option = st.radio(
        "Choose leads to analyze:",
        options=["Recently collected leads (session)", "All unscored leads from Supabase"],
        horizontal=True,
    )

    leads_to_analyze: list[dict] = []

    if source_option == "Recently collected leads (session)":
        leads_to_analyze = st.session_state.get("collected_leads", [])
        if not leads_to_analyze:
            st.info("No recently collected leads in this session. Collect some leads first or upload a PDF!")
    else:
        all_db_leads = _cached_get_leads()
        leads_to_analyze = [
            l for l in all_db_leads
            if not l.get("lead_score") or l["lead_score"] == ""
        ]
        if not leads_to_analyze:
            st.info("All leads in Supabase are already scored! 🎉")

    if leads_to_analyze:
        st.write(f"**{len(leads_to_analyze)}** leads ready for analysis.")

        if st.button("🤖 Score Leads", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            analyzed = []
            for i, lead in enumerate(leads_to_analyze):
                status_text.text(f"Analyzing {i+1}/{len(leads_to_analyze)}: {lead.get('company_name', 'Unknown')}...")
                progress_bar.progress((i + 1) / len(leads_to_analyze))

                result = analyze_lead(lead)
                analyzed.append(result)

            st.session_state["analyzed_leads"] = analyzed
            progress_bar.empty()
            status_text.empty()
            st.success(f"✅ Analysis complete for **{len(analyzed)}** leads!")

    if "analyzed_leads" in st.session_state and st.session_state["analyzed_leads"]:
        analyzed = st.session_state["analyzed_leads"]
        df = pd.DataFrame(analyzed)

        st.subheader("🎯 Analysis Results")

        if "lead_score" in df.columns:
            score_cols = st.columns(3)
            high = sum(1 for l in analyzed if l.get("lead_score") == "High")
            med = sum(1 for l in analyzed if l.get("lead_score") == "Medium")
            low = sum(1 for l in analyzed if l.get("lead_score") == "Low")
            score_cols[0].metric("🟢 High", high)
            score_cols[1].metric("🟡 Medium", med)
            score_cols[2].metric("🔴 Low", low)

        display_cols = _safe_cols(df, [
            "company_name", "industry", "lead_score", "ai_reason",
            "source_platform", "website", "profile_url",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        st.divider()
        if st.button("💾 Save Analysis to Supabase", type="secondary", use_container_width=True):
            with st.spinner("Updating lead scores in Supabase..."):
                updated = 0
                for lead in analyzed:
                    insert_leads([lead])
                    if update_lead_analysis(
                        lead.get("company_name", ""),
                        lead.get("lead_score", "Medium"),
                        lead.get("ai_reason", ""),
                    ):
                        updated += 1
            _cached_get_leads.clear()  # refresh cache after write
            st.success(f"✅ Updated **{updated}** leads in Supabase!")


# ════════════════════════════════════════════════════════════
# PAGE: Stored Leads
# ════════════════════════════════════════════════════════════
elif page == "💾 Stored Leads":
    st.markdown('<p class="main-header">Stored Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Browse and filter all leads in your Supabase database</p>', unsafe_allow_html=True)

    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        db_industries = _cached_get_industries()
        industry_filter = st.selectbox(
            "🏭 Filter by Industry",
            options=["All"] + db_industries,
            index=0,
        )

    with filter_col2:
        db_scores = _cached_get_lead_scores()
        score_filter = st.selectbox(
            "🎯 Filter by Lead Score",
            options=["All"] + db_scores,
            index=0,
        )

    st.divider()

    if st.button("🔄 Load Leads", type="primary", use_container_width=True):
        # Clear cache so we get fresh data on explicit reload
        _cached_get_leads.clear()
        with st.spinner("Fetching leads from Supabase..."):
            kwargs = {}
            if industry_filter != "All":
                kwargs["industry"] = industry_filter
            if score_filter != "All":
                kwargs["lead_score"] = score_filter
            leads = _cached_get_leads(**kwargs)

        if leads:
            st.session_state["stored_leads"] = leads
            st.success(f"Loaded **{len(leads)}** leads.")
        else:
            st.session_state["stored_leads"] = []
            st.info("No leads match the selected filters.")

    if "stored_leads" in st.session_state and st.session_state["stored_leads"]:
        df = pd.DataFrame(st.session_state["stored_leads"])

        total = len(df)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Results", total)
        if "lead_score" in df.columns:
            col2.metric("🟢 High Score", sum(df["lead_score"] == "High"))
            col3.metric("🔴 Low Score", sum(df["lead_score"] == "Low"))

        display_cols = _safe_cols(df, [
            "company_name", "website", "industry", "lead_score",
            "ai_reason", "contact_person", "job_title", "email",
            "source_platform", "profile_url", "collected_at",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════
# PAGE: Reports
# ════════════════════════════════════════════════════════════
elif page == "📄 Reports":
    st.markdown('<p class="main-header">PDF Reports</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Generate professional lead intelligence reports with buyer contacts</p>', unsafe_allow_html=True)

    report_source = st.radio(
        "Select leads for the report:",
        options=[
            "All leads from Supabase",
            "Recently analyzed leads (session)",
        ],
        horizontal=True,
    )

    st.divider()

    if st.button("📄 Generate PDF Report", type="primary", use_container_width=True):
        if report_source == "All leads from Supabase":
            with st.spinner("Loading leads from Supabase..."):
                report_leads = _cached_get_leads()
        else:
            report_leads = st.session_state.get("analyzed_leads", [])

        if not report_leads:
            st.warning("No leads available. Collect and analyze leads first!")
        else:
            with st.spinner(f"Generating PDF for {len(report_leads)} leads..."):
                filepath = generate_report(report_leads)

            # Store bytes in session_state so the download button
            # persists across Streamlit reruns (fixes disappearing button bug)
            with open(filepath, "rb") as f:
                st.session_state["report_pdf_bytes"] = f.read()
            # Use os.path.basename to reliably get filename with .pdf extension
            pdf_filename = os.path.basename(filepath)
            if not pdf_filename.lower().endswith(".pdf"):
                pdf_filename = pdf_filename + ".pdf"
            st.session_state["report_pdf_name"] = pdf_filename
            st.session_state["report_lead_count"] = len(report_leads)

    # Always render download button if a PDF was generated this session
    if st.session_state.get("report_pdf_bytes"):
        count = st.session_state.get("report_lead_count", 0)
        st.success(f"✅ Report ready with **{count}** leads!")
        st.download_button(
            label="⬇️ Download PDF Report",
            data=st.session_state["report_pdf_bytes"],
            file_name=st.session_state.get("report_pdf_name", "lead_report.pdf"),
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )