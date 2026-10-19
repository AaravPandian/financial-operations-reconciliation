"""FinRecon interactive financial operations dashboard (run: streamlit run app.py)."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from finrecon.database import recent_runs, save_run
from finrecon.io import DataValidationError, load_csv_pair
from finrecon.metrics import control_metrics, pence_to_gbp
from finrecon.reconciliation import STATUSES, reconcile
from finrecon.reviews import REVIEW_STATUSES, read_reviews, write_review

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REVIEW_PATH = ROOT / "outputs" / "case_reviews.csv"

st.set_page_config(page_title="FinRecon | Financial Controls", page_icon="💷", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 1.8rem; max-width: 1450px;}
    h1, h2, h3 {letter-spacing: -0.025em;}
    [data-testid="stMetric"] {border: 1px solid rgba(132,146,166,.25);
        border-radius: 11px; padding: 14px 16px;}
    </style>""",
    unsafe_allow_html=True,
)

st.title("FinRecon")
st.caption("Financial Operations & Reconciliation  •  Synthetic payments  •  Python / Pandas / MySQL / Streamlit / Plotly")

with st.sidebar:
    st.header("Reconciliation controls")
    st.write("**Data source**")
    st.caption("Upload both CSV files or leave both blank to use the bundled demo.")
    ledger_upload = st.file_uploader("Internal ledger CSV", type="csv", key="ledger")
    bank_upload = st.file_uploader("Bank statement CSV", type="csv", key="bank")
    tolerance = st.slider("Allowed date difference (calendar days)", 0, 10, 2)
    st.divider()
    st.write("**Case filters**")

if bool(ledger_upload) != bool(bank_upload):
    st.info("Please upload **both** CSV files, or remove both to use the bundled demo.")
    st.stop()

try:
    if ledger_upload is not None:
        ledger_upload.seek(0)
        bank_upload.seek(0)
        ledger, bank = load_csv_pair(ledger_upload, bank_upload)
        source = "Uploaded data"
    else:
        ledger, bank = load_csv_pair(DATA / "ledger.csv", DATA / "bank_statement.csv")
        source = "Bundled synthetic demo"
    cases = reconcile(ledger, bank, allowed_date_lag_days=tolerance)
except (DataValidationError, ValueError, FileNotFoundError) as exc:
    st.error(f"Input validation failed: {exc}")
    st.stop()

metrics = control_metrics(cases, ledger)
reviews = read_reviews(REVIEW_PATH)
if not reviews.empty:
    cases = cases.merge(reviews[["case_id", "review_status", "analyst_note"]], on="case_id", how="left", validate="one_to_one")
else:
    cases["review_status"] = pd.NA
    cases["analyst_note"] = pd.NA
cases["review_status"] = cases["review_status"].fillna("Open")
cases["analyst_note"] = cases["analyst_note"].fillna("")

with st.sidebar:
    status_filter = st.multiselect(
        "Reconciliation status", options=STATUSES, default=STATUSES,
        format_func=lambda s: s.replace("_", " ").title(),
    )
    priority_filter = st.multiselect(
        "Priority", options=["High", "Medium", "None"], default=["High", "Medium", "None"]
    )
    search = st.text_input("Search transaction ID / counterparty", placeholder="TXN-0000123")
    first, last = cases["case_date"].min().date(), cases["case_date"].max().date()
    date_range = st.date_input("Case date range", value=(first, last), min_value=first, max_value=last)
    st.caption(f"Source: {source}")
    st.caption("Reconciliation is ID-based, not fuzzy. Reviews don't change matching outcomes.")

filtered = cases.loc[cases["status"].isin(status_filter) & cases["priority"].isin(priority_filter)].copy()
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    filtered = filtered.loc[
        filtered["case_date"].dt.date.between(date_range[0], date_range[1])
    ]
if search.strip():
    needle = search.strip()
    filtered = filtered.loc[
        filtered["transaction_id"].str.contains(needle, case=False, regex=False, na=False)
        | filtered["counterparty"].fillna("").str.contains(needle, case=False, regex=False, na=False)
    ]

st.info(
    "**Demo data only.** Values are stored as signed integer pence; comparisons require an exact ID, "
    "matching currency and amount, and a configurable calendar-day tolerance. "
    "Match rate = matched cases ÷ unique ledger transaction IDs."
)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Ledger rows", f"{metrics['ledger_rows']:,}")
k2.metric("Matched cases", f"{metrics['matched']:,}")
k3.metric("Exceptions", f"{metrics['exceptions']:,}")
k4.metric("Match rate", f"{metrics['match_rate_pct']:.2f}%")
k5.metric("Matched GBP volume¹", pence_to_gbp(metrics["matched_gbp_absolute_pence"]))
st.caption("¹ Sum of absolute matched ledger amounts denominated in GBP (not net cash, not all-currency volume). Global KPIs are not affected by sidebar filters.")

overview, exceptions_tab, raw_tab, mysql_tab = st.tabs(
    ["📊 Overview", "🚩 Exception management", "🧾 Data explorer", "🗄️ MySQL history"]
)

with overview:
    st.subheader("Reconciliation outcomes")
    chart1, chart2 = st.columns([1.2, 1])
    if filtered.empty:
        st.warning("No cases match the current filters.")
    else:
        counts = (
            filtered.groupby("status", as_index=False).size()
            .rename(columns={"size": "cases"})
            .sort_values("cases", ascending=True)
        )
        counts["outcome"] = counts["status"].str.replace("_", " ").str.title()
        fig1 = px.bar(
            counts, y="outcome", x="cases", orientation="h", color="status",
            color_discrete_map={"matched": "#19a38b"},
            labels={"cases": "Cases", "outcome": "Classification"},
        )
        fig1.update_layout(showlegend=False, height=400, margin=dict(l=0, r=20, t=10, b=20))
        chart1.plotly_chart(fig1, width="stretch")

        exception_only = filtered.loc[filtered["status"].ne("matched")].copy()
        if not exception_only.empty:
            exception_only["week"] = exception_only["case_date"].dt.to_period("W").dt.start_time
            trend = exception_only.groupby("week", as_index=False).size().rename(columns={"size": "exceptions"})
            fig2 = px.line(trend, x="week", y="exceptions", markers=True, title="Exceptions by case week")
            fig2.update_traces(line_color="#df9952")
            fig2.update_layout(height=400, margin=dict(l=0, r=20, t=45, b=20))
            chart2.plotly_chart(fig2, width="stretch")
        else:
            chart2.success("No exceptions under the current filters.")

        st.subheader("Priority breakdown")
        priority_data = (exception_only.groupby(["priority", "status"], as_index=False).size()
                         .rename(columns={"size": "cases"}))
        if not priority_data.empty:
            fig3 = px.bar(priority_data, x="priority", y="cases", color="status", barmode="stack",
                          category_orders={"priority": ["High", "Medium"]},
                          labels={"priority": "Control priority", "cases": "Exceptions"})
            fig3.update_layout(height=360, margin=dict(l=0, r=20, t=10, b=10))
            st.plotly_chart(fig3, width="stretch")
    st.caption("The same transaction ID is counted as one case even if it has duplicate source rows.")

with exceptions_tab:
    st.subheader("Investigation queue")
    exception_view = filtered.loc[filtered["status"].ne("matched")].copy()
    order = {"High": 0, "Medium": 1, "None": 2}
    exception_view["priority_order"] = exception_view["priority"].map(order)
    exception_view = exception_view.sort_values(["priority_order", "case_date", "case_id"])
    display_columns = ["case_id", "status", "priority", "reason", "ledger_rows", "bank_rows",
                       "ledger_amount_pence", "bank_amount_pence", "amount_difference_pence",
                       "date_lag_days", "review_status", "analyst_note"]
    st.caption(f"{len(exception_view):,} exception cases match the current filters.")
    st.dataframe(exception_view[display_columns], hide_index=True, width="stretch", height=360)
    st.download_button(
        "Download filtered exceptions (CSV)",
        exception_view.drop(columns=["priority_order"]).to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
        file_name="finrecon_exceptions.csv", mime="text/csv",
    )
    st.divider()
    st.subheader("Case review")
    st.caption("An analyst's review status is tracked separately from the machine-detected reconciliation result.")
    if exception_view.empty:
        st.info("Select a filter that includes at least one exception to review a case.")
    else:
        selected_case = st.selectbox("Select case", exception_view["case_id"].tolist())
        selection = cases.loc[cases["case_id"].eq(selected_case)].iloc[0]
        st.write(f"**{selection['status'].replace('_', ' ').title()}** — {selection['reason']}")
        current_review = str(selection["review_status"])
        with st.form("case_review_form"):
            review_status = st.selectbox(
                "Investigation status", REVIEW_STATUSES,
                index=REVIEW_STATUSES.index(current_review) if current_review in REVIEW_STATUSES else 0,
            )
            analyst_note = st.text_area("Investigator notes", value=str(selection["analyst_note"]),
                                        max_chars=2000)
            submitted = st.form_submit_button("Save case review", type="primary")
            if submitted:
                write_review(selected_case, review_status, analyst_note, REVIEW_PATH)
                st.success("Review saved locally.")
                st.rerun()
    st.caption("Local case reviews are demo-only and can be lost on an ephemeral cloud host; they are not stored in MySQL.")

with raw_tab:
    st.subheader("Source data")
    lcol, bcol = st.columns(2)
    with lcol:
        st.write(f"**Internal ledger** — {len(ledger):,} rows")
        st.dataframe(ledger.head(200), hide_index=True, width="stretch", height=350)
        st.download_button("Download ledger CSV", ledger.to_csv(index=False).encode("utf-8"),
                           "ledger_export.csv", mime="text/csv")
    with bcol:
        st.write(f"**Bank statement** — {len(bank):,} rows")
        st.dataframe(bank.head(200), hide_index=True, width="stretch", height=350)
        st.download_button("Download bank CSV", bank.to_csv(index=False).encode("utf-8"),
                           "bank_export.csv", mime="text/csv")
    st.divider()
    st.write("**All reconciliation cases**")
    st.dataframe(cases.head(300), hide_index=True, width="stretch", height=360)
    st.download_button("Download full reconciliation (CSV)",
                       cases.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
                       "reconciliation_cases.csv", mime="text/csv")
    st.caption("Showing first 200 raw rows and first 300 cases in tables; CSV downloads contain all records.")

with mysql_tab:
    st.subheader("Optional MySQL database")
    st.write("The dashboard works completely in CSV mode. Connect MySQL only if you want persistent run snapshots and SQL analysis in MySQL Workbench.")
    st.code("cp .env.example .env  # edit MYSQL_USER / MYSQL_PASSWORD, start MySQL", language="bash")
    left, right = st.columns(2)
    if left.button("Save this reconciliation to MySQL", type="primary"):
        try:
            new_run = save_run(ledger, bank, reconcile(ledger, bank, allowed_date_lag_days=tolerance), tolerance)
            st.success(f"Stored reconciliation run #{new_run} and its raw entries/cases.")
        except Exception as exc:
            st.error(f"Unable to store run. Check MySQL server and .env settings. Details: {exc}")
    if right.button("Load recent MySQL runs"):
        try:
            past_runs = recent_runs()
            if past_runs.empty:
                st.info("No stored runs yet.")
            else:
                st.dataframe(past_runs, hide_index=True, width="stretch")
        except Exception as exc:
            st.error(f"Unable to connect to MySQL: {exc}")
    st.caption("The MySQL database is opt-in; no data is sent to an external service by default.")
