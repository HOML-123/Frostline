from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)

INVENTORY_FILE = SYNTHETIC / "inventory_batches.csv"
PRODUCTS_FILE = SYNTHETIC / "products.csv"
ZONES_FILE = SYNTHETIC / "zones.csv"
RISK_FILE = REPORTS / "batch_risk_assessment.csv"

required_files = [
    INVENTORY_FILE,
    PRODUCTS_FILE,
    ZONES_FILE,
    RISK_FILE
]

missing_files = [str(path) for path in required_files if not path.exists()]

if missing_files:
    raise FileNotFoundError(
        "Required files are missing:\n" + "\n".join(missing_files)
    )

inventory = pd.read_csv(INVENTORY_FILE)
products = pd.read_csv(PRODUCTS_FILE)
zones = pd.read_csv(ZONES_FILE)
risk = pd.read_csv(RISK_FILE)

for dataframe in [inventory, products, zones, risk]:
    dataframe.columns = dataframe.columns.str.strip()

required_columns = {
    "inventory": {
        "batch_id", "lot_id", "product_id", "zone_id",
        "quantity_units", "received_date", "expiry_date", "batch_status"
    },
    "products": {
        "product_id", "product_name", "category", "storage_min_c",
        "storage_max_c", "priority_class"
    },
    "zones": {
        "zone_id", "zone_name", "zone_type", "capacity_units",
        "current_occupancy_units", "available_capacity_units"
    },
    "risk": {
        "batch_id", "risk_score", "risk_level", "review_reasons",
        "zone_compatible", "assessment_scope"
    }
}

datasets = {
    "inventory": inventory,
    "products": products,
    "zones": zones,
    "risk": risk
}

for name, columns in required_columns.items():
    missing = columns - set(datasets[name].columns)
    if missing:
        raise ValueError(
            f"{name} is missing required columns: {', '.join(sorted(missing))}"
        )

for name, dataframe, key in [
    ("inventory", inventory, "batch_id"),
    ("products", products, "product_id"),
    ("zones", zones, "zone_id"),
    ("risk", risk, "batch_id")
]:
    if dataframe[key].duplicated().any():
        raise ValueError(f"Duplicate {key} values found in {name}.")

inventory["quantity_units"] = pd.to_numeric(
    inventory["quantity_units"], errors="coerce"
)
inventory["received_date"] = pd.to_datetime(
    inventory["received_date"], errors="coerce"
).dt.normalize()
inventory["expiry_date"] = pd.to_datetime(
    inventory["expiry_date"], errors="coerce"
).dt.normalize()

products["storage_min_c"] = pd.to_numeric(
    products["storage_min_c"], errors="coerce"
)
products["storage_max_c"] = pd.to_numeric(
    products["storage_max_c"], errors="coerce"
)
zones["capacity_units"] = pd.to_numeric(
    zones["capacity_units"], errors="coerce"
)
zones["current_occupancy_units"] = pd.to_numeric(
    zones["current_occupancy_units"], errors="coerce"
)
zones["available_capacity_units"] = pd.to_numeric(
    zones["available_capacity_units"], errors="coerce"
)
risk["risk_score"] = pd.to_numeric(risk["risk_score"], errors="coerce")
risk["zone_compatible"] = (
    risk["zone_compatible"].astype(str).str.strip().str.lower().map({
        "true": True,
        "false": False
    })
)

if inventory[["quantity_units", "received_date", "expiry_date"]].isna().any().any():
    raise ValueError("Inventory contains invalid quantities or dates.")

if (inventory["quantity_units"] < 0).any():
    raise ValueError("Inventory quantities cannot be negative.")

if products[["storage_min_c", "storage_max_c"]].isna().any().any():
    raise ValueError("Product temperature limits contain invalid values.")

if zones[
    ["capacity_units", "current_occupancy_units", "available_capacity_units"]
].isna().any().any():
    raise ValueError("Zone capacity information contains invalid values.")

if risk[["risk_score", "risk_level", "zone_compatible"]].isna().any().any():
    raise ValueError("Risk assessment contains invalid values.")

unknown_products = set(inventory["product_id"]) - set(products["product_id"])
unknown_zones = set(inventory["zone_id"]) - set(zones["zone_id"])
missing_risk = set(inventory["batch_id"]) - set(risk["batch_id"])

if unknown_products:
    raise ValueError(f"Unknown product IDs: {sorted(unknown_products)}")

if unknown_zones:
    raise ValueError(f"Unknown zone IDs: {sorted(unknown_zones)}")

if missing_risk:
    raise ValueError(
        f"Missing risk assessments for batches: {sorted(missing_risk)}"
    )

today = pd.Timestamp.today().normalize()

product_columns = [
    "product_id", "product_name", "category",
    "storage_min_c", "storage_max_c", "priority_class"
]

zone_columns = [
    "zone_id", "zone_name", "zone_type",
    "capacity_units", "current_occupancy_units",
    "available_capacity_units"
]

risk_columns = [
    "batch_id", "risk_score", "risk_level", "review_reasons",
    "zone_compatible", "assessment_scope"
]

register = (
    inventory
    .merge(products[product_columns], on="product_id", how="left", validate="many_to_one")
    .merge(zones[zone_columns], on="zone_id", how="left", validate="many_to_one")
    .merge(risk[risk_columns], on="batch_id", how="left", validate="one_to_one")
)

register["days_to_expiry"] = (register["expiry_date"] - today).dt.days
register["is_expired"] = register["days_to_expiry"] < 0
register["expires_within_7_days"] = register["days_to_expiry"].between(0, 7)

review_levels = {"Critical", "High"}
register["risk_review_required"] = register["risk_level"].isin(review_levels)
register["storage_review_required"] = ~register["zone_compatible"]

register["inventory_management_status"] = "Available for planning"

register.loc[
    register["batch_status"].astype(str).str.strip().str.lower() != "available",
    "inventory_management_status"
] = "Not available in source status"

register.loc[
    register["expires_within_7_days"],
    "inventory_management_status"
] = "Expiry review"

register.loc[
    register["is_expired"],
    "inventory_management_status"
] = "Expired - review required"

register.loc[
    register["risk_review_required"] | register["storage_review_required"],
    "inventory_management_status"
] = "Risk or storage review required"

register["planning_quantity_units"] = register["quantity_units"]

register.loc[
    register["inventory_management_status"] != "Available for planning",
    "planning_quantity_units"
] = 0

register["review_required"] = (
    register["inventory_management_status"] != "Available for planning"
)

register["inventory_value_basis"] = "Units only; no monetary valuation available"
register["data_source"] = "Synthetic demonstration inventory"

register = register.sort_values(
    ["review_required", "risk_score", "days_to_expiry"],
    ascending=[False, False, True]
).reset_index(drop=True)

register.to_csv(REPORTS / "inventory_register.csv", index=False)

product_summary = (
    register.groupby(
        ["product_id", "product_name", "category", "priority_class"],
        dropna=False
    )
    .agg(
        batch_count=("batch_id", "nunique"),
        total_quantity_units=("quantity_units", "sum"),
        planning_quantity_units=("planning_quantity_units", "sum"),
        review_quantity_units=(
            "quantity_units",
            lambda values: int(
                values[register.loc[values.index, "review_required"]].sum()
            )
        ),
        expired_batches=("is_expired", "sum"),
        review_required_batches=("review_required", "sum"),
        average_risk_score=("risk_score", "mean")
    )
    .reset_index()
)

product_summary["average_risk_score"] = product_summary[
    "average_risk_score"
].round(2)

product_summary.to_csv(
    REPORTS / "product_inventory_summary.csv",
    index=False
)

zone_summary = (
    register.groupby(
        ["zone_id", "zone_name", "zone_type", "capacity_units"],
        dropna=False
    )
    .agg(
        batch_count=("batch_id", "nunique"),
        inventory_units=("quantity_units", "sum"),
        planning_units=("planning_quantity_units", "sum"),
        review_required_batches=("review_required", "sum"),
        incompatible_batches=("storage_review_required", "sum")
    )
    .reset_index()
)

zone_summary["remaining_capacity_units"] = (
    zone_summary["capacity_units"] - zone_summary["inventory_units"]
)

zone_summary["capacity_utilisation_pct"] = (
    zone_summary["inventory_units"]
    .div(zone_summary["capacity_units"].replace(0, pd.NA))
    .mul(100)
    .round(2)
)

zone_summary["capacity_status"] = "Within configured capacity"
zone_summary.loc[
    zone_summary["remaining_capacity_units"] < 0,
    "capacity_status"
] = "Capacity exceeded - investigate"

zone_summary.to_csv(
    REPORTS / "zone_inventory_summary.csv",
    index=False
)

expiry_watchlist = register[
    register["days_to_expiry"] <= 14
].copy()

expiry_watchlist = expiry_watchlist.sort_values(
    ["days_to_expiry", "risk_score"],
    ascending=[True, False]
)

expiry_watchlist.to_csv(
    REPORTS / "inventory_expiry_watchlist.csv",
    index=False
)

review_queue = register[register["review_required"]].copy()

review_queue = review_queue.sort_values(
    ["risk_score", "days_to_expiry"],
    ascending=[False, True]
)

review_queue.to_csv(
    REPORTS / "inventory_review_queue.csv",
    index=False
)

traceability = register[[
    "batch_id",
    "lot_id",
    "product_id",
    "product_name",
    "zone_id",
    "zone_name",
    "quantity_units",
    "batch_status",
    "received_date",
    "expiry_date",
    "days_to_expiry",
    "risk_score",
    "risk_level",
    "inventory_management_status",
    "review_reasons",
    "assessment_scope"
]].copy()

traceability.to_csv(
    REPORTS / "inventory_traceability.csv",
    index=False
)

validation_rows = [
    {
        "check": "Inventory register contains unique batch IDs",
        "status": "PASS" if register["batch_id"].is_unique else "FAIL",
        "details": f"{register['batch_id'].nunique()} unique IDs across {len(register)} rows"
    },
    {
        "check": "Every batch has a product and zone",
        "status": "PASS" if register["product_name"].notna().all() and register["zone_name"].notna().all() else "FAIL",
        "details": "Product and zone references verified"
    },
    {
        "check": "Every batch has a risk assessment",
        "status": "PASS" if register["risk_level"].notna().all() else "FAIL",
        "details": "Risk records joined by batch ID"
    },
    {
        "check": "Inventory quantities are non-negative",
        "status": "PASS" if (register["quantity_units"] >= 0).all() else "FAIL",
        "details": "All batch quantities checked"
    },
    {
        "check": "Planning quantity does not exceed physical quantity",
        "status": "PASS" if (register["planning_quantity_units"] <= register["quantity_units"]).all() else "FAIL",
        "details": "Planning quantity is limited by review status"
    },
    {
        "check": "Expired batches are flagged for review",
        "status": "PASS" if register.loc[register["is_expired"], "review_required"].all() else "FAIL",
        "details": f"{int(register['is_expired'].sum())} expired batches found"
    },
    {
        "check": "Review queue contains only flagged batches",
        "status": "PASS" if review_queue["review_required"].all() else "FAIL",
        "details": f"{len(review_queue)} batches in the review queue"
    },
    {
        "check": "Inventory register retains assessment scope",
        "status": "PASS" if register["assessment_scope"].notna().all() else "FAIL",
        "details": "Sensor-to-batch mapping limitation retained"
    }
]

validation = pd.DataFrame(validation_rows)
validation.to_csv(REPORTS / "inventory_validation.csv", index=False)

print("FROSTLINE DAY 6 INVENTORY MANAGER COMPLETE")
print(f"Inventory batches: {len(register)}")
print(f"Total physical inventory units: {int(register['quantity_units'].sum())}")
print(f"Planning quantity units: {int(register['planning_quantity_units'].sum())}")
print(f"Batches requiring review: {len(review_queue)}")
print(f"Expired batches: {int(register['is_expired'].sum())}")
print(f"Products tracked: {register['product_id'].nunique()}")
print(f"Zones tracked: {register['zone_id'].nunique()}")
print(f"Validation checks passed: {(validation['status'] == 'PASS').sum()} of {len(validation)}")
print(f"Inventory register: {REPORTS / 'inventory_register.csv'}")
print(f"Review queue: {REPORTS / 'inventory_review_queue.csv'}")
print(f"Validation report: {REPORTS / 'inventory_validation.csv'}")