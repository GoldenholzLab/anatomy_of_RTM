#!/usr/bin/env python3
"""Build the JCE graphical abstract as deterministic vector artwork."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image


NAVY = "#17324D"
TEXT = "#1F2937"
MUTED = "#64748B"
LINE = "#CBD5E1"
PAPER = "#F8FAFC"
WHITE = "#FFFFFF"

BLUE = "#2563EB"
BLUE_BG = "#EFF6FF"
AMBER = "#D97706"
AMBER_BG = "#FFF7ED"
VIOLET = "#7C3AED"
VIOLET_BG = "#F5F3FF"


def rounded_box(ax, x, y, w, h, *, face, edge=LINE, lw=0.8, radius=0.018, z=1):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.006,rounding_size={radius}",
        transform=ax.transAxes,
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def text(ax, x, y, value, *, size, color=TEXT, weight="normal", ha="left", va="center", z=5, linespacing=1.05):
    return ax.text(
        x,
        y,
        value,
        transform=ax.transAxes,
        fontsize=size,
        color=color,
        fontweight=weight,
        ha=ha,
        va=va,
        zorder=z,
        linespacing=linespacing,
        fontfamily="Arial",
    )


def line(ax, xs, ys, *, color, lw=1.2, ls="-", z=4, alpha=1.0):
    ax.plot(xs, ys, transform=ax.transAxes, color=color, lw=lw, ls=ls, zorder=z, alpha=alpha, solid_capstyle="round")


def type_badge(ax, x, y, number, color):
    rounded_box(ax, x, y - 0.020, 0.062, 0.040, face=color, edge=color, lw=0, radius=0.010, z=6)
    text(ax, x + 0.031, y, f"Type {number}", size=6.1, color=WHITE, weight="bold", ha="center", z=7)


def transient_icon(ax, x, y, w, h, color):
    # A temporary high state overlaps baseline, then resolves.
    ax.add_patch(Rectangle((x + 0.34 * w, y), 0.30 * w, h, transform=ax.transAxes, facecolor=BLUE, alpha=0.09, edgecolor="none", zorder=2))
    line(ax, [x, x + w], [y + 0.18 * h, y + 0.18 * h], color=LINE, lw=0.8, z=3)
    xs = [x, x + 0.12 * w, x + 0.25 * w, x + 0.38 * w, x + 0.52 * w, x + 0.67 * w, x + 0.82 * w, x + w]
    ys = [y + 0.28 * h, y + 0.34 * h, y + 0.48 * h, y + 0.81 * h, y + 0.77 * h, y + 0.43 * h, y + 0.31 * h, y + 0.35 * h]
    line(ax, xs, ys, color=color, lw=1.8, z=5)
    line(ax, [x + 0.34 * w, x + 0.64 * w], [y + 0.88 * h, y + 0.88 * h], color=color, lw=1.0, ls=(0, (2, 2)), z=4)


def selection_icon(ax, x, y, w, h, color):
    # Enrollment occurs when natural fluctuation crosses a high threshold.
    threshold = y + 0.63 * h
    line(ax, [x, x + w], [threshold, threshold], color=color, lw=1.0, ls=(0, (2, 2)), z=4)
    xs = [x, x + 0.12 * w, x + 0.25 * w, x + 0.38 * w, x + 0.52 * w, x + 0.66 * w, x + 0.80 * w, x + w]
    ys = [y + 0.28 * h, y + 0.43 * h, y + 0.34 * h, y + 0.72 * h, y + 0.82 * h, y + 0.49 * h, y + 0.38 * h, y + 0.32 * h]
    line(ax, xs, ys, color=color, lw=1.8, z=5)
    ax.add_patch(Circle((x + 0.52 * w, y + 0.82 * h), 0.006, transform=ax.transAxes, facecolor=WHITE, edgecolor=color, lw=1.3, zorder=6))
    arrow = FancyArrowPatch(
        (x + 0.52 * w, y + 0.96 * h),
        (x + 0.52 * w, y + 0.86 * h),
        transform=ax.transAxes,
        arrowstyle="-|>",
        mutation_scale=7,
        linewidth=0.9,
        color=color,
        zorder=6,
    )
    ax.add_patch(arrow)


def measurement_icon(ax, x, y, w, h, color):
    # Sensitivity: one true event is missed. False alarms: one observed event has no source.
    top_y = y + 0.76 * h
    bottom_y = y + 0.24 * h
    dot_xs = [x + 0.08 * w, x + 0.28 * w, x + 0.48 * w, x + 0.68 * w]
    for dot_x in dot_xs:
        ax.add_patch(Circle((dot_x, top_y), 0.0055, transform=ax.transAxes, facecolor=color, edgecolor="none", zorder=5))

    missed_index = 2
    for index, dot_x in enumerate(dot_xs):
        if index == missed_index:
            ax.add_patch(Circle((dot_x, bottom_y), 0.0060, transform=ax.transAxes, facecolor=WHITE, edgecolor=color, lw=1.1, zorder=5))
            line(ax, [dot_x, dot_x], [bottom_y + 0.012, top_y - 0.012], color=color, lw=0.8, ls=(0, (1, 2)), z=4, alpha=0.75)
        else:
            ax.add_patch(Circle((dot_x, bottom_y), 0.0055, transform=ax.transAxes, facecolor=color, edgecolor="none", zorder=5))
            line(ax, [dot_x, dot_x], [bottom_y + 0.012, top_y - 0.012], color=color, lw=0.8, z=4, alpha=0.28)

    false_x = x + 0.92 * w
    ax.add_patch(Circle((false_x, bottom_y), 0.0058, transform=ax.transAxes, facecolor=color, edgecolor="none", zorder=6))
    ax.add_patch(Circle((false_x, bottom_y), 0.0105, transform=ax.transAxes, facecolor="none", edgecolor=color, lw=0.8, zorder=5))
    ray = 0.014
    line(ax, [false_x - ray, false_x - 0.009], [bottom_y + ray, bottom_y + 0.009], color=color, lw=0.8, z=5)
    line(ax, [false_x + 0.009, false_x + ray], [bottom_y + 0.009, bottom_y + ray], color=color, lw=0.8, z=5)


def source_card(ax, x, y, w, h, *, number, title, color, bg, icon):
    rounded_box(ax, x, y, w, h, face=bg, edge=color, lw=0.85, radius=0.015, z=2)
    type_badge(ax, x + 0.015, y + 0.5 * h, number, color)
    text(ax, x + 0.092, y + 0.5 * h, title, size=7.5, color=TEXT, weight="bold", linespacing=1.0)
    icon(ax, x + 0.250, y + 0.18 * h, w - 0.270, 0.64 * h, color)


def make_figure(output_root: Path, pdf_root: Path) -> dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    pdf_root.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(
        {
            "font.family": "Arial",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    # JCE ratio and physical size: 13.28 cm x 5.31 cm. Raster export is 300 dpi.
    width_in = 13.28 / 2.54
    height_in = 5.31 / 2.54
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=300)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    text(
        ax,
        0.5,
        0.948,
        "Different mechanisms. Same apparent improvement.",
        size=13.4,
        color=NAVY,
        weight="bold",
        ha="center",
    )
    text(
        ax,
        0.5,
        0.885,
        "Three operational sources of regression to the mean in clinical trials",
        size=8.2,
        color=MUTED,
        ha="center",
    )

    text(ax, 0.207, 0.817, "THREE SOURCES", size=6.7, color=NAVY, weight="bold", ha="center")
    text(ax, 0.720, 0.817, "ONE TRIAL-FACING SIGNAL", size=6.7, color=NAVY, weight="bold", ha="center")

    card_x, card_w, card_h = 0.025, 0.365, 0.133
    card_centers = [0.675, 0.505, 0.335]
    source_card(
        ax,
        card_x,
        card_centers[0] - card_h / 2,
        card_w,
        card_h,
        number=1,
        title="Transient\nworsening",
        color=BLUE,
        bg=BLUE_BG,
        icon=transient_icon,
    )
    source_card(
        ax,
        card_x,
        card_centers[1] - card_h / 2,
        card_w,
        card_h,
        number=2,
        title="High-baseline\nselection",
        color=AMBER,
        bg=AMBER_BG,
        icon=selection_icon,
    )
    source_card(
        ax,
        card_x,
        card_centers[2] - card_h / 2,
        card_w,
        card_h,
        number=3,
        title="Measurement\nerror",
        color=VIOLET,
        bg=VIOLET_BG,
        icon=measurement_icon,
    )

    # Three colored paths converge on a single observed signal.
    junction = (0.432, 0.505)
    for center, color in zip(card_centers, [BLUE, AMBER, VIOLET]):
        line(ax, [card_x + card_w, junction[0]], [center, junction[1]], color=color, lw=1.25, z=3, alpha=0.9)
    ax.add_patch(Circle(junction, 0.007, transform=ax.transAxes, facecolor=NAVY, edgecolor=WHITE, lw=0.7, zorder=6))
    ax.add_patch(
        FancyArrowPatch(
            (junction[0] + 0.004, junction[1]),
            (0.462, junction[1]),
            transform=ax.transAxes,
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.2,
            color=NAVY,
            zorder=5,
        )
    )

    center_x, center_y, center_w, center_h = 0.465, 0.247, 0.510, 0.538
    rounded_box(ax, center_x, center_y, center_w, center_h, face=WHITE, edge=LINE, lw=0.9, radius=0.018, z=2)
    text(
        ax,
        center_x + center_w / 2,
        0.716,
        "Baseline high, follow-up lower",
        size=10.1,
        color=NAVY,
        weight="bold",
        ha="center",
        linespacing=0.98,
    )
    text(
        ax,
        center_x + center_w / 2,
        0.654,
        "Same observed pattern: regression to the mean",
        size=7.0,
        color=MUTED,
        weight="bold",
        ha="center",
        linespacing=1.0,
    )

    baseline = (0.580, 0.555)
    followup = (0.860, 0.405)
    line(ax, [0.535, 0.915], [0.352, 0.352], color=LINE, lw=1.0, z=3)
    ax.add_patch(
        FancyArrowPatch(
            baseline,
            followup,
            transform=ax.transAxes,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=2.5,
            color=NAVY,
            zorder=4,
        )
    )
    ax.add_patch(Circle(baseline, 0.014, transform=ax.transAxes, facecolor=NAVY, edgecolor=WHITE, lw=1.0, zorder=6))
    ax.add_patch(Circle(followup, 0.014, transform=ax.transAxes, facecolor=WHITE, edgecolor=NAVY, lw=1.6, zorder=6))
    text(ax, baseline[0], 0.322, "Baseline", size=7.1, color=TEXT, weight="bold", ha="center")
    text(ax, followup[0], 0.322, "Follow-up", size=7.1, color=TEXT, weight="bold", ha="center")

    rounded_box(ax, 0.650, 0.255, 0.140, 0.043, face="#EEF2F7", edge="none", lw=0, radius=0.012, z=3)
    text(ax, 0.720, 0.2765, "Treatment effect = 0", size=7.5, color=NAVY, weight="bold", ha="center", z=5)

    rounded_box(ax, 0.025, 0.064, 0.950, 0.118, face=NAVY, edge=NAVY, lw=0, radius=0.018, z=2)
    text(
        ax,
        0.5,
        0.123,
        "1,000,000 synthetic patients   |   fixed cohort   |   epilepsy model   |   treatment effect = 0",
        size=8.0,
        color=WHITE,
        weight="bold",
        ha="center",
        z=5,
    )

    stem = "anatomy_of_RTM_JCE_graphical_abstract"
    svg_path = output_root / f"{stem}.svg"
    tiff_path = output_root / f"{stem}.tif"
    png_path = output_root / f"{stem}_preview.png"
    pdf_path = pdf_root / f"{stem}.pdf"

    fig.savefig(svg_path, format="svg", facecolor=PAPER)
    fig.savefig(pdf_path, format="pdf", facecolor=PAPER)
    fig.savefig(
        tiff_path,
        format="tiff",
        dpi=300,
        facecolor=PAPER,
        pil_kwargs={"compression": "tiff_lzw"},
    )
    fig.savefig(png_path, format="png", dpi=300, facecolor=PAPER)
    plt.close(fig)

    # Submission raster: flatten to RGB while retaining 300-dpi metadata and LZW compression.
    with Image.open(tiff_path) as tiff_image:
        tiff_image.convert("RGB").save(tiff_path, format="TIFF", compression="tiff_lzw", dpi=(300, 300))

    manifest = {
        "title": "Different mechanisms. Same apparent improvement.",
        "journal": "Journal of Clinical Epidemiology",
        "canvas_cm": {"width": 13.28, "height": 5.31},
        "raster_dpi": 300,
        "exports": {
            "editable_vector": str(svg_path),
            "submission_vector": str(pdf_path),
            "submission_raster": str(tiff_path),
            "review_preview": str(png_path),
        },
        "exact_claims": [
            "1,000,000 synthetic patients",
            "fixed cohort",
            "epilepsy model",
            "treatment effect = 0",
        ],
        "accessibility": "Color is redundant with numbering, direct labels, and distinct diagrams.",
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance_path = output_root / "PROVENANCE.md"
    provenance_path.write_text(
        "# Graphical abstract provenance\n\n"
        "The artwork was composed deterministically from original vector shapes and text. "
        "No generative image model, third-party icons, photographs, or copyrighted visual assets were used.\n\n"
        "The visual claims and design-control language were derived from the revised JCE manuscript. "
        "The quantitative magnitudes in the manuscript are model-specific; this abstract emphasizes "
        "the general methodological structure.\n\n"
        "JCE's current guide states that AI-assisted graphical-abstract artwork is not permitted. "
        "The authors should therefore treat this file as a precise design draft and determine whether "
        "manual reconstruction is required before submission.\n",
        encoding="utf-8",
    )

    return {
        "svg": svg_path,
        "pdf": pdf_path,
        "tiff": tiff_path,
        "png": png_path,
        "manifest": manifest_path,
        "provenance": provenance_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("output/graphical_abstract"))
    parser.add_argument("--pdf-root", type=Path, default=Path("output/pdf"))
    args = parser.parse_args()
    outputs = make_figure(args.output_root, args.pdf_root)
    for label, path in outputs.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
