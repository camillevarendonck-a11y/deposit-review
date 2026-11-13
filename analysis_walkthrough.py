"""Earlier learning version. Outputs go to walkthrough_outputs/ only.
Use analysis.py or the dashboard for current validation and results.
"""
import csv
from pathlib import Path
from datetime import datetime
from statistics import median
from collections import Counter
import json

# Find deposits.csv in the same folder as this Python file.
data_file = Path(__file__).parent / "deposits.csv"

# Read the table. Each row becomes a dictionary.
with data_file.open(newline="") as file:
    reader = csv.DictReader(file)
    expected_columns = [
        "deposit_id", "amount_usdc", "initiated_at", "confirmed_at", "credited_at"
    ]
    if reader.fieldnames != expected_columns:
        raise ValueError("CSV column names do not match the expected five columns.")

    deposits = []
    for line_number, deposit in enumerate(reader, start=2):
        # Empty fields are allowed; missing or extra columns are not.
        if None in deposit or any(value is None for value in deposit.values()):
            raise ValueError(f"CSV line {line_number}: expected exactly five fields.")
        deposits.append(deposit)

print(f"Loaded {len(deposits)} deposits.")

# Fixed observation time for this fictional dataset.
observation_time = datetime.fromisoformat("2026-11-10T14:00:00")

# Check source records before calculating or saving anything.
# Every deposit must have a unique ID.
deposit_ids = [deposit["deposit_id"] for deposit in deposits]

if not (len(set(deposit_ids)) == len(deposits)):
    raise ValueError('Some deposits have duplicate IDs.')

# Recorded events must follow the correct order.
for deposit in deposits:
    initiated = datetime.fromisoformat(deposit["initiated_at"])

    if not (initiated <= observation_time):
        raise ValueError(f"{deposit['deposit_id']}: initiation is after the observation time.")

    if deposit["confirmed_at"]:
        confirmed = datetime.fromisoformat(deposit["confirmed_at"])

        if not (initiated <= confirmed <= observation_time):
            raise ValueError(f"{deposit['deposit_id']}: check the confirmation timestamp.")

    if deposit["credited_at"]:
        if not (deposit['confirmed_at']):
            raise ValueError(f"{deposit['deposit_id']}: credit exists without confirmation.")

        credited = datetime.fromisoformat(deposit["credited_at"])

        if not (confirmed <= credited <= observation_time):
            raise ValueError(f"{deposit['deposit_id']}: check the credit timestamp.")


for deposit in deposits:
    deposit_id = deposit["deposit_id"]
    initiated = datetime.fromisoformat(deposit["initiated_at"])

    if not deposit["confirmed_at"]:
        elapsed = (observation_time - initiated).total_seconds() / 60

        print(
            f"{deposit_id}: No confirmation recorded | "
            f"{elapsed:.0f} min since initiation"
        )

    elif not deposit["credited_at"]:
        confirmed = datetime.fromisoformat(deposit["confirmed_at"])
        elapsed = (observation_time - initiated).total_seconds() / 60
        since_confirmation = (
            observation_time - confirmed
        ).total_seconds() / 60

        print(
            f"{deposit_id}: No credit recorded | "
            f"{elapsed:.0f} min since initiation | "
            f"{since_confirmation:.0f} min since confirmation"
        )

    else:
        confirmed = datetime.fromisoformat(deposit["confirmed_at"])
        credited = datetime.fromisoformat(deposit["credited_at"])

        before_confirmation = (confirmed - initiated).total_seconds() / 60
        after_confirmation = (credited - confirmed).total_seconds() / 60
        total_time = (credited - initiated).total_seconds() / 60

        print(
            f"{deposit_id}: "
            f"before confirmation = {before_confirmation:.0f} min | "
            f"after confirmation = {after_confirmation:.0f} min | "
            f"total = {total_time:.0f} min"
        )

target_minutes = 120

within_target = 0
over_target = 0
not_yet_due = 0

print("\n--- Time target check ---")

for deposit in deposits:
    initiated = datetime.fromisoformat(deposit["initiated_at"])

    if deposit["credited_at"]:
        credited = datetime.fromisoformat(deposit["credited_at"])
        duration = (credited - initiated).total_seconds() / 60

        if duration <= target_minutes:
            status = "Within target"
            within_target += 1
        else:
            status = "Over target"
            over_target += 1

    else:
        elapsed = (observation_time - initiated).total_seconds() / 60

        if elapsed > target_minutes:
            status = "Over target — still unresolved"
            over_target += 1
        else:
            status = "Not yet due — still unresolved"
            not_yet_due += 1

    print(f"{deposit['deposit_id']}: {status}")

print(f"\nWithin target: {within_target}")
print(f"Over target: {over_target}")
print(f"Not yet due: {not_yet_due}")

# Include completed deposits and overdue unresolved deposits.
# Exclude unresolved deposits that are not yet due.
eligible_deposits = within_target + over_target

if eligible_deposits > 0:
    target_rate = (within_target / eligible_deposits) * 100
    print(f"\nCredited within target: {target_rate:.1f}%")
else:
    print("\nNo deposits are eligible for assessment yet.")

completed_times = []

for deposit in deposits:
    if deposit["credited_at"]:
        initiated = datetime.fromisoformat(deposit["initiated_at"])
        credited = datetime.fromisoformat(deposit["credited_at"])

        duration = (credited - initiated).total_seconds() / 60
        completed_times.append(duration)

print(f"\nCompleted deposit times: {sorted(completed_times)}")

if completed_times:
    median_time = median(completed_times)
    print(f"Median completion time: {median_time:.0f} minutes")
else:
    print("No completed deposits to calculate a median.")

print("\n--- Investigation priorities ---")
category_counts = Counter()
investigation_results = []

for deposit in deposits:
    initiated = datetime.fromisoformat(deposit["initiated_at"])

    # Timing and evidence are separate: missing confirmation does not mean late.
    if deposit["credited_at"]:
        credited = datetime.fromisoformat(deposit["credited_at"])
        duration = (credited - initiated).total_seconds() / 60
        deadline_status = "Within target" if duration <= target_minutes else "Over target"
    else:
        elapsed = (observation_time - initiated).total_seconds() / 60
        deadline_status = "Overdue, no credit recorded" if elapsed > target_minutes else "Not yet due"

    if not deposit["confirmed_at"]:
        category = "Missing confirmation evidence"

    elif not deposit["credited_at"]:
        category = "Confirmed, awaiting account credit"

    else:
        confirmed = datetime.fromisoformat(deposit["confirmed_at"])
        credited = datetime.fromisoformat(deposit["credited_at"])

        total_minutes = (credited - initiated).total_seconds() / 60
        before_minutes = (confirmed - initiated).total_seconds() / 60
        after_minutes = (credited - confirmed).total_seconds() / 60

        if total_minutes <= target_minutes:
            category = "Completed within target"

        elif before_minutes > after_minutes:
            category = "Over target; most waiting before confirmation"

        elif after_minutes > before_minutes:
            category = "Over target; most waiting after confirmation"

        else:
            category = "Over target; waiting equally split"
    category_counts[category] += 1

    print(f"{deposit['deposit_id']}: {category}")
    investigation_results.append({
        "deposit_id": deposit["deposit_id"],
        "amount_usdc": deposit["amount_usdc"],
        "deadline_status": deadline_status,
        "category": category
    })

print("\n--- Category summary ---")

for category, count in category_counts.items():
    print(f"{category}: {count}")

total_categorized = sum(category_counts.values())

print(f"\nTotal categorized: {total_categorized}")
print(f"Total loaded: {len(deposits)}")




# Count deposits without a recorded account credit.
unresolved_count = sum(
    1 for deposit in deposits
    if not deposit["credited_at"]
)

# Collect the headline metrics.
summary = {
    "total_deposits": len(deposits),
    "completed_deposits": len(completed_times),
    "median_scope": "Completed deposits only; excludes records without a credit timestamp.",
    "unresolved_deposits": unresolved_count,
    "target_minutes": target_minutes,
    "within_target": within_target,
    "over_target": over_target,
    "not_yet_due": not_yet_due,
    "target_rate_percent": (
        round(target_rate, 1) if eligible_deposits > 0 else None
    ),
    "median_completion_minutes": (
        median(completed_times) if completed_times else None
    )
}



print("\n--- Validation checks ---")

# Every deposit must receive one investigation result.
if not (len(investigation_results) == len(deposits)):
    raise ValueError('Some investigation results are missing.')

# Every deposit must appear in one target-status group.
if not (within_target + over_target + not_yet_due == len(deposits)):
    raise ValueError('The target-status counts do not match the dataset.')

print("All validation checks passed.")



print("\n--- Improvement scenario ---")

additional_within_target = 0

for deposit in deposits:
    # Only evaluate completed deposits.
    if not deposit["confirmed_at"] or not deposit["credited_at"]:
        continue

    initiated = datetime.fromisoformat(deposit["initiated_at"])
    confirmed = datetime.fromisoformat(deposit["confirmed_at"])
    credited = datetime.fromisoformat(deposit["credited_at"])

    before_minutes = (confirmed - initiated).total_seconds() / 60
    after_minutes = (credited - confirmed).total_seconds() / 60
    original_total = before_minutes + after_minutes

    # Focus on overdue deposits whose larger wait occurred after confirmation.
    if original_total > target_minutes and after_minutes > before_minutes:
        improved_after = after_minutes * 0.5
        improved_total = before_minutes + improved_after

        print(
            f"{deposit['deposit_id']}: "
            f"{original_total:.0f} min originally → "
            f"{improved_total:.0f} min in the scenario"
        )

        if improved_total <= target_minutes:
            additional_within_target += 1

scenario_within_target = within_target + additional_within_target

if eligible_deposits > 0:
    scenario_rate = (
        scenario_within_target / eligible_deposits
    ) * 100

    print(f"Original target attainment: {target_rate:.1f}%")
    print(f"Scenario target attainment: {scenario_rate:.1f}%")
    print(f"Additional deposits within target: {additional_within_target}")

scenario = {
    "original_rate": (
        round(target_rate, 1) if eligible_deposits > 0 else None
    ),
    "scenario_rate": (
        round(scenario_rate, 1) if eligible_deposits > 0 else None
    ),
    "additional_within_target": additional_within_target
}

# Export only after source validation and all calculations have succeeded.
output_folder = Path(__file__).parent / "walkthrough_outputs"
output_folder.mkdir(exist_ok=True)
output_file = output_folder / "investigation_results.csv"

with output_file.open("w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=["deposit_id", "amount_usdc", "deadline_status", "category"]
    )

    writer.writeheader()
    writer.writerows(investigation_results)

print(f"\nSaved {len(investigation_results)} results to {output_file.name}")

# Save the learning metrics in the separate walkthrough output folder.
summary_file = output_folder / "summary.json"

with summary_file.open("w") as file:
    json.dump(summary, file, indent=4)

print(f"Saved summary to {summary_file.name}")

# Save learning results separately from the current dashboard analysis.
results_file = output_folder / "investigation_results.json"

with results_file.open("w") as file:
    json.dump(investigation_results, file, indent=4)

print(f"Saved {len(investigation_results)} dashboard investigation results.")

scenario_file = output_folder / "scenario.json"

with scenario_file.open("w") as file:
    json.dump(scenario, file, indent=4)

print(f"Saved walkthrough outputs in {output_folder}")
