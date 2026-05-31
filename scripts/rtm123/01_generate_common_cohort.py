#!/usr/bin/env python3
"""Generate or resume the shared 36-month RTM123 CHOCOLATES cohort."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtm_anatomy.rtm123 import DEFAULT_MASTER_SEED, generate_common_cohort, parse_workers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--n-patients", type=int, default=1_000_000)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--days-per-month", type=int, default=30)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--workers", default="1")
    parser.add_argument("--master-seed", type=int, default=DEFAULT_MASTER_SEED)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    generate_common_cohort(
        output_dir=args.output_dir,
        n_patients=args.n_patients,
        months=args.months,
        days_per_month=args.days_per_month,
        chunk_size=args.chunk_size,
        workers=parse_workers(args.workers),
        master_seed=args.master_seed,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()

