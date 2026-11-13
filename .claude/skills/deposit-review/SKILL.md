---
name: deposit-review
description: Review a crypto deposit CSV for delays and missing evidence. Use when asked to analyze deposits, check target attainment, build an investigation queue, explain a deposit, or verify the Deposit Review numbers.
---

# Deposit review

Analyze deposit records (`deposit_id, amount_usdc, initiated_at, confirmed_at, credited_at`) the way the Deposit Review dashboard does. Use the `deposit-review` MCP tools when available (`analyze_deposit_file`, `review_queue`, `explain_record`). Otherwise call `engine.analyze(csv_text, observation_time, target_minutes)` from this folder. Never use `analysis.py` for a quick check: it overwrites the saved output files.

## Steps

1. **Settings.** Ask for, or state, the observation time (UTC unless an offset is given) and the credit target in minutes. Defaults: `2026-11-10T14:00:00` and 120.
2. **Run the analysis.** If it raises a validation error, report the message and stop. Do not repair the data silently.
3. **Verify independently.** Recompute at least the headline numbers from the raw timestamps without the engine: for 20 records or fewer, every record; otherwise the counts and the median. Report any mismatch.
4. **Check the boundaries.**
   - A credited deposit at exactly the target is within target.
   - An unresolved deposit is overdue only when elapsed time is greater than the target.
   - Unresolved and not yet due records are excluded from the attainment denominator.
5. **Report** target attainment with its denominator, the completed-only median, the top of the investigation queue, and one suggested next check for the first few records. State the scenario only as hypothetical.

## Reference values

`deposits.csv` at the defaults: 5 records, 3 completed, 1 within target, 20.0% attainment, median 155 minutes, scenario 40.0%. Queue order: DEP-004, DEP-005, DEP-003, DEP-002, DEP-001.

## Rules

- Missing confirmation or credit is missing evidence, not proof an event never happened.
- Do not infer causes, fraud, customer harm, or where funds are.
- All sample data is synthetic. Never present results as real company performance.
- Do not edit `deposits.csv`, `synthetic_deposits.csv` or the saved output files unless the user asks.
