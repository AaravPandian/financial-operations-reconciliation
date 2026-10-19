"""Lightweight local case-review workflow for demonstrations only."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REVIEW_COLUMNS = ["case_id", "review_status", "analyst_note", "reviewed_at"]
REVIEW_STATUSES = ["Open", "Investigating", "Resolved"]


def read_reviews(path: str | Path = "outputs/case_reviews.csv") -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        return pd.DataFrame(columns=REVIEW_COLUMNS)
    return pd.read_csv(path, dtype="string", keep_default_na=False).loc[:, REVIEW_COLUMNS]


def write_review(
    case_id: str, review_status: str, analyst_note: str,
    path: str | Path = "outputs/case_reviews.csv",
) -> None:
    if review_status not in REVIEW_STATUSES:
        raise ValueError("Unrecognized review status")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = read_reviews(path)
    df = df.loc[df["case_id"].ne(case_id)].reset_index(drop=True)
    df.loc[len(df)] = [case_id, review_status, analyst_note,
                        datetime.now(timezone.utc).isoformat(timespec="seconds")]
    df.to_csv(path, index=False)
