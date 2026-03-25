#!/usr/bin/env python3
"""Diagnostic visualization of a compiled PRIO-GRID.

Usage:
    uv run python scripts/visualize_grid.py data/compiled/

Reads grid.npy + sidecars from the specified directory and produces
diagnostic PNGs in reports/. Each plot answers a specific question
about the compiled data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from viz_style import CMAP_SEQ, DPI, EXTENT, FONT_ANNOT, FONT_TITLE  # noqa: E402


def load_grid(grid_dir: Path) -> dict:
    """Load compiled grid + sidecars."""
    grid = np.load(grid_dir / "grid.npy")
    pgids = np.load(grid_dir / "pgids.npy")
    time_steps = np.load(grid_dir / "time_steps.npy")
    feature_names = json.loads((grid_dir / "feature_names.json").read_text())
    return {
        "grid": grid,
        "pgids": pgids,
        "time_steps": time_steps,
        "feature_names": feature_names,
    }


def plot_spatial_heatmap(data: dict, output_dir: Path) -> Path:
    """Plot 1: Spatial heatmap — 'Does it look right?'

    Shows total event count per cell on an equirectangular map.
    Hotspots should match known conflict zones.
    """
    grid = data["grid"]
    pgids = data["pgids"]

    # Sum event count (feature 0) across all months
    total_counts = grid[:, :, 0].sum(axis=1)

    # Convert pgids to lat/lon using the grid formula
    # pgid = row * 720 + col + 1 (1-indexed, row-major from bottom-left)
    ncol = 720
    idx = pgids - 1
    rows = idx // ncol
    cols = idx % ncol
    # Create 2D image (360 rows x 720 cols)
    img = np.full((360, 720), np.nan)
    for i in range(len(pgids)):
        r = int(rows[i])
        c = int(cols[i])
        if 0 <= r < 360 and 0 <= c < 720:
            img[r, c] = total_counts[i]

    # Flip vertically (row 0 = south, but imshow puts row 0 at top)
    img = img[::-1]

    fig, ax = plt.subplots(figsize=(16, 8))
    # Use log scale for color to handle extreme skew
    with np.errstate(divide="ignore"):
        log_img = np.log10(1 + img)
    im = ax.imshow(
        log_img,
        extent=EXTENT,
        cmap=CMAP_SEQ,
        aspect="auto",
        interpolation="nearest",
    )
    cbar = plt.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("log10(1 + event count)")

    ax.set_title(
        "UCDP/GED Events on PRIO-GRID — Spatial Distribution\n"
        "Q: Do hotspots match known conflict zones?",
        fontsize=FONT_TITLE,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Annotate key statistics
    n_active = (total_counts > 0).sum()
    n_total = len(total_counts)
    ax.text(
        0.02,
        0.02,
        f"Active cells: {n_active:,} / {n_total:,} "
        f"({100 * n_active / n_total:.2f}%)\n"
        f"Total events: {total_counts.sum():,.0f}",
        transform=ax.transAxes,
        fontsize=FONT_ANNOT,
        va="bottom",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    path = output_dir / "grid_spatial_heatmap.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def plot_temporal_profile(data: dict, output_dir: Path) -> Path:
    """Plot 2: Temporal profile — 'Is there signal in time?'

    Bar chart of total events per month. Temporal variation means
    the time dimension carries signal for models.
    """
    grid = data["grid"]
    time_steps = data["time_steps"]
    feature_names = data["feature_names"]

    n_steps = grid.shape[1]
    months = [str(ts)[:7] for ts in time_steps[:n_steps]]

    fig, ax1 = plt.subplots(figsize=(12, 5))

    # Event counts per month
    events_per_month = grid[:, :, 0].sum(axis=0)
    ax1.bar(months, events_per_month, color="#d62728", alpha=0.7, label="Events")
    ax1.set_ylabel("Event Count", color="#d62728")
    ax1.tick_params(axis="y", labelcolor="#d62728")

    # Overlay fatalities if available
    if len(feature_names) > 1:
        ax2 = ax1.twinx()
        fatalities_per_month = grid[:, :, 1].sum(axis=0)
        ax2.plot(
            months,
            fatalities_per_month,
            color="#1f77b4",
            marker="o",
            linewidth=2,
            label="Fatalities",
        )
        ax2.set_ylabel("Fatalities (sum best)", color="#1f77b4")
        ax2.tick_params(axis="y", labelcolor="#1f77b4")

    ax1.set_title(
        "Monthly Conflict Profile\n"
        "Q: Does conflict vary across months, or is it flat?",
        fontsize=FONT_TITLE,
    )
    ax1.set_xlabel("Month")
    plt.xticks(rotation=45)

    fig.tight_layout()
    path = output_dir / "grid_temporal_profile.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def plot_zero_inflation(data: dict, output_dir: Path) -> Path:
    """Plot 3: Zero-inflation — 'How sparse is conflict?'

    Histogram of per-cell event counts. The zero-inflation rate
    is the first calibration target for synthetic generators (RQ-1).
    """
    grid = data["grid"]

    # Total events per cell (summed across months)
    cell_totals = grid[:, :, 0].sum(axis=1)

    n_zero = (cell_totals == 0).sum()
    n_total = len(cell_totals)
    zero_rate = n_zero / n_total

    # Positive cells only for the histogram
    positive = cell_totals[cell_totals > 0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: pie chart of zero vs non-zero
    ax1.pie(
        [n_zero, n_total - n_zero],
        labels=[f"Zero ({zero_rate:.1%})", f"Active ({1 - zero_rate:.1%})"],
        colors=["#cccccc", "#d62728"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax1.set_title("Zero-Inflation Rate\n(calibration target for synthetic gen)")

    # Right: histogram of positive cell counts (log scale)
    if len(positive) > 0:
        ax2.hist(positive, bins=50, color="#d62728", alpha=0.7, edgecolor="black")
        ax2.set_yscale("log")
        ax2.set_xlabel("Events per cell (annual total)")
        ax2.set_ylabel("Number of cells (log scale)")
        ax2.set_title(
            "Distribution of Active Cell Counts\n"
            "Q: Power law or exponential tail?"
        )

        # Annotate statistics
        ax2.text(
            0.95,
            0.95,
            f"Active cells: {len(positive):,}\n"
            f"Median: {np.median(positive):.0f}\n"
            f"Mean: {np.mean(positive):.1f}\n"
            f"Max: {np.max(positive):.0f}\n"
            f"p95: {np.percentile(positive, 95):.0f}\n"
            f"p99: {np.percentile(positive, 99):.0f}",
            transform=ax2.transAxes,
            fontsize=FONT_ANNOT,
            va="top",
            ha="right",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.8},
        )

    fig.suptitle(
        "Conflict Data Sparsity on PRIO-GRID",
        fontsize=FONT_TITLE,
        y=1.02,
    )
    fig.tight_layout()
    path = output_dir / "grid_zero_inflation.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def plot_fatalities_vs_events(data: dict, output_dir: Path) -> Path:
    """Plot 4: Fatalities vs events — 'Are these correlated?'

    Scatter of (event_count, fatalities) per active cell.
    If strongly correlated, one feature may be redundant.
    """
    grid = data["grid"]

    if grid.shape[2] < 2:
        print("  Skipped: only 1 feature, need 2 for correlation plot")
        return output_dir

    cell_events = grid[:, :, 0].sum(axis=1)
    cell_fatalities = grid[:, :, 1].sum(axis=1)

    # Active cells only
    mask = cell_events > 0
    x = cell_events[mask]
    y = cell_fatalities[mask]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(x, y, alpha=0.3, s=10, color="#1f77b4")
    ax.set_xlabel("Event Count (annual total)")
    ax.set_ylabel("Fatalities (sum best, annual total)")
    ax.set_title(
        "Fatalities vs. Event Count per Cell\n"
        "Q: Are these correlated, or does intensity vary independently?",
        fontsize=FONT_TITLE,
    )

    # Log-log scale for readability
    ax.set_xscale("log")
    ax.set_yscale("log")

    # Correlation
    if len(x) > 2:
        corr = np.corrcoef(np.log1p(x), np.log1p(y))[0, 1]
        ax.text(
            0.05,
            0.95,
            f"Log-log correlation: {corr:.3f}\n"
            f"Active cells: {len(x):,}",
            transform=ax.transAxes,
            fontsize=FONT_ANNOT,
            va="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.8},
        )

    path = output_dir / "grid_fatalities_vs_events.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")
    return path


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <compiled_grid_dir>")
        print(f"Example: {sys.argv[0]} data/compiled/")
        return 1

    grid_dir = Path(sys.argv[1])
    if not (grid_dir / "grid.npy").exists():
        print(f"Error: {grid_dir / 'grid.npy'} not found")
        return 1

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    print(f"Loading grid from {grid_dir}...")
    data = load_grid(grid_dir)
    grid = data["grid"]
    print(
        f"  Shape: {grid.shape} "
        f"({grid.shape[0]:,} cells × {grid.shape[1]} months × "
        f"{grid.shape[2]} features)"
    )
    print(f"  Features: {data['feature_names']}")
    print()

    print("Generating diagnostic plots...")
    plot_spatial_heatmap(data, output_dir)
    plot_temporal_profile(data, output_dir)
    plot_zero_inflation(data, output_dir)
    plot_fatalities_vs_events(data, output_dir)

    print()
    print(f"All plots saved to {output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
