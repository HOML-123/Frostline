
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "outputs" / "reports"
SYNTHETIC = ROOT / "data" / "synthetic"

REPORTS.mkdir(parents=True, exist_ok=True)

inventory = pd.read_csv(REPORTS / "inventory_register.csv")
orders = pd.read_csv(SYNTHETIC / "orders.csv")
order_lines = pd.read_csv(SYNTHETIC / "order_lines.csv")
products = pd.read_csv(SYNTHETIC / "products.csv")

required_inventory = [
    "batch_id",
    "product_id",
    "planning_quantity_units",
    "days_to_expiry",
    "review_required",
    "inventory_management_status",
]

required_orders = [
    "order_id",
    "customer_id",
    "created_at",
    "required_by",
    "priority",
]

required_lines = [
    "order_line_id",
    "order_id",
    "product_id",
    "requested_quantity_units",
]

for name, frame, columns in [
    ("inventory_register.csv", inventory, required_inventory),
    ("orders.csv", orders, required_orders),
    ("order_lines.csv", order_lines, required_lines),
]:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")

inventory["planning_quantity_units"] = pd.to_numeric(
    inventory["planning_quantity_units"], errors="coerce"
).fillna(0).clip(lower=0)

inventory["days_to_expiry"] = pd.to_numeric(
    inventory["days_to_expiry"], errors="coerce"
)

inventory["review_required"] = (
    inventory["review_required"]
    .astype(str)
    .str.strip()
    .str.lower()
    .isin(["true", "1", "yes", "y"])
)

inventory["inventory_management_status"] = (
    inventory["inventory_management_status"]
    .astype(str)
    .str.strip()
    .str.lower()
)

eligible = inventory[
    (~inventory["review_required"])
    & (inventory["inventory_management_status"] == "available for planning")
    & (inventory["days_to_expiry"] > 0)
    & (inventory["planning_quantity_units"] > 0)
].copy()

eligible = eligible.sort_values(
    ["product_id", "days_to_expiry", "batch_id"]
)

orders["priority_rank"] = (
    orders["priority"]
    .astype(str)
    .str.strip()
    .str.lower()
    .map({
        "critical": 1,
        "urgent": 1,
        "high": 2,
        "medium": 3,
        "normal": 4,
        "low": 5,
    })
    .fillna(3)
)

orders["required_by"] = pd.to_datetime(orders["required_by"], errors="coerce")
orders["created_at"] = pd.to_datetime(orders["created_at"], errors="coerce")

orders = orders.sort_values(
    ["priority_rank", "required_by", "created_at", "order_id"],
    kind="stable",
)

remaining = dict(
    zip(eligible["batch_id"], eligible["planning_quantity_units"])
)

allocation_records = []

lines = order_lines.merge(
    orders[
        ["order_id", "customer_id", "created_at", "required_by", "priority", "priority_rank"]
    ],
    on="order_id",
    how="left",
    validate="many_to_one",
)

lines["requested_quantity_units"] = pd.to_numeric(
    lines["requested_quantity_units"], errors="coerce"
).fillna(0).clip(lower=0)

lines = lines.sort_values(
    ["priority_rank", "required_by", "created_at", "order_id", "order_line_id"],
    kind="stable",
)

for _, line in lines.iterrows():
    requested = float(line["requested_quantity_units"])
    remaining_request = requested

    candidates = eligible[eligible["product_id"] == line["product_id"]]

    for _, batch in candidates.iterrows():
        if remaining_request <= 0:
            break

        batch_id = batch["batch_id"]
        available = max(0, float(remaining.get(batch_id, 0)))
        allocated = min(remaining_request, available)

        if allocated <= 0:
            continue

        remaining[batch_id] = available - allocated
        remaining_request -= allocated

        allocation_records.append({
            "order_line_id": line["order_line_id"],
            "order_id": line["order_id"],
            "customer_id": line["customer_id"],
            "product_id": line["product_id"],
            "batch_id": batch_id,
            "requested_quantity_units": requested,
            "allocated_quantity_units": allocated,
            "batch_days_to_expiry": batch["days_to_expiry"],
            "allocation_method": "Priority-based FEFO",
            "planning_note": "Simulated allocation; verify before operational use",
        })

allocation_details = pd.DataFrame(allocation_records)

if allocation_details.empty:
    allocation_details = pd.DataFrame(columns=[
        "order_line_id",
        "order_id",
        "customer_id",
        "product_id",
        "batch_id",
        "requested_quantity_units",
        "allocated_quantity_units",
        "batch_days_to_expiry",
        "allocation_method",
        "planning_note",
    ])

allocated_by_line = (
    allocation_details.groupby("order_line_id")["allocated_quantity_units"]
    .sum()
    .to_dict()
)

line_summary = order_lines.copy()

line_summary["requested_quantity_units"] = pd.to_numeric(
    line_summary["requested_quantity_units"], errors="coerce"
).fillna(0).clip(lower=0)

line_summary["allocated_quantity_units"] = line_summary["order_line_id"].map(
    allocated_by_line
).fillna(0)

line_summary["unfulfilled_quantity_units"] = (
    line_summary["requested_quantity_units"]
    - line_summary["allocated_quantity_units"]
).clip(lower=0)

line_summary["fulfilment_percentage"] = (
    line_summary["allocated_quantity_units"]
    .div(line_summary["requested_quantity_units"].replace(0, pd.NA))
    .mul(100)
    .fillna(100)
    .clip(0, 100)
)

line_summary["line_fulfilment_status"] = "Partially fulfilled"
line_summary.loc[
    line_summary["allocated_quantity_units"] <= 0,
    "line_fulfilment_status"
] = "Unfulfilled"
line_summary.loc[
    line_summary["unfulfilled_quantity_units"] <= 0,
    "line_fulfilment_status"
] = "Fulfilled"

order_totals = line_summary.groupby("order_id", as_index=False).agg(
    requested_quantity_units=("requested_quantity_units", "sum"),
    allocated_quantity_units=("allocated_quantity_units", "sum"),
    unfulfilled_quantity_units=("unfulfilled_quantity_units", "sum"),
    total_lines=("order_line_id", "count"),
)

order_summary = orders.drop(columns=["priority_rank"]).merge(
    order_totals,
    on="order_id",
    how="left",
)

for column in [
    "requested_quantity_units",
    "allocated_quantity_units",
    "unfulfilled_quantity_units",
    "total_lines",
]:
    order_summary[column] = order_summary[column].fillna(0)

order_summary["fulfilment_percentage"] = (
    order_summary["allocated_quantity_units"]
    .div(order_summary["requested_quantity_units"].replace(0, pd.NA))
    .mul(100)
    .fillna(100)
    .clip(0, 100)
)

order_summary["rescue_status"] = "Partially fulfilled"
order_summary.loc[
    order_summary["allocated_quantity_units"] <= 0,
    "rescue_status"
] = "Unfulfilled"
order_summary.loc[
    order_summary["unfulfilled_quantity_units"] <= 0,
    "rescue_status"
] = "Fulfilled"

remaining_inventory = eligible.copy()
remaining_inventory["remaining_quantity_units"] = (
    remaining_inventory["batch_id"].map(remaining).fillna(0)
)

allocation_details.to_csv(
    REPORTS / "order_allocation_details.csv", index=False
)
line_summary.to_csv(
    REPORTS / "order_line_fulfilment_summary.csv", index=False
)
order_summary.to_csv(
    REPORTS / "order_fulfilment_summary.csv", index=False
)
remaining_inventory.to_csv(
    REPORTS / "order_allocation_remaining_inventory.csv", index=False
)

total_requested = float(line_summary["requested_quantity_units"].sum())
total_allocated = float(line_summary["allocated_quantity_units"].sum())
total_unfulfilled = float(line_summary["unfulfilled_quantity_units"].sum())

summary = pd.DataFrame([{
    "total_orders": int(len(orders)),
    "total_order_lines": int(len(order_lines)),
    "total_requested_units": total_requested,
    "total_allocated_units": total_allocated,
    "total_unfulfilled_units": total_unfulfilled,
    "overall_fulfilment_percentage": (
        total_allocated / total_requested * 100 if total_requested > 0 else 100
    ),
    "fulfilled_orders": int((order_summary["rescue_status"] == "Fulfilled").sum()),
    "partially_fulfilled_orders": int(
        (order_summary["rescue_status"] == "Partially fulfilled").sum()
    ),
    "unfulfilled_orders": int(
        (order_summary["rescue_status"] == "Unfulfilled").sum()
    ),
    "method": "Priority-based order allocation with earliest-expiry-first batch selection",
    "scope": "Synthetic planning simulation; not an operational release decision",
}])

summary.to_csv(REPORTS / "order_rescue_summary.csv", index=False)

validation = pd.DataFrame([
    {
        "check": "Allocation does not exceed requested quantity",
        "passed": bool(
            (line_summary["allocated_quantity_units"]
             <= line_summary["requested_quantity_units"] + 1e-9).all()
        ),
    },
    {
        "check": "No negative unfulfilled quantities",
        "passed": bool((line_summary["unfulfilled_quantity_units"] >= 0).all()),
    },
    {
        "check": "Allocation does not exceed eligible batch stock",
        "passed": bool(all(value >= -1e-9 for value in remaining.values())),
    },
    {
        "check": "Allocation quantities are non-negative",
        "passed": bool(
            (allocation_details["allocated_quantity_units"] >= 0).all()
        ),
    },
])

validation.to_csv(REPORTS / "order_rescue_validation.csv", index=False)

print("Day 9 order rescue completed.")
print(f"Orders processed: {len(orders)}")
print(f"Order lines processed: {len(order_lines)}")
print(f"Eligible inventory batches: {len(eligible)}")
print(f"Total requested units: {total_requested:.0f}")
print(f"Total allocated units: {total_allocated:.0f}")
print(f"Total unfulfilled units: {total_unfulfilled:.0f}")
print(f"Overall fulfilment: {summary.loc[0, 'overall_fulfilment_percentage']:.2f}%")
print(f"All validation checks passed: {validation['passed'].all()}")
print(f"Reports saved to: {REPORTS}")
