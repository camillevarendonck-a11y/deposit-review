"""Independent checks of the reproducible synthetic fixture."""
import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import analyze
from generate_demo import generate, OBSERVATION

class DemoChecks(unittest.TestCase):
    def test_reproducibility_and_independent_calculations(self):
        text = generate()
        self.assertEqual(text, generate())
        self.assertEqual(text, (ROOT / 'synthetic_deposits.csv').read_text())
        rows = list(csv.DictReader(StringIO(text)))
        self.assertEqual(len(rows), 1000)
        self.assertEqual(len({r['deposit_id'] for r in rows}), 1000)
        counts = dict(within=0, before_late=0, after_late=0, confirmed_overdue=0, missing_overdue=0, not_due=0)
        recovered = 0
        for r in rows:
            self.assertTrue(r['deposit_id'].startswith('SYN-'))
            self.assertGreater(float(r['amount_usdc']), 0)
            start = datetime.fromisoformat(r['initiated_at'])
            confirm = datetime.fromisoformat(r['confirmed_at']) if r['confirmed_at'] else None
            credit = datetime.fromisoformat(r['credited_at']) if r['credited_at'] else None
            self.assertLessEqual(start, OBSERVATION)
            if confirm:
                self.assertLessEqual(start, confirm)
                self.assertLessEqual(confirm, OBSERVATION)
            if credit:
                self.assertIsNotNone(confirm)
                self.assertLessEqual(confirm, credit)
                self.assertLessEqual(credit, OBSERVATION)
                before = (confirm - start).total_seconds() / 60
                after = (credit - confirm).total_seconds() / 60
                if before + after <= 120:
                    counts['within'] += 1
                elif before > after:
                    counts['before_late'] += 1
                else:
                    counts['after_late'] += 1
                    if before + after / 2 <= 120:
                        recovered += 1
            elif (OBSERVATION - start).total_seconds() / 60 <= 120:
                counts['not_due'] += 1
            else:
                counts['confirmed_overdue' if confirm else 'missing_overdue'] += 1
        self.assertEqual(counts, dict(within=650, before_late=100, after_late=100, confirmed_overdue=50, missing_overdue=40, not_due=60))
        result = analyze(text)
        s = result['summary']
        self.assertEqual((s['completed_deposits'], s['unresolved_deposits']), (850, 150))
        self.assertEqual((s['within_target'], s['over_target'], s['not_yet_due']), (650, 290, 60))
        self.assertEqual(s['target_rate_percent'], round(650 / 940 * 100, 1))
        self.assertEqual(result['scenario']['additional_within_target'], recovered)
        self.assertEqual(result['scenario']['scenario_rate'], round((650 + recovered) / 940 * 100, 1))

    def test_demo_routes(self):
        from test_upload import UploadChecks
        api = UploadChecks().request(method='GET', path='/api/demo')
        self.assertEqual(api['status'], 200)
        self.assertIn('Synthetic', api['body']['filename'])
        self.assertEqual(api['body']['analysis']['summary']['total_deposits'], 1000)
        download = UploadChecks().request(method='GET', path='/synthetic-demo.csv')
        self.assertEqual(download['status'], 200)
        self.assertEqual(download['body'].decode(), generate())
