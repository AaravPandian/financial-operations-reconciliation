"""Reproducible synthetic data with seeded reconciliation breaks."""

from datetime import date, timedelta
from random import Random

import pandas as pd

COUNTERPARTIES = [
    "Northstar Retail Ltd", "Meridian Services", "Harbour Logistics",
    "Oakfield Energy", "Summit Digital", "Bluefin Foods", "Atlas Systems",
    "Maple & Co", "Pioneer Supply", "Cedar Hospitality",
]
RATES = {
    "missing_bank": 0.020,
    "amount_mismatch": 0.012,
    "currency_mismatch": 0.006,
    "date_mismatch": 0.008,
    "duplicate_bank": 0.006,
    "duplicate_ledger": 0.004,
}


def generate_demo_data(
    count: int = 5000, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate financial records. All names, IDs and amounts are fictional.

    count is the count of base ledger transactions before injected duplicates.
    Each exception type is mutually exclusive; an extra set of unexpected
    bank transactions is generated independently.
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 100:
        raise ValueError("count must be an integer of at least 100")
    rng = Random(seed)
    shuffled = list(range(count))
    rng.shuffle(shuffled)
    injection: dict[int, str] = {}
    pos = 0
    for kind, rate in RATES.items():
        take = max(1, round(count * rate))
        for idx in shuffled[pos:pos + take]:
            injection[idx] = kind
        pos += take

    ledger: list[dict] = []
    bank: list[dict] = []
    next_bank_id = 1
    start = date(2026, 1, 1)

    def new_bank_row(txn: str, posting: date, amount: int, currency: str, reference: str) -> dict:
        nonlocal next_bank_id
        row = {
            "bank_entry_id": f"BNK-{next_bank_id:07d}",
            "transaction_id": txn,
            "posting_date": posting.isoformat(),
            "amount_pence": amount,
            "currency": currency,
            "reference": reference,
        }
        next_bank_id += 1
        return row

    for idx in range(count):
        txn = f"TXN-{idx + 1:07d}"
        tx_date = start + timedelta(days=rng.randrange(90))
        amount = rng.randint(500, 500_000)
        if rng.random() < 0.08:
            amount = -amount  # refunds remain signed on both sides
        reference = f"INV-{rng.randint(10_000, 99_999)}"
        row = {
            "transaction_id": txn,
            "transaction_date": tx_date.isoformat(),
            "amount_pence": amount,
            "currency": "GBP",
            "counterparty": rng.choice(COUNTERPARTIES),
            "reference": reference,
        }
        ledger.append(row)
        kind = injection.get(idx)
        if kind == "duplicate_ledger":
            ledger.append({**row, "reference": reference + "-DUP"})
        if kind == "missing_bank":
            continue
        posting = tx_date + timedelta(days=rng.choice([0, 0, 1, 1, 2]))
        bank_amount = amount
        bank_currency = "GBP"
        if kind == "amount_mismatch":
            bank_amount += rng.choice([-1, 1]) * rng.randint(100, 5000)
        elif kind == "currency_mismatch":
            bank_currency = "EUR"
        elif kind == "date_mismatch":
            posting = tx_date + timedelta(days=rng.randint(4, 9))
        bank.append(new_bank_row(txn, posting, bank_amount, bank_currency, reference))
        if kind == "duplicate_bank":
            bank.append(new_bank_row(txn, posting, bank_amount, bank_currency, reference))

    for idx in range(max(1, round(count * 0.012))):
        txn = f"EXT-{idx + 1:07d}"
        bank.append(new_bank_row(
            txn,
            start + timedelta(days=rng.randrange(90)),
            rng.randint(500, 120_000),
            "GBP",
            f"UNREC-{idx + 1:06d}",
        ))
    return pd.DataFrame(ledger), pd.DataFrame(bank)
