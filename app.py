
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "outputs" / "reports"
CHARTS = ROOT / "outputs" / "charts"
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(
    page_title="Frostline | Cold-Chain Intelligence",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

.stApp {
    background: radial-gradient(ellipse at 10% 0%, rgba(0,190,220,.08), transparent 35%), #07111f;
    color: #e6f2ff;
    font-family: 'DM Sans', sans-serif;
}

header[data-testid="stHeader"] {
    background: rgba(7,17,31,.96);
    height: 3.5rem;
}

[data-testid="stToolbar"] {
    visibility: visible;
    right: 1rem;
}

.block-container {
    max-width: 1500px;
    padding-top: 3rem !important;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    color: #f1f8ff !important;
    font-family: 'Space Grotesk', sans-serif !important;
    letter-spacing: -.35px;
}

h1 {
    padding-top: .2rem;
    line-height: 1.3 !important;
}

p, li, label {
    color: #c1d2e3;
}

[data-testid="stSidebar"] {
    background: #091523;
    border-right: 1px solid rgba(103,232,249,.16);
}

[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.5rem;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    line-height: 1.55;
}

[data-testid="stSidebar"] [data-testid="stRadio"] > label {
    color: #8fa9bd;
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    margin-bottom: .6rem;
}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
    gap: 5px;
}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] > label {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 10px 11px;
    margin: 0;
    transition: background .2s ease, border-color .2s ease;
}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] > label:hover {
    background: rgba(22,54,76,.65);
    border-color: rgba(103,232,249,.15);
}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
    background: rgba(8,145,178,.17);
    border-color: rgba(103,232,249,.3);
}

[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] > label p {
    color: #d7e9f5;
    font-size: .88rem;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #132a3f, #0c1c2d);
    border: 1px solid rgba(103,232,249,.18);
    border-radius: 14px;
    padding: 17px 19px;
}

[data-testid="stMetricLabel"] {
    color: #9eb8cd !important;
}

[data-testid="stMetricValue"] {
    color: #e8fbff !important;
    font-family: 'Space Grotesk', sans-serif;
}

.stDataFrame, [data-testid="stTable"] {
    border: 1px solid rgba(103,232,249,.14);
    border-radius: 11px;
    overflow: hidden;
}

[data-testid="stExpander"] {
    background: rgba(15,34,52,.55);
    border: 1px solid rgba(103,232,249,.14);
    border-radius: 11px;
    margin-bottom: 8px;
}

.stButton > button, .stDownloadButton > button {
    background: linear-gradient(110deg, #0e7490, #0891b2);
    color: #f0fdff;
    border: 1px solid rgba(103,232,249,.3);
    border-radius: 9px;
    font-weight: 600;
}

.stButton > button:hover, .stDownloadButton > button:hover {
    background: #0891b2;
    border-color: #67e8f9;
    color: white;
}

.stSelectbox div[data-baseweb="select"] > div,
.stTextInput input,
.stNumberInput input {
    background: #102337;
    color: #e6f2ff;
    border-color: #25445d;
    border-radius: 9px;
}

hr {
    border-color: rgba(103,232,249,.15);
}

.hero {
    background: linear-gradient(120deg, #0c2338, #0a4258, #16284f);
    border: 1px solid rgba(103,232,249,.25);
    border-radius: 20px;
    padding: 30px;
    margin: 8px 0 25px;
    box-shadow: 0 16px 45px rgba(0,0,0,.16);
}

.eyebrow, .section-label {
    color: #67e8f9;
    font-size: .73rem;
    font-weight: 700;
    letter-spacing: 1.7px;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.hero-title {
    color: #f0f9ff;
    font-family: 'Space Grotesk', sans-serif;
    font-size: clamp(2rem, 4vw, 3.1rem);
    line-height: 1.2;
    font-weight: 700;
    margin: 0 0 14px;
}

.hero-description {
    color: #bfd7e8;
    font-size: .98rem;
    max-width: 800px;
    line-height: 1.8;
    margin-bottom: 18px;
}

.status-pill {
    display: inline-block;
    color: #a5f3fc;
    background: rgba(8,145,178,.14);
    border: 1px solid rgba(103,232,249,.28);
    border-radius: 999px;
    padding: 7px 12px;
    font-size: .75rem;
    font-weight: 600;
}

.module-card {
    background: linear-gradient(145deg, rgba(19,42,63,.78), rgba(11,26,43,.86));
    border: 1px solid rgba(103,232,249,.15);
    border-radius: 14px;
    padding: 19px;
    min-height: 145px;
    margin-bottom: 12px;
}

.module-card h3 {
    font-size: 1.03rem;
    margin-bottom: 8px;
}

.module-card p {
    color: #a9c0d2;
    font-size: .87rem;
    line-height: 1.65;
}

.module-number {
    color: #67e8f9;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: 1.3px;
    margin-bottom: 8px;
}

.small-note {
    color: #8fa9bd;
    font-size: .8rem;
}

@media (max-width: 768px) {
    .block-container {
        padding: 2rem 1rem !important;
    }

    .hero {
        padding: 21px;
    }

    .module-card {
        min-height: auto;
    }
}
</style>
""", unsafe_allow_html=True)


def load_csv(folder, filename):
    path = folder / filename

    if not path.exists():
        return None

    try:
        return pd.read_csv(path)
    except Exception as error:
        st.warning(f"Could not read {filename}: {error}")
        return None


def show_header(title, subtitle):
    st.markdown(
        f"""
        <div class="section-label">FROSTLINE / OPERATIONS</div>
        <h1>{title}</h1>
        <p style="color:#9eb8cd;margin-top:0;">{subtitle}</p>
        """,
        unsafe_allow_html=True,
    )


def show_report(filename, title=None, folder=REPORTS):
    title = title or filename.replace(".csv", "").replace("_", " ").title()
    data = load_csv(folder, filename)

    st.subheader(title)

    if data is None:
        st.caption(f"Report not available yet: {filename}")
        return

    st.caption(f"{len(data):,} rows · {len(data.columns)} columns")
    st.dataframe(data, use_container_width=True, hide_index=True)

    st.download_button(
        label=f"Download {filename}",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=f"download_{folder.name}_{filename}",
    )


def show_chart(filename, title=None):
    path = CHARTS / filename

    if path.exists():
        st.subheader(title or filename.replace("_", " ").replace(".png", "").title())
        st.image(str(path), use_container_width=True)


def show_validation(filename, title):
    data = load_csv(REPORTS, filename)
    st.subheader(title)

    if data is None:
        st.caption("Validation report is not available yet.")
        return

    if "passed" in data.columns:
        passed = data["passed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        first, second = st.columns(2)
        first.metric("Checks passed", int(passed.sum()))
        second.metric("Checks needing attention", int((~passed).sum()))

        if passed.all():
            st.success("All recorded validation checks passed.")
        else:
            st.warning("Some checks need attention. Review the rows below.")

    st.dataframe(data, use_container_width=True, hide_index=True)


with st.sidebar:
    st.markdown(
        """
        <div style="padding:8px 0 16px;">
            <div style="font-size:2rem;">❄️</div>
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.6rem;font-weight:700;color:#67e8f9;">FROSTLINE</div>
            <div style="font-size:.68rem;letter-spacing:1.4px;color:#8fa9bd;">COLD-CHAIN INTELLIGENCE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    page = st.radio(
        "WORKSPACE",
        [
            "Overview",
            "Thermal Monitoring",
            "Risk & Inventory",
            "Relocation Planning",
            "Order Rescue",
            "Cooling Failure",
            "Uncertainty & Audit",
            "Data Quality & Validation",
        ],
        label_visibility="visible",
    )

    st.divider()
    st.caption("DECISION SUPPORT PROTOTYPE")
    st.caption("Historical data · Simulated scenarios")


if page == "Overview":
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">COLD-CHAIN INTELLIGENCE PLATFORM</div>
            <div class="hero-title">See the risks.<br>Plan the response.</div>
            <div class="hero-description">
                Explore temperature trends, review inventory risks, plan relocations,
                analyse order fulfilment and compare recovery scenarios in one workspace.
            </div>
            <span class="status-pill">❄ &nbsp; ANALYSIS WORKSPACE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">SYSTEM OVERVIEW</div>', unsafe_allow_html=True)
    st.subheader("Your operations at a glance")

    risk = load_csv(REPORTS, "risk_level_summary.csv")
    inventory = load_csv(REPORTS, "inventory_register.csv")
    orders = load_csv(REPORTS, "order_fulfilment_summary.csv")
    thermal = load_csv(REPORTS, "thermal_sensor_summary.csv")
    rescue = load_csv(REPORTS, "order_rescue_summary.csv")
    cooling = load_csv(REPORTS, "cooling_failure_simulation_summary.csv")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Inventory batches", f"{len(inventory):,}" if inventory is not None else "—")
    col2.metric("Thermal sensor records", f"{len(thermal):,}" if thermal is not None else "—")
    col3.metric("Orders analysed", f"{len(orders):,}" if orders is not None else "—")

    if rescue is not None and not rescue.empty and "overall_fulfilment_percentage" in rescue.columns:
        col4.metric("Simulated fulfilment", f"{float(rescue.iloc[0]['overall_fulfilment_percentage']):.1f}%")
    else:
        col4.metric("Simulated fulfilment", "—")

    st.divider()
    st.markdown('<div class="section-label">KEY REPORTS</div>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.subheader("Risk distribution")
        if risk is not None:
            st.dataframe(risk, use_container_width=True, hide_index=True)
        else:
            st.caption("Run the risk engine to populate this section.")

    with right:
        st.subheader("Cooling scenario")
        if cooling is not None:
            st.dataframe(cooling, use_container_width=True, hide_index=True)
        else:
            st.caption("Run the Day 10 simulator to populate this section.")

    st.divider()
    st.markdown('<div class="section-label">EXPLORE THE WORKSPACE</div>', unsafe_allow_html=True)
    st.subheader("Analysis modules")

    modules = [
        ("01", "Thermal Monitoring", "Explore sensor summaries, temperature trends and recorded excursions."),
        ("02", "Risk & Inventory", "Review batch risk assessments, inventory records and expiry watchlists."),
        ("03", "Relocation Planning", "Compare baseline relocation plans and constrained optimisation results."),
        ("04", "Order Rescue", "Explore simulated order allocation and fulfilment results."),
        ("05", "Cooling Failure", "Review simulated temperature recovery and affected inventory."),
        ("06", "Uncertainty & Audit", "Compare predefined scenarios and inspect simulation run history."),
        ("07", "Data Quality & Validation", "Review source quality, cleaning reports and validation checks."),
    ]

    for start in range(0, len(modules), 2):
        columns = st.columns(2)

        for column, (number, title, description) in zip(columns, modules[start:start + 2]):
            with column:
                st.markdown(
                    f"""
                    <div class="module-card">
                        <div class="module-number">MODULE {number}</div>
                        <h3>{title}</h3>
                        <p>{description}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.info(
        "Decision-support prototype. Temperature scenarios and inventory flags are analytical outputs, "
        "not certification of product safety or release approval."
    )

elif page == "Thermal Monitoring":
    show_header("Thermal Monitoring", "Explore processed sensor data and recorded temperature analysis.")
    show_chart("temperature_timeline.png", "Temperature Timeline")
    show_chart("daily_mean_temperature.png", "Daily Mean Temperature")
    show_chart("temperature_excursions_by_sensor.png", "Excursions by Sensor")

    for filename, title in [
        ("thermal_sensor_summary.csv", "Sensor Summary"),
        ("thermal_daily_summary.csv", "Daily Temperature Summary"),
        ("temperature_excursions.csv", "Recorded Temperature Excursions"),
        ("sensor_data_gaps.csv", "Sensor Data Gaps"),
        ("thermal_file_status.csv", "Thermal File Status"),
    ]:
        show_report(filename, title)

    readings = load_csv(PROCESSED, "thermal_readings.csv")

    if readings is not None:
        st.subheader("Processed Thermal Readings")
        st.dataframe(readings.head(500), use_container_width=True, hide_index=True)
        st.caption("Showing up to the first 500 records.")
        st.download_button(
            "Download processed thermal readings",
            data=readings.to_csv(index=False).encode("utf-8"),
            file_name="thermal_readings.csv",
            mime="text/csv",
        )

elif page == "Risk & Inventory":
    show_header("Risk & Inventory", "Review risk assessments and inventory planning outputs.")
    st.info("Flags indicate a need for review, not a product safety determination.")

    for filename, title in [
        ("risk_level_summary.csv", "Risk Level Summary"),
        ("risk_engine_summary.csv", "Risk Engine Summary"),
        ("batch_risk_assessment.csv", "Batch Risk Assessment"),
        ("inventory_register.csv", "Inventory Register"),
        ("product_inventory_summary.csv", "Product Inventory Summary"),
        ("zone_inventory_summary.csv", "Zone Inventory Summary"),
        ("inventory_expiry_watchlist.csv", "Expiry Watchlist"),
        ("inventory_review_queue.csv", "Inventory Review Queue"),
        ("inventory_traceability.csv", "Inventory Traceability"),
    ]:
        with st.expander(title, expanded=filename in ["risk_level_summary.csv", "inventory_review_queue.csv"]):
            show_report(filename, title)

elif page == "Relocation Planning":
    show_header("Relocation Planning", "Compare baseline relocation strategies with constrained optimisation.")

    for filename, title in [
        ("baseline_relocation_comparison.csv", "Baseline Comparison"),
        ("relocation_optimiser_summary.csv", "Optimised Plan Summary"),
        ("baseline_relocation_capacity.csv", "Baseline Capacity"),
        ("relocation_optimiser_capacity.csv", "Optimised Capacity"),
        ("relocation_plan_first_fit.csv", "First-Fit Plan"),
        ("relocation_plan_best_fit.csv", "Best-Fit Plan"),
        ("relocation_plan_priority_first.csv", "Priority-First Plan"),
        ("relocation_plan_optimised.csv", "Constrained Optimised Plan"),
        ("baseline_relocation_validation.csv", "Baseline Validation"),
        ("relocation_optimiser_validation.csv", "Optimiser Validation"),
    ]:
        with st.expander(title):
            show_report(filename, title)

    st.caption("The constrained optimiser is a heuristic and is not guaranteed to find the globally optimal solution.")

elif page == "Order Rescue":
    show_header("Order Rescue", "Explore simulated order allocation and fulfilment results.")
    st.info("Allocation is a simulation. It does not authorise release or shipment of goods that require quality review.")

    summary = load_csv(REPORTS, "order_rescue_summary.csv")

    if summary is not None and not summary.empty:
        row = summary.iloc[0]
        a, b, c, d = st.columns(4)
        a.metric("Orders", f"{int(row['total_orders']):,}")
        b.metric("Requested units", f"{row['total_requested_units']:,.0f}")
        c.metric("Allocated units", f"{row['total_allocated_units']:,.0f}")
        d.metric("Fulfilment", f"{row['overall_fulfilment_percentage']:.1f}%")

    for filename, title in [
        ("order_rescue_summary.csv", "Rescue Summary"),
        ("order_fulfilment_summary.csv", "Order Fulfilment"),
        ("order_line_fulfilment_summary.csv", "Order-Line Fulfilment"),
        ("order_allocation_details.csv", "Allocation Details"),
        ("order_allocation_remaining_inventory.csv", "Remaining Eligible Inventory"),
    ]:
        with st.expander(title, expanded=filename == "order_rescue_summary.csv"):
            show_report(filename, title)

elif page == "Cooling Failure":
    show_header("Cooling Failure & Recovery", "Inspect the saved cooling failure scenario and affected inventory.")
    st.info("This is an illustrative linear temperature model, not live equipment telemetry.")
    show_chart("cooling_failure_recovery.png", "Simulated Temperature Recovery")

    summary = load_csv(REPORTS, "cooling_failure_simulation_summary.csv")

    if summary is not None and not summary.empty:
        row = summary.iloc[0]
        a, b, c = st.columns(3)
        a.metric("Peak simulated temperature", f"{row['peak_simulated_temperature_c']:.2f} °C")
        b.metric("Batches in selected zone", f"{int(row['inventory_batches_in_zone']):,}")
        c.metric("Batches flagged for review", f"{int(row['batches_flagged_for_review']):,}")

    for filename, title in [
        ("cooling_failure_simulation_summary.csv", "Simulation Summary"),
        ("cooling_failure_temperature_timeline.csv", "Temperature Timeline"),
        ("cooling_failure_affected_inventory.csv", "Affected Inventory Review"),
        ("cooling_failure_equipment_context.csv", "Equipment Context"),
    ]:
        with st.expander(title, expanded=filename == "cooling_failure_simulation_summary.csv"):
            show_report(filename, title)

elif page == "Uncertainty & Audit":
    show_header("Uncertainty & Audit", "Compare predefined scenarios and inspect the simulation run history.")
    st.info("Mild, Moderate and Severe are predefined sensitivity scenarios, not probability estimates or forecasts.")

    scenarios = load_csv(REPORTS, "uncertainty_scenario_comparison.csv")

    if scenarios is not None and not scenarios.empty:
        if {"scenario", "peak_simulated_temperature_c"}.issubset(scenarios.columns):
            st.subheader("Peak Temperature by Scenario")
            st.bar_chart(scenarios.set_index("scenario")[["peak_simulated_temperature_c"]])

        if "batches_flagged_for_review" in scenarios.columns:
            st.subheader("Batches Flagged for Review")
            st.bar_chart(scenarios.set_index("scenario")[["batches_flagged_for_review"]])

    for filename, title in [
        ("uncertainty_scenario_comparison.csv", "Scenario Comparison"),
        ("uncertainty_inventory_review.csv", "Scenario Inventory Review"),
        ("simulation_audit_log.csv", "Simulation Audit Log"),
    ]:
        with st.expander(title, expanded=filename == "uncertainty_scenario_comparison.csv"):
            show_report(filename, title)

elif page == "Data Quality & Validation":
    show_header("Data Quality & Validation", "Review source data quality, cleaning reports and validation checks.")

    for filename, title in [
        ("data_quality_summary.csv", "Source Data Quality"),
        ("cleaning_quality_report.csv", "Sensor Cleaning Report"),
        ("synthetic_data_validation.csv", "Synthetic Data Validation"),
    ]:
        with st.expander(title, expanded=True):
            show_report(filename, title)

    for filename, title in [
        ("risk_engine_validation.csv", "Risk Engine Validation"),
        ("inventory_validation.csv", "Inventory Validation"),
        ("baseline_relocation_validation.csv", "Baseline Relocation Validation"),
        ("relocation_optimiser_validation.csv", "Optimiser Validation"),
        ("order_rescue_validation.csv", "Order Rescue Validation"),
        ("cooling_failure_validation.csv", "Cooling Failure Validation"),
        ("uncertainty_validation.csv", "Uncertainty Analysis Validation"),
    ]:
        with st.expander(title):
            show_validation(filename, title)

    profile_path = REPORTS / "dataset_profile.txt"

    if profile_path.exists():
        with st.expander("Dataset Profile"):
            st.text(profile_path.read_text(encoding="utf-8", errors="replace"))

st.divider()
st.markdown(
    '<p class="small-note">FROSTLINE · Cold-chain decision support · Analytical outputs and simulated scenarios</p>',
    unsafe_allow_html=True,
)