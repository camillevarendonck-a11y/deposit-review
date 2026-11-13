"""Meaningful upload and configurable-analysis checks. No network or real records."""
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import analyze
import server

ROOT = Path(__file__).resolve().parents[1]

class UploadChecks(unittest.TestCase):
    def setUp(self):
        self.csv = (ROOT / 'deposits.csv').read_text()

    def request(self, payload=None, method='POST', origin='http://127.0.0.1:8767', path='/api/analyze', extra_headers=None):
        h = object.__new__(server.Handler)
        h.server = SimpleNamespace(server_port=8767)
        h.path = path
        body = json.dumps(payload).encode()
        h.headers = {'Host': '127.0.0.1:8767', 'Origin': origin, 'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        h.headers.update(extra_headers or {})
        h.rfile = BytesIO(body)
        captured = {}
        def send(body, status=200, content_type='application/json'):
            captured.update(body=body, status=status, content_type=content_type)
        h.send = send
        h.do_GET() if method == 'GET' else h.do_POST()
        return captured

    def test_target_is_configurable(self):
        r = analyze(self.csv, target_minutes=180)
        self.assertEqual(r['summary']['target_rate_percent'], 60)
        self.assertEqual(r['summary']['within_target'], 3)
        self.assertEqual(r['scenario']['scenario_rate'], 60)

    def test_observation_changes_pending_outcome(self):
        csv = self.csv + 'DEP-006,300,2026-11-10T12:30:00,,\n'
        earlier = analyze(csv)
        later = analyze(csv, '2026-11-10T14:45:00')
        self.assertEqual(earlier['records'][-1]['deadline_code'], 'pending')
        self.assertEqual(later['records'][-1]['deadline_code'], 'late')
        self.assertEqual(later['summary']['target_rate_percent'], 16.7)
        self.assertEqual(earlier['summary']['target_rate_percent'], 20)

    def test_no_eligible_cases_returns_null_not_nan(self):
        csv = 'deposit_id,amount_usdc,initiated_at,confirmed_at,credited_at\nPENDING,1,2026-11-10T13:30:00,,\n'
        r = analyze(csv)
        self.assertIsNone(r['summary']['target_rate_percent'])
        self.assertIsNone(r['summary']['median_completion_minutes'])
        self.assertIsNone(r['scenario']['scenario_rate'])
        json.dumps(r, allow_nan=False)

    def test_offsets_are_normalized_to_utc(self):
        r = analyze(self.csv, '2026-11-10T09:00:00-05:00')
        self.assertEqual(r['summary']['target_rate_percent'], 20)
        self.assertEqual(r['observation_time'], '2026-11-10T14:00:00+00:00')

    def test_bad_amounts_rejected(self):
        for value in ['NaN', 'Infinity', '-1', '0', 'word', '1E9999999']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    analyze(self.csv.replace('DEP-001,100,', 'DEP-001,'+value+','))

    def test_amounts_require_plain_ascii_decimal_format(self):
        for value in ['1_000', '１００', '1e3', '+100', '.5', '100.', '1,000']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze(self.csv.replace('DEP-001,100,', 'DEP-001,'+value+','))
        self.assertEqual(analyze(self.csv.replace('DEP-001,100,', 'DEP-001,100.50,'))['records'][0]['amount_usdc'], '100.50')

    def test_timestamp_format_and_utc_overflow_are_validation_errors(self):
        for value in ['2026-11-10', '2026-11-10 10:00:00', '20261110T100000',
                      '２０２６-11-10T10:00:00', '0001-01-01T00:00:00+05:00',
                      '9999-12-31T23:59:59-05:00']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Invalid isoformat'):
                analyze(self.csv.replace('2026-11-10T10:00:00', value))

    def test_supported_timestamp_variants(self):
        for value in ['2026-11-10T10:00', '2026-11-10T10:00:00Z',
                      '2026-11-10T05:00:00-05:00', '2026-11-10T10:00:00.000000+00:00']:
            with self.subTest(value=value):
                self.assertEqual(analyze(self.csv.replace('2026-11-10T10:00:00', value))['summary']['target_rate_percent'], 20)

    def test_timestamp_overflow_returns_json_error(self):
        invalid = self.csv.replace('2026-11-10T10:00:00', '0001-01-01T00:00:00+05:00')
        result = self.request(dict(csv_text=invalid, observation_time='2026-11-10T14:00:00', target_minutes=120))
        self.assertEqual(result['status'], 400)
        self.assertIn('Invalid isoformat', result['body']['error'])
        self.assertNotIn('summary', result['body'])

    def test_empty_and_invalid_configuration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no deposit records'):
            analyze(self.csv.splitlines()[0]+'\n')
        for target in [0, -1, True, 1.5, '120', 10081]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                analyze(self.csv, target_minutes=target)
        with self.assertRaisesRegex(ValueError, 'Observation time'):
            analyze(self.csv, 'yesterday')

    def test_bom_and_reordered_columns(self):
        text = '\ufeffamount_usdc,deposit_id,initiated_at,credited_at,confirmed_at\n100,ONE,2026-11-10T10:00:00,2026-11-10T10:15:00,2026-11-10T10:10:00\n'
        self.assertEqual(analyze(text)['summary']['target_rate_percent'], 100)

    def test_future_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'credit timestamp'):
            analyze(self.csv, '2026-11-10T12:33:00')

    def test_valid_upload_does_not_change_source_or_outputs(self):
        paths = [ROOT/name for name in ['deposits.csv', 'summary.json', 'scenario.json', 'investigation_results.csv', 'investigation_results.json']]
        before = {p: p.read_bytes() for p in paths}
        r = self.request(dict(csv_text=self.csv, observation_time='2026-11-10T14:00:00', target_minutes=180))
        self.assertEqual(r['status'], 200)
        self.assertEqual(r['body']['summary']['target_rate_percent'], 60)
        self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_error_is_returned_without_partial_results(self):
        r = self.request(dict(csv_text=self.csv.replace('DEP-005,','DEP-001,'), observation_time='2026-11-10T14:00:00', target_minutes=120))
        self.assertEqual(r['status'], 400)
        self.assertIn('duplicate IDs', r['body']['error'])
        self.assertNotIn('summary', r['body'])

    def test_local_origin_and_host_guard(self):
        self.assertEqual(self.request({}, origin='https://unrelated.example')['status'], 403)
        self.assertEqual(self.request({}, extra_headers={'Host':'unrelated.example'})['status'], 403)

    def test_request_size_and_private_files(self):
        self.assertEqual(self.request({}, extra_headers={'Content-Length':str(server.MAX_BODY+1)})['status'], 413)
        self.assertEqual(self.request([], path='/api/analyze')['status'], 400)
        for path in ['/engine.py', '/analysis.py', '/.env', '/../analysis.py']:
            self.assertEqual(self.request(method='GET', path=path)['status'], 404)

if __name__ == '__main__':
    unittest.main()
