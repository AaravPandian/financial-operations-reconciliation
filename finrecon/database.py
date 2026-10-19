"""Optional MySQL storage. CSV/Streamlit works without a MySQL server.

Runs are append-only snapshots; each run stores its own raw inputs and cases.
Credentials are loaded from .env and never hard-coded into the repository.
"""

import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from finrecon.io import validate_bank, validate_ledger
from finrecon.metrics import control_metrics

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def mysql_config() -> dict:
    load_dotenv()
    db_name = os.getenv("MYSQL_DATABASE", "finrecon")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", db_name):
        raise ValueError("MYSQL_DATABASE must be a safe SQL identifier.")
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": db_name,
    }


def _driver():
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt to enable MySQL support.") from exc
    return mysql.connector


def initialize_mysql():
    """Create the configured DB and schema, returning an open connection."""
    connector = _driver()
    config = mysql_config()
    db_name = config.pop("database")
    connection = connector.connect(**config)
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{db_name}`")
        for stmt in SCHEMA_PATH.read_text(encoding="utf-8").split(";"):
            # Remove SQL comment-only lines before executing a statement.
            cleaned = "\n".join(line for line in stmt.splitlines() if not line.lstrip().startswith("--")).strip()
            if cleaned:
                cursor.execute(cleaned)
        connection.commit()
        cursor.close()
        return connection
    except Exception:
        connection.close()
        raise


def _nullable(value):
    return None if pd.isna(value) else value


def save_run(
    ledger: pd.DataFrame, bank: pd.DataFrame, cases: pd.DataFrame,
    date_tolerance_days: int = 2,
) -> int:
    """Save an immutable run snapshot, rollback on any insert failure."""
    ledger = validate_ledger(ledger)
    bank = validate_bank(bank)
    metrics = control_metrics(cases, ledger)
    conn = initialize_mysql()
    try:
        conn.start_transaction()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO reconciliation_runs
            (date_tolerance_days, ledger_rows, bank_rows, case_count,
             matched_cases, exception_cases, match_rate_pct)
             VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (date_tolerance_days, len(ledger), len(bank), len(cases),
             metrics["matched"], metrics["exceptions"], metrics["match_rate_pct"]),
        )
        run_id = int(cursor.lastrowid)
        cursor.executemany(
            """INSERT INTO ledger_entries
            (run_id, transaction_id, transaction_date, amount_pence,
             currency, counterparty, reference)
             VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (run_id, str(row.transaction_id), row.transaction_date.date(),
                 int(row.amount_pence), str(row.currency), str(row.counterparty), str(row.reference))
                for row in ledger.itertuples(index=False)
            ],
        )
        cursor.executemany(
            """INSERT INTO bank_entries
            (run_id, bank_entry_id, transaction_id, posting_date, amount_pence,
             currency, reference)
             VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (run_id, str(row.bank_entry_id), str(row.transaction_id),
                 row.posting_date.date(), int(row.amount_pence),
                 str(row.currency), str(row.reference))
                for row in bank.itertuples(index=False)
            ],
        )
        cursor.executemany(
            """INSERT INTO reconciliation_cases
            (run_id, case_id, status, priority, reason, ledger_rows, bank_rows,
             ledger_amount_pence, bank_amount_pence, amount_difference_pence,
             ledger_currency, bank_currency, case_date, date_lag_days)
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    run_id, str(row.case_id), str(row.status), str(row.priority),
                    str(row.reason), int(row.ledger_rows), int(row.bank_rows),
                    int(row.ledger_amount_pence) if pd.notna(row.ledger_amount_pence) else None,
                    int(row.bank_amount_pence) if pd.notna(row.bank_amount_pence) else None,
                    int(row.amount_difference_pence) if pd.notna(row.amount_difference_pence) else None,
                    _nullable(row.ledger_currency), _nullable(row.bank_currency),
                    row.case_date.date() if pd.notna(row.case_date) else None,
                    int(row.date_lag_days) if pd.notna(row.date_lag_days) else None,
                ) for row in cases.itertuples(index=False)
            ],
        )
        conn.commit()
        cursor.close()
        return run_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def recent_runs(limit: int = 10) -> pd.DataFrame:
    """Read the most recent stored reconciliation run summaries."""
    limit = max(1, min(int(limit), 100))
    conn = initialize_mysql()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT run_id, created_at, ledger_rows, bank_rows, case_count,
               matched_cases, exception_cases, match_rate_pct
               FROM reconciliation_runs ORDER BY run_id DESC LIMIT %s""", (limit,)
        )
        rows = cursor.fetchall()
        cursor.close()
        return pd.DataFrame(rows)
    finally:
        conn.close()
