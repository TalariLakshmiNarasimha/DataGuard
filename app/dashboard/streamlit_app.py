"""DataGuard Streamlit Dashboard.

A monitoring dashboard for the DataGuard ETL pipeline.
Launch with: streamlit run app/dashboard/streamlit_app.py
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import get_config
from app.ingestion.csv_reader import REQUIRED_COLUMNS
from app.pipeline import run_pipeline
from app.storage.database import get_engine, init_schema

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DataGuard — Data Quality Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for professional look
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d7377 50%, #14a085 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }

    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    .main-header p {
        margin: 0.3rem 0 0 0;
        font-size: 0.9rem;
        opacity: 0.85;
    }

    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        transition: transform 0.2s;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e3a5f;
        margin: 0;
    }

    .metric-label {
        font-size: 0.8rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0;
    }

    .status-success { color: #14a085; }
    .status-partial { color: #f0ad4e; }
    .status-failed  { color: #dc3545; }
    .status-running { color: #0d7377; }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #0d7377 100%);
    }

    div[data-testid="stSidebar"] .stMarkdown p,
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: white;
    }

    div[data-testid="stSidebar"] .stRadio label {
        color: white !important;
    }

    .empty-state {
        text-align: center;
        padding: 3rem;
        color: #6c757d;
    }

    .empty-state h3 {
        color: #495057;
    }

    .synthetic-note {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-size: 0.8rem;
        color: #856404;
        margin-bottom: 1rem;
    }

    .schema-pill {
        display: inline-block;
        padding: 4px 12px;
        margin: 3px;
        border-radius: 16px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }

    .schema-pill-valid {
        background: #e6fcf5;
        color: #0ca678;
        border: 1px solid #63e6be;
    }

    .schema-pill-missing {
        background: #fff5f5;
        color: #e03131;
        border: 1px solid #ffc9c9;
    }

    .upload-cta-box {
        background: linear-gradient(135deg, #f0fdf4 0%, #e6fcf5 100%);
        border: 1px solid #b2f2bb;
        border-radius: 10px;
        padding: 1rem 1.4rem;
        margin-bottom: 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db_engine():
    """Create a cached database engine and initialize schema."""
    try:
        config = get_config()
        engine = get_engine(config.db.url)
        init_schema(engine)
        return engine
    except Exception as e:
        return None


def run_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """Run a read-only parameterized SQL query and return a DataFrame."""
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params or {})
    except Exception as e:
        st.error(f"Database query error: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown("# 🛡️ DataGuard")
st.sidebar.markdown("Data Quality Monitoring")
st.sidebar.markdown("---")

nav_options = [
    "📊 Overview",
    "📤 Upload & Ingest",
    "🔄 Pipeline Runs",
    "📈 Data Quality",
    "🔍 Quarantine Explorer",
    "📦 Orders",
]

if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "📊 Overview"

default_idx = (
    nav_options.index(st.session_state["nav_page"])
    if st.session_state["nav_page"] in nav_options
    else 0
)

page = st.sidebar.radio(
    "Navigation",
    nav_options,
    index=default_idx,
    label_visibility="collapsed",
    key="nav_radio_selection",
)
st.session_state["nav_page"] = page

st.sidebar.markdown("---")
_active_engine = get_db_engine()
_dialect = _active_engine.dialect.name if _active_engine is not None else "unknown"
if _dialect == "sqlite":
    st.sidebar.caption("💾 **Storage**: `SQLite (Embedded / Cloud)`")
else:
    st.sidebar.caption("🐘 **Storage**: `PostgreSQL (Connected)`")

st.sidebar.markdown(
    '<div class="synthetic-note">⚠️ All data shown is synthetic sample data for demonstration purposes.</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helper: status badge
# ---------------------------------------------------------------------------

def status_badge(status: str) -> str:
    """Return an HTML span with a colored status label."""
    colors = {
        "SUCCESS": "#14a085",
        "PARTIAL_SUCCESS": "#f0ad4e",
        "FAILED": "#dc3545",
        "RUNNING": "#0d7377",
    }
    color = colors.get(status, "#6c757d")
    return f'<span style="background:{color};color:white;padding:2px 10px;border-radius:4px;font-size:0.8rem;font-weight:600">{status}</span>'


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------

def page_overview():
    st.markdown(
        """
        <div class="main-header">
            <h1>🛡️ DataGuard Dashboard</h1>
            <p>Data Quality Monitoring & ETL Pipeline Platform</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    runs_df = run_query("SELECT * FROM pipeline_runs ORDER BY started_at DESC")

    if runs_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                <h3>🚀 No Pipeline Runs Yet</h3>
                <p>Upload a CSV file or run your first pipeline to see metrics here.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("📤 Upload & Ingest CSV Now", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "📤 Upload & Ingest"
            st.rerun()
        return

    # Ingestion quick action banner
    st.markdown(
        """
        <div class="upload-cta-box">
            <span style="color: #2b8a3e; font-weight: 600; font-size: 0.95rem;">
                📥 Have a new batch of orders to process?
            </span>
            <span style="color: #495057; font-size: 0.88rem; margin-left: 8px;">
                Upload your CSV, validate schema compliance, and ingest directly into PostgreSQL with automated quarantine.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key metrics
    total_runs = len(runs_df)
    success_runs = len(runs_df[runs_df["status"] == "SUCCESS"])
    partial_runs = len(runs_df[runs_df["status"] == "PARTIAL_SUCCESS"])
    failed_runs = len(runs_df[runs_df["status"] == "FAILED"])

    latest = runs_df.iloc[0]
    total_accepted = int(runs_df["accepted_records"].sum())
    total_rejected = int(runs_df["rejected_records"].sum())

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Total Runs", total_runs)
    with col2:
        st.metric("✅ Successful", success_runs)
    with col3:
        st.metric("⚠️ Partial", partial_runs)
    with col4:
        st.metric("❌ Failed", failed_runs)
    with col5:
        st.metric("📥 Accepted", f"{total_accepted:,}")
    with col6:
        st.metric("🚫 Rejected", f"{total_rejected:,}")

    st.markdown("---")

    # Latest run summary
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🕐 Latest Run")
        st.markdown(f"**Run ID:** `{latest['run_id'][:12]}...`")
        st.markdown(f"**Source:** `{latest['source_file']}`")
        st.markdown(f"**Status:** {status_badge(latest['status'])}", unsafe_allow_html=True)
        st.markdown(f"**Started:** {latest['started_at']}")
        st.markdown(f"**Records:** {latest['total_records']} total | {latest['accepted_records']} accepted | {latest['rejected_records']} rejected")

    with col_right:
        st.subheader("📊 Pipeline Status Distribution")
        status_counts = runs_df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        colors_map = {
            "SUCCESS": "#14a085",
            "PARTIAL_SUCCESS": "#f0ad4e",
            "FAILED": "#dc3545",
            "RUNNING": "#0d7377",
        }
        fig = px.pie(
            status_counts,
            values="Count",
            names="Status",
            color="Status",
            color_discrete_map=colors_map,
            hole=0.4,
        )
        fig.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=280,
            font=dict(family="Inter"),
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Quality over time
    st.subheader("📈 Records Over Time")
    if len(runs_df) > 1:
        trend_df = runs_df.sort_values("started_at")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=trend_df["started_at"],
            y=trend_df["accepted_records"],
            name="Accepted",
            mode="lines+markers",
            line=dict(color="#14a085", width=2),
            fill="tozeroy",
            fillcolor="rgba(20, 160, 133, 0.1)",
        ))
        fig2.add_trace(go.Scatter(
            x=trend_df["started_at"],
            y=trend_df["rejected_records"],
            name="Rejected",
            mode="lines+markers",
            line=dict(color="#dc3545", width=2),
            fill="tozeroy",
            fillcolor="rgba(220, 53, 69, 0.1)",
        ))
        fig2.update_layout(
            margin=dict(t=20, b=40, l=40, r=20),
            height=300,
            font=dict(family="Inter"),
            xaxis_title="Run Time",
            yaxis_title="Record Count",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Run the pipeline multiple times to see trends.")


# ---------------------------------------------------------------------------
# Page: Upload & Ingest CSV
# ---------------------------------------------------------------------------

def page_upload_csv():
    st.markdown(
        """
        <div class="main-header">
            <h1>📤 Upload & Run ETL Pipeline</h1>
            <p>Upload a CSV file of business orders to validate, transform, and ingest into PostgreSQL</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top description & Template download
    col_info, col_tmpl = st.columns([2, 1])
    with col_info:
        st.markdown(
            """
            **DataGuard Quality & ETL Pipeline Workflow**:
            - **1. Schema Ingestion**: Verifies CSV integrity and mandatory header presence.
            - **2. Data Quality Audit**: Applies 7 validation rules (format, values, duplicates).
            - **3. Normalization**: Trims strings, parses dates, calculates `total_amount`.
            - **4. Storage & Quarantine**: Upserts valid orders (idempotent) and isolates invalid rows in PostgreSQL.
            """
        )
    with col_tmpl:
        st.markdown("#### Quick Tools & Templates")
        
        template_csv = (
            "order_id,customer_id,order_date,product,quantity,unit_price,status\n"
            "ORD-101,CUST-501,2026-10-15,Widget A,5,29.99,shipped\n"
            "ORD-102,CUST-502,2026-10-16,Gadget Pro,2,99.50,pending\n"
            "ORD-103,CUST-503,2026-10-17,Widget B,10,49.99,delivered\n"
            "ORD-104,CUST-504,2026-10-18,Gadget Lite,1,149.00,cancelled\n"
        )
        st.download_button(
            label="📥 Download CSV Template",
            data=template_csv,
            file_name="dataguard_order_template.csv",
            mime="text/csv",
            help="Download a pre-formatted CSV template with required columns",
            use_container_width=True,
        )

        sample_path = Path("data/sample_orders.csv")
        if sample_path.exists():
            if st.button("⚡ Load Built-in Sample Data", use_container_width=True, help="Load 'data/sample_orders.csv' (26 records: 18 valid, 8 with deliberate errors)"):
                st.session_state["uploaded_file_data"] = sample_path.read_bytes()
                st.session_state["uploaded_file_name"] = "sample_orders.csv"
                st.session_state["use_sample_active"] = True
                st.rerun()

    st.markdown("---")

    # 1. File Upload Section
    st.subheader("1. Select / Upload Orders CSV")
    
    uploaded_file = st.file_uploader(
        "Choose an orders CSV file to process",
        type=["csv"],
        help="Upload an order records CSV file (UTF-8 encoded)",
    )

    file_bytes: bytes = b""
    file_name: str = ""

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
        st.session_state["use_sample_active"] = False
        st.session_state["uploaded_file_data"] = file_bytes
        st.session_state["uploaded_file_name"] = file_name
    elif st.session_state.get("use_sample_active") and "uploaded_file_data" in st.session_state:
        file_bytes = st.session_state.get("uploaded_file_data", b"")
        file_name = st.session_state.get("uploaded_file_name", "sample_orders.csv")
        st.info(f"Loaded built-in sample file: **{file_name}** ({len(file_bytes):,} bytes)")

    if not file_bytes or not file_name:
        st.markdown(
            """
            <div style="background: #f8f9fa; border: 2px dashed #ced4da; border-radius: 10px; padding: 2.5rem; text-align: center; color: #6c757d;">
                <h4 style="color: #495057; margin-bottom: 0.5rem;">📂 No CSV File Selected</h4>
                <p>Upload your orders CSV file above or click <b>⚡ Load Built-in Sample Data</b> to test the platform.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Parse and preview raw data
    try:
        preview_df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:
        st.error(f"❌ Failed to parse CSV: {exc}")
        return

    if preview_df.empty:
        st.warning("⚠️ The uploaded CSV file has no data rows.")
        return

    # Clean column names to check schema compliance
    cleaned_cols = [c.strip().lower() for c in preview_df.columns]
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in cleaned_cols]
    schema_valid = len(missing_cols) == 0

    st.markdown("### 2. File Inspection & Schema Compliance")
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    with col_stat1:
        st.metric("Source File", file_name)
    with col_stat2:
        st.metric("File Size", f"{len(file_bytes) / 1024:.1f} KB")
    with col_stat3:
        st.metric("Total Rows", f"{len(preview_df):,}")
    with col_stat4:
        st.metric("Total Columns", len(preview_df.columns))

    # Schema checklist pills
    st.markdown("**Required Columns Compliance:**")
    pill_html = ""
    for col_req in REQUIRED_COLUMNS:
        if col_req in cleaned_cols:
            pill_html += f'<span class="schema-pill schema-pill-valid">✓ {col_req}</span> '
        else:
            pill_html += f'<span class="schema-pill schema-pill-missing">✗ {col_req} (missing)</span> '
    st.markdown(pill_html, unsafe_allow_html=True)

    if not schema_valid:
        st.error(
            f"❌ **Schema Error**: The file is missing {len(missing_cols)} required column(s): "
            f"**{', '.join(missing_cols)}**. Please revise your CSV headers or use the template."
        )
    else:
        st.success("✅ **Schema Valid**: All 7 required columns are present and ready for ingestion.")

    # Data preview expander
    with st.expander(f"👁️ Preview Raw CSV Data (First {min(15, len(preview_df))} rows)", expanded=True):
        st.dataframe(preview_df.head(15), use_container_width=True, hide_index=False)

    # 3. Execution Section
    st.markdown("---")
    st.subheader("3. Execute Data Quality & ETL Pipeline")
    
    col_exec, col_opt = st.columns([2, 1])
    with col_exec:
        run_button = st.button(
            "🚀 Ingest & Run DataGuard Pipeline",
            type="primary",
            use_container_width=True,
            disabled=not schema_valid,
        )
    with col_opt:
        if st.button("🔄 Reset / Clear File", use_container_width=True):
            st.session_state.pop("uploaded_file_data", None)
            st.session_state.pop("uploaded_file_name", None)
            st.session_state.pop("use_sample_active", None)
            st.session_state.pop("last_run_summary", None)
            st.rerun()

    if run_button:
        # Save file to data/uploads
        uploads_dir = Path("data/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        target_path = uploads_dir / file_name
        
        try:
            target_path.write_bytes(file_bytes)
        except Exception as exc:
            st.error(f"Failed to save uploaded file: {exc}")
            return

        with st.spinner("Processing pipeline: Ingesting ➔ Validating ➔ Transforming ➔ Upserting to PostgreSQL & Quarantining..."):
            try:
                summary = run_pipeline(str(target_path))
                st.session_state["last_run_summary"] = summary
                st.session_state["last_run_file"] = file_name
                st.toast("Pipeline execution completed!", icon="🎉")
            except Exception as exc:
                st.error(f"❌ Pipeline failed unexpectedly: {exc}")
                return

    # 4. Display Results if available
    summary = st.session_state.get("last_run_summary")
    if summary and summary.get("source_file") == file_name:
        st.markdown("---")
        st.subheader("4. Execution Results & Audit Summary")

        status = summary.get("status", "UNKNOWN")
        run_id = summary.get("run_id", "N/A")

        # Top alert banner
        if status == "SUCCESS":
            st.success(f"🎉 **Pipeline Run Successful** — All records passed validation! Run ID: `{run_id}`")
        elif status == "PARTIAL_SUCCESS":
            st.warning(f"⚠️ **Partial Success** — Valid orders ingested, anomalies quarantined. Run ID: `{run_id}`")
        else:
            st.error(f"❌ **Pipeline Run Failed** — {summary.get('error', 'Validation or ingestion failure')}. Run ID: `{run_id}`")

        # 5 Metric Cards
        tot = summary.get("total_records", 0)
        acc = summary.get("accepted_records", 0)
        rej = summary.get("rejected_records", 0)
        ins = summary.get("inserted_records", 0)
        upd = summary.get("updated_records", 0)
        acc_pct = (acc / tot * 100) if tot > 0 else 0
        rej_pct = (rej / tot * 100) if tot > 0 else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Total Rows Ingested", f"{tot:,}")
        with m2:
            st.metric("✅ Accepted Orders", f"{acc:,}", f"{acc_pct:.1f}%")
        with m3:
            st.metric("🔒 Quarantined", f"{rej:,}", f"-{rej_pct:.1f}%", delta_color="inverse")
        with m4:
            st.metric("📦 Newly Inserted", f"{ins:,}")
        with m5:
            st.metric("🔄 Updated (Idempotent)", f"{upd:,}")

        # Visual Analytics Row
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("##### 📊 Quality Pass vs Quarantine")
            fig_pie = go.Figure(
                data=[
                    go.Pie(
                        labels=["Accepted Orders", "Quarantined Records"],
                        values=[acc, rej],
                        hole=0.55,
                        marker_colors=["#14a085", "#dc3545"],
                        textinfo="label+percent",
                    )
                ]
            )
            fig_pie.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                height=260,
                showlegend=False,
                font=dict(family="Inter"),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_c2:
            st.markdown("##### 🔍 Rejection Reasons Breakdown")
            if rej > 0:
                q_rows = run_query(
                    "SELECT rejection_reasons FROM quarantined_records WHERE run_id = :run_id",
                    {"run_id": run_id},
                )
                if not q_rows.empty:
                    all_reasons = []
                    for reasons_val in q_rows["rejection_reasons"]:
                        if isinstance(reasons_val, list):
                            all_reasons.extend(reasons_val)
                        elif isinstance(reasons_val, str):
                            try:
                                parsed = json.loads(reasons_val)
                                if isinstance(parsed, list):
                                    all_reasons.extend(parsed)
                                else:
                                    all_reasons.append(str(parsed))
                            except Exception:
                                all_reasons.append(reasons_val)

                    reason_counts = pd.Series(all_reasons).value_counts().reset_index()
                    reason_counts.columns = ["Reason", "Count"]

                    fig_bar = px.bar(
                        reason_counts,
                        x="Count",
                        y="Reason",
                        orientation="h",
                        color_discrete_sequence=["#dc3545"],
                    )
                    fig_bar.update_layout(
                        margin=dict(t=10, b=20, l=10, r=20),
                        height=260,
                        yaxis=dict(autorange="reversed"),
                        font=dict(family="Inter"),
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("No quarantine details found for this run.")
            else:
                st.success("🎯 Zero records quarantined! Clean batch.")

        # Interactive Data Breakdown Tabs
        tab_acc, tab_rej, tab_run = st.tabs([
            f"✅ Accepted Orders ({acc})",
            f"🔒 Quarantined Records ({rej})",
            "📋 Run Audit Details",
        ])

        with tab_acc:
            if acc > 0:
                orders_df = run_query(
                    """
                    SELECT order_id, customer_id, order_date, product, quantity,
                           unit_price, total_amount, status, created_at, updated_at
                    FROM orders
                    WHERE source_file = :src
                    ORDER BY order_id
                    """,
                    {"src": file_name},
                )
                if not orders_df.empty:
                    st.dataframe(
                        orders_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
                            "total_amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
                            "order_date": st.column_config.DateColumn("Order Date", format="YYYY-MM-DD"),
                        },
                    )
                else:
                    st.info("No orders found matching this source file.")
            else:
                st.info("No orders accepted in this run.")

        with tab_rej:
            if rej > 0:
                quarantine_df = run_query(
                    """
                    SELECT source_row_number, rejection_reasons, raw_record, quarantined_at
                    FROM quarantined_records
                    WHERE run_id = :run_id
                    ORDER BY source_row_number
                    """,
                    {"run_id": run_id},
                )
                if not quarantine_df.empty:
                    st.dataframe(
                        quarantine_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "source_row_number": st.column_config.NumberColumn("CSV Line #"),
                            "rejection_reasons": st.column_config.TextColumn("Rejection Reasons"),
                            "raw_record": st.column_config.TextColumn("Raw CSV Record"),
                            "quarantined_at": st.column_config.DatetimeColumn("Quarantined At", format="YYYY-MM-DD HH:mm:ss"),
                        },
                    )
                else:
                    st.info("No quarantined records recorded.")
            else:
                st.success("All records passed validation. Nothing quarantined.")

        with tab_run:
            run_details_df = run_query(
                "SELECT * FROM pipeline_runs WHERE run_id = :run_id",
                {"run_id": run_id},
            )
            if not run_details_df.empty:
                st.dataframe(run_details_df, use_container_width=True, hide_index=True)

        # Quick navigation actions
        st.markdown("---")
        st.markdown("##### 🚀 Next Actions")
        col_nav1, col_nav2, col_nav3 = st.columns(3)
        with col_nav1:
            if st.button("📊 Go to Global Overview", use_container_width=True):
                st.session_state["nav_page"] = "📊 Overview"
                st.rerun()
        with col_nav2:
            if st.button("🔄 View All Pipeline Runs", use_container_width=True):
                st.session_state["nav_page"] = "🔄 Pipeline Runs"
                st.rerun()
        with col_nav3:
            if st.button("🔍 Open Quarantine Explorer", use_container_width=True):
                st.session_state["nav_page"] = "🔍 Quarantine Explorer"
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Pipeline Runs
# ---------------------------------------------------------------------------

def page_pipeline_runs():
    st.markdown(
        """
        <div class="main-header">
            <h1>🔄 Pipeline Runs</h1>
            <p>History of all ETL pipeline executions</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    runs_df = run_query("SELECT * FROM pipeline_runs ORDER BY started_at DESC")

    if runs_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                <h3>No runs found</h3>
                <p>Execute the pipeline first to see run history.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=runs_df["status"].unique().tolist(),
            default=runs_df["status"].unique().tolist(),
        )
    with col_f2:
        if "started_at" in runs_df.columns and not runs_df["started_at"].isna().all():
            runs_df["started_at"] = pd.to_datetime(runs_df["started_at"])
            min_date = runs_df["started_at"].min().date()
            max_date = runs_df["started_at"].max().date()
            date_range = st.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )

    filtered = runs_df[runs_df["status"].isin(status_filter)]

    # Display
    display_cols = [
        "run_id", "source_file", "started_at", "finished_at", "status",
        "total_records", "accepted_records", "rejected_records",
        "inserted_records", "updated_records",
    ]
    available_cols = [c for c in display_cols if c in filtered.columns]
    st.dataframe(
        filtered[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "run_id": st.column_config.TextColumn("Run ID", width="medium"),
            "status": st.column_config.TextColumn("Status"),
            "started_at": st.column_config.DatetimeColumn("Started At", format="YYYY-MM-DD HH:mm:ss"),
            "finished_at": st.column_config.DatetimeColumn("Finished At", format="YYYY-MM-DD HH:mm:ss"),
        },
    )

    st.caption(f"Showing {len(filtered)} of {len(runs_df)} runs")


# ---------------------------------------------------------------------------
# Page: Data Quality
# ---------------------------------------------------------------------------

def page_data_quality():
    st.markdown(
        """
        <div class="main-header">
            <h1>📈 Data Quality</h1>
            <p>Validation metrics and rejection analysis</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    runs_df = run_query(
        "SELECT * FROM pipeline_runs WHERE status != 'RUNNING' ORDER BY started_at DESC"
    )
    quarantine_df = run_query("SELECT * FROM quarantined_records")

    if runs_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                <h3>No quality data yet</h3>
                <p>Run the pipeline to generate quality metrics.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Accepted vs Rejected
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("✅ Accepted vs 🚫 Rejected")
        total_accepted = int(runs_df["accepted_records"].sum())
        total_rejected = int(runs_df["rejected_records"].sum())
        fig = px.pie(
            values=[total_accepted, total_rejected],
            names=["Accepted", "Rejected"],
            color_discrete_sequence=["#14a085", "#dc3545"],
            hole=0.45,
        )
        fig.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            font=dict(family="Inter"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📋 Most Common Rejection Reasons")
        if not quarantine_df.empty and "rejection_reasons" in quarantine_df.columns:
            all_reasons = []
            for reasons_json in quarantine_df["rejection_reasons"]:
                try:
                    if isinstance(reasons_json, str):
                        reasons = json.loads(reasons_json)
                    else:
                        reasons = reasons_json
                    if isinstance(reasons, list):
                        all_reasons.extend(reasons)
                except (json.JSONDecodeError, TypeError):
                    pass

            if all_reasons:
                reason_counts = pd.Series(all_reasons).value_counts().head(10)
                fig2 = px.bar(
                    x=reason_counts.values,
                    y=reason_counts.index,
                    orientation="h",
                    color_discrete_sequence=["#0d7377"],
                    labels={"x": "Count", "y": "Reason"},
                )
                fig2.update_layout(
                    margin=dict(t=10, b=40, l=10, r=20),
                    height=300,
                    font=dict(family="Inter"),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No rejection reasons found.")
        else:
            st.info("No quarantined records yet.")

    # Quality trend by run
    st.subheader("📊 Quality Trend by Run")
    if len(runs_df) >= 1:
        trend = runs_df.sort_values("started_at")
        trend["quality_rate"] = (
            trend["accepted_records"]
            / trend["total_records"].replace(0, 1)
            * 100
        ).round(1)

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=trend["started_at"].astype(str),
            y=trend["accepted_records"],
            name="Accepted",
            marker_color="#14a085",
        ))
        fig3.add_trace(go.Bar(
            x=trend["started_at"].astype(str),
            y=trend["rejected_records"],
            name="Rejected",
            marker_color="#dc3545",
        ))
        fig3.update_layout(
            barmode="stack",
            margin=dict(t=20, b=40, l=40, r=20),
            height=350,
            font=dict(family="Inter"),
            xaxis_title="Run",
            yaxis_title="Records",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig3, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Quarantine Explorer
# ---------------------------------------------------------------------------

def page_quarantine_explorer():
    st.markdown(
        """
        <div class="main-header">
            <h1>🔍 Quarantine Explorer</h1>
            <p>Inspect rejected records and their rejection reasons</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quarantine_df = run_query(
        "SELECT * FROM quarantined_records ORDER BY quarantined_at DESC LIMIT 500"
    )

    if quarantine_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                <h3>No quarantined records</h3>
                <p>All records passed validation, or no pipeline has been run yet.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Filters
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        source_files = quarantine_df["source_file"].unique().tolist()
        file_filter = st.multiselect("Filter by Source File", source_files, default=source_files)

    with col_f2:
        search = st.text_input("Search rejection reasons", "")

    filtered = quarantine_df[quarantine_df["source_file"].isin(file_filter)]
    if search:
        filtered = filtered[
            filtered["rejection_reasons"].astype(str).str.contains(search, case=False, na=False)
        ]

    st.caption(f"Showing {len(filtered)} quarantined records")

    # Display records
    for _, row in filtered.iterrows():
        with st.expander(
            f"Row {row['source_row_number']} — {row['source_file']} (Run: {str(row['run_id'])[:8]}...)"
        ):
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Rejection Reasons:**")
                try:
                    reasons = row["rejection_reasons"]
                    if isinstance(reasons, str):
                        reasons = json.loads(reasons)
                    for r in reasons:
                        st.markdown(f"- 🚫 {r}")
                except (json.JSONDecodeError, TypeError):
                    st.text(str(row["rejection_reasons"]))

            with col_b:
                st.markdown("**Raw Record:**")
                try:
                    raw = row["raw_record"]
                    if isinstance(raw, str):
                        raw = json.loads(raw)
                    st.json(raw)
                except (json.JSONDecodeError, TypeError):
                    st.text(str(row["raw_record"]))

            st.caption(f"Quarantined at: {row['quarantined_at']}")


# ---------------------------------------------------------------------------
# Page: Orders
# ---------------------------------------------------------------------------

def page_orders():
    st.markdown(
        """
        <div class="main-header">
            <h1>📦 Orders</h1>
            <p>Valid orders loaded into the database</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    orders_df = run_query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 500")

    if orders_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                <h3>No orders found</h3>
                <p>Run the ETL pipeline to load valid orders.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        statuses = orders_df["status"].unique().tolist()
        status_filter = st.multiselect("Filter by Status", statuses, default=statuses)
    with col_f2:
        if "order_date" in orders_df.columns:
            orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
            min_d = orders_df["order_date"].min().date()
            max_d = orders_df["order_date"].max().date()
            date_range = st.date_input("Order Date Range", value=(min_d, max_d))

    filtered = orders_df[orders_df["status"].isin(status_filter)]

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Orders", len(filtered))
    with col2:
        if "total_amount" in filtered.columns:
            st.metric("Total Revenue", f"${filtered['total_amount'].sum():,.2f}")
    with col3:
        if "quantity" in filtered.columns:
            st.metric("Total Items", f"{filtered['quantity'].sum():,}")

    st.markdown("---")

    # Orders table
    display_cols = [
        "order_id", "customer_id", "order_date", "product",
        "quantity", "unit_price", "total_amount", "status",
    ]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(
        filtered[available],
        use_container_width=True,
        hide_index=True,
        column_config={
            "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
            "total_amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
            "order_date": st.column_config.DateColumn("Order Date", format="YYYY-MM-DD"),
        },
    )

    # Product breakdown
    st.subheader("📊 Orders by Product")
    if "product" in filtered.columns:
        product_counts = filtered["product"].value_counts().reset_index()
        product_counts.columns = ["Product", "Orders"]
        fig = px.bar(
            product_counts,
            x="Product",
            y="Orders",
            color_discrete_sequence=["#0d7377"],
        )
        fig.update_layout(
            margin=dict(t=20, b=40, l=40, r=20),
            height=300,
            font=dict(family="Inter"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page Router
# ---------------------------------------------------------------------------

if page == "📊 Overview":
    page_overview()
elif page == "📤 Upload & Ingest":
    page_upload_csv()
elif page == "🔄 Pipeline Runs":
    page_pipeline_runs()
elif page == "📈 Data Quality":
    page_data_quality()
elif page == "🔍 Quarantine Explorer":
    page_quarantine_explorer()
elif page == "📦 Orders":
    page_orders()
