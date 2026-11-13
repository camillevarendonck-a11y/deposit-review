import asyncio
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import deposit_tools as tools
from engine import analyze


class ToolChecks(unittest.TestCase):
    def test_sample_numbers_match_hand_calculation(self):
        result = tools.analyze_file('deposits.csv')
        self.assertEqual(result['summary']['target_rate_percent'], 20.0)
        self.assertEqual(result['summary']['median_completion_minutes'], 155)
        self.assertEqual(result['summary']['completed_deposits'], 3)
        self.assertEqual(result['scenario']['scenario_rate_percent'], 40.0)

    def test_queue_order_for_sample(self):
        queue = tools.review_queue('deposits.csv', limit=10)['queue']
        self.assertEqual([r['deposit_id'] for r in queue], ['DEP-004', 'DEP-005', 'DEP-003', 'DEP-002', 'DEP-001'])
        self.assertEqual([r['minutes_over_target'] for r in queue], [120, 120, 60, 35, 0])

    def test_queue_groups_for_demo(self):
        result = analyze((ROOT / 'synthetic_deposits.csv').read_text())
        ordered = tools.queue_order(result['records'], 120)
        tag = lambda r: 'L' if r['deadline_code'] == 'late' and r['credited_at'] else 'O' if r['deadline_code'] == 'late' else 'P' if r['deadline_code'] == 'pending' else 'W'
        sequence = ''.join(tag(r) for r in ordered)
        self.assertRegex(sequence, r'^O{90}L{200}P{60}W{650}$')
        overdue = [tools.minutes_over_target(r, 120) for r in ordered[:90]]
        self.assertEqual(overdue, sorted(overdue, reverse=True))

    def test_explain_record(self):
        record = tools.explain_record('deposits.csv', 'DEP-003')
        self.assertEqual(record['suggested_check']['title'], 'Review the confirmation-to-credit interval')
        self.assertEqual(record['minutes_over_target'], 60)
        self.assertEqual(tools.explain_record('deposits.csv', 'DEP-005')['suggested_check']['title'],
                         'Locate the missing confirmation evidence first')
        with self.assertRaises(ValueError):
            tools.explain_record('deposits.csv', 'NOPE')

    def test_settings_are_validated(self):
        with self.assertRaises(ValueError):
            tools.analyze_file('deposits.csv', target_minutes=0)
        with self.assertRaises(ValueError):
            tools.analyze_file('deposits.csv', observation_time='yesterday')
        with self.assertRaises(ValueError):
            tools.review_queue('deposits.csv', limit=0)

    def test_only_project_csv_files_can_be_read(self):
        for name in ['../README.md', 'README.md', '/etc/passwd', 'tests/x.csv', '..', '', None, 'deposits.csv/..']:
            with self.assertRaises(ValueError, msg=repr(name)):
                tools.read_csv(name)
        with self.assertRaises(ValueError):
            tools.read_csv('missing.csv')

    def test_tools_do_not_write_files(self):
        before = {p: p.stat().st_mtime_ns for p in ROOT.glob('*.csv')} | {p: p.stat().st_mtime_ns for p in ROOT.glob('*.json')}
        tools.analyze_file('deposits.csv'); tools.review_queue('synthetic_deposits.csv'); tools.explain_record('deposits.csv', 'DEP-001')
        after = {p: p.stat().st_mtime_ns for p in ROOT.glob('*.csv')} | {p: p.stat().st_mtime_ns for p in ROOT.glob('*.json')}
        self.assertEqual(before, after)

    @unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
    def test_python_suggestions_match_review_js(self):
        records = analyze((ROOT / 'synthetic_deposits.csv').read_text())['records']
        records += analyze((ROOT / 'deposits.csv').read_text())['records']
        # An equally split late record is not in either dataset.
        records += analyze('deposit_id,amount_usdc,initiated_at,confirmed_at,credited_at\nEQ,1,2026-11-10T10:00:00,2026-11-10T11:05:00,2026-11-10T12:10:00\n')['records']
        script = "const R=require('./review.js');const r=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(r.map(x=>R.nextCheck(x))))"
        out = subprocess.run(['node', '-e', script], input=json.dumps(records), capture_output=True, text=True, cwd=ROOT, check=True)
        self.assertEqual(json.loads(out.stdout), [tools.next_check(r) for r in records])
        self.assertIn('Review both recorded intervals', {tools.next_check(r)['title'] for r in records})


try:
    import mcp_server
except ImportError:
    mcp_server = None


@unittest.skipIf(mcp_server is None, 'optional: pip install mcp to test the MCP wrapper')
class ServerChecks(unittest.TestCase):
    def test_tools_are_registered(self):
        names = {tool.name for tool in asyncio.run(mcp_server.mcp.list_tools())}
        self.assertEqual(names, {'analyze_deposit_file', 'review_queue', 'explain_record'})


if __name__ == '__main__':
    unittest.main()
