
from pathlib import Path
import unittest
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "outputs" / "reports"


class TestFrostline(unittest.TestCase):

    def read_report(self, filename):
        path = REPORTS / filename
        self.assertTrue(path.exists(), f"Missing report: {filename}")
        return pd.read_csv(path)

    def check_validation_report(self, filename):
        report = self.read_report(filename)

        self.assertIn("check", report.columns)
        self.assertIn("passed", report.columns)
        self.assertGreater(len(report), 0)

        passed = (
            report["passed"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(["true", "1", "yes"])
        )

        failures = report.loc[~passed, "check"].tolist()

        self.assertTrue(
            passed.all(),
            f"Validation failures in {filename}: {failures}"
        )

    def test_day9_validation(self):
        self.check_validation_report("order_rescue_validation.csv")

    def test_day9_allocations_do_not_exceed_requests(self):
        report = self.read_report("order_line_fulfilment_summary.csv")

        self.assertIn("requested_quantity_units", report.columns)
        self.assertIn("allocated_quantity_units", report.columns)
        self.assertIn("unfulfilled_quantity_units", report.columns)

        self.assertTrue(
            (report["requested_quantity_units"] >= 0).all()
        )
        self.assertTrue(
            (
                report["allocated_quantity_units"]
                <= report["requested_quantity_units"] + 1e-9
            ).all()
        )
        self.assertTrue(
            (report["unfulfilled_quantity_units"] >= 0).all()
        )

    def test_day10_validation(self):
        self.check_validation_report("cooling_failure_validation.csv")

    def test_day10_temperature_timeline(self):
        report = self.read_report(
            "cooling_failure_temperature_timeline.csv"
        )

        self.assertGreater(len(report), 0)
        self.assertIn("simulation_hour", report.columns)
        self.assertIn("simulated_temperature_c", report.columns)

        self.assertTrue(
            report["simulated_temperature_c"].notna().all()
        )
        self.assertTrue(
            report["simulation_hour"].is_monotonic_increasing
        )

        self.assertAlmostEqual(
            float(report.iloc[0]["simulation_hour"]),
            0.0
        )

    def test_day10_inventory_belongs_to_selected_zone(self):
        timeline = self.read_report(
            "cooling_failure_temperature_timeline.csv"
        )
        inventory = self.read_report(
            "cooling_failure_affected_inventory.csv"
        )

        self.assertIn("zone_id", timeline.columns)
        self.assertIn("zone_id", inventory.columns)

        selected_zones = set(timeline["zone_id"].astype(str))
        inventory_zones = set(inventory["zone_id"].astype(str))

        self.assertLessEqual(inventory_zones, selected_zones)

    def test_day11_validation(self):
        self.check_validation_report("uncertainty_validation.csv")

    def test_day11_has_three_scenarios(self):
        report = self.read_report(
            "uncertainty_scenario_comparison.csv"
        )

        self.assertEqual(
            report["scenario"].tolist(),
            ["Mild", "Moderate", "Severe"]
        )

        self.assertTrue(
            report["peak_simulated_temperature_c"].notna().all()
        )

        self.assertTrue(
            report["peak_simulated_temperature_c"]
            .is_monotonic_increasing
        )

    def test_day11_audit_log(self):
        report = self.read_report("simulation_audit_log.csv")

        required = [
            "run_id",
            "run_timestamp_utc",
            "scenario",
            "zone_id",
            "peak_simulated_temperature_c",
        ]

        for column in required:
            self.assertIn(column, report.columns)

        self.assertGreaterEqual(len(report), 3)
        self.assertTrue(report["run_id"].notna().all())
        self.assertTrue(report["run_timestamp_utc"].notna().all())

    def test_core_input_files_exist(self):
        required_files = [
            ROOT / "data" / "synthetic" / "zones.csv",
            ROOT / "data" / "synthetic" / "equipment.csv",
            ROOT / "data" / "synthetic" / "inventory_batches.csv",
            ROOT / "data" / "synthetic" / "orders.csv",
            ROOT / "data" / "synthetic" / "order_lines.csv",
        ]

        for path in required_files:
            self.assertTrue(path.exists(), f"Missing input file: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
