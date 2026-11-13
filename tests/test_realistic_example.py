"""Checks the mixed-format example against hand-derived expectations."""
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import analyze
from deposit_tools import queue_order

class RealisticExampleChecks(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / 'realistic-example.csv').read_text()
        self.result = analyze(self.text, '2026-11-10T14:00:00', 120)

    def test_summary_matches_hand_calculation(self):
        s = self.result['summary']
        self.assertEqual((s['total_deposits'], s['completed_deposits'], s['within_target'],
                          s['over_target'], s['not_yet_due'], s['eligible_deposits']), (16, 10, 5, 8, 3, 13))
        self.assertEqual(s['target_rate_percent'], 38.5)
        self.assertAlmostEqual(s['median_completion_minutes'], 120.0, places=1)

    def test_boundaries_and_scenario(self):
        codes = {r['deposit_id']: r['deadline_code'] for r in self.result['records']}
        self.assertEqual(codes['ETH-20483'], 'within')   # credited at exactly 120 minutes
        self.assertEqual(codes['ETH-20484'], 'late')     # one second over
        self.assertEqual(codes['BASE-3303'], 'pending')  # unresolved at exactly 120 minutes
        scenario = self.result['scenario']
        self.assertEqual(scenario['additional_within_target'], 4)
        self.assertEqual(scenario['scenario_rate'], 69.2)

    def test_queue_order_and_time_zones(self):
        order = [r['deposit_id'] for r in queue_order(self.result['records'], 120)]
        self.assertEqual(order, ['ETH-20485', 'ARB-7733', 'BASE-3302', 'ARB-7731', 'BASE-3306',
                                 'ETH-20486', 'ARB-7732', 'ETH-20484', 'ARB-7734', 'BASE-3303',
                                 'BASE-3304', 'BASE-3305', 'ETH-20481', 'ETH-20482', 'ETH-20483', 'ETH-20487'])
        first = {r['deposit_id']: r['initiated_at'] for r in self.result['records']}
        self.assertEqual(first['BASE-3302'], '2026-11-10T10:00:00+00:00')  # -05:00 input
        self.assertEqual(first['ARB-7731'], '2026-11-10T09:00:00+00:00')   # +01:00 input

    def test_download_route(self):
        from test_upload import UploadChecks
        response = UploadChecks().request(method='GET', path='/realistic-example.csv')
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['body'].decode(), self.text)

if __name__ == '__main__':
    unittest.main()
