"""Run the shared analysis and save local results. The browser uses the same engine.
The original step-by-step learning script is preserved in analysis_walkthrough.py.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile
from engine import analyze, DEFAULT_OBSERVATION, DEFAULT_TARGET

ROOT = Path(__file__).resolve().parent

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Analyze a crypto deposit CSV.')
    parser.add_argument('--input', type=Path, default=ROOT / 'deposits.csv')
    parser.add_argument('--observation', default=DEFAULT_OBSERVATION, help='ISO timestamp; no timezone means UTC')
    parser.add_argument('--target', type=int, default=DEFAULT_TARGET, help='Credit target, in minutes')
    args = parser.parse_args()
    try:
        result = analyze(args.input.read_text(encoding='utf-8-sig'), args.observation, args.target)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    columns = ['deposit_id', 'amount_usdc', 'deadline_status', 'category']
    records = [{key: r[key] for key in columns} for r in result['records']]
    # Stage files only after validation. Individual replacements are atomic,
    # but the four-file set is not a transaction if a process is interrupted.
    with tempfile.TemporaryDirectory(dir=ROOT) as temp:
        staged = Path(temp)
        for name, value in [('summary.json', result['summary']), ('scenario.json', result['scenario']), ('investigation_results.json', records)]:
            (staged / name).write_text(json.dumps(value, indent=4) + '\n')
        with (staged / 'investigation_results.csv').open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)
        for file in staged.iterdir():
            os.replace(file, ROOT / file.name)
    print('All validation checks passed.')
    print(json.dumps(result['summary'], indent=2))
    print('Saved summary, scenario, and investigation results.')
