"""CLI: python -m finrecon.cli generate|reconcile."""

import argparse
from pathlib import Path

from finrecon.database import save_run
from finrecon.generator import generate_demo_data
from finrecon.io import load_csv_pair
from finrecon.metrics import control_metrics
from finrecon.reconciliation import reconcile


def main() -> None:
    parser = argparse.ArgumentParser(description="FinRecon financial reconciliation")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Regenerate synthetic CSV data")
    gen.add_argument("--count", type=int, default=5000)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--out-dir", type=Path, default=Path("data"))

    run = sub.add_parser("reconcile", help="Run reconciliation and export case CSV")
    run.add_argument("--ledger", type=Path, default=Path("data/ledger.csv"))
    run.add_argument("--bank", type=Path, default=Path("data/bank_statement.csv"))
    run.add_argument("--output", type=Path, default=Path("outputs/reconciliation_cases.csv"))
    run.add_argument("--date-tolerance", type=int, default=2)
    run.add_argument("--save-mysql", action="store_true", help="Store a run in MySQL")

    args = parser.parse_args()
    if args.command == "generate":
        ledger, bank = generate_demo_data(args.count, args.seed)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        ledger.to_csv(args.out_dir / "ledger.csv", index=False)
        bank.to_csv(args.out_dir / "bank_statement.csv", index=False)
        print(f"Generated {len(ledger):,} ledger and {len(bank):,} bank rows in {args.out_dir}/")
    else:
        ledger, bank = load_csv_pair(args.ledger, args.bank)
        cases = reconcile(ledger, bank, allowed_date_lag_days=args.date_tolerance)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        cases.to_csv(args.output, index=False, date_format="%Y-%m-%d")
        metrics = control_metrics(cases, ledger)
        print(f"Matched: {metrics['matched']:,} | Exceptions: {metrics['exceptions']:,} | "
              f"Match rate: {metrics['match_rate_pct']:.2f}%")
        print(f"Saved {args.output}")
        if args.save_mysql:
            run_id = save_run(ledger, bank, cases, args.date_tolerance)
            print(f"Saved MySQL run #{run_id}")


if __name__ == "__main__":
    main()
