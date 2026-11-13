"""Read-only helpers behind the MCP server (mcp_server.py). Standard library only.

They reuse engine.analyze, so every number matches the dashboard. Nothing is
written to disk, and only .csv files inside this project folder can be read.
"""
import re
from pathlib import Path
from engine import analyze, DEFAULT_OBSERVATION, DEFAULT_TARGET

ROOT = Path(__file__).resolve().parent
MAX_FILE_BYTES = 1024 * 1024

CAUTIONS = [
    'Median time to credit covers completed deposits only; unresolved cases are excluded.',
    'The scenario is a hypothetical 50% cut in after-confirmation waits, not a forecast.',
    'Missing records do not establish a cause, fraud, or the location of funds.',
]


def read_csv(filename):
    """Return the text of a .csv that sits directly inside the project folder."""
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.lower().endswith('.csv'):
        raise ValueError('Use the name of a .csv file inside the project folder, for example deposits.csv.')
    path = (ROOT / filename).resolve()
    if path.parent != ROOT or not path.is_file():
        raise ValueError(f'No such CSV in the project folder: {filename}')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('CSV files larger than 1 MB are not supported.')
    return path.read_text(encoding='utf-8-sig')


def _natural(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', text)]


def _rank(record):
    if record['deadline_code'] == 'late':
        return 1 if record['credited_at'] else 0
    return 2 if record['deadline_code'] == 'pending' else 3


def minutes_over_target(record, target):
    return max(0.0, record['elapsed_minutes'] - target)


def queue_order(records, target):
    """Same rule as the dashboard: overdue/no credit, completed late, not yet due, within target."""
    return sorted(records, key=lambda r: (
        _rank(r),
        -minutes_over_target(r, target) if r['deadline_code'] == 'late' else 0,
        _natural(r['deposit_id'])))


def next_check(record):
    """Python mirror of ReviewTools.nextCheck in review.js (a test keeps them identical)."""
    if record['deadline_code'] == 'pending':
        return dict(title='Recheck after the target boundary',
                    text='This record is not yet overdue. Recalculate after the target boundary has passed, or when new source events arrive. Missing timestamps alone do not establish a processing failure.')
    if record['deadline_code'] == 'within':
        return dict(title='Retain the supporting records',
                    text='The recorded credit met the selected target. No delay investigation is indicated by these timestamps alone; retain the source events so the result can be checked.')
    if not record['confirmed_at']:
        return dict(title='Locate the missing confirmation evidence first',
                    text='Neither confirmation nor credit is recorded. First search the source system using this deposit ID for a confirmation event; also reconcile any credit recorded elsewhere. Until those records are located, the waiting stage cannot be determined.')
    if not record['credited_at']:
        return dict(title='Trace account credit after the recorded confirmation',
                    text='Confirmation is recorded, but credit is not. Use the confirmation timestamp as the starting point: check subsequent account-credit events and reconcile the customer ledger. Establish whether credit occurred without appearing in this extract before concluding it is still pending.')
    before, after = record['before_confirmation_minutes'], record['after_confirmation_minutes']
    if after > before:
        return dict(title='Review the confirmation-to-credit interval',
                    text='Retrieve audit events between the recorded confirmation and credit. Check intermediate states, timestamp meanings and clock consistency. The larger wait occurred in this interval; its cause is not established.')
    if before > after:
        return dict(title='Review the initiation-to-confirmation interval',
                    text='Retrieve source events between initiation and confirmation. Verify identifiers, timestamp meanings and clock consistency. The larger recorded wait occurred here; this alone does not establish a network or process cause.')
    return dict(title='Review both recorded intervals',
                text='The recorded waiting time is equally split before and after confirmation. Retrieve audit events for both intervals and verify timestamp meanings and clock consistency before proposing a cause.')


def _run(filename, observation_time, target_minutes):
    return analyze(read_csv(filename), observation_time, target_minutes)


def analyze_file(filename='deposits.csv', observation_time=DEFAULT_OBSERVATION, target_minutes=DEFAULT_TARGET):
    result = _run(filename, observation_time, target_minutes)
    scenario = result['scenario']
    return dict(
        file=filename, observation_time=result['observation_time'], summary=result['summary'],
        scenario=dict(original_rate_percent=scenario['original_rate'], scenario_rate_percent=scenario['scenario_rate'],
                      additional_within_target=scenario['additional_within_target'], assumption=scenario['assumption']),
        cautions=CAUTIONS)


def review_queue(filename='deposits.csv', limit=10, observation_time=DEFAULT_OBSERVATION, target_minutes=DEFAULT_TARGET):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('limit must be a whole number from 1 to 200.')
    result = _run(filename, observation_time, target_minutes)
    ordered = queue_order(result['records'], target_minutes)
    return dict(
        file=filename, total_records=len(ordered), shown=min(limit, len(ordered)),
        order_rule='Overdue with no credit (longest overdue first), then completed late, then not yet due, then within target; ties by deposit ID.',
        queue=[dict(deposit_id=r['deposit_id'], amount_usdc=r['amount_usdc'], deadline_status=r['deadline_status'],
                    minutes_over_target=round(minutes_over_target(r, target_minutes), 2), category=r['category'])
               for r in ordered[:limit]])


def explain_record(filename, deposit_id, observation_time=DEFAULT_OBSERVATION, target_minutes=DEFAULT_TARGET):
    result = _run(filename, observation_time, target_minutes)
    matches = [r for r in result['records'] if r['deposit_id'] == deposit_id]
    if not matches:
        raise ValueError(f'No deposit with ID {deposit_id!r} in {filename}.')
    r = matches[0]
    return dict(
        deposit_id=r['deposit_id'], amount_usdc=r['amount_usdc'], deadline_status=r['deadline_status'], category=r['category'],
        initiated_at=r['initiated_at'], confirmed_at=r['confirmed_at'], credited_at=r['credited_at'],
        minutes_before_confirmation=r['before_confirmation_minutes'], minutes_after_confirmation=r['after_confirmation_minutes'],
        minutes_elapsed=r['elapsed_minutes'], minutes_over_target=round(minutes_over_target(r, target_minutes), 2),
        suggested_check=next_check(r),
        caution='Rule-based triage for human review. It is not a verified cause, and missing records do not prove an event never happened.')
