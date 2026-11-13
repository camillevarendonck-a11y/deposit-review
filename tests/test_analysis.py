"""Run the learning script in isolated folders, leaving the demo data untouched."""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
OUTPUTS = ["summary.json", "scenario.json", "investigation_results.csv", "investigation_results.json"]

class AnalysisChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        shutil.copy(PROJECT / "analysis.py", self.folder / "analysis.py")
        shutil.copy(PROJECT / "engine.py", self.folder / "engine.py")
        self.data = (PROJECT / "deposits.csv").read_text()

    def run_script(self, data, optimized=False):
        (self.folder / "deposits.csv").write_text(data)
        return subprocess.run([sys.executable] + (["-O"] if optimized else []) + [str(self.folder / "analysis.py")],
                              capture_output=True, text=True)

    def test_original_five_deposits(self):
        result = self.run_script(self.data)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.folder / "summary.json").read_text())
        self.assertEqual(summary["total_deposits"], 5)
        self.assertEqual(summary["unresolved_deposits"], 2)
        self.assertEqual(summary["target_rate_percent"], 20)
        self.assertEqual(summary["median_completion_minutes"], 155)
        self.assertEqual(json.loads((self.folder / "scenario.json").read_text())["scenario_rate"], 40)
        with (self.folder / "investigation_results.csv").open(newline="") as f:
            self.assertEqual(len(list(csv.DictReader(f))), 5)

    def test_recent_unresolved_deposit_is_not_a_target_failure(self):
        result = self.run_script(self.data + "DEP-006,300,2026-11-10T12:30:00,,\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.folder / "summary.json").read_text())
        self.assertEqual(summary["total_deposits"], 6)
        self.assertEqual(summary["unresolved_deposits"], 3)
        self.assertEqual(summary["not_yet_due"], 1)
        self.assertEqual(summary["over_target"], 4)
        self.assertEqual(summary["target_rate_percent"], 20)
        records = json.loads((self.folder / "investigation_results.json").read_text())
        self.assertEqual(records[-1]["category"], "Missing confirmation evidence")
        self.assertEqual(records[-1]["deadline_status"], "Not yet due")
        self.assertEqual(records[-2]["deadline_status"], "Overdue, no credit recorded")
        self.assertEqual(summary["median_completion_minutes"], 155)
        self.assertEqual(summary["completed_deposits"], 3)

    def assert_rejected_without_export(self, data, message, optimized=False):
        for name in OUTPUTS:
            (self.folder / name).write_text("PREVIOUS VALID OUTPUT")
        result = self.run_script(data, optimized=optimized)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        for name in OUTPUTS:
            self.assertEqual((self.folder / name).read_text(), "PREVIOUS VALID OUTPUT")

    def test_missing_column_does_not_overwrite_outputs(self):
        malformed = self.data.replace("DEP-005,1000,2026-11-10T10:00:00,,", "DEP-005,1000,2026-11-10T10:00:00,")
        self.assert_rejected_without_export(malformed, "expected exactly five fields")

    def test_invalid_event_order_does_not_overwrite_outputs(self):
        invalid = self.data.replace("2026-11-10T10:15:00", "2026-11-10T09:59:00")
        self.assert_rejected_without_export(invalid, "check the credit timestamp")

    def test_duplicate_id_does_not_overwrite_outputs(self):
        invalid = self.data.replace("DEP-005,", "DEP-001,")
        self.assert_rejected_without_export(invalid, "duplicate IDs")


    def test_validation_stays_active_in_optimized_python(self):
        invalid = self.data.replace("DEP-005,", "DEP-001,")
        self.assert_rejected_without_export(invalid, "duplicate IDs", optimized=True)

    def test_unparseable_timestamp_does_not_overwrite_outputs(self):
        invalid = self.data.replace("2026-11-10T10:15:00", "not-a-date")
        self.assert_rejected_without_export(invalid, "Invalid isoformat")

    def test_extreme_timestamp_gives_clean_error_without_export(self):
        invalid = self.data.replace('2026-11-10T10:00:00', '0001-01-01T00:00:00+05:00')
        self.assert_rejected_without_export(invalid, 'Invalid isoformat')
        result = self.run_script(invalid)
        self.assertNotIn('Traceback', result.stderr)

    def test_walkthrough_does_not_overwrite_current_exports(self):
        self.assertEqual(self.run_script(self.data).returncode, 0)
        before = {name: (self.folder / name).read_bytes() for name in OUTPUTS}
        shutil.copy(PROJECT / 'analysis_walkthrough.py', self.folder / 'analysis_walkthrough.py')
        result = subprocess.run([sys.executable, str(self.folder / 'analysis_walkthrough.py')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {name: (self.folder / name).read_bytes() for name in OUTPUTS})
        self.assertTrue(all((self.folder / 'walkthrough_outputs' / name).exists() for name in OUTPUTS))

    def test_credit_without_confirmation_does_not_overwrite_outputs(self):
        invalid = self.data.replace("2026-11-10T10:10:00,2026-11-10T10:15:00", ",2026-11-10T10:15:00")
        self.assert_rejected_without_export(invalid, "credit exists without confirmation")

    def test_exact_target_boundary_completed_and_pending(self):
        data = self.data + (
            "DEP-006,300,2026-11-10T12:00:00,,\n"
            "DEP-007,300,2026-11-10T10:00:00,2026-11-10T11:00:00,2026-11-10T12:00:00\n"
        )
        result = self.run_script(data)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.folder / "summary.json").read_text())
        records = json.loads((self.folder / "investigation_results.json").read_text())
        self.assertEqual(records[-2]["deadline_status"], "Not yet due")
        self.assertEqual(records[-1]["deadline_status"], "Within target")
        self.assertEqual(summary["within_target"], 2)
        self.assertEqual(summary["not_yet_due"], 1)
        self.assertEqual(summary["over_target"], 4)
        self.assertEqual(summary["target_rate_percent"], 33.3)

if __name__ == "__main__":
    unittest.main()
