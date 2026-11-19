#!/usr/bin/env python3
"""Run RTM type 1/2/3 conditions on a shared RTM123 cohort."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtm_anatomy.rtm123 import run_all_conditions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_all_conditions(
        cohort_dir=args.cohort_dir,
        output_dir=args.output_dir,
        chunk_size=args.chunk_size,
        resume=args.resume,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()

