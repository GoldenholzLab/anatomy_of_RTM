#!/usr/bin/env python3
"""Make a clear RTM type 1/2/3 explainer figure."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def draw_mini_bars(
    ax,
    x0: float,
    width: float,
    y0: float,
    height: float,
    color: str,
    values: list[float],
    marker: str,
    show_threshold: bool = False,
    show_measurement_error: bool = False,
) -> None:
    """Draw simple monthly bars with baseline higher than test."""

    import matplotlib.patches as patches

    labels = ["B1", "B2", "T1", "T2", "T3"]
    ref_y = y0 + height * 0.50
    ax.plot([x0, x0 + width], [ref_y, ref_y], color="#64748B", lw=0.8, ls=(0, (2, 2)))
    ax.text(x0 + width + 0.008, ref_y, "ref", ha="left", va="center", fontsize=7.2, color="#64748B")

    group_w = width / 5.0
    if marker == "type1":
        temp_y = y0 + height * 0.84
        left = x0 + group_w * 0.12
        right = x0 + group_w * 1.88
        ax.plot([left, right], [temp_y, temp_y], color="#B91C1C", lw=1.1, ls=(0, (2, 2)))
        ax.text(
            (left + right) / 2,
            temp_y + 0.023,
            "temp ref",
            ha="center",
            va="bottom",
            fontsize=7.0,
            color="#991B1B",
            fontweight="bold",
        )

    if show_threshold:
        threshold_y = y0 + height * 0.74
        ax.plot([x0, x0 + width], [threshold_y, threshold_y], color="#D97706", lw=0.9, ls=(0, (2, 2)))
        ax.text(
            x0 + width / 2,
            threshold_y + 0.025,
            "elig cutoff",
            ha="center",
            va="bottom",
            fontsize=7.2,
            color="#92400E",
            fontweight="bold",
        )

    if show_measurement_error:
        true_values = [0.51, 0.50, 0.49, 0.51, 0.50]
        true_color = "#94A3B8"
        measured_color = color
        bar_w = group_w * 0.26
        for idx, (true_value, measured_value) in enumerate(zip(true_values, values)):
            center = x0 + group_w * (idx + 0.5)
            true_x = center - bar_w - group_w * 0.035
            measured_x = center + group_w * 0.035
            ax.add_patch(
                patches.Rectangle(
                    (true_x, y0),
                    bar_w,
                    true_value * height,
                    linewidth=0,
                    facecolor=true_color,
                    alpha=0.95,
                )
            )
            ax.add_patch(
                patches.Rectangle(
                    (measured_x, y0),
                    bar_w,
                    measured_value * height,
                    linewidth=0,
                    facecolor=measured_color,
                    alpha=0.92,
                )
            )
    else:
        bar_w = group_w * 0.42
        for idx, value in enumerate(values):
            bx = x0 + group_w * (idx + 0.5) - bar_w / 2
            rect = patches.Rectangle(
                (bx, y0),
                bar_w,
                value * height,
                linewidth=0,
                facecolor=color,
                alpha=0.92,
            )
            ax.add_patch(rect)

    ax.plot([x0, x0 + width], [y0, y0], color="#CBD5E1", lw=0.9)
    for idx, label in enumerate(labels):
        center = x0 + group_w * (idx + 0.5)
        ax.text(center, y0 - 0.034, label, ha="center", va="center", fontsize=6.2, color="#334155", fontweight="bold")


def draw_column(
    ax,
    x0: float,
    width: float,
    title: str,
    slogan: str,
    mechanism: str,
    color: str,
    bars: list[float],
    marker: str,
) -> None:
    """Draw one RTM subtype column."""

    ax.text(x0 + width / 2, 0.825, title, ha="center", va="center", fontsize=15.5, fontweight="bold", color="#111827")
    ax.text(
        x0 + width / 2,
        0.755,
        slogan,
        ha="center",
        va="center",
        fontsize=8.0,
        color=color,
        fontweight="bold",
        linespacing=1.02,
    )

    ax.text(
        x0 + width / 2,
        0.61,
        mechanism,
        ha="center",
        va="center",
        fontsize=8.0,
        color="#334155",
        bbox={
            "boxstyle": "round,pad=0.25,rounding_size=0.03",
            "facecolor": "#F8FAFC",
            "edgecolor": "#CBD5E1",
            "linewidth": 0.7,
        },
    )

    draw_mini_bars(
        ax,
        x0 + width * 0.04,
        width * 0.84,
        0.335,
        0.19,
        color,
        bars,
        marker,
        show_threshold=marker == "type2",
        show_measurement_error=marker == "type3",
    )

    if marker == "type3":
        import matplotlib.patches as patches

        legend_y = 0.56
        square = 0.012
        first_x = x0 + width * 0.16
        second_y = legend_y - 0.027
        ax.add_patch(patches.Rectangle((first_x, legend_y - square / 2), square, square, linewidth=0, facecolor="#94A3B8"))
        ax.text(first_x + square + 0.006, legend_y, "true rate", ha="left", va="center", fontsize=6.5, color="#334155")
        ax.add_patch(patches.Rectangle((first_x, second_y - square / 2), square, square, linewidth=0, facecolor=color))
        ax.text(first_x + square + 0.006, second_y, "measured rate", ha="left", va="center", fontsize=6.5, color="#334155")


def make_explainer_figure(output_dir: Path, dpi: int = 300) -> dict[str, Path]:
    """Create PNG and PDF versions of the RTM subtype explainer."""

    os.environ.setdefault("MPLCONFIGDIR", str(output_dir / ".matplotlib-cache"))
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(5, 5), dpi=dpi)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.94, "RTM subtype context", ha="center", va="center", fontsize=13.2, fontweight="bold", color="#111827")
    ax.text(
        0.5,
        0.895,
        "same cohort | first eligible window | 2B + 3T",
        ha="center",
        va="center",
        fontsize=7.6,
        color="#475569",
    )

    starts = [0.055, 0.37, 0.685]
    width = 0.25
    for split_x in [0.34, 0.655]:
        ax.plot([split_x, split_x], [0.19, 0.675], color="#E2E8F0", lw=0.9)

    draw_column(
        ax,
        starts[0],
        width,
        "RTM 1",
        "temporarily\nmuch more sick\nthan usual",
        "true rate change",
        "#2563EB",
        [0.86, 0.80, 0.42, 0.47, 0.44],
        "type1",
    )
    draw_column(
        ax,
        starts[1],
        width,
        "RTM 2",
        "natural\nvariability",
        "high-B selection",
        "#D97706",
        [0.83, 0.77, 0.50, 0.45, 0.48],
        "type2",
    )
    draw_column(
        ax,
        starts[2],
        width,
        "RTM 3",
        "measurement\nerror",
        "observed counts",
        "#7C3AED",
        [0.77, 0.72, 0.48, 0.39, 0.43],
        "type3",
    )

    ax.text(
        0.5,
        0.125,
        "RTM pattern: B high, T closer to ref",
        ha="center",
        va="center",
        fontsize=8.3,
        color="#111827",
        bbox={
            "boxstyle": "round,pad=0.35,rounding_size=0.035",
            "facecolor": "#FFFFFF",
            "edgecolor": "#CBD5E1",
            "linewidth": 0.8,
        },
    )
    ax.text(
        0.5,
        0.075,
        "RTM rule: B > ref; B-ref > |T-ref|",
        ha="center",
        va="center",
        fontsize=7.4,
        color="#475569",
    )

    png_path = output_dir / "rtm123_explainer.png"
    pdf_path = output_dir / "rtm123_explainer.pdf"
    fig.savefig(png_path, dpi=dpi)
    fig.savefig(pdf_path)
    plt.close(fig)
    return {"png": png_path, "pdf": pdf_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rtm123_1m"))
    parser.add_argument("--dpi", type=int, default=300)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    outputs = make_explainer_figure(args.output_dir, dpi=args.dpi)
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
