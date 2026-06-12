"""
============================================================
PerfectParser Lead Intelligence Platform
Main Streamlit Application
============================================================
A modern dashboard for collecting, analyzing, storing, and
reporting on potential leads for PerfectParser — an AI-powered
document processing tool.

Run with:  streamlit run app.py
============================================================
"""

import time
import logging
import streamlit as st
import pandas as pd

from src.scraper import (
    collect_leads_multi,
    SUPPORTED_INDUSTRIES,
    PLATFORMS,
    PLATFORM_NAMES,
)
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
    page_title="PerfectParser Lead Intelligence",
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
    color: #1e3a5f;
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem;
}
.sub-header {
    color: #475569;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* ── Metric Cards ───────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border: 1px solid #e2e8f0;
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
    background: #eff6ff;
    color: #1e3a5f;
    font-size: 1rem;
    margin-bottom: 1rem;
}

/* ── Platform Cards ─────────────────────────────────────── */
.platform-info {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
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


# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 PerfectParser")
    st.markdown("**Lead Intelligence Platform**")
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
    st.caption("© 2026 PerfectParser")


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

    # Fetch all leads for stats
    all_leads = get_leads()

    if all_leads:
        total = len(all_leads)
        high = sum(1 for l in all_leads if l.get("lead_score") == "High")
        medium = sum(1 for l in all_leads if l.get("lead_score") == "Medium")
        low = sum(1 for l in all_leads if l.get("lead_score") == "Low")
        unscored = total - high - medium - low

        # Metric cards
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Leads", total)
        col2.metric("🟢 High Score", high)
        col3.metric("🟡 Medium Score", medium)
        col4.metric("🔴 Low Score", low)
        col5.metric("⚪ Unscored", unscored)

        st.divider()

        df = pd.DataFrame(all_leads)

        # Recent leads
        st.subheader("🕐 Recent Leads")
        recent_cols = _safe_cols(df, ["company_name", "industry", "lead_score", "source_platform", "website", "collected_at"])
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

    # ── Industry & Settings ─────────────────────────────────
    col1, col2 = st.columns([2, 1])

    with col1:
        selected_industry = st.selectbox(
            "🏭 Select Target Industry",
            options=SUPPORTED_INDUSTRIES,
            index=0,
        )

    with col2:
        max_leads = st.slider("Max leads", min_value=5, max_value=30, value=15)

    # ── Platform Selection ──────────────────────────────────
    st.subheader("🌍 Select Platforms")
    st.caption("Choose which platforms to search for leads")

    # Build platform checkboxes in a grid
    platform_cols = st.columns(len(PLATFORM_NAMES))
    selected_platforms: list[str] = []

    for i, pname in enumerate(PLATFORM_NAMES):
        pinfo = PLATFORMS[pname]
        with platform_cols[i]:
            checked = st.checkbox(
                f"{pinfo['icon']} {pname}",
                value=True,
                key=f"platform_{pname}",
            )
            if checked:
                selected_platforms.append(pname)

    st.divider()

    # ── Collect Button ──────────────────────────────────────
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

    # ── Display collected leads ─────────────────────────────
    if "collected_leads" in st.session_state and st.session_state["collected_leads"]:
        leads = st.session_state["collected_leads"]
        df = pd.DataFrame(leads)

        st.subheader(f"📋 Collected Leads ({len(leads)})")

        # Show platform breakdown
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

        # ── Store in Supabase ───────────────────────────────
        st.divider()
        if st.button("💾 Store in Supabase", type="secondary", use_container_width=True):
            with st.spinner("Storing leads in Supabase..."):
                count = insert_leads(leads)
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

    # ── File Uploader ───────────────────────────────────────
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        accept_multiple_files=False,
        help="Upload a PDF file containing business/company information",
    )

    # ── Optional Context ────────────────────────────────────
    context = st.text_input(
        "🔍 Additional context (optional)",
        placeholder="e.g. 'Healthcare companies in USA', 'Law firms', 'Tech startups'",
        help="Provide context to help better identify leads from the document",
    )

    st.divider()

    # ── Process PDF ─────────────────────────────────────────
    if uploaded_file is not None:
        st.info(f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

        # Step 1: Extract text from PDF
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
                        uploaded_file.seek(0)  # Reset file pointer
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

        # Show extracted text preview
        if "pdf_text" in st.session_state and st.session_state["pdf_text"]:
            st.divider()
            st.subheader("📄 Extracted Text Preview")
            preview = st.session_state["pdf_text"][:3000]
            if len(st.session_state["pdf_text"]) > 3000:
                preview += "\n\n... [text truncated for preview] ..."
            st.text_area("PDF Content", value=preview, height=300, disabled=True)

    else:
        st.info("👆 Upload a PDF file to get started.")

    # ── Display extracted leads ─────────────────────────────
    if "pdf_leads" in st.session_state and st.session_state["pdf_leads"]:
        leads = st.session_state["pdf_leads"]
        df = pd.DataFrame(leads)

        st.subheader(f"📋 Extracted Leads ({len(leads)})")

        # Show a summary
        if "industry" in df.columns:
            industries = df["industry"].value_counts()
            ind_cols = st.columns(min(len(industries), 5))
            for i, (ind, cnt) in enumerate(industries.head(5).items()):
                ind_cols[i].metric(ind, cnt)

        # Full table with all enriched fields
        display_cols = _safe_cols(df, [
            "company_name", "website", "industry", "company_size",
            "contact_person", "job_title", "email",
            "profile_url", "reason", "source_platform",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

        # ── Actions ─────────────────────────────────────────
        st.divider()
        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("💾 Store in Supabase", key="pdf_store", type="secondary", use_container_width=True):
                with st.spinner("Storing PDF leads in Supabase..."):
                    count = insert_leads(leads)
                if count > 0:
                    st.success(f"✅ **{count}** leads stored in Supabase!")
                else:
                    st.info("No new leads to store (all duplicates).")

        with action_col2:
            if st.button("🤖 Score Leads", key="pdf_analyze", type="secondary", use_container_width=True):
                # Move PDF leads to collected_leads for the Analyze page
                st.session_state["collected_leads"] = leads
                st.success("✅ Leads ready for analysis! Go to **Analyze Leads** page.")


# ════════════════════════════════════════════════════════════
# PAGE: Analyze Leads
# ════════════════════════════════════════════════════════════
elif page == "🤖 Analyze Leads":
    st.markdown('<p class="main-header">Score Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Use our internal algorithm to score and evaluate each lead</p>', unsafe_allow_html=True)

    # Determine the source of leads to analyze
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
        # Load unscored leads from Supabase
        all_db_leads = get_leads()
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

            # Analyze leads
            analyzed = []
            for i, lead in enumerate(leads_to_analyze):
                status_text.text(f"Analyzing {i+1}/{len(leads_to_analyze)}: {lead.get('company_name', 'Unknown')}...")
                progress_bar.progress((i + 1) / len(leads_to_analyze))

                result = analyze_lead(lead)
                analyzed.append(result)

                # Small delay for rate limiting
                if i < len(leads_to_analyze) - 1:
                    time.sleep(1.0)

            st.session_state["analyzed_leads"] = analyzed
            progress_bar.empty()
            status_text.empty()
            st.success(f"✅ Analysis complete for **{len(analyzed)}** leads!")

    # ── Display analyzed results ────────────────────────────
    if "analyzed_leads" in st.session_state and st.session_state["analyzed_leads"]:
        analyzed = st.session_state["analyzed_leads"]
        df = pd.DataFrame(analyzed)

        st.subheader("🎯 Analysis Results")

        # Show score summary
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

        # ── Update Supabase with analysis results ───────────
        st.divider()
        if st.button("💾 Save Analysis to Supabase", type="secondary", use_container_width=True):
            with st.spinner("Updating lead scores in Supabase..."):
                updated = 0
                for lead in analyzed:
                    # First, make sure the lead exists in DB
                    insert_leads([lead])
                    # Then update the analysis fields
                    if update_lead_analysis(
                        lead.get("company_name", ""),
                        lead.get("lead_score", "Medium"),
                        lead.get("ai_reason", ""),
                    ):
                        updated += 1
            st.success(f"✅ Updated **{updated}** leads in Supabase!")


# ════════════════════════════════════════════════════════════
# PAGE: Stored Leads
# ════════════════════════════════════════════════════════════
elif page == "💾 Stored Leads":
    st.markdown('<p class="main-header">Stored Leads</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Browse and filter all leads in your Supabase database</p>', unsafe_allow_html=True)

    # ── Filters ─────────────────────────────────────────────
    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        db_industries = get_industries()
        industry_filter = st.selectbox(
            "🏭 Filter by Industry",
            options=["All"] + db_industries,
            index=0,
        )

    with filter_col2:
        db_scores = get_lead_scores()
        score_filter = st.selectbox(
            "🎯 Filter by Lead Score",
            options=["All"] + db_scores,
            index=0,
        )

    st.divider()

    # ── Load & Display ──────────────────────────────────────
    if st.button("🔄 Load Leads", type="primary", use_container_width=True):
        with st.spinner("Fetching leads from Supabase..."):
            leads = get_leads(
                industry=industry_filter if industry_filter != "All" else None,
                lead_score=score_filter if score_filter != "All" else None,
            )

        if leads:
            st.session_state["stored_leads"] = leads
            st.success(f"Loaded **{len(leads)}** leads.")
        else:
            st.session_state["stored_leads"] = []
            st.info("No leads match the selected filters.")

    # Display stored leads
    if "stored_leads" in st.session_state and st.session_state["stored_leads"]:
        df = pd.DataFrame(st.session_state["stored_leads"])

        # Summary metrics
        total = len(df)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Results", total)
        if "lead_score" in df.columns:
            col2.metric("🟢 High Score", sum(df["lead_score"] == "High"))
            col3.metric("🔴 Low Score", sum(df["lead_score"] == "Low"))

        # Full table
        display_cols = _safe_cols(df, [
            "company_name", "website", "industry", "lead_score",
            "ai_reason", "contact_person", "email",
            "source_platform", "profile_url", "collected_at",
        ])
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════
# PAGE: Reports
# ════════════════════════════════════════════════════════════
elif page == "📄 Reports":
    st.markdown('<p class="main-header">PDF Reports</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Generate professional lead intelligence reports</p>', unsafe_allow_html=True)

    # Choose data source for the report
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
        # Gather leads
        if report_source == "All leads from Supabase":
            with st.spinner("Loading leads from Supabase..."):
                report_leads = get_leads()
        else:
            report_leads = st.session_state.get("analyzed_leads", [])

        if not report_leads:
            st.warning("No leads available. Collect and analyze leads first!")
        else:
            with st.spinner(f"Generating PDF for {len(report_leads)} leads..."):
                filepath = generate_report(report_leads)

            st.success(f"✅ Report generated with **{len(report_leads)}** leads!")

            # Offer download
            with open(filepath, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=f.read(),
                    file_name=filepath.split("/")[-1].split("\\")[-1],
                    mime="application/pdf",
                    use_container_width=True,
                )