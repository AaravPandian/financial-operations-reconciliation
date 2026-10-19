"""Deterministic one-to-one reconciliation keyed by transaction_id.

Duplicate transaction IDs are quarantined BEFORE monetary comparisons, so a
many-to-many join cannot falsely mark repeated payments as reconciled.
"""

import pandas as pd

from finrecon.io import validate_bank, validate_ledger

STATUSES = [
    "matched", "amount_mismatch", "currency_mismatch", "date_mismatch",
    "missing_bank", "unexpected_bank", "duplicate_ledger", "duplicate_bank",
    "duplicate_both",
]
PRIORITY = {
    "matched": "None",
    "amount_mismatch": "High",
    "currency_mismatch": "High",
    "date_mismatch": "Medium",
    "missing_bank": "High",
    "unexpected_bank": "Medium",
    "duplicate_ledger": "High",
    "duplicate_bank": "High",
    "duplicate_both": "High",
}


def reconcile(
    ledger: pd.DataFrame, bank: pd.DataFrame, *, allowed_date_lag_days: int = 2
) -> pd.DataFrame:
    """Return one reconciliation case per distinct transaction ID.

    Rules (in order): duplicate IDs -> missing side -> currency -> amount ->
    date -> match. Signed amounts are compared as exact integer minor units.
    Dates use calendar days. No fuzzy reference matching or partial payments.
    """
    if isinstance(allowed_date_lag_days, bool) or not isinstance(allowed_date_lag_days, int) or allowed_date_lag_days < 0:
        raise ValueError("allowed_date_lag_days must be a nonnegative integer")

    ledger = validate_ledger(ledger)
    bank = validate_bank(bank)
    l = ledger.groupby("transaction_id", as_index=False, sort=True).agg(
        ledger_rows=("transaction_id", "size"),
        ledger_date=("transaction_date", "first"),
        ledger_amount_pence=("amount_pence", "first"),
        ledger_currency=("currency", "first"),
        counterparty=("counterparty", "first"),
        ledger_reference=("reference", "first"),
    )
    b = bank.groupby("transaction_id", as_index=False, sort=True).agg(
        bank_rows=("transaction_id", "size"),
        bank_date=("posting_date", "first"),
        bank_amount_pence=("amount_pence", "first"),
        bank_currency=("currency", "first"),
        bank_reference=("reference", "first"),
        bank_entry_id=("bank_entry_id", "first"),
    )
    merged = l.merge(b, on="transaction_id", how="outer", validate="one_to_one")
    merged["ledger_rows"] = merged["ledger_rows"].fillna(0).astype(int)
    merged["bank_rows"] = merged["bank_rows"].fillna(0).astype(int)

    # Values from duplicate ID groups are deliberately nulled: a 'first' amount
    # must not be presented as the authoritative amount for that group.
    merged.loc[merged["ledger_rows"].ne(1), "ledger_amount_pence"] = pd.NA
    merged.loc[merged["bank_rows"].ne(1), "bank_amount_pence"] = pd.NA
    merged["ledger_amount_pence"] = merged["ledger_amount_pence"].astype("Int64")
    merged["bank_amount_pence"] = merged["bank_amount_pence"].astype("Int64")

    statuses: list[str] = []
    reasons: list[str] = []
    amount_deltas: list[int | None] = []
    date_deltas: list[int | None] = []

    for row in merged.itertuples(index=False):
        if row.ledger_rows > 1 and row.bank_rows > 1:
            status, reason = "duplicate_both", "Repeated transaction ID on both sides"
        elif row.ledger_rows > 1:
            status, reason = "duplicate_ledger", "Repeated transaction ID in ledger"
        elif row.bank_rows > 1:
            status, reason = "duplicate_bank", "Repeated transaction ID in bank statement"
        elif row.ledger_rows == 0:
            status, reason = "unexpected_bank", "Bank transaction absent from ledger"
        elif row.bank_rows == 0:
            status, reason = "missing_bank", "Ledger transaction absent from bank statement"
        elif row.ledger_currency != row.bank_currency:
            status, reason = "currency_mismatch", "Currencies do not agree"
        elif row.ledger_amount_pence != row.bank_amount_pence:
            status, reason = "amount_mismatch", "Signed amounts do not agree"
        elif abs((row.bank_date - row.ledger_date).days) > allowed_date_lag_days:
            status, reason = "date_mismatch", f"Outside ±{allowed_date_lag_days} calendar-day window"
        else:
            status, reason = "matched", "ID, currency, amount and date checks passed"

        if row.ledger_rows == 1 and row.bank_rows == 1:
            date_delta = (row.bank_date - row.ledger_date).days
            amount_delta = (
                int(row.bank_amount_pence - row.ledger_amount_pence)
                if row.ledger_currency == row.bank_currency else None
            )
        else:
            date_delta, amount_delta = None, None
        statuses.append(status)
        reasons.append(reason)
        amount_deltas.append(amount_delta)
        date_deltas.append(date_delta)

    merged["status"] = statuses
    merged["priority"] = merged["status"].map(PRIORITY)
    merged["reason"] = reasons
    merged["amount_difference_pence"] = pd.array(amount_deltas, dtype="Int64")
    merged["date_lag_days"] = pd.array(date_deltas, dtype="Int64")
    merged.insert(0, "case_id", merged["transaction_id"].astype(str))
    merged["case_date"] = merged["ledger_date"].fillna(merged["bank_date"])
    return merged.sort_values("case_id").reset_index(drop=True)
