from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)

THERMAL_FILE = PROCESSED / "thermal_readings.csv"
PRODUCTS_FILE = SYNTHETIC / "products.csv"
ZONES_FILE = SYNTHETIC / "zones.csv"
INVENTORY_FILE = SYNTHETIC / "inventory_batches.csv"

REQUIRED_FILES = [
    THERMAL_FILE,
    PRODUCTS_FILE,
    ZONES_FILE,
    INVENTORY_FILE
]

missing_files = [str(path) for path in REQUIRED_FILES if not path.exists()]

if missing_files:
    raise FileNotFoundError(
        "Required files are missing:\n" + "\n".join(missing_files)
    )

thermal = pd.read_csv(THERMAL_FILE)
products = pd.read_csv(PRODUCTS_FILE)
zones = pd.read_csv(ZONES_FILE)
inventory = pd.read_csv(INVENTORY_FILE)

thermal.columns = thermal.columns.str.strip()
products.columns = products.columns.str.strip()
zones.columns = zones.columns.str.strip()
inventory.columns = inventory.columns.str.strip()

required_columns = {
    "thermal": {"timestamp", "temperature", "sensor"},
    "products": {
        "product_id", "product_name", "category", "storage_min_c",
        "storage_max_c", "priority_class", "shelf_life_days"
    },
    "zones": {
        "zone_id", "zone_name", "zone_type", "min_temp_c", "max_temp_c"
    },
    "inventory": {
        "batch_id", "lot_id", "product_id", "zone_id",
        "quantity_units", "expiry_date", "batch_status"
    }
}

datasets = {
    "thermal": thermal,
    "products": products,
    "zones": zones,
    "inventory": inventory
}

for dataset_name, required in required_columns.items():
    missing_columns = required - set(datasets[dataset_name].columns)
    if missing_columns:
        raise ValueError(
            f"{dataset_name} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

if products["product_id"].duplicated().any():
    raise ValueError("Duplicate product IDs found.")

if zones["zone_id"].duplicated().any():
    raise ValueError("Duplicate zone IDs found.")

if inventory["batch_id"].duplicated().any():
    raise ValueError("Duplicate batch IDs found.")

for column in ["storage_min_c", "storage_max_c"]:
    products[column] = pd.to_numeric(products[column], errors="coerce")

for column in ["min_temp_c", "max_temp_c"]:
    zones[column] = pd.to_numeric(zones[column], errors="coerce")

inventory["quantity_units"] = pd.to_numeric(
    inventory["quantity_units"], errors="coerce"
)
inventory["expiry_date"] = pd.to_datetime(
    inventory["expiry_date"], errors="coerce"
).dt.normalize()

thermal["timestamp"] = pd.to_datetime(
    thermal["timestamp"], errors="coerce"
)
thermal["temperature"] = pd.to_numeric(
    thermal["temperature"], errors="coerce"
)

thermal = thermal.dropna(
    subset=["timestamp", "temperature", "sensor"]
).copy()

products = products.dropna(
    subset=["product_id", "storage_min_c", "storage_max_c"]
).copy()

zones = zones.dropna(
    subset=["zone_id", "min_temp_c", "max_temp_c"]
).copy()

inventory = inventory.dropna(
    subset=["batch_id", "product_id", "zone_id", "quantity_units", "expiry_date"]
).copy()

if (products["storage_min_c"] > products["storage_max_c"]).any():
    raise ValueError("Some products have invalid temperature limits.")

if (zones["min_temp_c"] > zones["max_temp_c"]).any():
    raise ValueError("Some zones have invalid temperature limits.")

if (inventory["quantity_units"] < 0).any():
    raise ValueError("Inventory quantities cannot be negative.")

unknown_products = set(inventory["product_id"]) - set(products["product_id"])
unknown_zones = set(inventory["zone_id"]) - set(zones["zone_id"])

if unknown_products:
    raise ValueError(f"Unknown product IDs in inventory: {sorted(unknown_products)}")

if unknown_zones:
    raise ValueError(f"Unknown zone IDs in inventory: {sorted(unknown_zones)}")

today = pd.Timestamp.today().normalize()

product_lookup = products.set_index("product_id").to_dict("index")
zone_lookup = zones.set_index("zone_id").to_dict("index")

thermal_results = {}

chilled_thermal = thermal.copy()

if not chilled_thermal.empty:
    for product_id, product in product_lookup.items():
        if str(product.get("category", "")).strip().lower() != "chilled":
            thermal_results[product_id] = {
                "thermal_coverage": "No matching sensor evidence",
                "reference_readings": 0,
                "reference_out_of_range_readings": 0,
                "reference_out_of_range_pct": None,
                "reference_mean_deviation_c": None,
                "reference_sensor_out_of_range_minutes": None,
                "thermal_score": 0.0
            }
            continue

        minimum = float(product["storage_min_c"])
        maximum = float(product["storage_max_c"])

        reference = chilled_thermal.copy()
        reference["outside_limits"] = (
            (reference["temperature"] < minimum)
            | (reference["temperature"] > maximum)
        )
        reference["deviation_c"] = (
            minimum - reference["temperature"]
        ).clip(lower=0) + (
            reference["temperature"] - maximum
        ).clip(lower=0)

        total_readings = len(reference)
        outside_count = int(reference["outside_limits"].sum())
        outside_pct = (
            outside_count / total_readings * 100
            if total_readings
            else 0.0
        )

        mean_deviation = (
            float(reference.loc[reference["outside_limits"], "deviation_c"].mean())
            if outside_count
            else 0.0
        )

        reference_minutes = 0.0

        for _, sensor_group in reference.groupby("sensor", sort=True):
            sensor_group = sensor_group.sort_values("timestamp").copy()
            intervals = (
                sensor_group["timestamp"].diff().dt.total_seconds() / 60
            )
            typical_interval = intervals[intervals > 0].median()

            if pd.isna(typical_interval) or typical_interval <= 0:
                continue

            previous_outside = sensor_group["outside_limits"].shift(
                1, fill_value=False
            )
            consecutive_outside = (
                sensor_group["outside_limits"] & previous_outside
            )
            valid_interval = (
                intervals.gt(0) & intervals.le(typical_interval * 3)
            )

            reference_minutes += float(
                intervals[consecutive_outside & valid_interval].sum()
            )

        thermal_score = min(
            60.0,
            outside_pct * 0.45 + min(mean_deviation, 5.0) * 3.0
        )

        thermal_results[product_id] = {
            "thermal_coverage": "Chilled reference signal only",
            "reference_readings": total_readings,
            "reference_out_of_range_readings": outside_count,
            "reference_out_of_range_pct": round(outside_pct, 2),
            "reference_mean_deviation_c": round(mean_deviation, 3),
            "reference_sensor_out_of_range_minutes": round(reference_minutes, 2),
            "thermal_score": round(thermal_score, 2)
        }
else:
    for product_id, product in product_lookup.items():
        thermal_results[product_id] = {
            "thermal_coverage": "No valid sensor readings",
            "reference_readings": 0,
            "reference_out_of_range_readings": 0,
            "reference_out_of_range_pct": None,
            "reference_mean_deviation_c": None,
            "reference_sensor_out_of_range_minutes": None,
            "thermal_score": 0.0
        }

risk_rows = []

priority_points = {
    "Critical": 10,
    "High": 6,
    "Medium": 3,
    "Low": 0
}

for _, batch in inventory.iterrows():
    product = product_lookup[batch["product_id"]]
    zone = zone_lookup[batch["zone_id"]]

    product_min = float(product["storage_min_c"])
    product_max = float(product["storage_max_c"])
    zone_min = float(zone["min_temp_c"])
    zone_max = float(zone["max_temp_c"])

    zone_compatible = (
        zone_min <= product_min and zone_max >= product_max
    )

    days_to_expiry = int((batch["expiry_date"] - today).days)

    if days_to_expiry < 0:
        expiry_score = 20
        expiry_status = "Expired - review required"
    elif days_to_expiry <= 3:
        expiry_score = 18
        expiry_status = "Expires within 3 days"
    elif days_to_expiry <= 7:
        expiry_score = 14
        expiry_status = "Expires within 7 days"
    elif days_to_expiry <= 14:
        expiry_score = 9
        expiry_status = "Expires within 14 days"
    elif days_to_expiry <= 30:
        expiry_score = 4
        expiry_status = "Expires within 30 days"
    else:
        expiry_score = 0
        expiry_status = "No immediate expiry warning"

    thermal_info = thermal_results.get(
        batch["product_id"],
        {
            "thermal_coverage": "No matching sensor evidence",
            "reference_readings": 0,
            "reference_out_of_range_readings": 0,
            "reference_out_of_range_pct": None,
            "reference_mean_deviation_c": None,
            "reference_sensor_out_of_range_minutes": None,
            "thermal_score": 0.0
        }
    )

    priority = str(product["priority_class"]).strip().title()
    priority_score = priority_points.get(priority, 0)
    zone_score = 0 if zone_compatible else 20

    total_score = min(
        100.0,
        float(thermal_info["thermal_score"])
        + expiry_score
        + zone_score
        + priority_score
    )

    if total_score >= 60:
        risk_level = "Critical"
    elif total_score >= 40:
        risk_level = "High"
    elif total_score >= 20:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    review_reasons = []

    if not zone_compatible:
        review_reasons.append("Storage zone does not cover product temperature limits")

    if days_to_expiry < 0:
        review_reasons.append("Batch expiry date has passed")
    elif days_to_expiry <= 7:
        review_reasons.append("Expiry is approaching")

    if (
        thermal_info["reference_out_of_range_readings"] is not None
        and thermal_info["reference_out_of_range_readings"] > 0
    ):
        review_reasons.append(
            "Reference sensor readings fall outside this product's configured limits"
        )

    if thermal_info["thermal_coverage"] != "Chilled reference signal only":
        review_reasons.append("No product-matched sensor evidence available")

    if not review_reasons:
        review_reasons.append("Continue routine monitoring")

    risk_rows.append({
        "batch_id": batch["batch_id"],
        "lot_id": batch["lot_id"],
        "product_id": batch["product_id"],
        "product_name": product["product_name"],
        "product_category": product["category"],
        "zone_id": batch["zone_id"],
        "zone_name": zone["zone_name"],
        "quantity_units": int(batch["quantity_units"]),
        "batch_status": batch["batch_status"],
        "expiry_date": batch["expiry_date"].date(),
        "days_to_expiry": days_to_expiry,
        "product_min_temp_c": product_min,
        "product_max_temp_c": product_max,
        "zone_min_temp_c": zone_min,
        "zone_max_temp_c": zone_max,
        "zone_compatible": zone_compatible,
        "priority_class": priority,
        "thermal_coverage": thermal_info["thermal_coverage"],
        "reference_readings": thermal_info["reference_readings"],
        "reference_out_of_range_readings": thermal_info[
            "reference_out_of_range_readings"
        ],
        "reference_out_of_range_pct": thermal_info[
            "reference_out_of_range_pct"
        ],
        "reference_mean_deviation_c": thermal_info[
            "reference_mean_deviation_c"
        ],
        "reference_sensor_out_of_range_minutes": thermal_info[
            "reference_sensor_out_of_range_minutes"
        ],
        "thermal_score": thermal_info["thermal_score"],
        "expiry_score": expiry_score,
        "zone_mismatch_score": zone_score,
        "priority_score": priority_score,
        "risk_score": round(total_score, 2),
        "risk_level": risk_level,
        "review_reasons": "; ".join(review_reasons),
        "assessment_scope": (
            "Screening only; sensor readings are not mapped to this batch or zone"
        )
    })

risk_report = pd.DataFrame(risk_rows)

risk_report = risk_report.sort_values(
    ["risk_score", "days_to_expiry", "batch_id"],
    ascending=[False, True, True]
).reset_index(drop=True)

risk_report.to_csv(REPORTS / "batch_risk_assessment.csv", index=False)

risk_summary = (
    risk_report.groupby("risk_level", dropna=False)
    .agg(
        batch_count=("batch_id", "count"),
        total_quantity_units=("quantity_units", "sum"),
        average_risk_score=("risk_score", "mean")
    )
    .reset_index()
)

risk_summary["average_risk_score"] = risk_summary[
    "average_risk_score"
].round(2)

risk_summary.to_csv(REPORTS / "risk_level_summary.csv", index=False)

reason_summary = pd.DataFrame([
    {
        "metric": "Inventory batches assessed",
        "value": len(risk_report)
    },
    {
        "metric": "Critical risk batches",
        "value": int((risk_report["risk_level"] == "Critical").sum())
    },
    {
        "metric": "High risk batches",
        "value": int((risk_report["risk_level"] == "High").sum())
    },
    {
        "metric": "Batches in incompatible zones",
        "value": int((~risk_report["zone_compatible"]).sum())
    },
    {
        "metric": "Expired batches",
        "value": int((risk_report["days_to_expiry"] < 0).sum())
    },
    {
        "metric": "Batches expiring within 7 days",
        "value": int(
            risk_report["days_to_expiry"].between(0, 7).sum()
        )
    },
    {
        "metric": "Batches without matching sensor evidence",
        "value": int(
            (risk_report["thermal_coverage"] != "Chilled reference signal only").sum()
        )
    }
])

reason_summary.to_csv(REPORTS / "risk_engine_summary.csv", index=False)

validation_rows = [
    {
        "check": "Every assessed batch has a unique batch ID",
        "status": "PASS" if risk_report["batch_id"].is_unique else "FAIL",
        "details": f"{risk_report['batch_id'].nunique()} unique IDs across {len(risk_report)} rows"
    },
    {
        "check": "Risk scores remain between 0 and 100",
        "status": "PASS" if risk_report["risk_score"].between(0, 100).all() else "FAIL",
        "details": "Score range: 0 to 100"
    },
    {
        "check": "All risk levels are assigned",
        "status": "PASS" if risk_report["risk_level"].notna().all() else "FAIL",
        "details": f"{risk_report['risk_level'].isna().sum()} missing risk levels"
    },
    {
        "check": "All batches retain product references",
        "status": "PASS" if risk_report["product_id"].isin(products["product_id"]).all() else "FAIL",
        "details": "Product IDs checked against products.csv"
    },
    {
        "check": "All batches retain zone references",
        "status": "PASS" if risk_report["zone_id"].isin(zones["zone_id"]).all() else "FAIL",
        "details": "Zone IDs checked against zones.csv"
    },
    {
        "check": "Every batch assessment states its scope",
        "status": "PASS" if risk_report["assessment_scope"].notna().all() else "FAIL",
        "details": "Sensor-to-batch mapping limitation is explicitly recorded"
    }
]

validation = pd.DataFrame(validation_rows)
validation.to_csv(REPORTS / "risk_engine_validation.csv", index=False)

print("FROSTLINE DAY 5 RISK ENGINE COMPLETE")
print(f"Batches assessed: {len(risk_report)}")
print(f"Critical risk: {(risk_report['risk_level'] == 'Critical').sum()}")
print(f"High risk: {(risk_report['risk_level'] == 'High').sum()}")
print(f"Incompatible storage zones: {(~risk_report['zone_compatible']).sum()}")
print(f"Validation checks passed: {(validation['status'] == 'PASS').sum()} of {len(validation)}")
print(f"Batch assessment: {REPORTS / 'batch_risk_assessment.csv'}")
print(f"Risk summary: {REPORTS / 'risk_level_summary.csv'}")
print(f"Validation report: {REPORTS / 'risk_engine_validation.csv'}")