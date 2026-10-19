import pandas as pd
import pytest

from finrecon.io import DataValidationError, load_csv_pair, validate_bank, validate_ledger
from finrecon.metrics import control_metrics
from finrecon.reconciliation import reconcile


def statuses(ledger, bank, **kwargs):
    return reconcile(ledger, bank, **kwargs).set_index("case_id")["status"].to_dict()


def test_exact_and_signed_refund_match(simple_pair):
    ledger, bank = simple_pair
    assert statuses(ledger, bank) == {"T001": "matched", "T002": "matched"}
    metrics = control_metrics(reconcile(ledger, bank), ledger)
    assert metrics["matched"] == 2
    assert metrics["exceptions"] == 0
    assert metrics["matched_gbp_absolute_pence"] == 3500


def test_missing_and_unexpected_bank(simple_pair):
    ledger, bank = simple_pair
    bank.loc[1, "transaction_id"] = "EXTERNAL"
    assert statuses(ledger, bank) == {
        "T001": "matched", "T002": "missing_bank", "EXTERNAL": "unexpected_bank"
    }


def test_amount_mismatch_one_penny(simple_pair):
    ledger, bank = simple_pair
    bank.loc[0, "amount_pence"] += 1
    cases = reconcile(ledger, bank).set_index("case_id")
    assert cases.loc["T001", "status"] == "amount_mismatch"
    assert cases.loc["T001", "amount_difference_pence"] == 1


def test_currency_mismatch_does_not_report_unconverted_delta(simple_pair):
    ledger, bank = simple_pair
    bank.loc[0, "currency"] = "EUR"
    cases = reconcile(ledger, bank).set_index("case_id")
    assert cases.loc["T001", "status"] == "currency_mismatch"
    assert pd.isna(cases.loc["T001", "amount_difference_pence"])


def test_date_tolerance_is_inclusive(simple_pair):
    ledger, bank = simple_pair
    bank.loc[0, "posting_date"] = "2026-01-03"  # 2 days after ledger
    assert statuses(ledger, bank)["T001"] == "matched"
    bank.loc[0, "posting_date"] = "2026-01-04"
    assert statuses(ledger, bank)["T001"] == "date_mismatch"
    assert statuses(ledger, bank, allowed_date_lag_days=3)["T001"] == "matched"


def test_duplicate_bank_prevents_false_match(simple_pair):
    ledger, bank = simple_pair
    extra = bank.iloc[[0]].copy()
    extra.loc[extra.index[0], "bank_entry_id"] = "B999"
    bank = pd.concat([bank, extra], ignore_index=True)
    cases = reconcile(ledger, bank).set_index("case_id")
    assert cases.loc["T001", "status"] == "duplicate_bank"
    assert cases.loc["T001", "bank_rows"] == 2
    assert pd.isna(cases.loc["T001", "bank_amount_pence"])


def test_duplicate_ledger_and_both(simple_pair):
    ledger, bank = simple_pair
    ledger = pd.concat([ledger, ledger.iloc[[0]]], ignore_index=True)
    assert statuses(ledger, bank)["T001"] == "duplicate_ledger"
    bank_extra = bank.iloc[[0]].copy()
    bank_extra.loc[bank_extra.index[0], "bank_entry_id"] = "B999"
    bank = pd.concat([bank, bank_extra], ignore_index=True)
    assert statuses(ledger, bank)["T001"] == "duplicate_both"


def test_duplicate_bank_entry_id_is_invalid(simple_pair):
    _, bank = simple_pair
    bank.loc[1, "bank_entry_id"] = "B001"
    with pytest.raises(DataValidationError, match="bank_entry_id"):
        validate_bank(bank)


def test_rejects_fractional_minor_units(simple_pair):
    ledger, _ = simple_pair
    ledger["amount_pence"] = ledger["amount_pence"].astype(float)
    ledger.loc[0, "amount_pence"] = 1000.5
    with pytest.raises(DataValidationError, match="integer"):
        validate_ledger(ledger)


def test_rejects_empty_ids(simple_pair):
    ledger, _ = simple_pair
    ledger.loc[1, "transaction_id"] = ""
    with pytest.raises(DataValidationError, match="transaction_id"):
        validate_ledger(ledger)


def test_does_not_accept_negative_tolerance(simple_pair):
    ledger, bank = simple_pair
    with pytest.raises(ValueError, match="allowed_date"):
        reconcile(ledger, bank, allowed_date_lag_days=-1)


def test_csv_roundtrip_preserves_leading_zeros(simple_pair, tmp_path):
    ledger, bank = simple_pair
    ledger.loc[0, "transaction_id"] = "000001"
    bank.loc[0, "transaction_id"] = "000001"
    lp, bp = tmp_path / "l.csv", tmp_path / "b.csv"
    ledger.to_csv(lp, index=False)
    bank.to_csv(bp, index=False)
    l, b = load_csv_pair(lp, bp)
    assert l.loc[0, "transaction_id"] == "000001"
    assert b.loc[0, "transaction_id"] == "000001"
