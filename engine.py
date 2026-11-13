"""Shared CSV analysis for the dashboard and command-line script. No file writes."""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import re
from statistics import median

COLUMNS = ['deposit_id', 'amount_usdc', 'initiated_at', 'confirmed_at', 'credited_at']
DEFAULT_OBSERVATION = '2026-11-10T14:00:00'
DEFAULT_TARGET = 120
MAX_ROWS = 5000
TIMESTAMP_FORMAT = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?')
AMOUNT_FORMAT = re.compile(r'[0-9]+(?:\.[0-9]+)?')


def timestamp(value, label):
    try:
        if not isinstance(value, str) or not TIMESTAMP_FORMAT.fullmatch(value):
            raise ValueError('Expected an ISO date and time.')
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Unqualified timestamps are explicitly interpreted as UTC throughout the app.
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise ValueError(f'{label}: Invalid isoformat timestamp. Use YYYY-MM-DDTHH:MM:SS.') from None


def analyze(csv_text, observation_time=DEFAULT_OBSERVATION, target_minutes=DEFAULT_TARGET):
    """Validate every input before returning a result; callers decide how to save it."""
    if not isinstance(csv_text, str):
        raise ValueError('CSV content must be text.')
    if type(target_minutes) is not int or not 1 <= target_minutes <= 10080:
        raise ValueError('Credit target must be a whole number between 1 and 10,080 minutes.')
    observed = timestamp(observation_time, 'Observation time')
    reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')), strict=True)
    try:
        headers = reader.fieldnames
    except csv.Error as error:
        raise ValueError(f'Could not read CSV header: {error}') from None
    if not headers or len(headers) != 5 or set(headers) != set(COLUMNS):
        raise ValueError('CSV column names must be: ' + ', '.join(COLUMNS))
    records, seen = [], set()
    try:
        for line, raw in enumerate(reader, 2):
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError(f'CSV line {line}: expected exactly five fields.')
            if len(records) >= MAX_ROWS:
                raise ValueError(f'Use no more than {MAX_ROWS:,} rows per file.')
            row = {key: value.strip() for key, value in raw.items()}
            deposit_id = row['deposit_id']
            if not deposit_id:
                raise ValueError(f'CSV line {line}: deposit_id is required.')
            if deposit_id in seen:
                raise ValueError(f'{deposit_id}: Some deposits have duplicate IDs.')
            seen.add(deposit_id)
            if len(row['amount_usdc']) > 40:
                raise ValueError(f'{deposit_id}: amount_usdc has too many digits.')
            if not AMOUNT_FORMAT.fullmatch(row['amount_usdc']):
                raise ValueError(f'{deposit_id}: amount_usdc must use digits 0–9 and an optional decimal point (for example 1000.50).')
            try:
                amount = Decimal(row['amount_usdc'])
            except InvalidOperation:
                raise ValueError(f'{deposit_id}: amount_usdc must be a positive number.') from None
            if not amount.is_finite() or amount <= 0:
                raise ValueError(f'{deposit_id}: amount_usdc must be a positive finite number.')
            if amount.adjusted() > 14 or amount.as_tuple().exponent < -8:
                raise ValueError(f'{deposit_id}: use at most 15 whole-number digits and 8 decimal places.')
            initiated = timestamp(row['initiated_at'], deposit_id + ' initiation')
            confirmed = timestamp(row['confirmed_at'], deposit_id + ' confirmation') if row['confirmed_at'] else None
            credited = timestamp(row['credited_at'], deposit_id + ' credit') if row['credited_at'] else None
            if initiated > observed:
                raise ValueError(f'{deposit_id}: initiation is after the observation time.')
            if confirmed and not initiated <= confirmed <= observed:
                raise ValueError(f'{deposit_id}: check the confirmation timestamp; it must be between initiation and observation.')
            if credited and not confirmed:
                raise ValueError(f'{deposit_id}: credit exists without confirmation. Reconcile source records first.')
            if credited and not confirmed <= credited <= observed:
                raise ValueError(f'{deposit_id}: check the credit timestamp; it must be between confirmation and observation.')

            before = (confirmed - initiated).total_seconds() / 60 if confirmed else None
            after = (credited - confirmed).total_seconds() / 60 if credited else None
            elapsed = ((credited or observed) - initiated).total_seconds() / 60
            if credited:
                deadline = 'Within target' if elapsed <= target_minutes else 'Over target'
                code = 'within' if elapsed <= target_minutes else 'late'
            else:
                deadline = 'Overdue, no credit recorded' if elapsed > target_minutes else 'Not yet due'
                code = 'late' if elapsed > target_minutes else 'pending'
            if not confirmed:
                category = 'Missing confirmation evidence'
            elif not credited:
                category = 'Confirmed, awaiting account credit'
            elif elapsed <= target_minutes:
                category = 'Completed within target'
            elif before > after:
                category = 'Over target; most waiting before confirmation'
            elif after > before:
                category = 'Over target; most waiting after confirmation'
            else:
                category = 'Over target; waiting equally split'
            records.append(dict(
                deposit_id=deposit_id, amount_usdc=format(amount, 'f'),
                initiated_at=initiated.isoformat(), confirmed_at=confirmed.isoformat() if confirmed else None,
                credited_at=credited.isoformat() if credited else None,
                deadline_status=deadline, deadline_code=code, category=category,
                completion_minutes=elapsed if credited else None, elapsed_minutes=elapsed,
                before_confirmation_minutes=before, after_confirmation_minutes=after,
            ))
    except csv.Error as error:
        raise ValueError(f'Could not read CSV: {error}') from None
    if not records:
        raise ValueError('The CSV contains no deposit records. Add at least one row below the header.')

    completed = [r['completion_minutes'] for r in records if r['credited_at']]
    within = sum(r['deadline_code'] == 'within' for r in records)
    late = sum(r['deadline_code'] == 'late' for r in records)
    pending = len(records) - within - late
    eligible = within + late
    rate = round(within / eligible * 100, 1) if eligible else None
    improved, affected = 0, []
    for r in records:
        if r['credited_at'] and r['deadline_code'] == 'late' and r['after_confirmation_minutes'] > r['before_confirmation_minutes']:
            new_duration = r['before_confirmation_minutes'] + r['after_confirmation_minutes'] * .5
            crossed = new_duration <= target_minutes
            improved += crossed
            affected.append(dict(deposit_id=r['deposit_id'], original_minutes=r['completion_minutes'], scenario_minutes=new_duration, meets_target=crossed))
    summary = dict(total_deposits=len(records), completed_deposits=len(completed),
                   unresolved_deposits=len(records)-len(completed), target_minutes=target_minutes,
                   within_target=within, over_target=late, not_yet_due=pending, eligible_deposits=eligible,
                   target_rate_percent=rate, median_completion_minutes=median(completed) if completed else None,
                   median_scope='Completed deposits only; excludes records without a credit timestamp.')
    return dict(summary=summary, records=records, observation_time=observed.isoformat(),
                scenario=dict(original_rate=rate, scenario_rate=round((within+improved)/eligible*100,1) if eligible else None,
                              additional_within_target=improved, affected_records=affected,
                              assumption='Halve after-confirmation waits only for completed, overdue deposits whose larger wait occurred after confirmation. All other records are unchanged.'))
