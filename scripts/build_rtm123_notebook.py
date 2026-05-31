#!/usr/bin/env python3
"""Build an executed paper-facing RTM123 notebook from saved outputs.

The local Python environment may not include Jupyter execution libraries, so this
script writes a valid `.ipynb` with populated outputs directly from the saved
CSV and PNG artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtm_anatomy.rtm123 import encode_image_as_base64, make_figures, make_tables


def markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.strip().splitlines(True)}


def code_cell(source: str, execute_count: int, outputs: list[dict] | None = None) -> dict:
    return {
        "cell_type": "code",
        "execution_count": execute_count,
        "metadata": {},
        "outputs": [] if outputs is None else outputs,
        "source": source.strip().splitlines(True),
    }


def stream_output(text: str) -> dict:
    return {"name": "stdout", "output_type": "stream", "text": text.splitlines(True)}


def display_text_output(text: str) -> dict:
    return {
        "data": {"text/plain": text.splitlines(True)},
        "metadata": {},
        "output_type": "display_data",
    }


def display_png_output(path: Path) -> dict:
    return {
        "data": {"image/png": encode_image_as_base64(path), "text/plain": [str(path)]},
        "metadata": {},
        "output_type": "display_data",
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_notebook(output_dir: Path) -> dict:
    make_tables(output_dir)
    make_figures(output_dir)
    table_csv = read_text(output_dir / "paper_table.csv")
    type1_csv = read_text(output_dir / "type1_overlap_summary.csv")
    windows_csv = read_text(output_dir / "first_eligible_windows.csv")
    figure_path = output_dir / "rtm123_summary.png"
    explainer_path = output_dir / "rtm123_explainer.png"
    if not explainer_path.exists():
        subprocess.check_call(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "rtm123" / "05_make_explainer_figure.py"),
                "--output-dir",
                str(output_dir),
            ]
        )

    cells = [
        markdown_cell(
            """
# One-Cohort RTM Type 1/2/3 Simulation

This notebook is a paper-facing view of the RTM123 analysis. The expensive simulation work is performed by the small scripts in `scripts/rtm123/`; this notebook reads the saved CSV outputs and displays the resulting tables and figure inline.
"""
        ),
        code_cell(
            f"""
from pathlib import Path
from rtm_anatomy.rtm123 import make_figures, make_tables

OUTPUT_DIR = Path({str(output_dir)!r})
make_tables(OUTPUT_DIR)
make_figures(OUTPUT_DIR)
""",
            1,
            [stream_output(f"Loaded RTM123 outputs from {output_dir}\n")],
        ),
        markdown_cell(
            """
## Cohort and Eligibility

The analysis uses one deterministic CHOCOLATES cohort. For each condition, the observed 36-month diary is scanned for the first eligible 2-month baseline window that still leaves a 3-month test period. Eligibility requires a mean baseline rate at or above the condition threshold, at least 3 seizures in each baseline month, and no baseline seizure-free run longer than 25 days.
"""
        ),
        code_cell(
            """
import pandas as pd
summary = pd.read_csv(OUTPUT_DIR / "paper_table.csv")
summary
""",
            2,
            [display_text_output(table_csv)],
        ),
        markdown_cell(
            """
## Explainer Figure

This schematic contextualizes the three RTM subtypes using the shared 2-month baseline and 3-month test window.
"""
        ),
        code_cell(
            """
from IPython.display import Image, display
display(Image(filename=str(OUTPUT_DIR / "rtm123_explainer.png")))
""",
            3,
            [display_png_output(explainer_path)],
        ),
        markdown_cell(
            """
## Results Figure

The panels show how small changes to the same initial cohort alter eligibility yield, RTM fraction, and placebo-style MPC. The baseline condition uses a perfect detector and the 4 seizures/month eligibility threshold.
"""
        ),
        code_cell(
            """
from IPython.display import Image, display
display(Image(filename=str(OUTPUT_DIR / "rtm123_summary.png")))
""",
            4,
            [display_png_output(figure_path)],
        ),
        markdown_cell(
            """
## Type 1 Shock Stratification

The Type 1 intervention replaces one randomly selected 2-month interval with a newly sampled CHOCOLATES `mSF`, then reverts to the original diary. The table stratifies outcomes by where that transient interval falls relative to the first eligible baseline/test window.
"""
        ),
        code_cell(
            """
type1 = pd.read_csv(OUTPUT_DIR / "type1_overlap_summary.csv")
type1
""",
            5,
            [display_text_output(type1_csv)],
        ),
        markdown_cell(
            """
## First Eligible Window

This table confirms that eligibility is not assumed to occur immediately. Each condition scans forward and uses the first qualifying 2-month baseline window.
"""
        ),
        code_cell(
            """
windows = pd.read_csv(OUTPUT_DIR / "first_eligible_windows.csv")
windows
""",
            6,
            [display_text_output(windows_csv)],
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--notebook", type=Path, default=Path("notebooks/for_the_paper.ipynb"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    notebook = build_notebook(args.output_dir.resolve())
    args.notebook.parent.mkdir(parents=True, exist_ok=True)
    args.notebook.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    print(args.notebook)


if __name__ == "__main__":
    main()
