import pandas as pd

from finrecon.generator import RATES, generate_demo_data
from finrecon.reconciliation import reconcile
from finrecon.reviews import read_reviews, write_review


def test_generated_data_deterministic_and_diverse():
    ledger, bank = generate_demo_data(200, 42)
    ledger2, bank2 = generate_demo_data(200, 42)
    pd.testing.assert_frame_equal(ledger, ledger2)
    pd.testing.assert_frame_equal(bank, bank2)
    assert len(ledger) > 200
    assert len(bank) > 0
    result = reconcile(ledger, bank)
    required = set(RATES) | {"unexpected_bank", "matched"}
    assert required.issubset(set(result["status"]))
    assert len(result) == result["case_id"].nunique()


def test_generated_count_validation():
    try:
        generate_demo_data(5, 42)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected invalid count to raise")


def test_review_save_and_update(tmp_path):
    path = tmp_path / "reviews.csv"
    write_review("T001", "Investigating", "Contact bank", path)
    write_review("T002", "Open", "", path)
    write_review("T001", "Resolved", "Corrected", path)
    reviews = read_reviews(path)
    assert len(reviews) == 2
    assert reviews.set_index("case_id").loc["T001", "review_status"] == "Resolved"
