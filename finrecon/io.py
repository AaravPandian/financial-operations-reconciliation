"""Strict input validation shared by the dashboard, CLI and tests."""

from pathlib import Path
from typing import IO

import pandas as pd

LEDGER_COLUMNS = [
    "transaction_id", "transaction_date", "amount_pence", "currency",
    "counterparty", "reference",
]
BANK_COLUMNS = [
    "bank_entry_id", "transaction_id", "posting_date", "amount_pence",
    "currency", "reference",
]


class DataValidationError(ValueError):
    """Raised when a CSV is structurally unsuitable for reconciliation."""


def _required_text(df: pd.DataFrame, column: str) -> None:
    df[column] = df[column].astype("string").str.strip()
    if df[column].isna().any() or df[column].eq("").any():
        raise DataValidationError(f"Column '{column}' contains a missing/blank value.")


def _normalize(df: pd.DataFrame, columns: list[str], date_col: str) -> pd.DataFrame:
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {', '.join(missing)}")
    df = df.loc[:, columns].copy()
    if df.empty:
        raise DataValidationError("The file contains no transactions.")

    for column in ("transaction_id", "currency"):
        _required_text(df, column)
    for column in ("bank_entry_id",) if "bank_entry_id" in df else ():
        _required_text(df, column)
    for column in ("reference", "counterparty"):
        if column in df:
            df[column] = df[column].fillna("").astype("string").str.strip()

    df["currency"] = df["currency"].str.upper()
    if not df["currency"].str.fullmatch(r"[A-Z]{3}").all():
        raise DataValidationError("Currencies must use three-letter codes (e.g. GBP).")

    try:
        numbers = pd.to_numeric(df["amount_pence"], errors="raise")
        if numbers.isna().any() or not (numbers % 1 == 0).all():
            raise ValueError("amount_pence must contain whole numbers")
        df["amount_pence"] = numbers.astype("int64")
    except (ValueError, TypeError, OverflowError) as exc:
        raise DataValidationError("'amount_pence' must contain integer minor units.") from exc

    try:
        df[date_col] = pd.to_datetime(df[date_col], format="%Y-%m-%d", errors="raise")
    except (ValueError, TypeError) as exc:
        raise DataValidationError(f"'{date_col}' must use YYYY-MM-DD dates.") from exc
    if df[date_col].isna().any():
        raise DataValidationError(f"'{date_col}' contains a missing date.")
    return df


def validate_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a ledger, preserving duplicate transaction IDs as potential cases."""
    return _normalize(df, LEDGER_COLUMNS, "transaction_date")


def validate_bank(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a bank statement; bank entry IDs must be unique."""
    result = _normalize(df, BANK_COLUMNS, "posting_date")
    if result["bank_entry_id"].duplicated().any():
        raise DataValidationError("bank_entry_id must uniquely identify each bank row.")
    return result


def load_csv_pair(
    ledger_path: str | Path | IO, bank_path: str | Path | IO
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read CSV paths or file-like objects, preserving text IDs including zeroes."""
    read_opts = {"dtype": "string", "keep_default_na": False}
    try:
        ledger = pd.read_csv(ledger_path, **read_opts)
        bank = pd.read_csv(bank_path, **read_opts)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise DataValidationError(f"Could not read CSV inputs: {exc}") from exc
    return validate_ledger(ledger), validate_bank(bank)
