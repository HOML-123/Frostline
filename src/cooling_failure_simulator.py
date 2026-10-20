
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"
CHARTS = ROOT / "outputs" / "charts"

REPORTS.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

FAILURE_DURATION_HOURS = 6
TOTAL_SIMULATION_HOURS = 18
TIME_STEP_HOURS = 0.5
TEMPERATURE_RISE_C_PER_HOUR = 1.2
RECOVERY_RATE_C_PER_HOUR = 0.8

zones = pd.read_csv(SYNTHETIC / "zones.csv")
equipment = pd.read_csv(SYNTHETIC / "equipment.csv")
inventory = pd.read_csv(REPORTS / "inventory_register.csv")

required_zone_columns = [
    "zone_id",
    "zone_name",
    "min_temp_c",
    "max_temp_c",
    "capacity_units",
]

required_equipment_columns = [
    "equipment_id",
    "equipment_type",
    "zone_id",
    "equipment_status",
    "backup_power_available",
]

required_inventory_columns = [
    "batch_id",
    "product_id",
    "zone_id",
    "quantity_units",
    "product_name",
    "storage_min_c",
    "storage_max_c",
    "review_required",
]

for name, frame, columns in [
    ("zones.csv", zones, required_zone_columns),
    ("equipment.csv", equipment, required_equipment_columns),
    ("inventory_register.csv", inventory, required_inventory_columns),
]:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")

if zones.empty:
    raise ValueError("zones.csv contains no zones")

zones["min_temp_c"] = pd.to_numeric(zones["min_temp_c"], errors="coerce")
zones["max_temp_c"] = pd.to_numeric(zones["max_temp_c"], errors="coerce")

zones = zones.dropna(subset=["zone_id", "min_temp_c", "max_temp_c"])

if zones.empty:
    raise ValueError("No zones have valid temperature limits")

equipment["zone_id"] = equipment["zone_id"].astype(str)
zones["zone_id"] = zones["zone_id"].astype(str)
inventory["zone_id"] = inventory["zone_id"].astype(str)

equipment["equipment_type"] = equipment["equipment_type"].fillna("Unknown")
equipment["equipment_status"] = equipment["equipment_status"].fillna("Unknown")
equipment["backup_power_available"] = (
    equipment["backup_power_available"]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin(["true", "1", "yes", "y"])
)

zone_equipment_counts = equipment.groupby("zone_id").size().to_dict()
zones["equipment_count"] = zones["zone_id"].map(zone_equipment_counts).fillna(0)

zones_with_equipment = zones[zones["equipment_count"] > 0]

if not zones_with_equipment.empty:
    selected_zone = zones_with_equipment.iloc[0]
else:
    selected_zone = zones.iloc[0]

zone_id = str(selected_zone["zone_id"])
zone_name = str(selected_zone["zone_name"])
zone_min = float(selected_zone["min_temp_c"])
zone_max = float(selected_zone["max_temp_c"])
baseline_temperature = (zone_min + zone_max) / 2

if zone_min >= zone_max:
    raise ValueError(f"Invalid temperature range for zone {zone_name}")

zone_equipment = equipment[equipment["zone_id"] == zone_id].copy()
zone_inventory = inventory[inventory["zone_id"] == zone_id].copy()

time_values = [
    round(value, 2)
    for value in [
        i * TIME_STEP_HOURS
        for i in range(
            int(TOTAL_SIMULATION_HOURS / TIME_STEP_HOURS) + 1
        )
    ]
]

current_temperature = baseline_temperature
timeline_records = []

for hour in time_values:
    if hour < FAILURE_DURATION_HOURS:
        current_temperature = (
            baseline_temperature
            + TEMPERATURE_RISE_C_PER_HOUR * hour
        )
        phase = "Cooling failure"
    else:
        recovery_hours = hour - FAILURE_DURATION_HOURS
        current_temperature = (
            baseline_temperature
            + TEMPERATURE_RISE_C_PER_HOUR * FAILURE_DURATION_HOURS
            - RECOVERY_RATE_C_PER_HOUR * recovery_hours
        )
        current_temperature = max(
            baseline_temperature,
            current_temperature
        )
        phase = "Recovery"

    outside_zone_range = (
        current_temperature < zone_min
        or current_temperature > zone_max
    )

    timeline_records.append({
        "zone_id": zone_id,
        "zone_name": zone_name,
        "simulation_hour": hour,
        "phase": phase,
        "simulated_temperature_c": round(current_temperature, 3),
        "zone_min_temp_c": zone_min,
        "zone_max_temp_c": zone_max,
        "outside_zone_temperature_range": outside_zone_range,
        "simulation_assumption": True,
    })

timeline = pd.DataFrame(timeline_records)

peak_temperature = float(timeline["simulated_temperature_c"].max())
first_outside = timeline[timeline["outside_zone_temperature_range"]]

if first_outside.empty:
    first_outside_hour = None
else:
    first_outside_hour = float(first_outside.iloc[0]["simulation_hour"])

inventory_review = zone_inventory.copy()

inventory_review["storage_min_c"] = pd.to_numeric(
    inventory_review["storage_min_c"], errors="coerce"
)
inventory_review["storage_max_c"] = pd.to_numeric(
    inventory_review["storage_max_c"], errors="coerce"
)

inventory_review["simulated_peak_zone_temperature_c"] = peak_temperature

inventory_review["peak_exceeds_product_maximum"] = (
    inventory_review["storage_max_c"].notna()
    & (peak_temperature > inventory_review["storage_max_c"])
)

inventory_review["peak_below_product_minimum"] = (
    inventory_review["storage_min_c"].notna()
    & (peak_temperature < inventory_review["storage_min_c"])
)

inventory_review["existing_review_required"] = (
    inventory_review["review_required"]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin(["true", "1", "yes", "y"])
)

inventory_review["simulated_review_flag"] = (
    inventory_review["peak_exceeds_product_maximum"]
    | inventory_review["peak_below_product_minimum"]
    | inventory_review["existing_review_required"]
)

inventory_review["review_reason"] = "No new temperature-range flag in this simulation"
inventory_review.loc[
    inventory_review["peak_exceeds_product_maximum"],
    "review_reason"
] = "Simulated peak exceeds recorded product storage maximum; authorised review required"
inventory_review.loc[
    inventory_review["peak_below_product_minimum"],
    "review_reason"
] = "Simulated peak is below recorded product storage minimum; authorised review required"
inventory_review.loc[
    inventory_review["existing_review_required"],
    "review_reason"
] = "Existing inventory review flag"

inventory_review["assessment_scope"] = (
    "Illustrative zone-level simulation only; not evidence of actual batch exposure or product safety"
)

equipment_summary = zone_equipment.copy()
equipment_summary["simulated_failure_scenario"] = True
equipment_summary["scenario_note"] = (
    "Cooling failure is imposed as a simulation assumption regardless of equipment status or backup power"
)

timeline.to_csv(
    REPORTS / "cooling_failure_temperature_timeline.csv",
    index=False
)

inventory_review.to_csv(
    REPORTS / "cooling_failure_affected_inventory.csv",
    index=False
)

equipment_summary.to_csv(
    REPORTS / "cooling_failure_equipment_context.csv",
    index=False
)

summary = pd.DataFrame([{
    "zone_id": zone_id,
    "zone_name": zone_name,
    "zone_min_temp_c": zone_min,
    "zone_max_temp_c": zone_max,
    "baseline_temperature_c": round(baseline_temperature, 3),
    "failure_duration_hours": FAILURE_DURATION_HOURS,
    "total_simulation_hours": TOTAL_SIMULATION_HOURS,
    "temperature_rise_c_per_hour": TEMPERATURE_RISE_C_PER_HOUR,
    "recovery_rate_c_per_hour": RECOVERY_RATE_C_PER_HOUR,
    "peak_simulated_temperature_c": round(peak_temperature, 3),
    "first_outside_zone_range_hour": first_outside_hour,
    "timeline_points": len(timeline),
    "equipment_records_in_zone": len(zone_equipment),
    "inventory_batches_in_zone": len(zone_inventory),
    "batches_flagged_for_review": int(inventory_review["simulated_review_flag"].sum()),
    "method": "Illustrative linear temperature rise and recovery",
    "scope": "Synthetic scenario; no actual batch exposure or safety determination",
}])

summary.to_csv(
    REPORTS / "cooling_failure_simulation_summary.csv",
    index=False
)

validation = pd.DataFrame([
    {
        "check": "Simulation timeline has expected number of rows",
        "passed": len(timeline) == len(time_values),
    },
    {
        "check": "Simulation starts at baseline temperature",
        "passed": abs(
            timeline.iloc[0]["simulated_temperature_c"]
            - baseline_temperature
        ) < 1e-6,
    },
    {
        "check": "Peak temperature is not below baseline",
        "passed": peak_temperature >= baseline_temperature,
    },
    {
        "check": "Simulation temperatures are numeric and finite",
        "passed": bool(
            timeline["simulated_temperature_c"].notna().all()
            and timeline["simulated_temperature_c"].map(
                lambda value: pd.notna(value) and abs(value) != float("inf")
            ).all()
        ),
    },
    {
        "check": "Affected inventory output includes only selected zone",
        "passed": bool(
            (inventory_review["zone_id"] == zone_id).all()
        ),
    },
    {
        "check": "Review flags are present for every inventory row",
        "passed": "simulated_review_flag" in inventory_review.columns,
    },
])

validation.to_csv(
    REPORTS / "cooling_failure_validation.csv",
    index=False
)

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(
    timeline["simulation_hour"],
    timeline["simulated_temperature_c"],
    marker="o",
    markersize=3,
    label="Simulated temperature",
)
ax.axhline(
    zone_max,
    linestyle="--",
    label="Zone maximum temperature",
)
ax.axhline(
    zone_min,
    linestyle="--",
    label="Zone minimum temperature",
)
ax.axvline(
    FAILURE_DURATION_HOURS,
    linestyle=":",
    label="Cooling recovery begins",
)
ax.set_title(f"Illustrative Cooling Failure and Recovery — {zone_name}")
ax.set_xlabel("Simulation time (hours)")
ax.set_ylabel("Temperature (°C)")
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(
    CHARTS / "cooling_failure_recovery.png",
    dpi=150,
)
plt.close(fig)

print("Day 10 cooling failure simulation completed.")
print(f"Selected zone: {zone_name} ({zone_id})")
print(f"Peak simulated temperature: {peak_temperature:.2f} C")
print(f"Inventory batches in selected zone: {len(zone_inventory)}")
print(
    "Batches flagged for review: "
    f"{int(inventory_review['simulated_review_flag'].sum())}"
)
print(f"All validation checks passed: {validation['passed'].all()}")
print(f"Reports saved to: {REPORTS}")
print(f"Chart saved to: {CHARTS / 'cooling_failure_recovery.png'}")
