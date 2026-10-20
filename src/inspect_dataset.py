
from pathlib import Path
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXTRACTED = RAW / "preprocessed_extracted"
REPORTS = ROOT / "outputs" / "reports"

EXTRACTED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

zip_path = RAW / "Preprocessed.zip"
overview_path = RAW / "overview.csv"

if not overview_path.exists():
    raise FileNotFoundError("overview.csv was not found in data/raw")

if not zip_path.exists():
    raise FileNotFoundError("Preprocessed.zip was not found in data/raw")

with zipfile.ZipFile(zip_path, "r") as archive:
    archive.extractall(EXTRACTED)

csv_files = sorted(set(RAW.rglob("*.csv")))
profile_lines = []
quality_rows = []

profile_lines.append("FROSTLINE DATASET PROFILE")
profile_lines.append("=" * 50)

for file_path in csv_files:
    if EXTRACTED not in file_path.parents and file_path != overview_path:
        continue

    profile_lines.append("")
    profile_lines.append(f"FILE: {file_path.relative_to(ROOT)}")

    try:
        df = None
        last_error = None

        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            for separator in [",", ";", "\t"]:
                try:
                    candidate = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=separator,
                        low_memory=False
                    )
                    if len(candidate.columns) > 1 or separator == "\t":
                        df = candidate
                        break
                except Exception as error:
                    last_error = error

            if df is not None:
                break

        if df is None:
            raise ValueError(f"Could not read CSV: {last_error}")

        missing = df.isna().sum()
        missing_columns = missing[missing > 0]
        duplicate_count = int(df.duplicated().sum())

        profile_lines.append(f"Rows: {len(df)}")
        profile_lines.append(f"Columns: {len(df.columns)}")
        profile_lines.append(f"Duplicate rows: {duplicate_count}")
        profile_lines.append("")
        profile_lines.append("COLUMN DETAILS")

        for column in df.columns:
            profile_lines.append(
                f"{column} | Type: {df[column].dtype} | Missing: {int(missing[column])}"
            )

        profile_lines.append("")
        profile_lines.append("FIRST FIVE ROWS")
        profile_lines.append(df.head().to_string(index=False))

        quality_rows.append({
            "file": str(file_path.relative_to(ROOT)),
            "rows": len(df),
            "columns": len(df.columns),
            "duplicate_rows": duplicate_count,
            "missing_cells": int(missing.sum()),
            "columns_with_missing_values": len(missing_columns),
            "status": "Read successfully"
        })

        print(f"Inspected: {file_path.name}")
        print(f"Rows: {len(df)} | Columns: {len(df.columns)}")
        print(f"Missing cells: {int(missing.sum())}")
        print(f"Duplicate rows: {duplicate_count}")
        print("-" * 40)

    except Exception as error:
        profile_lines.append(f"ERROR: {error}")
        quality_rows.append({
            "file": str(file_path.relative_to(ROOT)),
            "rows": None,
            "columns": None,
            "duplicate_rows": None,
            "missing_cells": None,
            "columns_with_missing_values": None,
            "status": f"Failed: {error}"
        })
        print(f"Could not inspect {file_path.name}: {error}")

profile_path = REPORTS / "dataset_profile.txt"
quality_path = REPORTS / "data_quality_summary.csv"

profile_path.write_text("\n".join(profile_lines), encoding="utf-8")
pd.DataFrame(quality_rows).to_csv(quality_path, index=False)

print("")
print("FROSTLINE DAY 1 INSPECTION COMPLETE")
print(f"Profile report: {profile_path}")
print(f"Quality summary: {quality_path}")
print(f"CSV files discovered: {len(csv_files)}")
