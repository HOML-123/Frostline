from pathlib import Path
import random
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"
REPORTS = ROOT / "outputs" / "reports"

SYNTHETIC.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

rng = random.Random(42)
today = pd.Timestamp.today().normalize()

products = pd.DataFrame([
    {"product_id": "PRD001", "product_name": "Fresh Dairy", "category": "Chilled", "storage_min_c": 2, "storage_max_c": 8, "shelf_life_days": 14, "priority_class": "High", "unit": "units"},
    {"product_id": "PRD002", "product_name": "Fresh Produce", "category": "Chilled", "storage_min_c": 2, "storage_max_c": 8, "shelf_life_days": 10, "priority_class": "High", "unit": "units"},
    {"product_id": "PRD003", "product_name": "Ready Meals", "category": "Chilled", "storage_min_c": 2, "storage_max_c": 5, "shelf_life_days": 7, "priority_class": "Critical", "unit": "units"},
    {"product_id": "PRD004", "product_name": "Medical Refrigerated Supplies", "category": "Chilled", "storage_min_c": 2, "storage_max_c": 8, "shelf_life_days": 90, "priority_class": "Critical", "unit": "units"},
    {"product_id": "PRD005", "product_name": "Frozen Vegetables", "category": "Frozen", "storage_min_c": -25, "storage_max_c": -18, "shelf_life_days": 365, "priority_class": "Medium", "unit": "units"},
    {"product_id": "PRD006", "product_name": "Frozen Seafood", "category": "Frozen", "storage_min_c": -25, "storage_max_c": -18, "shelf_life_days": 180, "priority_class": "High", "unit": "units"},
    {"product_id": "PRD007", "product_name": "Frozen Meals", "category": "Frozen", "storage_min_c": -23, "storage_max_c": -18, "shelf_life_days": 270, "priority_class": "High", "unit": "units"},
    {"product_id": "PRD008", "product_name": "Frozen Desserts", "category": "Frozen", "storage_min_c": -25, "storage_max_c": -18, "shelf_life_days": 240, "priority_class": "Medium", "unit": "units"},
    {"product_id": "PRD009", "product_name": "Packaged Snacks", "category": "Ambient", "storage_min_c": 15, "storage_max_c": 25, "shelf_life_days": 180, "priority_class": "Low", "unit": "units"},
    {"product_id": "PRD010", "product_name": "Dry Ingredients", "category": "Ambient", "storage_min_c": 15, "storage_max_c": 25, "shelf_life_days": 270, "priority_class": "Medium", "unit": "units"},
    {"product_id": "PRD011", "product_name": "Beverages", "category": "Ambient", "storage_min_c": 15, "storage_max_c": 25, "shelf_life_days": 180, "priority_class": "Low", "unit": "units"},
    {"product_id": "PRD012", "product_name": "Medical Dry Supplies", "category": "Ambient", "storage_min_c": 15, "storage_max_c": 25, "shelf_life_days": 365, "priority_class": "High", "unit": "units"}
])

zones = pd.DataFrame([
    {"zone_id": "CH-01", "zone_name": "Chilled Storage A", "zone_type": "Chilled", "min_temp_c": 2, "max_temp_c": 8, "capacity_units": 8000, "is_backup": False},
    {"zone_id": "CH-02", "zone_name": "Chilled Storage B", "zone_type": "Chilled", "min_temp_c": 2, "max_temp_c": 8, "capacity_units": 8000, "is_backup": False},
    {"zone_id": "FR-01", "zone_name": "Frozen Storage A", "zone_type": "Frozen", "min_temp_c": -25, "max_temp_c": -18, "capacity_units": 8000, "is_backup": False},
    {"zone_id": "FR-02", "zone_name": "Frozen Storage B", "zone_type": "Frozen", "min_temp_c": -25, "max_temp_c": -18, "capacity_units": 8000, "is_backup": False},
    {"zone_id": "BK-CH", "zone_name": "Backup Chilled Storage", "zone_type": "Chilled", "min_temp_c": 2, "max_temp_c": 8, "capacity_units": 5000, "is_backup": True},
    {"zone_id": "BK-FR", "zone_name": "Backup Frozen Storage", "zone_type": "Frozen", "min_temp_c": -25, "max_temp_c": -18, "capacity_units": 5000, "is_backup": True},
    {"zone_id": "AM-01", "zone_name": "Ambient Storage A", "zone_type": "Ambient", "min_temp_c": 15, "max_temp_c": 25, "capacity_units": 8000, "is_backup": False},
    {"zone_id": "AM-02", "zone_name": "Ambient Storage B", "zone_type": "Ambient", "min_temp_c": 15, "max_temp_c": 25, "capacity_units": 8000, "is_backup": False}
])

equipment_rows = []

for _, zone in zones.iterrows():
    equipment_rows.append({
        "equipment_id": f"EQ-{zone['zone_id']}",
        "equipment_type": "Backup Cooling Unit" if zone["is_backup"] else (
            "Refrigeration Unit" if zone["zone_type"] != "Ambient" else "Climate Monitoring Unit"
        ),
        "zone_id": zone["zone_id"],
        "equipment_status": "Operational",
        "last_maintenance_date": (today - pd.Timedelta(days=rng.randint(5, 60))).date(),
        "next_maintenance_date": (today + pd.Timedelta(days=rng.randint(15, 90))).date(),
        "backup_power_available": bool(zone["zone_type"] != "Ambient")
    })

equipment = pd.DataFrame(equipment_rows)

product_lookup = products.set_index("product_id").to_dict("index")
batches = []
batch_counter = 1

zone_product_categories = {
    "Chilled": ["Chilled"],
    "Frozen": ["Frozen"],
    "Ambient": ["Ambient"]
}

for _, zone in zones.iterrows():
    eligible_products = products[
        products["category"].isin(zone_product_categories[zone["zone_type"]])
    ]

    for _ in range(15):
        product = eligible_products.iloc[rng.randrange(len(eligible_products))]
        product_id = product["product_id"]
        quantity = rng.randint(50, 250)
        days_to_expiry = rng.randint(1, int(product["shelf_life_days"]))

        batches.append({
            "batch_id": f"BAT{batch_counter:04d}",
            "lot_id": f"LOT-{today.strftime('%Y%m')}-{batch_counter:04d}",
            "product_id": product_id,
            "zone_id": zone["zone_id"],
            "quantity_units": quantity,
            "received_date": (today - pd.Timedelta(days=rng.randint(1, 60))).date(),
            "expiry_date": (today + pd.Timedelta(days=days_to_expiry)).date(),
            "batch_status": "Available"
        })
        batch_counter += 1

inventory = pd.DataFrame(batches)

occupancy = inventory.groupby("zone_id")["quantity_units"].sum().to_dict()
zones["current_occupancy_units"] = zones["zone_id"].map(occupancy).fillna(0).astype(int)
zones["available_capacity_units"] = (
    zones["capacity_units"] - zones["current_occupancy_units"]
).clip(lower=0)

order_rows = []
order_line_rows = []
order_counter = 1
line_counter = 1

priority_weights = [("Critical", 4), ("High", 3), ("Medium", 2), ("Low", 1)]
priority_values = [item[0] for item in priority_weights]
priority_probabilities = [item[1] for item in priority_weights]

for _ in range(100):
    order_id = f"ORD{order_counter:04d}"
    created_at = today + pd.Timedelta(hours=rng.randint(0, 24 * 7))
    due_at = created_at + pd.Timedelta(hours=rng.randint(6, 72))
    priority = rng.choices(priority_values, weights=priority_probabilities, k=1)[0]
    line_count = rng.randint(1, 3)

    order_rows.append({
        "order_id": order_id,
        "customer_id": f"CUS{rng.randint(1, 30):03d}",
        "created_at": created_at,
        "required_by": due_at,
        "priority": priority,
        "order_status": "Open"
    })

    chosen_products = rng.sample(
        products["product_id"].tolist(),
        k=line_count
    )

    for product_id in chosen_products:
        order_line_rows.append({
            "order_line_id": f"OL{line_counter:05d}",
            "order_id": order_id,
            "product_id": product_id,
            "requested_quantity_units": rng.randint(20, 180),
            "allocated_quantity_units": 0,
            "line_status": "Unallocated"
        })
        line_counter += 1

    order_counter += 1

orders = pd.DataFrame(order_rows)
order_lines = pd.DataFrame(order_line_rows)

products["data_source"] = "Synthetic demonstration data"
zones["data_source"] = "Synthetic demonstration data"
equipment["data_source"] = "Synthetic demonstration data"
inventory["data_source"] = "Synthetic demonstration data"
orders["data_source"] = "Synthetic demonstration data"
order_lines["data_source"] = "Synthetic demonstration data"

output_files = {
    "products.csv": products,
    "zones.csv": zones,
    "equipment.csv": equipment,
    "inventory_batches.csv": inventory,
    "orders.csv": orders,
    "order_lines.csv": order_lines
}

for filename, dataframe in output_files.items():
    dataframe.to_csv(SYNTHETIC / filename, index=False)

validation_rows = []

for filename, dataframe in output_files.items():
    validation_rows.append({
        "dataset": filename,
        "row_count": len(dataframe),
        "column_count": len(dataframe.columns),
        "duplicate_rows": int(dataframe.duplicated().sum()),
        "missing_cells": int(dataframe.isna().sum().sum()),
        "status": "PASS" if len(dataframe) > 0 and not dataframe.isna().any().any() and not dataframe.duplicated().any() else "CHECK"
    })

validation_rows.extend([
    {
        "dataset": "inventory_zone_capacity",
        "row_count": len(zones),
        "column_count": 4,
        "duplicate_rows": 0,
        "missing_cells": 0,
        "status": "PASS" if (zones["current_occupancy_units"] <= zones["capacity_units"]).all() else "CHECK"
    },
    {
        "dataset": "inventory_product_references",
        "row_count": len(inventory),
        "column_count": 2,
        "duplicate_rows": 0,
        "missing_cells": 0,
        "status": "PASS" if inventory["product_id"].isin(products["product_id"]).all() else "CHECK"
    },
    {
        "dataset": "inventory_zone_references",
        "row_count": len(inventory),
        "column_count": 2,
        "duplicate_rows": 0,
        "missing_cells": 0,
        "status": "PASS" if inventory["zone_id"].isin(zones["zone_id"]).all() else "CHECK"
    },
    {
        "dataset": "order_line_references",
        "row_count": len(order_lines),
        "column_count": 2,
        "duplicate_rows": 0,
        "missing_cells": 0,
        "status": "PASS" if order_lines["order_id"].isin(orders["order_id"]).all() and order_lines["product_id"].isin(products["product_id"]).all() else "CHECK"
    }
])

validation = pd.DataFrame(validation_rows)
validation.to_csv(REPORTS / "synthetic_data_validation.csv", index=False)

print("FROSTLINE DAY 4 DATA GENERATION COMPLETE")
print(f"Products: {len(products)}")
print(f"Warehouse zones: {len(zones)}")
print(f"Equipment records: {len(equipment)}")
print(f"Inventory batches: {len(inventory)}")
print(f"Orders: {len(orders)}")
print(f"Order lines: {len(order_lines)}")
print(f"Validation checks passed: {(validation['status'] == 'PASS').sum()} of {len(validation)}")
print(f"Synthetic datasets: {SYNTHETIC}")
print(f"Validation report: {REPORTS / 'synthetic_data_validation.csv'}")