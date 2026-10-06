# OpsPulse

A small weekly operations reporting tool for messy task tracker exports. Manual weekly reporting is slow and error-prone; OpsPulse makes cleanup visible, calculates repeatable KPIs, and produces a one-page PDF. **All included records are synthetic. There are no real people, clients, or company data.**

## What it does

- Reads CSV or Excel task exports and reports what it normalized, removed, and flagged.
- Calculates period and weekly delivery metrics, with owner workload and deadline views.
- Creates deterministic plain-English observations from measured values (no external API or LLM).
- Exports a cleaned CSV and one-page A4 PDF.

## Demo

- [Live OpsPulse app](https://opspulse-o146.onrender.com)
- Sample input: `data/sample_tasks.csv`

The free Render instance may take 50 seconds or more to wake after inactivity.

## How to run

From this directory, Python 3.12 is recommended.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app opens at `http://127.0.0.1:5000` with sample data. Use the sidebar to upload `.csv`, `.xlsx`, or `.xls` files and adjust the report date and filters. Expected columns: `Task ID`, `Created Date`, `Due Date`, `Completed Date`, `Owner`, `Team`, `Priority`, `Status`, `Client/Project`, `Estimated Hours`, `Actual Hours`, and `Rework`.

## Deploy on Render

Create a web service from the GitHub repository with these settings:

- Root directory: `opspulse`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app`
- Environment variables: `PYTHON_VERSION=3.12` and `SECRET_KEY` set to a long, randomly generated value

On the free tier, the first load after inactivity can take about 50 seconds while the service wakes.

Regenerate sample data with `python data/generate_sample.py`; run tests with `pytest`; measure the full pipeline with `python benchmark.py`.

## KPI definitions

| KPI | Exact formula | Edge cases |
|---|---|---|
| On-time completion rate | Completed tasks with a known due date completed on/before due ÷ completed tasks with both dates | Missing due/completion dates excluded; empty denominator is N/A. |
| Average cycle time | Mean `(Completed Date - Created Date)` in days for completed tasks | Missing dates and negative intervals excluded; empty set is N/A. |
| Throughput | Count of Done tasks grouped by completion week (Monday-start week) | Tasks without completion date are not assigned a week. |
| Overdue backlog | At report-as-of date: tasks created by then, due before then, and either not completed or completed after then | Default report-as-of is the latest Completed Date among Done tasks. Missing created/due dates cannot qualify. Average age is mean `as-of - Due Date`; empty backlog age is N/A, overall and per week. |
| Rework rate | Done tasks marked Rework ÷ Done tasks | Missing/false-like rework treated as No; empty denominator is N/A. |
| Estimate accuracy | Sum actual hours ÷ sum estimated hours for rows with positive estimate and nonnegative actual | Invalid/nonpositive estimates and missing/negative actuals excluded; empty denominator is N/A. Ratio 1.0 matches estimates. |
| Workload by owner | Open task count and sum of nonnegative estimated hours by owner | Missing owner becomes Unassigned. Load ratio is owner's open count ÷ mean open count across owners; above 1.5 is highlighted. |
| Deadline performance by priority | On-time completed tasks ÷ completed tasks with both dates, grouped by priority | Missing dates excluded; empty groups omitted. |
| Week-over-week change | Current complete calendar week KPI minus the immediately previous complete calendar week KPI | A week is complete when its Sunday is on/before report-as-of. Weeks with fewer than 20 completed tasks are labeled low sample; comparisons involving either such week are N/A. Rates are shown as percentage points (pts); counts and averages use native units. Weekly backlog uses tasks created by week end and due before week end that are incomplete at that time. |

Period throughput is exactly the sum of weekly throughput. Done tasks without completion dates are flagged and excluded from throughput. The PDF reports the selected as-of date. Undefined ratios display as N/A. The dashboard labels every week with fewer than 20 completed tasks as low sample; WoW comparisons use the latest two adjacent complete weeks only when neither is low sample.

## Measured benchmark

Measured with `python benchmark.py` after dependencies were installed in the project virtual environment. The benchmark times CSV loading through PDF generation; these are observations from this run, not a performance guarantee.

| Input | Cleaned rows | PDF size | Runtime |
|---|---:|---:|---:|
| Generated sample | 1,202 | 24,796 bytes | 1.685 seconds |
| Generated 10× sample | 12,021 | 26,606 bytes | 6.223 seconds |

## Data cleaning rules

- Dates accept ISO, day/month/year, month/day/year, and abbreviated/full month names. Invalid nonblank dates are flagged; blank optional dates remain blank.
- Status variants map to Done, In Progress, Blocked, or Not Started. Unknown statuses map to Not Started.
- Owner whitespace and capitalization are normalized; blanks become Unassigned. Priority is title-cased; blank priority becomes Medium.
- Exact duplicate rows are removed (first copy retained) and counted. Near duplicates stay.
- Negative and missing hours, extreme hours, due before created, unparseable dates, completed-date/status mismatches, and Done tasks missing a completion date receive row-level flags. A Done task missing its completion date also receives its own specifically named flag. Zero hour values are retained without a flag. All flagged nonduplicate records remain.
- Extreme hours means above the greater of 100 hours or the median plus three scaled median absolute deviations of nonnegative hour values. Issue counts can overlap.
- Data quality score is the share of cleaned rows with no flagged issue. The change log shows transformations and retention behavior.

## Design decisions

Rule-based summaries are free, repeatable, private, and traceable to displayed numbers. Suspicious values are flagged instead of deleted so a reviewer can distinguish real work from export errors. Only exact duplicates are removed, and that count is visible.

## Limitations

All included records are synthetic; they demonstrate patterns, not real operational performance. Uploads need the exact column names above. Ambiguous dates such as `04/03/2026` are read as day/month/year. There are no live tracker integrations, accounts, or database. The portfolio demo is hosted as a free Render service. Weekly backlog is reconstructed from available dates, not a historical snapshot captured at that week.

## Future improvements

- Add a mapping screen for alternate tracker column names.
- Add locale controls for ambiguous dates.
- Save weekly snapshots for historically accurate backlog.
- Add configurable thresholds and team targets.
