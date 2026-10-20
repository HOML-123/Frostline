from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)

INVENTORY_FILE = REPORTS / "inventory_register.csv"
ZONES_FILE = SYNTHETIC / "zones.csv"
PRODUCTS_FILE = SYNTHETIC / "products.csv"

for path in [INVENTORY_FILE, ZONES_FILE, PRODUCTS_FILE]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

inventory = pd.read_csv(INVENTORY_FILE)
zones = pd.read_csv(ZONES_FILE)
products = pd.read_csv(PRODUCTS_FILE)

for dataframe in [inventory, zones, products]:
    dataframe.columns = dataframe.columns.str.strip()

inventory_required = {
    "batch_id", "lot_id", "product_id", "product_name", "category",
    "zone_id", "zone_name", "quantity_units", "batch_status",
    "priority_class", "risk_score", "risk_level", "review_required",
    "inventory_management_status", "days_to_expiry"
}

zone_required = {
    "zone_id", "zone_name", "zone_type", "min_temp_c", "max_temp_c",
    "capacity_units", "is_backup"
}

product_required = {
    "product_id", "storage_min_c", "storage_max_c", "category"
}

for name, dataframe, required in [
    ("inventory register", inventory, inventory_required),
    ("zones", zones, zone_required),
    ("products", products, product_required)
]:
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(
            f"{name} is missing columns: {', '.join(sorted(missing))}"
        )

if inventory["batch_id"].duplicated().any():
    raise ValueError("Duplicate batch IDs found in the inventory register.")

if zones["zone_id"].duplicated().any():
    raise ValueError("Duplicate zone IDs found in the zone data.")

if products["product_id"].duplicated().any():
    raise ValueError("Duplicate product IDs found in the product data.")

for column in ["quantity_units", "risk_score", "days_to_expiry"]:
    inventory[column] = pd.to_numeric(
        inventory[column], errors="coerce"
    )

for column in ["min_temp_c", "max_temp_c", "capacity_units"]:
    zones[column] = pd.to_numeric(zones[column], errors="coerce")

for column in ["storage_min_c", "storage_max_c"]:
    products[column] = pd.to_numeric(
        products[column], errors="coerce"
    )

zones["is_backup"] = (
    zones["is_backup"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({"true": True, "false": False})
)

inventory["review_required"] = (
    inventory["review_required"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({"true": True, "false": False})
)

if inventory[
    ["quantity_units", "risk_score", "days_to_expiry", "review_required"]
].isna().any().any():
    raise ValueError("Inventory contains invalid quantity, risk, expiry or review values.")

if zones[
    ["min_temp_c", "max_temp_c", "capacity_units", "is_backup"]
].isna().any().any():
    raise ValueError("Zone data contains invalid temperature, capacity or backup values.")

if products[
    ["storage_min_c", "storage_max_c"]
].isna().any().any():
    raise ValueError("Product temperature limits contain invalid values.")

if (inventory["quantity_units"] <= 0).any():
    raise ValueError("Inventory quantities must be greater than zero.")

if (zones["capacity_units"] < 0).any():
    raise ValueError("Zone capacity cannot be negative.")

if (zones["min_temp_c"] > zones["max_temp_c"]).any():
    raise ValueError("A zone has invalid temperature limits.")

if (products["storage_min_c"] > products["storage_max_c"]).any():
    raise ValueError("A product has invalid temperature limits.")

unknown_products = set(inventory["product_id"]) - set(products["product_id"])
unknown_zones = set(inventory["zone_id"]) - set(zones["zone_id"])

if unknown_products:
    raise ValueError(f"Unknown product IDs: {sorted(unknown_products)}")

if unknown_zones:
    raise ValueError(f"Unknown zone IDs: {sorted(unknown_zones)}")

product_lookup = products.set_index("product_id").to_dict("index")
zone_lookup = zones.set_index("zone_id").to_dict("index")

backup_zones = zones[zones["is_backup"]].copy()
source_zone_ids = set(zones.loc[~zones["is_backup"], "zone_id"])
backup_zone_ids = set(backup_zones["zone_id"])

if backup_zones.empty:
    raise ValueError("No backup zones are configured.")

starting_occupancy = (
    inventory.groupby("zone_id")["quantity_units"].sum().to_dict()
)

remaining_capacity = {}

for _, zone in backup_zones.iterrows():
    zone_id = zone["zone_id"]
    used = int(starting_occupancy.get(zone_id, 0))
    capacity = int(zone["capacity_units"])

    if used > capacity:
        raise ValueError(
            f"Backup zone {zone_id} already exceeds its configured capacity."
        )

    remaining_capacity[zone_id] = capacity - used

source_inventory = inventory[
    inventory["zone_id"].isin(source_zone_ids)
].copy()

priority_weights = {
    "critical": 40,
    "urgent": 35,
    "high": 30,
    "medium": 20,
    "normal": 15,
    "low": 10
}

def get_expiry_urgency(days):
    if days <= 0:
        return 30
    if days <= 3:
        return 20
    if days <= 7:
        return 12
    if days <= 14:
        return 6
    return 0

def get_priority_score(batch):
    priority = str(batch["priority_class"]).strip().lower()
    risk = float(batch["risk_score"])
    expiry = get_expiry_urgency(float(batch["days_to_expiry"]))
    return risk * 2 + priority_weights.get(priority, 10) + expiry

def get_compatible_zones(batch):
    product = product_lookup[batch["product_id"]]

    compatible = backup_zones[
        (backup_zones["zone_type"] == product["category"])
        & (backup_zones["min_temp_c"] <= product["storage_min_c"])
        & (backup_zones["max_temp_c"] >= product["storage_max_c"])
    ]

    return compatible.sort_values("zone_id").to_dict("records")

batch_records = source_inventory.to_dict("records")
batch_by_id = {str(batch["batch_id"]): batch for batch in batch_records}
eligible = {}
results = {}

for batch in batch_records:
    batch_id = str(batch["batch_id"])
    status = str(batch["inventory_management_status"]).strip()

    if batch["review_required"] or status != "Available for planning":
        results[batch_id] = {
            "destination_zone_id": "",
            "destination_zone_name": "",
            "destination_min_temp_c": None,
            "destination_max_temp_c": None,
            "priority_score": get_priority_score(batch),
            "placement_status": "Held for review",
            "reason": "Batch requires review before it can be considered for relocation"
        }
        continue

    compatible = get_compatible_zones(batch)

    if not compatible:
        results[batch_id] = {
            "destination_zone_id": "",
            "destination_zone_name": "",
            "destination_min_temp_c": None,
            "destination_max_temp_c": None,
            "priority_score": get_priority_score(batch),
            "placement_status": "No compatible backup zone",
            "reason": "No backup zone meets the product temperature requirements"
        }
        continue

    eligible[batch_id] = {
        "batch": batch,
        "compatible_zones": compatible,
        "priority_score": get_priority_score(batch)
    }

unassigned = set(eligible)

while unassigned:
    feasible_assignments = []

    for batch_id in unassigned:
        item = eligible[batch_id]
        batch = item["batch"]
        quantity = int(batch["quantity_units"])

        for zone in item["compatible_zones"]:
            zone_id = zone["zone_id"]
            available = remaining_capacity[zone_id]

            if available >= quantity:
                score_density = item["priority_score"] / quantity
                leftover = available - quantity

                feasible_assignments.append((
                    -score_density,
                    -item["priority_score"],
                    leftover,
                    str(batch_id),
                    str(zone_id),
                    zone
                ))

    if not feasible_assignments:
        break

    feasible_assignments.sort(
        key=lambda item: (item[0], item[1], item[2], item[3], item[4])
    )

    _, _, _, batch_id, zone_id, destination = feasible_assignments[0]
    item = eligible[batch_id]
    batch = item["batch"]
    quantity = int(batch["quantity_units"])

    remaining_capacity[destination["zone_id"]] -= quantity
    unassigned.remove(batch_id)

    results[batch_id] = {
        "destination_zone_id": destination["zone_id"],
        "destination_zone_name": destination["zone_name"],
        "destination_min_temp_c": destination["min_temp_c"],
        "destination_max_temp_c": destination["max_temp_c"],
        "priority_score": item["priority_score"],
        "placement_status": "Assigned by optimiser",
        "reason": (
            "Highest-ranked feasible assignment at this step; "
            "capacity and temperature constraints satisfied"
        )
    }

for batch_id in unassigned:
    item = eligible[batch_id]
    batch = item["batch"]
    quantity = int(batch["quantity_units"])

    any_compatible_zone = item["compatible_zones"]

    if not any_compatible_zone:
        status = "No compatible backup zone"
        reason = "No backup zone meets the product temperature requirements"
    else:
        status = "Insufficient backup capacity"
        reason = (
            "No compatible backup zone had sufficient remaining capacity "
            "when the optimisation ended"
        )

    results[batch_id] = {
        "destination_zone_id": "",
        "destination_zone_name": "",
        "destination_min_temp_c": None,
        "destination_max_temp_c": None,
        "priority_score": item["priority_score"],
        "placement_status": status,
        "reason": reason
    }

plan_rows = []

for batch in batch_records:
    batch_id = str(batch["batch_id"])
    result = results[batch_id]
    product = product_lookup[batch["product_id"]]

    plan_rows.append({
        "batch_id": batch["batch_id"],
        "lot_id": batch["lot_id"],
        "product_id": batch["product_id"],
        "product_name": batch["product_name"],
        "category": product["category"],
        "quantity_units": int(batch["quantity_units"]),
        "priority_class": batch["priority_class"],
        "risk_score": float(batch["risk_score"]),
        "risk_level": batch["risk_level"],
        "days_to_expiry": int(batch["days_to_expiry"]),
        "source_zone_id": batch["zone_id"],
        "source_zone_name": batch["zone_name"],
        "product_storage_min_c": product["storage_min_c"],
        "product_storage_max_c": product["storage_max_c"],
        "destination_zone_id": result["destination_zone_id"],
        "destination_zone_name": result["destination_zone_name"],
        "destination_min_temp_c": result["destination_min_temp_c"],
        "destination_max_temp_c": result["destination_max_temp_c"],
        "priority_score": round(result["priority_score"], 2),
        "placement_status": result["placement_status"],
        "reason": result["reason"],
        "assessment_scope": (
            "Constrained planning simulation only; no physical move occurred"
        )
    })

plan = pd.DataFrame(plan_rows)
plan.to_csv(REPORTS / "relocation_plan_optimised.csv", index=False)

assigned = plan[plan["placement_status"] == "Assigned by optimiser"]

capacity_rows = []

for _, zone in backup_zones.iterrows():
    zone_id = zone["zone_id"]

    relocated_units = int(
        assigned.loc[
            assigned["destination_zone_id"] == zone_id,
            "quantity_units"
        ].sum()
    )

    used_before = int(starting_occupancy.get(zone_id, 0))
    capacity = int(zone["capacity_units"])
    used_after = used_before + relocated_units

    capacity_rows.append({
        "zone_id": zone_id,
        "zone_name": zone["zone_name"],
        "capacity_units": capacity,
        "starting_occupancy_units": used_before,
        "relocated_in_units": relocated_units,
        "simulated_final_occupancy_units": used_after,
        "simulated_remaining_capacity_units": capacity - used_after,
        "capacity_valid": used_after <= capacity
    })

capacity_report = pd.DataFrame(capacity_rows)
capacity_report.to_csv(
    REPORTS / "relocation_optimiser_capacity.csv",
    index=False
)

total_source_units = int(plan["quantity_units"].sum())
assigned_units = int(assigned["quantity_units"].sum())

summary = pd.DataFrame([{
    "source_batches_considered": len(plan),
    "batches_assigned": len(assigned),
    "units_available_in_source_batches": total_source_units,
    "units_assigned": assigned_units,
    "assigned_units_pct": round(
        assigned_units / total_source_units * 100, 2
    ) if total_source_units else 0.0,
    "batches_held_for_review": int(
        (plan["placement_status"] == "Held for review").sum()
    ),
    "batches_without_compatible_zone": int(
        (plan["placement_status"] == "No compatible backup zone").sum()
    ),
    "batches_without_capacity": int(
        (plan["placement_status"] == "Insufficient backup capacity").sum()
    ),
    "method": "Greedy constrained heuristic, not a global optimum"
}])

summary.to_csv(
    REPORTS / "relocation_optimiser_summary.csv",
    index=False
)

assigned_destination = plan[
    plan["placement_status"] == "Assigned by optimiser"
]

temperature_valid = (
    (
        assigned_destination["destination_min_temp_c"]
        <= assigned_destination["product_storage_min_c"]
    )
    & (
        assigned_destination["destination_max_temp_c"]
        >= assigned_destination["product_storage_max_c"]
    )
).all()

validation_rows = [
    {
        "check": "Batch IDs are unique in the plan",
        "status": "PASS" if plan["batch_id"].is_unique else "FAIL",
        "details": "Each source batch appears once"
    },
    {
        "check": "Assigned destinations are backup zones",
        "status": "PASS" if assigned_destination[
            "destination_zone_id"
        ].isin(backup_zone_ids).all() else "FAIL",
        "details": "Only configured backup zones are used"
    },
    {
        "check": "Assigned zones satisfy product temperature limits",
        "status": "PASS" if temperature_valid else "FAIL",
        "details": "Destination temperature range contains the product storage range"
    },
    {
        "check": "Backup-zone capacity is respected",
        "status": "PASS" if capacity_report["capacity_valid"].all() else "FAIL",
        "details": "Starting occupancy plus assigned inventory does not exceed capacity"
    },
    {
        "check": "Review-required batches are not assigned",
        "status": "PASS" if plan.loc[
            plan["placement_status"] == "Held for review",
            "destination_zone_id"
        ].eq("").all() else "FAIL",
        "details": "Batches held for review have no destination"
    },
    {
        "check": "Assignment quantities are positive",
        "status": "PASS" if (
            assigned_destination["quantity_units"] > 0
        ).all() else "FAIL",
        "details": "Every assigned batch has a positive quantity"
    },
    {
        "check": "Simulation scope is recorded",
        "status": "PASS" if plan["assessment_scope"].notna().all() else "FAIL",
        "details": "The plan does not claim that physical relocation occurred"
    }
]

validation = pd.DataFrame(validation_rows)
validation.to_csv(
    REPORTS / "relocation_optimiser_validation.csv",
    index=False
)

print("FROSTLINE DAY 8 RELOCATION OPTIMISER COMPLETE")
print(f"Source batches considered: {len(plan)}")
print(f"Batches assigned: {len(assigned)}")
print(f"Units assigned: {assigned_units}")
print(
    f"Validation checks passed: "
    f"{(validation['status'] == 'PASS').sum()} of {len(validation)}"
)
print(f"Optimised plan: {REPORTS / 'relocation_plan_optimised.csv'}")
print(f"Summary: {REPORTS / 'relocation_optimiser_summary.csv'}")
print(f"Capacity report: {REPORTS / 'relocation_optimiser_capacity.csv'}")
print(f"Validation report: {REPORTS / 'relocation_optimiser_validation.csv'}")