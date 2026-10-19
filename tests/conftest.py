import pandas as pd
import pytest


@pytest.fixture
def simple_pair():
    ledger = pd.DataFrame([
        {"transaction_id": "T001", "transaction_date": "2026-01-01", "amount_pence": 1000,
         "currency": "GBP", "counterparty": "Acme", "reference": "A1"},
        {"transaction_id": "T002", "transaction_date": "2026-01-02", "amount_pence": -2500,
         "currency": "GBP", "counterparty": "Acme", "reference": "A2"},
    ])
    bank = pd.DataFrame([
        {"bank_entry_id": "B001", "transaction_id": "T001", "posting_date": "2026-01-02",
         "amount_pence": 1000, "currency": "GBP", "reference": "A1"},
        {"bank_entry_id": "B002", "transaction_id": "T002", "posting_date": "2026-01-02",
         "amount_pence": -2500, "currency": "GBP", "reference": "A2"},
    ])
    return ledger, bank
