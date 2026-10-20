from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"
CHARTS = ROOT / "outputs" / "charts"

MIN_TEMPERATURE = 2.0
MAX_TEMPERATURE = 8.0
GAP_MULTIPLIER = 3.0

REPORTS.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

def find_column(columns, keywords):
    for column in columns:
        name = str(column).strip().lower().replace("°", "")
        if any(keyword in name for keyword in keywords):
            return column
    return None

def load_sensor_file(file_path):
    df = pd.read_csv(file_path, sep=None, engine="python")
    df.columns = [str(column).strip() for column in df.columns]

    timestamp_column = find_column(
        df.columns,
        ["timestamp", "datetime", "date_time", "date time", "time"]
    )
    temperature_column = find_column(
        df.columns,
        ["temperature", "temp"]
    )

    if timestamp_column is None or temperature_column is None:
        raise ValueError(
            f"Could not identify timestamp and temperature columns. "
            f"Columns found: {list(df.columns)}"
        )

    result = pd.DataFrame({
        "timestamp": pd.to_datetime(df[timestamp_column], errors="coerce"),
        "temperature": pd.to_numeric(
            df[temperature_column].astype(str).str.replace(",", ".", regex=False),
            errors="coerce"
        )
    })

    humidity_column = find_column(df.columns, ["humidity", "relative_humidity", "rh"])
    if humidity_column is not None:
        result["humidity"] = pd.to_numeric(
            df[humidity_column].astype(str).str.replace(",", ".", regex=False),
            errors="coerce"
        )

    result["sensor"] = file_path.stem.replace("_preprocessed", "")
    result["source_file"] = str(file_path.relative_to(ROOT))
    result["original_rows"] = len(df)

    valid = result["timestamp"].notna() & result["temperature"].notna()
    result = result.loc[valid].copy()
    result = result.drop_duplicates(subset=["timestamp", "sensor"])
    result = result.sort_values("timestamp").reset_index(drop=True)

    return result

sensor_files = sorted(
    file_path
    for file_path in PROCESSED.rglob("*.csv")
    if file_path.stem.upper().startswith("SENSOR")
)

if not sensor_files:
    raise FileNotFoundError(
        f"No sensor CSV files were found in {PROCESSED}. "
        "Run the Day 2 cleaning script first."
    )

sensor_frames = []
file_results = []

for file_path in sensor_files:
    try:
        sensor_df = load_sensor_file(file_path)
        sensor_frames.append(sensor_df)
        file_results.append({
            "sensor": sensor_df["sensor"].iloc[0] if not sensor_df.empty else file_path.stem,
            "source_file": str(file_path.relative_to(ROOT)),
            "status": "Loaded" if not sensor_df.empty else "No valid readings",
            "rows_loaded": len(sensor_df),
            "error": ""
        })
        print(f"Analysed input: {file_path.name}")
    except Exception as error:
        file_results.append({
            "sensor": file_path.stem,
            "source_file": str(file_path.relative_to(ROOT)),
            "status": "Failed",
            "rows_loaded": 0,
            "error": str(error)
        })
        print(f"Could not load {file_path.name}: {error}")

if not sensor_frames:
    raise ValueError(
        "No sensor files could be analysed. Check the input columns and "
        "the file errors in thermal_file_status.csv."
    )

data = pd.concat(sensor_frames, ignore_index=True)
data = data.sort_values(["sensor", "timestamp"]).reset_index(drop=True)
data["below_limit"] = data["temperature"] < MIN_TEMPERATURE
data["above_limit"] = data["temperature"] > MAX_TEMPERATURE
data["excursion"] = data["below_limit"] | data["above_limit"]
data["excursion_type"] = "Within configured limits"
data.loc[data["below_limit"], "excursion_type"] = "Below minimum"
data.loc[data["above_limit"], "excursion_type"] = "Above maximum"

sensor_summaries = []
gap_records = []
excursion_records = []
daily_frames = []

for sensor, group in data.groupby("sensor", sort=True):
    group = group.sort_values("timestamp").copy()
    time_differences = group["timestamp"].diff().dt.total_seconds().div(60)
    positive_differences = time_differences[time_differences > 0]

    expected_interval = (
        float(positive_differences.median())
        if not positive_differences.empty
        else None
    )
    gap_threshold = (
        expected_interval * GAP_MULTIPLIER
        if expected_interval is not None
        else None
    )

    group["interval_minutes"] = time_differences
    group["data_gap"] = (
        group["interval_minutes"] > gap_threshold
        if gap_threshold is not None
        else False
    )

    for row_index in group.index[group["data_gap"]]:
        previous_time = group.loc[row_index - 1, "timestamp"]
        current_time = group.loc[row_index, "timestamp"]
        gap_records.append({
            "sensor": sensor,
            "gap_start": previous_time,
            "gap_end": current_time,
            "gap_minutes": round(
                (current_time - previous_time).total_seconds() / 60, 2
            ),
            "expected_interval_minutes": round(expected_interval, 2)
        })

    excursion_group = group.loc[group["excursion"]].copy()

    if not excursion_group.empty:
        excursion_group["episode_break"] = (
            excursion_group["excursion_type"].ne(
                excursion_group["excursion_type"].shift()
            )
            | excursion_group["timestamp"].diff().dt.total_seconds().div(60).gt(
                gap_threshold if gap_threshold is not None else float("inf")
            )
        )
        excursion_group["episode_id"] = excursion_group["episode_break"].cumsum()

        for episode_id, episode in excursion_group.groupby("episode_id"):
            excursion_records.append({
                "sensor": sensor,
                "episode": int(episode_id),
                "excursion_type": episode["excursion_type"].iloc[0],
                "start_time": episode["timestamp"].min(),
                "end_time": episode["timestamp"].max(),
                "duration_minutes": round(
                    (
                        episode["timestamp"].max()
                        - episode["timestamp"].min()
                    ).total_seconds() / 60,
                    2
                ),
                "reading_count": len(episode),
                "minimum_temperature": round(episode["temperature"].min(), 3),
                "maximum_temperature": round(episode["temperature"].max(), 3)
            })

    daily = group.set_index("timestamp").resample("D")["temperature"].agg(
        ["count", "mean", "min", "max"]
    ).reset_index()
    daily["sensor"] = sensor
    daily_frames.append(daily)

    sensor_summaries.append({
        "sensor": sensor,
        "first_reading": group["timestamp"].min(),
        "last_reading": group["timestamp"].max(),
        "valid_readings": len(group),
        "expected_interval_minutes": (
            round(expected_interval, 2)
            if expected_interval is not None
            else None
        ),
        "minimum_temperature": round(group["temperature"].min(), 3),
        "maximum_temperature": round(group["temperature"].max(), 3),
        "mean_temperature": round(group["temperature"].mean(), 3),
        "readings_below_minimum": int(group["below_limit"].sum()),
        "readings_above_maximum": int(group["above_limit"].sum()),
        "total_excursion_readings": int(group["excursion"].sum()),
        "detected_data_gaps": int(group["data_gap"].sum()),
        "configured_minimum": MIN_TEMPERATURE,
        "configured_maximum": MAX_TEMPERATURE
    })

daily_summary = (
    pd.concat(daily_frames, ignore_index=True)
    if daily_frames
    else pd.DataFrame()
)

excursions = pd.DataFrame(excursion_records, columns=[
    "sensor",
    "episode",
    "excursion_type",
    "start_time",
    "end_time",
    "duration_minutes",
    "reading_count",
    "minimum_temperature",
    "maximum_temperature"
])

gaps = pd.DataFrame(gap_records, columns=[
    "sensor",
    "gap_start",
    "gap_end",
    "gap_minutes",
    "expected_interval_minutes"
])

summary = pd.DataFrame(sensor_summaries)
file_status = pd.DataFrame(file_results)

data.to_csv(PROCESSED / "thermal_readings.csv", index=False)
summary.to_csv(REPORTS / "thermal_sensor_summary.csv", index=False)
daily_summary.to_csv(REPORTS / "thermal_daily_summary.csv", index=False)
excursions.to_csv(REPORTS / "temperature_excursions.csv", index=False)
gaps.to_csv(REPORTS / "sensor_data_gaps.csv", index=False)
file_status.to_csv(REPORTS / "thermal_file_status.csv", index=False)

plt.figure(figsize=(13, 6))
for sensor, group in data.groupby("sensor", sort=True):
    plt.plot(
        group["timestamp"],
        group["temperature"],
        linewidth=0.8,
        label=sensor
    )
plt.axhline(MIN_TEMPERATURE, linestyle="--", label="Configured minimum")
plt.axhline(MAX_TEMPERATURE, linestyle="--", label="Configured maximum")
plt.title("Cold Storage Temperature Over Time")
plt.xlabel("Timestamp")
plt.ylabel("Temperature (°C)")
plt.legend(loc="best", ncol=2)
plt.grid(True, alpha=0.25)
plt.tight_layout()
plt.savefig(CHARTS / "temperature_timeline.png", dpi=160)
plt.close()

plt.figure(figsize=(12, 6))
for sensor, group in daily_summary.groupby("sensor", sort=True):
    plt.plot(
        group["timestamp"],
        group["mean"],
        marker=".",
        linewidth=1.2,
        label=sensor
    )
plt.axhline(MIN_TEMPERATURE, linestyle="--", label="Configured minimum")
plt.axhline(MAX_TEMPERATURE, linestyle="--", label="Configured maximum")
plt.title("Daily Mean Temperature by Sensor")
plt.xlabel("Date")
plt.ylabel("Mean temperature (°C)")
plt.legend(loc="best", ncol=2)
plt.grid(True, alpha=0.25)
plt.tight_layout()
plt.savefig(CHARTS / "daily_mean_temperature.png", dpi=160)
plt.close()

plt.figure(figsize=(11, 6))
chart_data = summary.set_index("sensor")[
    ["readings_below_minimum", "readings_above_maximum"]
]
chart_data.plot(kind="bar", figsize=(11, 6))
plt.title("Temperature Excursion Readings by Sensor")
plt.xlabel("Sensor")
plt.ylabel("Number of readings")
plt.xticks(rotation=0)
plt.grid(axis="y", alpha=0.25)
plt.tight_layout()
plt.savefig(CHARTS / "temperature_excursions_by_sensor.png", dpi=160)
plt.close()

print("FROSTLINE DAY 3 THERMAL ANALYSIS COMPLETE")
print(f"Sensor files found: {len(sensor_files)}")
print(f"Sensor files loaded: {int((file_status['status'] == 'Loaded').sum())}")
print(f"Valid temperature readings: {len(data)}")
print(f"Excursion episodes detected: {len(excursions)}")
print(f"Data gaps detected: {len(gaps)}")
print(f"Reports saved to: {REPORTS}")
print(f"Charts saved to: {CHARTS}")