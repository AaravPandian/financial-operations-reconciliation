"""Reconciliation control metrics. No FX conversion or mixed-currency sums."""

import pandas as pd


def control_metrics(cases: pd.DataFrame, ledger: pd.DataFrame) -> dict:
    unique_ledger = int(ledger["transaction_id"].nunique())
    matched = int(cases["status"].eq("matched").sum())
    exceptions = int(cases["status"].ne("matched").sum())
    matched_gbp = cases.loc[
        cases["status"].eq("matched") & cases["ledger_currency"].eq("GBP"),
        "ledger_amount_pence",
    ].abs().sum()
    return {
        "ledger_rows": int(len(ledger)),
        "unique_ledger_ids": unique_ledger,
        "case_count": int(len(cases)),
        "matched": matched,
        "exceptions": exceptions,
        "match_rate_pct": round(100 * matched / unique_ledger, 2) if unique_ledger else 0.0,
        "matched_gbp_absolute_pence": int(matched_gbp),
    }


def pence_to_gbp(pence: int | float) -> str:
    return f"£{pence / 100:,.2f}"
