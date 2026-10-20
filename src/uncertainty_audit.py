
from pathlib import Path
from datetime import datetime, timezone
import uuid
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)

zones = pd.read_csv(SYNTHETIC / "zones.csv")
equipment = pd.read_csv(SYNTHETIC / "equipment.csv")
inventory = pd.read_csv(REPORTS / "inventory_register.csv")

required = {
    "zones.csv": (zones, [
        "zone_id", "zone_name", "min_temp_c", "max_temp_c"
    ]),
    "equipment.csv": (equipment, [
        "equipment_id", "zone_id"
    ]),
    "inventory_register.csv": (inventory, [
        "batch_id", "product_id", "zone_id", "product_name",
        "storage_min_c", "storage_max_c", "review_required"
    ]),
}

for name, (frame, columns) in required.items():
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")

zones["zone_id"] = zones["zone_id"].astype(str)
equipment["zone_id"] = equipment["zone_id"].astype(str)
inventory["zone_id"] = inventory["zone_id"].astype(str)

zones["min_temp_c"] = pd.to_numeric(
    zones["min_temp_c"], errors="coerce"
)
zones["max_temp_c"] = pd.to_numeric(
    zones["max_temp_c"], errors="coerce"
)

zones = zones.dropna(
    subset=["zone_id", "min_temp_c", "max_temp_c"]
)

zones = zones[zones["min_temp_c"] < zones["max_temp_c"]]

if zones.empty:
    raise ValueError("No zones have valid temperature limits")

equipment_zones = set(equipment["zone_id"].dropna())
zones_with_equipment = zones[
    zones["zone_id"].isin(equipment_zones)
]

if not zones_with_equipment.empty:
    selected_zone = zones_with_equipment.iloc[0]
else:
    selected_zone = zones.iloc[0]

zone_id = str(selected_zone["zone_id"])
zone_name = str(selected_zone["zone_name"])
zone_min = float(selected_zone["min_temp_c"])
zone_max = float(selected_zone["max_temp_c"])
baseline_temperature = (zone_min + zone_max) / 2

zone_inventory = inventory[
    inventory["zone_id"] == zone_id
].copy()

zone_inventory["storage_min_c"] = pd.to_numeric(
    zone_inventory["storage_min_c"], errors="coerce"
)
zone_inventory["storage_max_c"] = pd.to_numeric(
    zone_inventory["storage_max_c"], errors="coerce"
)

zone_inventory["existing_review_required"] = (
    zone_inventory["review_required"]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin(["true", "1", "yes", "y"])
)

scenarios = [
    {
        "scenario": "Mild",
        "failure_duration_hours": 4,
        "temperature_rise_c_per_hour": 0.6,
        "recovery_rate_c_per_hour": 1.0,
        "total_simulation_hours": 18,
    },
    {
        "scenario": "Moderate",
        "failure_duration_hours": 6,
        "temperature_rise_c_per_hour": 1.2,
        "recovery_rate_c_per_hour": 0.8,
        "total_simulation_hours": 18,
    },
    {
        "scenario": "Severe",
        "failure_duration_hours": 8,
        "temperature_rise_c_per_hour": 1.8,
        "recovery_rate_c_per_hour": 0.6,
        "total_simulation_hours": 18,
    },
]

run_id = str(uuid.uuid4())
run_timestamp = datetime.now(timezone.utc).isoformat()

scenario_records = []
inventory_records = []
audit_records = []

for scenario in scenarios:
    name = scenario["scenario"]
    failure_hours = scenario["failure_duration_hours"]
    rise_rate = scenario["temperature_rise_c_per_hour"]
    recovery_rate = scenario["recovery_rate_c_per_hour"]
    total_hours = scenario["total_simulation_hours"]

    peak_temperature = (
        baseline_temperature + rise_rate * failure_hours
    )

    recovery_hours = max(0, total_hours - failure_hours)

    ending_temperature = max(
        baseline_temperature,
        peak_temperature - recovery_rate * recovery_hours,
    )

    sample_times = [
        step / 2
        for step in range(total_hours * 2 + 1)
    ]

    timeline_temperatures = []

    for hour in sample_times:
        if hour <= failure_hours:
            temperature = (
                baseline_temperature + rise_rate * hour
            )
        else:
            temperature = max(
                baseline_temperature,
                peak_temperature
                - recovery_rate * (hour - failure_hours),
            )

        timeline_temperatures.append(temperature)

    peak_temperature = max(timeline_temperatures)

    outside_zone_count = sum(
        temperature < zone_min or temperature > zone_max
        for temperature in timeline_temperatures
    )

    above_product_max = (
        zone_inventory["storage_max_c"].notna()
        & (peak_temperature > zone_inventory["storage_max_c"])
    )

    below_product_min = (
        zone_inventory["storage_min_c"].notna()
        & (peak_temperature < zone_inventory["storage_min_c"])
    )

    product_range_flags = above_product_max | below_product_min

    for index, batch in zone_inventory.iterrows():
        exceeds_max = bool(above_product_max.loc[index])
        below_min = bool(below_product_min.loc[index])
        existing_review = bool(batch["existing_review_required"])

        reasons = []

        if exceeds_max:
            reasons.append("Simulated peak exceeds recorded product maximum")

        if below_min:
            reasons.append("Simulated peak is below recorded product minimum")

        if existing_review:
            reasons.append("Existing inventory review flag")

        inventory_records.append({
            "run_id": run_id,
            "scenario": name,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "batch_id": batch["batch_id"],
            "product_id": batch["product_id"],
            "product_name": batch["product_name"],
            "simulated_peak_temperature_c": round(
                peak_temperature, 3
            ),
            "peak_exceeds_product_maximum": exceeds_max,
            "peak_below_product_minimum": below_min,
            "existing_review_required": existing_review,
            "simulated_review_flag": bool(
                exceeds_max or below_min or existing_review
            ),
            "review_reason": (
                "; ".join(reasons)
                if reasons
                else "No new temperature-range flag in this scenario"
            ),
            "assessment_scope": (
                "Illustrative scenario only; not evidence of actual "
                "batch exposure or product safety"
            ),
        })

    flagged_batches = int(
        (
            product_range_flags
            | zone_inventory["existing_review_required"]
        ).sum()
    )

    scenario_records.append({
        "run_id": run_id,
        "scenario": name,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "baseline_temperature_c": round(
            baseline_temperature, 3
        ),
        "failure_duration_hours": failure_hours,
        "temperature_rise_c_per_hour": rise_rate,
        "recovery_rate_c_per_hour": recovery_rate,
        "total_simulation_hours": total_hours,
        "peak_simulated_temperature_c": round(
            peak_temperature, 3
        ),
        "ending_simulated_temperature_c": round(
            ending_temperature, 3
        ),
        "timeline_points_outside_zone_range": outside_zone_count,
        "inventory_batches_in_zone": len(zone_inventory),
        "batches_flagged_for_review": flagged_batches,
        "scope": (
            "Illustrative temperature model; not an operational "
            "product-safety determination"
        ),
    })

    audit_records.append({
        "run_id": run_id,
        "run_timestamp_utc": run_timestamp,
        "scenario": name,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "baseline_temperature_c": round(
            baseline_temperature, 3
        ),
        "failure_duration_hours": failure_hours,
        "temperature_rise_c_per_hour": rise_rate,
        "recovery_rate_c_per_hour": recovery_rate,
        "total_simulation_hours": total_hours,
        "peak_simulated_temperature_c": round(
            peak_temperature, 3
        ),
        "ending_simulated_temperature_c": round(
            ending_temperature, 3
        ),
        "batches_flagged_for_review": flagged_batches,
        "method": "Linear temperature rise and recovery",
        "data_basis": "Synthetic warehouse data and scenario assumptions",
        "scope": "Planning simulation only",
    })

scenario_summary = pd.DataFrame(scenario_records)
inventory_summary = pd.DataFrame(inventory_records)
audit_new = pd.DataFrame(audit_records)

scenario_summary.to_csv(
    REPORTS / "uncertainty_scenario_comparison.csv",
    index=False,
)

inventory_summary.to_csv(
    REPORTS / "uncertainty_inventory_review.csv",
    index=False,
)

audit_path = REPORTS / "simulation_audit_log.csv"

if audit_path.exists():
    existing_audit = pd.read_csv(audit_path)

    if not existing_audit.empty and "run_id" in existing_audit.columns:
        existing_audit = existing_audit[
            existing_audit["run_id"].astype(str) != run_id
        ]

    audit_combined = pd.concat(
        [existing_audit, audit_new],
        ignore_index=True,
        sort=False,
    )
else:
    audit_combined = audit_new

audit_combined.to_csv(audit_path, index=False)

validation = pd.DataFrame([
    {
        "check": "All three scenarios were generated",
        "passed": len(scenario_summary) == 3,
    },
    {
        "check": "Every scenario has a finite peak temperature",
        "passed": bool(
            scenario_summary["peak_simulated_temperature_c"]
            .notna().all()
            and scenario_summary[
                "peak_simulated_temperature_c"
            ].map(lambda value: abs(value) != float("inf")).all()
        ),
    },
    {
        "check": "Scenario failure durations increase by severity",
        "passed": bool(
            scenario_summary["failure_duration_hours"].tolist()
            == [4, 6, 8]
        ),
    },
    {
        "check": "Scenario peak temperatures increase by severity",
        "passed": bool(
            scenario_summary[
                "peak_simulated_temperature_c"
            ].is_monotonic_increasing
        ),
    },
    {
        "check": "Inventory review output contains only the selected zone",
        "passed": bool(
            (inventory_summary["zone_id"] == zone_id).all()
        ),
    },
    {
        "check": "Audit log contains all scenarios for this run",
        "passed": bool(
            (audit_new["run_id"] == run_id).all()
            and len(audit_new) == 3
        ),
    },
])

validation.to_csv(
    REPORTS / "uncertainty_validation.csv",
    index=False,
)

print("Day 11 uncertainty analysis completed.")
print(f"Selected zone: {zone_name} ({zone_id})")
print(f"Scenario count: {len(scenario_summary)}")
print(
    "Peak temperatures: "
    + ", ".join(
        f"{row.scenario}={row.peak_simulated_temperature_c:.2f} C"
        for row in scenario_summary.itertuples()
    )
)
print(
    "Batches flagged by scenario: "
    + ", ".join(
        f"{row.scenario}={row.batches_flagged_for_review}"
        for row in scenario_summary.itertuples()
    )
)
print(f"Audit run ID: {run_id}")
print(f"All validation checks passed: {validation['passed'].all()}")
print(f"Reports saved to: {REPORTS}")
