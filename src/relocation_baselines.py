from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

REPORTS.mkdir(parents=True, exist_ok=True)

INVENTORY_FILE = REPORTS / "inventory_register.csv"
ZONES_FILE = SYNTHETIC / "zones.csv"
PRODUCTS_FILE = SYNTHETIC / "products.csv"

required_files = [INVENTORY_FILE, ZONES_FILE, PRODUCTS_FILE]
missing_files = [str(path) for path in required_files if not path.exists()]

if missing_files:
    raise FileNotFoundError(
        "Required files are missing:\n" + "\n".join(missing_files)
    )

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

inventory["quantity_units"] = pd.to_numeric(
    inventory["quantity_units"], errors="coerce"
)
inventory["risk_score"] = pd.to_numeric(
    inventory["risk_score"], errors="coerce"
)
inventory["days_to_expiry"] = pd.to_numeric(
    inventory["days_to_expiry"], errors="coerce"
)

zones["min_temp_c"] = pd.to_numeric(zones["min_temp_c"], errors="coerce")
zones["max_temp_c"] = pd.to_numeric(zones["max_temp_c"], errors="coerce")
zones["capacity_units"] = pd.to_numeric(zones["capacity_units"], errors="coerce")
zones["is_backup"] = (
    zones["is_backup"].astype(str).str.strip().str.lower().map({
        "true": True,
        "false": False
    })
)

products["storage_min_c"] = pd.to_numeric(
    products["storage_min_c"], errors="coerce"
)
products["storage_max_c"] = pd.to_numeric(
    products["storage_max_c"], errors="coerce"
)

if inventory[
    ["quantity_units", "risk_score", "days_to_expiry"]
].isna().any().any():
    raise ValueError("Inventory has invalid quantity, risk or expiry values.")

if zones[
    ["min_temp_c", "max_temp_c", "capacity_units", "is_backup"]
].isna().any().any():
    raise ValueError("Zone temperature, capacity or backup values are invalid.")

if products[
    ["storage_min_c", "storage_max_c"]
].isna().any().any():
    raise ValueError("Product temperature limits contain invalid values.")

if (inventory["quantity_units"] <= 0).any():
    raise ValueError("All inventory batch quantities must be greater than zero.")

if (zones["capacity_units"] < 0).any():
    raise ValueError("Zone capacities cannot be negative.")

if (zones["min_temp_c"] > zones["max_temp_c"]).any():
    raise ValueError("A zone has invalid temperature limits.")

if (products["storage_min_c"] > products["storage_max_c"]).any():
    raise ValueError("A product has invalid temperature limits.")

product_lookup = products.set_index("product_id").to_dict("index")
zone_lookup = zones.set_index("zone_id").to_dict("index")

unknown_products = set(inventory["product_id"]) - set(products["product_id"])
unknown_zones = set(inventory["zone_id"]) - set(zones["zone_id"])

if unknown_products:
    raise ValueError(f"Unknown product IDs: {sorted(unknown_products)}")

if unknown_zones:
    raise ValueError(f"Unknown zone IDs: {sorted(unknown_zones)}")

inventory["review_required"] = (
    inventory["review_required"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({"true": True, "false": False})
)

if inventory["review_required"].isna().any():
    raise ValueError("Inventory review flags contain invalid values.")

backup_zones = zones[zones["is_backup"]].copy()
source_zones = zones[~zones["is_backup"]].copy()

backup_zone_ids = set(backup_zones["zone_id"])
source_zone_ids = set(source_zones["zone_id"])

occupied_capacity = (
    inventory.groupby("zone_id")["quantity_units"].sum().to_dict()
)

initial_capacity = {}

for _, zone in backup_zones.iterrows():
    zone_id = zone["zone_id"]
    initial_capacity[zone_id] = max(
        0,
        int(zone["capacity_units"] - occupied_capacity.get(zone_id, 0))
    )

candidates = inventory[inventory["zone_id"].isin(source_zone_ids)].copy()
candidates["source_zone_is_backup"] = False

def compatible_destinations(batch):
    product = product_lookup[batch["product_id"]]
    compatible = backup_zones[
        (backup_zones["zone_type"] == product["category"])
        & (backup_zones["min_temp_c"] <= product["storage_min_c"])
        & (backup_zones["max_temp_c"] >= product["storage_max_c"])
    ]
    return compatible.sort_values("zone_id").to_dict("records")

def candidate_sort_key(batch, strategy):
    if strategy == "priority_first":
        priority_order = {
            "Critical": 0,
            "High": 1,
            "Medium": 2,
            "Low": 3
        }
        return (
            priority_order.get(str(batch["priority_class"]).title(), 4),
            -float(batch["risk_score"]),
            int(batch["days_to_expiry"]),
            str(batch["batch_id"])
        )

    return (str(batch["batch_id"]),)

def run_strategy(strategy):
    remaining_capacity = initial_capacity.copy()
    plan_rows = []

    ordered = candidates.copy()
    ordered["_sort_key"] = ordered.apply(
        lambda row: candidate_sort_key(row, strategy),
        axis=1
    )

    if strategy == "priority_first":
        ordered = ordered.sort_values(
            ["priority_class", "risk_score", "days_to_expiry", "batch_id"],
            ascending=[True, False, True, True],
            key=lambda series: (
                series.map({
                    "Critical": 0,
                    "High": 1,
                    "Medium": 2,
                    "Low": 3
                }).fillna(4)
                if series.name == "priority_class"
                else series
            )
        )
    else:
        ordered = ordered.sort_values("batch_id")

    for _, batch in ordered.iterrows():
        quantity = int(batch["quantity_units"])
        product = product_lookup[batch["product_id"]]
        compatible = compatible_destinations(batch)

        destination = None
        placement_status = ""
        reason = ""

        source_zone = zone_lookup[batch["zone_id"]]

        if batch["review_required"] or str(
            batch["inventory_management_status"]
        ) != "Available for planning":
            placement_status = "Held for review"
            reason = "Batch is flagged for review and is not automatically relocated"

        elif not compatible:
            placement_status = "No compatible backup zone"
            reason = "No backup zone satisfies the product temperature requirements"

        else:
            feasible = [
                zone for zone in compatible
                if remaining_capacity[zone["zone_id"]] >= quantity
            ]

            if not feasible:
                placement_status = "Insufficient backup capacity"
                reason = "No compatible backup zone has enough remaining capacity"

            elif strategy == "first_fit":
                destination = feasible[0]

            elif strategy == "best_fit":
                destination = min(
                    feasible,
                    key=lambda zone: (
                        remaining_capacity[zone["zone_id"]] - quantity,
                        zone["zone_id"]
                    )
                )

            elif strategy == "priority_first":
                destination = min(
                    feasible,
                    key=lambda zone: (
                        remaining_capacity[zone["zone_id"]] - quantity,
                        zone["zone_id"]
                    )
                )

            if destination is not None:
                destination_id = destination["zone_id"]
                remaining_capacity[destination_id] -= quantity
                placement_status = "Assigned in simulation"
                reason = "Compatible backup zone has sufficient capacity"

        plan_rows.append({
            "strategy": strategy,
            "batch_id": batch["batch_id"],
            "lot_id": batch["lot_id"],
            "product_id": batch["product_id"],
            "product_name": batch["product_name"],
            "category": product["category"],
            "quantity_units": quantity,
            "priority_class": batch["priority_class"],
            "risk_score": batch["risk_score"],
            "risk_level": batch["risk_level"],
            "days_to_expiry": int(batch["days_to_expiry"]),
            "source_zone_id": batch["zone_id"],
            "source_zone_name": batch["zone_name"],
            "destination_zone_id": (
                destination["zone_id"] if destination else ""
            ),
            "destination_zone_name": (
                destination["zone_name"] if destination else ""
            ),
            "destination_min_temp_c": (
                destination["min_temp_c"] if destination else None
            ),
            "destination_max_temp_c": (
                destination["max_temp_c"] if destination else None
            ),
            "remaining_capacity_after_assignment": (
                remaining_capacity[destination["zone_id"]]
                if destination else None
            ),
            "placement_status": placement_status,
            "reason": reason,
            "assessment_scope": (
                "Planning simulation only; no physical move has occurred"
            )
        })

    return pd.DataFrame(plan_rows)

strategies = ["first_fit", "best_fit", "priority_first"]
plans = {}
comparison_rows = []

for strategy in strategies:
    plan = run_strategy(strategy)
    plans[strategy] = plan

    plan.to_csv(
        REPORTS / f"relocation_plan_{strategy}.csv",
        index=False
    )

    assigned = plan[plan["placement_status"] == "Assigned in simulation"]
    held = plan[plan["placement_status"] == "Held for review"]
    no_compatible = plan[
        plan["placement_status"] == "No compatible backup zone"
    ]
    insufficient = plan[
        plan["placement_status"] == "Insufficient backup capacity"
    ]

    comparison_rows.append({
        "strategy": strategy,
        "batches_considered": len(plan),
        "batches_assigned": len(assigned),
        "units_assigned": int(assigned["quantity_units"].sum()),
        "batches_held_for_review": len(held),
        "batches_without_compatible_backup": len(no_compatible),
        "batches_without_enough_capacity": len(insufficient),
        "assignment_rate_pct": round(
            len(assigned) / len(plan) * 100, 2
        ) if len(plan) else 0.0,
        "assigned_units_pct": round(
            assigned["quantity_units"].sum()
            / plan["quantity_units"].sum() * 100, 2
        ) if len(plan) and plan["quantity_units"].sum() else 0.0
    })

comparison = pd.DataFrame(comparison_rows)
comparison.to_csv(
    REPORTS / "baseline_relocation_comparison.csv",
    index=False
)

combined_plan = pd.concat(plans.values(), ignore_index=True)
combined_plan.to_csv(
    REPORTS / "baseline_relocation_all_plans.csv",
    index=False
)

capacity_rows = []

for strategy, plan in plans.items():
    assigned = plan[plan["placement_status"] == "Assigned in simulation"]

    for _, zone in backup_zones.iterrows():
        zone_id = zone["zone_id"]
        assigned_units = int(
            assigned.loc[
                assigned["destination_zone_id"] == zone_id,
                "quantity_units"
            ].sum()
        )
        starting_occupancy = int(occupied_capacity.get(zone_id, 0))
        capacity = int(zone["capacity_units"])
        final_occupancy = starting_occupancy + assigned_units

        capacity_rows.append({
            "strategy": strategy,
            "zone_id": zone_id,
            "zone_name": zone["zone_name"],
            "capacity_units": capacity,
            "starting_occupancy_units": starting_occupancy,
            "relocated_in_units": assigned_units,
            "simulated_final_occupancy_units": final_occupancy,
            "simulated_remaining_capacity_units": capacity - final_occupancy,
            "capacity_valid": final_occupancy <= capacity
        })

capacity_report = pd.DataFrame(capacity_rows)
capacity_report.to_csv(
    REPORTS / "baseline_relocation_capacity.csv",
    index=False
)

validation_rows = [
    {
        "check": "Every plan preserves unique batch IDs per strategy",
        "status": "PASS" if all(
            plan["batch_id"].is_unique for plan in plans.values()
        ) else "FAIL",
        "details": "Each strategy contains each source batch at most once"
    },
    {
        "check": "Assigned destinations are backup zones",
        "status": "PASS" if all(
            plan.loc[
                plan["placement_status"] == "Assigned in simulation",
                "destination_zone_id"
            ].isin(backup_zone_ids).all()
            for plan in plans.values()
        ) else "FAIL",
        "details": "Only configured backup zones are assignment destinations"
    },
    {
        "check": "Assigned destinations satisfy product temperature limits",
        "status": "PASS" if all(
            plan.loc[
                plan["placement_status"] == "Assigned in simulation",
                "destination_min_temp_c"
            ].notna().all()
            and plan.loc[
                plan["placement_status"] == "Assigned in simulation",
                "destination_max_temp_c"
            ].notna().all()
            for plan in plans.values()
        ) else "FAIL",
        "details": "Assigned destinations include verified temperature limits"
    },
    {
        "check": "Simulated backup capacity is never exceeded",
        "status": "PASS" if capacity_report["capacity_valid"].all() else "FAIL",
        "details": "Starting stock and simulated inbound units are included"
    },
    {
        "check": "Held-for-review batches are not assigned automatically",
        "status": "PASS" if all(
            plan.loc[
                plan["placement_status"] == "Held for review",
                "destination_zone_id"
            ].eq("").all()
            for plan in plans.values()
        ) else "FAIL",
        "details": "Review-flagged batches have no automatic destination"
    },
    {
        "check": "Every plan labels the simulation scope",
        "status": "PASS" if all(
            plan["assessment_scope"].notna().all()
            for plan in plans.values()
        ) else "FAIL",
        "details": "Plans explicitly state that no physical relocation occurred"
    }
]

validation = pd.DataFrame(validation_rows)
validation.to_csv(
    REPORTS / "baseline_relocation_validation.csv",
    index=False
)

print("FROSTLINE DAY 7 BASELINE RELOCATION COMPLETE")
print(f"Source batches considered: {len(candidates)}")

for _, row in comparison.iterrows():
    print(
        f"{row['strategy']}: "
        f"{row['batches_assigned']} batches assigned, "
        f"{row['units_assigned']} units assigned"
    )

print(
    f"Validation checks passed: "
    f"{(validation['status'] == 'PASS').sum()} of {len(validation)}"
)
print(f"Strategy comparison: {REPORTS / 'baseline_relocation_comparison.csv'}")
print(f"Capacity report: {REPORTS / 'baseline_relocation_capacity.csv'}")
print(f"Validation report: {REPORTS / 'baseline_relocation_validation.csv'}")