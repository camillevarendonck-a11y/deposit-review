"""Reproducible fictional fixtures, not calibrated to any company's operations."""
import csv
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from random import Random

OBSERVATION = datetime(2026, 11, 10, 14)
SEED = 20261113
PROFILES = [('within', 650), ('before_late', 100), ('after_late', 100),
            ('confirmed_overdue', 50), ('missing_overdue', 40), ('not_due', 60)]


def generate():
    rng = Random(SEED)
    profiles = [name for name, count in PROFILES for _ in range(count)]
    rng.shuffle(profiles)
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['deposit_id', 'amount_usdc', 'initiated_at', 'confirmed_at', 'credited_at'])
    for number, profile in enumerate(profiles, 1):
        confirmed = credited = None
        if profile in ('within', 'before_late', 'after_late'):
            # All completed events precede the fixed observation, across seven days.
            credited = OBSERVATION - timedelta(minutes=rng.randint(0, 7 * 1440))
            if profile == 'within':
                total = rng.randint(5, 120)
                before = rng.randint(1, total - 1)
                after = total - before
            elif profile == 'before_late':
                before, after = rng.randint(121, 300), rng.randint(1, 20)
            else:
                before, after = rng.randint(1, 20), rng.randint(121, 300)
            confirmed = credited - timedelta(minutes=after)
            initiated = confirmed - timedelta(minutes=before)
        else:
            age = rng.randint(1, 120) if profile == 'not_due' else rng.randint(121, 1440)
            initiated = OBSERVATION - timedelta(minutes=age)
            if profile == 'confirmed_overdue' or (profile == 'not_due' and rng.choice([True, False])):
                confirmed = initiated + timedelta(minutes=rng.randint(0, min(age, 30)))
        # Amounts are arbitrary and do not determine delays or review status.
        amount = f'{rng.randint(100, 5000000) / 100:.2f}'
        fmt = lambda value: value.isoformat(timespec='seconds') if value else ''
        writer.writerow([f'SYN-{number:04}', amount, fmt(initiated), fmt(confirmed), fmt(credited)])
    return stream.getvalue()


if __name__ == '__main__':
    path = Path(__file__).with_name('synthetic_deposits.csv')
    path.write_text(generate(), encoding='utf-8')
    print(f'Created {path.name}: 1,000 fictional records; seed {SEED}.')
