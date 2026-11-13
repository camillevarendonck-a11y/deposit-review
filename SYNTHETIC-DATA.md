# The 1,000-record demonstration

Entirely fictional, generated for this project. No customer information, blockchain transactions or company records were used. Amounts, timing distributions and proportions are not calibrated to external data. This tests an analysis workflow; it cannot establish industry benchmarks, fraud rates or business impact.

## Reproduce it

Run `python3 generate_demo.py` in this folder to recreate `synthetic_deposits.csv` with Python's standard library and seed **20261113**. The five-record learning sample is unchanged. All generated IDs start with SYN-.

Default observation: **2026-11-10 14:00:00 UTC**. Target: **120 minutes**. Completed credits span seven days before observation; initiation may precede that window by its processing duration. Amounts are arbitrary independent draws from 1 to 50,000 USDC in cents.

## Deliberately constructed profiles

| Profile | Records | Generation rule |
|---|---:|---|
| Completed within target | 650 | Total 5–120 minutes, split between recorded stages |
| Completed late, larger wait before confirmation | 100 | Before 121–300 minutes; after 1–20 minutes |
| Completed late, larger wait after confirmation | 100 | Before 1–20 minutes; after 121–300 minutes |
| Overdue, confirmation recorded, credit missing | 50 | Age 121–1,440 minutes; confirmation within first 30 minutes |
| Overdue, confirmation and credit missing | 40 | Age 121–1,440 minutes |
| Unresolved, not yet due | 60 | Age 1–120 minutes; some confirmations recorded |

Profile order is shuffled. Timings are uniform integer draws within the stated bounds: test assumptions, not typical processing times. No reason for missing records is asserted. There are no network, queue or compliance logs, so causes cannot be inferred.

## Expected results at the defaults

- 1,000 total; 850 completed; 150 without credit recorded.
- 650 within target; 290 late/overdue; 60 not yet due.
- Eligible denominator: 940. Attainment: **69.1%**.
- Completed-only median: **80 minutes**; excludes the 150 unresolved cases.
- Existing what-if assumption (halve selected after-confirmation waits): 57 additional successes, **75.2%** attainment, approximately 6.1 percentage points higher. Feasibility is unvalidated; unresolved records stay unchanged.

Automated checks independently count the generated profiles and scenario gains from CSV timestamps before comparing with the engine. Small hand-checkable records, boundary cases and invalid-input tests remain separate.

For the competition: “I tested my deposit review workflow on 1,000 reproducible synthetic records covering varied timing and evidence situations. It distinguishes overdue deposits from cases not yet due and supports a labelled what-if calculation. Real operational data and user testing would be needed to establish business value.”
