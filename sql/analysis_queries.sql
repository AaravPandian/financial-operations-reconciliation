-- Run these queries in MySQL Workbench AFTER saving a run from the app or CLI.
-- 1. Latest run and coverage.
SELECT run_id, created_at, ledger_rows, bank_rows, matched_cases,
       exception_cases, match_rate_pct
FROM reconciliation_runs
ORDER BY run_id DESC LIMIT 10;

-- 2. Distribution of exceptions in the latest run.
SELECT status, priority, COUNT(*) AS cases
FROM reconciliation_cases
WHERE run_id = (SELECT MAX(run_id) FROM reconciliation_runs)
GROUP BY status, priority
ORDER BY cases DESC;

-- 3. Investigate amount mismatches (pence; same-currency comparisons only).
SELECT case_id, ledger_amount_pence, bank_amount_pence,
       amount_difference_pence, ledger_currency
FROM reconciliation_cases
WHERE run_id = (SELECT MAX(run_id) FROM reconciliation_runs)
  AND status = 'amount_mismatch'
ORDER BY ABS(amount_difference_pence) DESC LIMIT 20;

-- 4. Exception rate across stored runs.
SELECT run_id, created_at, exception_cases,
       ROUND(100.0 * exception_cases / NULLIF(case_count, 0), 2) AS exception_rate_pct
FROM reconciliation_runs
ORDER BY run_id DESC;

-- 5. Find raw duplicated bank transaction IDs in the most recent run.
SELECT transaction_id, COUNT(*) AS bank_entry_count
FROM bank_entries
WHERE run_id = (SELECT MAX(run_id) FROM reconciliation_runs)
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY bank_entry_count DESC;

-- 6. Outstanding value by currency. Never add currencies together.
SELECT ledger_currency AS currency, status,
       SUM(ABS(ledger_amount_pence)) AS gross_ledger_pence
FROM reconciliation_cases
WHERE run_id = (SELECT MAX(run_id) FROM reconciliation_runs)
  AND status <> 'matched'
  AND ledger_amount_pence IS NOT NULL
GROUP BY ledger_currency, status
ORDER BY currency, gross_ledger_pence DESC;
