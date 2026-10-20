
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"

PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

csv_files = sorted(RAW.rglob("*.csv"))

if not csv_files:
    raise FileNotFoundError(f"No CSV files found in {RAW}")

results = []

for file_path in csv_files:
    relative_path = file_path.relative_to(RAW)
    output_path = PROCESSED / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(file_path, sep=None, engine="python")
        original_rows = len(df)
        original_columns = len(df.columns)

        df.columns = [str(column).strip() for column in df.columns]
        df = df.dropna(axis=0, how="all")
        df = df.dropna(axis=1, how="all")

        for column in df.select_dtypes(include=["object", "string"]).columns:
            df[column] = df[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            df[column] = df[column].replace(
                ["", "NA", "N/A", "null", "NULL", "None", "?"],
                pd.NA
            )

        duplicates_removed = int(df.duplicated().sum())
        df = df.drop_duplicates()
        df.to_csv(output_path, index=False)

        results.append({
            "file": str(relative_path),
            "status": "Cleaned successfully",
            "original_rows": original_rows,
            "cleaned_rows": len(df),
            "original_columns": original_columns,
            "cleaned_columns": len(df.columns),
            "duplicates_removed": duplicates_removed,
            "missing_cells_after_cleaning": int(df.isna().sum().sum()),
            "output_file": str(output_path.relative_to(ROOT))
        })

        print(f"Cleaned: {relative_path}")

    except Exception as error:
        results.append({
            "file": str(relative_path),
            "status": f"Failed: {error}",
            "original_rows": None,
            "cleaned_rows": None,
            "original_columns": None,
            "cleaned_columns": None,
            "duplicates_removed": None,
            "missing_cells_after_cleaning": None,
            "output_file": None
        })
        print(f"Failed: {relative_path}: {error}")

report_path = REPORTS / "cleaning_quality_report.csv"
pd.DataFrame(results).to_csv(report_path, index=False)

print("FROSTLINE DAY 2 CLEANING COMPLETE")
print(f"Files processed: {len(results)}")
print(f"Report: {report_path}")
