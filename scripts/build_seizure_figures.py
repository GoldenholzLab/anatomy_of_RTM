#!/usr/bin/env python3
"""Set journal figure typography from the reviewed, unchanged summary table.

The plotting logic is copied from the reviewed summary function. Only size,
font settings, output paths and one panel heading differ.
"""
from pathlib import Path
import sys,os
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rtm_anatomy.rtm123 import read_csv_dicts, make_tables, plot_value

def make_seizure_figure(input_dir: str | Path) -> dict[str, Path]:
    """Generate manuscript-ready RTM123 summary figures."""

    os.environ.setdefault("MPLCONFIGDIR", str(Path(input_dir) / ".matplotlib-cache"))
    import matplotlib.pyplot as plt

    directory = Path(input_dir)
    journal_dir = ROOT / "output/seizure_figures"
    journal_dir.mkdir(parents=True, exist_ok=True)
    table_path = directory / "condition_summary_with_deltas.csv"
    if not table_path.exists():
        make_tables(directory)
    rows = read_csv_dicts(table_path)
    short_labels = {"baseline_perfect": "Reference", "type1_transient_msf": "Transient rate",
                    "type2_threshold_8": "Threshold 8", "type3_sensitivity_90": "Sens. 90%",
                    "type3_sensitivity_80": "Sens. 80%", "type3_sensitivity_70": "Sens. 70%",
                    "type3_far_1_per_month": "FAR 1/month", "type3_far_1_per_week": "FAR 1/week",
                    "type3_far_1_per_day": "FAR 1/day"}
    labels = [short_labels.get(row["condition"], row["label"]) for row in rows]
    x = np.arange(len(rows), dtype=float)
    rtm_values = np.asarray([100.0 * plot_value(row["fraction_RTM"]) for row in rows], dtype=float)
    mpc_values = np.asarray([plot_value(row["MPC"]) for row in rows], dtype=float)
    eligible_values = np.asarray([100.0 * plot_value(row["fraction_eligible"]) for row in rows], dtype=float)

    colors = []
    for row in rows:
        rtm_type = row["rtm_type"]
        if rtm_type == "baseline":
            colors.append("#4B5563")
        elif rtm_type == "type1":
            colors.append("#2563EB")
        elif rtm_type == "type2":
            colors.append("#D97706")
        elif rtm_type == "type3_sensitivity":
            colors.append("#059669")
        else:
            colors.append("#7C3AED")

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({"font.size": 11, "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, grid = plt.subplots(nrows=2, ncols=2, figsize=(7.5, 5.5))
    axes = grid.ravel()
    axes[0].bar(x, eligible_values, color=colors, alpha=0.88)
    axes[0].set_ylabel("Eligible (%)")
    axes[0].set_title("A  Eligibility yield", loc="left")
    true_rtm = np.array([100*plot_value(row["fraction_true_RTM"]) for row in rows])
    axes[1].bar(x-0.18, rtm_values, width=0.36, color="#4B5563", label="Measured counts")
    axes[1].bar(x+0.18, true_rtm, width=0.36, color="#AAB5C4", label="True counts")
    axes[1].set_ylabel("Participants (%)")
    axes[1].set_title("B  Measured and true-count RTM", loc="left")
    axes[1].set_ylim(0,100)
    axes[1].legend(fontsize=9,loc="upper left")
    type3 = np.array([100*plot_value(row["fraction_type3"]) for row in rows])
    true_only = np.array([100*plot_value(row["true_only_count"])/plot_value(row["n_eligible"]) if plot_value(row["n_eligible"]) else np.nan for row in rows])
    axes[2].bar(x-0.18, type3, width=0.36, color="#7C3AED", label="Measured only (Type 3)")
    axes[2].bar(x+0.18, true_only, width=0.36, color="#AAB5C4", label="True only")
    axes[2].set_ylabel("Participants (%)")
    axes[2].set_title("C  Classification disagreements", loc="left")
    axes[2].set_ylim(0,55)
    axes[2].legend(fontsize=9,loc="upper left")
    axes[3].bar(x, mpc_values, color=colors, alpha=0.88)
    axes[3].axhline(0, color="#111827", linewidth=0.8)
    axes[3].set_ylabel("Median reduction (%)")
    axes[3].set_title("D  Apparent improvement", loc="left")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, axis="y", color="#D1D5DB", linewidth=0.8)
        ax.grid(False, axis="x")

    fig.suptitle("Common underlying population; enrollment re-evaluated by condition", y=0.995, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    png_path = journal_dir / "Figure_2.png"
    pdf_path = ROOT / "anatomy_of_RTM_Seizure_Figure_2.pdf"
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    return {"png": png_path, "pdf": pdf_path}

if __name__ == "__main__":
    print(make_seizure_figure(ROOT / "outputs/rtm123_type3_1m"))
