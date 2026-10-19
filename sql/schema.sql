-- FinRecon MySQL 8.0 schema. Database itself is created by finrecon.database.
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_tolerance_days INT NOT NULL,
    ledger_rows INT NOT NULL,
    bank_rows INT NOT NULL,
    case_count INT NOT NULL,
    matched_cases INT NOT NULL,
    exception_cases INT NOT NULL,
    match_rate_pct DECIMAL(6,2) NOT NULL,
    PRIMARY KEY (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ledger_entries (
    row_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    run_id BIGINT UNSIGNED NOT NULL,
    transaction_id VARCHAR(64) NOT NULL,
    transaction_date DATE NOT NULL,
    amount_pence BIGINT NOT NULL,
    currency CHAR(3) NOT NULL,
    counterparty VARCHAR(255) NOT NULL,
    reference VARCHAR(255) NOT NULL,
    PRIMARY KEY (row_id),
    INDEX idx_ledger_run_transaction (run_id, transaction_id),
    CONSTRAINT fk_ledger_run FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bank_entries (
    run_id BIGINT UNSIGNED NOT NULL,
    bank_entry_id VARCHAR(64) NOT NULL,
    transaction_id VARCHAR(64) NOT NULL,
    posting_date DATE NOT NULL,
    amount_pence BIGINT NOT NULL,
    currency CHAR(3) NOT NULL,
    reference VARCHAR(255) NOT NULL,
    PRIMARY KEY (run_id, bank_entry_id),
    INDEX idx_bank_run_transaction (run_id, transaction_id),
    CONSTRAINT fk_bank_run FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reconciliation_cases (
    run_id BIGINT UNSIGNED NOT NULL,
    case_id VARCHAR(64) NOT NULL,
    status VARCHAR(40) NOT NULL,
    priority VARCHAR(12) NOT NULL,
    reason VARCHAR(255) NOT NULL,
    ledger_rows INT NOT NULL,
    bank_rows INT NOT NULL,
    ledger_amount_pence BIGINT NULL,
    bank_amount_pence BIGINT NULL,
    amount_difference_pence BIGINT NULL,
    ledger_currency CHAR(3) NULL,
    bank_currency CHAR(3) NULL,
    case_date DATE NULL,
    date_lag_days INT NULL,
    PRIMARY KEY (run_id, case_id),
    INDEX idx_cases_run_status (run_id, status),
    CONSTRAINT fk_cases_run FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
