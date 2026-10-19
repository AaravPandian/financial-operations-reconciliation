# Technical & business walkthrough

## Business problem

Finance and treasury operations need to establish whether recorded expected payments agree with the movements appearing on a bank statement. Unexplained differences can indicate timing issues, incorrect instructions, data-quality problems, or potentially duplicate processing.

FinRecon is a **fictional reconciliation control prototype**. A bank statement and an internal ledger are matched by transaction ID. The matching status is separated from a human analyst's review status, avoiding the incorrect assumption that a review marked `Resolved` has automatically fixed the books.

## Architecture decisions

**Python and Pandas:** input validation, deterministic normalization, group-by counts and outer joins. Unique transaction IDs are collapsed to a single case, so duplicates are flagged rather than multiplied in a many-to-many join.

**Integer money representation:** values use minor units and signed `int64` amounts. Comparing `250000` to `250001` correctly detects a one-penny difference, and negative refunds retain their sign. For production systems supporting very large values or currencies with different minor-unit exponents, use precision-safe decimal storage and a currency scale table.

**Configurable dates:** the default tolerance is ±2 calendar days, using the difference between bank posting date and ledger transaction date. True bank settlements require business calendars and sometimes cut-offs or value dates, none of which are simulated here.

**Streamlit + Plotly:** immediate usability without frontend development; filters, analyst queue, export actions, plots, and a dedicated MySQL tab.

**MySQL:** four normalized tables store each run's metadata, source ledger rows, source bank rows, and results, with run IDs isolating repeated experiments. Foreign keys tie entries and cases to the corresponding run. Transactions avoid committing partial snapshots. The `reconciliation_cases` table has one row per case ID per run.

**Local review workflow:** analyst review status and note are saved to an intentionally simple local CSV. Review changes do **not** update the matching engine outcome. In a multi-user app, replace the CSV file with authenticated database storage and a full audit log.

## Analytical controls

1. **Completeness:** ledger-only and bank-only IDs.
2. **Accuracy:** precise signed amount, transaction currency, and date comparisons.
3. **Uniqueness:** more than one occurrence of a transaction ID on either side.
4. **Coverage:** unique-ledger-ID match rate.
5. **Investigation:** prioritized case queue, manual review status and notes.
6. **Auditability of runs:** optional immutable MySQL source snapshots. (The basic local case-review notes are not audit-proof.)

### Example reconciliation

| Internal ID | Ledger | Bank | Classification |
| --- | --- | --- | --- |
| A01 | GBP 1,000.00 | GBP 1,000.00 | `matched` |
| A02 | GBP 150.00 | GBP 149.00 | `amount_mismatch` |
| A03 | GBP 80.00 | No entry | `missing_bank` |
| A04 | GBP 300.00 | Twice in bank | `duplicate_bank` |
| B05 | No entry | GBP 72.00 | `unexpected_bank` |

These are explanatory examples, not extracted from the generated sample rows.

## Data generation methodology

`finrecon/generator.py` generates fixed-seed synthetic transactions across an approximately 90-day period, including negative-signed refunds and ten fictional counterparties. It assigns mutually exclusive error classes across the base ledger IDs. New bank-only IDs are added separately. Recreating `--count 5000 --seed 42` yields identical CSVs. Since anomaly types are deliberately injected, the resulting exception frequency is **not** an estimate of real payments-industry error rates.

## Why the matching rules are strict

Transaction IDs are treated as the authoritative cross-system key. If IDs are absent or wrong, realistic finance systems may need multi-field matching, controlled fuzzy matching, partial settlement logic, or manual review. This sample **intentionally rejects** records with blank IDs rather than silently guessing a match.

## Engineering and assurance

- Strict CSV column contracts and deterministic status classifications.
- Exception conditions checked *before* normal comparisons.
- Database credentials isolated via `.env` (not version controlled).
- GitHub Actions performs repeatable test runs.
- Database persistence is opt-in; no external bank connections or data transmission by default.
- MySQL integration needs a running MySQL server and database privileges; CI does not launch or exercise MySQL.

## Known limitations and production gaps

- Amounts compared in integer minor units; no FX conversion or mixing of currency totals.
- No multi-line or one-to-many settlement matching.
- No partial-payment or fee reconciliation.
- Duplicates are cases by transaction ID, not a specialized duplicate-entry forensic tool.
- No reconciliation sign-off or segregation of duties.
- Local note file unsuitable for concurrent multi-user deployments and ephemeral Streamlit hosting.
- No authentication or encryption-at-rest policy (educational local CSV files only).
- SQL snapshot records source and output state but does not provide a tamper-proof event trail.

## Possible interview questions

**Why use an outer join?** It retains both ledger-only and bank-only IDs to detect completeness gaps.

**How do you prevent duplicate records from creating false matches?** First aggregate to counts by ID, quarantine IDs with repeated rows, then compare only unique pairs.

**How are monetary values safely compared?** In signed integer minor units, with currency compared first.

**Why isn't exception rate always equal to 100% minus match rate?** The match-rate denominator is unique ledger IDs, while the exception count includes bank-only IDs and duplicate cases.

**Why is MySQL optional?** The demo is instantly runnable and self-contained using CSVs, while MySQL demonstrates production-oriented relational storage and SQL query skills.

**What would you improve for a real bank?** Secure input pipelines, persistent role-based workflow, business-day date rules, source reconciliation control totals, traceable approvals, and contract-specific matching logic.
