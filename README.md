# Deposit Review

A local analysis workspace for USDC deposit operations. Upload records, choose an observation time and credit-time target, inspect delays and missing evidence, and export the calculated results. The included sample is fictional.

## Open from VS Code

Open this `my-deposit-project` folder in VS Code. In its terminal run:

```sh
python3 server.py
```

Open http://127.0.0.1:8767/ in your browser. Keep that terminal running; Ctrl+C stops it. The old `python3 -m http.server` command cannot run the upload calculations. If port 8767 is occupied, stop your previous preview server, or use `python3 server.py --port 8768` and open that port instead.

## Try your own records

1. Click **Download template** and keep its five column names.
2. Replace the example records, then **Choose CSV**.
3. Set the observation time in UTC and the credit-time target in minutes.
4. Click **Analyze records**. Inspect individual cases or filter deadline statuses.
5. Click **Export results** to download the results for every record, including the settings used. Filtering the table does not filter the export.

The dashboard opens with the **1,000-record synthetic demo**. Use **5-record sample** for the original hand-checkable example, or **1,000-record demo** to restore the larger dataset and default settings. **Download demo CSV** saves the generated input so you can practice the upload workflow. A smaller **mixed-format example** (`realistic-example.csv`, 16 deposits on Ethereum, Arbitrum and Base-style IDs) mimics an export with different time-zone offsets, a boundary case at exactly 120 minutes and missing confirmations. It is still fictional; download it from the setup panel and expect 5 of 13 eligible deposits within target (38.5%), a 69.2% scenario and ETH-20485 at the top of the queue. See [SYNTHETIC-DATA.md](SYNTHETIC-DATA.md) for generation assumptions and expected results. These patterns are deliberately constructed and do not describe real company performance. Changed inputs leave the previous results visible with an explicit warning until the next successful analysis. Export is disabled while results are out of date.

The browser accepts UTF-8 CSV files up to 1 MB and 5,000 records. Use exactly `deposit_id,amount_usdc,initiated_at,confirmed_at,credited_at` (column order may vary). IDs must be unique and are case-sensitive (`a` and `A` are distinct). Amounts must use ASCII digits 0–9 with an optional decimal part (for example `1000.50`), be positive, and have at most 15 whole digits and 8 decimal places. Signs, separators, underscores and scientific notation are rejected. A blank confirmation or credit means missing evidence, not proof the event never happened. Rows must contain all five fields, including trailing commas for blank values.

Use ISO timestamps with a date, `T`, and a time, such as `2026-11-10T10:00:00`. Minute precision (`2026-11-10T10:00`) is accepted; seconds may include up to six fractional digits. Optional timezone suffixes are `Z` or `±HH:MM`. Date-only values and out-of-range UTC conversions are rejected. Times without an offset are interpreted as UTC; offset-aware times are converted to UTC. Initiation, confirmation and credit must be in that order and no later than the observation time. This prototype requires confirmation evidence for a recorded credit. Reconcile incomplete source records before analysis. Targets must be whole minutes from 1 through 10,080.

## Using a real ledger export

Nothing here has been validated on real deposit data yet. To try it, export your records to the five columns below. Leave an event blank if it is unknown.

| Column | Meaning in your system |
| --- | --- |
| `deposit_id` | A unique deposit reference |
| `amount_usdc` | Amount in USDC, digits only, such as `1000.50` |
| `initiated_at` | When the customer's transfer started or the deposit was created |
| `confirmed_at` | When the blockchain confirmation was recorded |
| `credited_at` | When the customer's account was credited |

Before you trust the results, check three things: the timezone of every timestamp (times without an offset are read as UTC), what "credited" means in that system, and whether one target suits every network and deposit size. Public documentation shows that required confirmations vary by network and amount, so you may need separate runs with different targets.

A pilot would compare the queue with analysts' own prioritization and measure whether the suggested checks help. That has not been done.

## Filters, findings and suggested checks

Combine the deadline-status filter (including overdue with no credit and completed late) with the evidence filter (confirmation missing, credit missing, or both recorded). The two choices intersect with the deposit-ID search; they reset pagination and preserve the queue order. An empty intersection is shown explicitly.

Investigation findings summarize the entire last successfully analyzed dataset, independently of table filters. They separate overdue records by confirmation evidence and completed late records by which recorded stage had the larger wait. Zero counts are shown explicitly.

Inspect includes a deterministic suggested next check tailored to the evidence and deadline status. Not-yet-due cases get a recheck suggestion, while missing records get reconciliation checks. Suggestions do not establish cause, normality, fraud or the status of funds, and are not Claude responses. The review rules live in `review.js`.

## Investigation order

The queue puts overdue records with no credit recorded first, ordered by minutes over target (elapsed time minus the target). Completed late deposits follow, ordered by their completion time minus the target. Not-yet-due records follow those, then completed records within target. Ties and the last two groups use deposit ID order. This is a transparent triage rule, not a risk score or proof of customer harm. Filtering preserves this order; exports include all records in queue order and a `minutes_over_target` column (zero for records not over target). The selected target and observation time determine the order.

## What the metrics mean

- Completed at or before the target: success.
- Completed after the target, or unresolved with elapsed time greater than the target: miss on the available records.
- Unresolved at or before the target: not yet due and excluded from the attainment denominator.
- Median time to credit uses completed records only and can understate waits for unresolved cases.
- The improvement scenario assumes a 50% reduction in after-confirmation wait for completed overdue cases whose larger wait occurred after confirmation. It excludes unresolved cases. It establishes neither feasibility nor expected real-world impact.

All durations are compared before display rounding. Missing evidence cannot establish cause, fraud or the location of funds. A completed deposit at exactly the target qualifies; an unresolved one at that instant remains excluded. Percentages are rounded to one decimal using Python’s round-half-to-even convention (for example, exactly 6.25% becomes 6.2%). Percentages are undefined when there are no eligible records.

## Privacy and Claude status

Uploads are processed in memory by a Python server bound to this computer's loopback address. They do not overwrite sample records or saved analysis files. The app does not send uploads to Claude or any external service, and does not persist uploaded datasets between page reloads. Export results if needed. This is a local prototype, without production authentication or deployment infrastructure.

Claude's manually reviewed case briefs and evaluations are saved separately in `evaluations`. There is currently no live Claude API connection. Do not present the upload feature as an AI integration.

## Claude Code skill and MCP server

Claude can also work with this project from the outside, through two optional pieces. Neither changes the dashboard, and the dashboard still makes no Claude or other external calls.

- **Skill** (`.claude/skills/deposit-review/SKILL.md`): teaches Claude Code the review procedure: run the analysis, recompute the headline numbers independently, check the deadline boundaries, report the queue, and never infer causes or fraud. It does not run on its own; Claude Code loads it when a request matches.
- **MCP server** (`mcp_server.py`, registered in `.mcp.json`): gives Claude three read-only tools, `analyze_deposit_file`, `review_queue` and `explain_record`. They reuse `engine.py`, so numbers match the dashboard, and they read only `.csv` files inside this folder. `deposit_tools.py` holds the logic; a test keeps its suggested checks identical to `review.js`. Install once with `pip install mcp` (versions 1.x and 2.x both work), then open this folder in Claude Code.

Data handling: the server runs on this computer and makes no network calls. When you use it through Claude Code, the tool results (deposit IDs, amounts, timestamps) become part of that Claude conversation, so use only synthetic or approved data.

Tested once in Claude Code 2.1.323 (Opus 5.5) on 13 November 2026 on the project owner's computer: the skill loaded, the server connected with three tools, and the review reproduced the sample results (20.0%, 155-minute median, 40.0% scenario, queue DEP-004, DEP-005, DEP-003, DEP-002, DEP-001). The saved session is `claude-code-test-session.txt`. One session is a functional check, not an evaluation of the skill.

These tools support a human analyst. They are rule-based and the dashboard is not an AI feature.

## Understand the code

- `analysis_walkthrough.py`: the earlier learning script, preserved for reference with separate outputs. Running it writes its older-format results only into `walkthrough_outputs/`; it cannot overwrite the current analysis exports. It does not provide the current engine’s full validation, so use `analysis.py` or the dashboard for analysis.
- `engine.py`: shared validation and calculations, independent of the dashboard.
- `analysis.py`: command-line wrapper that uses the engine and saves the original analysis outputs only after validation.
- `server.py`: serves the page and calculates uploaded records without saving them.
- `deposit_tools.py`, `mcp_server.py`, `.mcp.json`: the read-only helpers and MCP server described above. `.claude/skills/deposit-review/`: the Claude Code skill.
- `index.html`: page structure; `style.css`: layout and colors; `app.js`: upload controls, rendering, filtering and export.

The command-line workflow still works: `python3 analysis.py`. Optional arguments are `--input`, `--observation`, and `--target`. This workflow writes output files; dashboard uploads do not.

## Checks

From this folder run `python3 -m unittest discover -s tests` and `node --test tests/test_review.js` (the latter requires Node.js for development checks only). The tests cover baseline calculations, denominator and deadline boundaries, invalid data, changed settings, and local upload request handling.
