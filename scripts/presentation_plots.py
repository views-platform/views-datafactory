#!/usr/bin/env python3
"""Presentation support plots — raw grid data for storytelling.

Usage:
    uv run python scripts/presentation_plots.py
    uv run python scripts/presentation_plots.py --output reports/presentation

Produces 5 figures from the assembled grid for the
"From Model to Meaning" presentation:

  1. pres_raw_series.png     — Ethiopia raw monthly fatalities
  2. pres_three_conflicts.png — Syria / Somalia / Colombia
  3. pres_spatial_context.png — Global heatmap + annotations
  4. pres_concentration.png   — Lorenz curve (Gini)
  5. pres_admin_zoom.png      — Horn of Africa admin-1 + conflict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from viz_style import (
    COLOR_ACCENT,
    COLOR_GRAY,
    EXTENT,
    FONT_ANNOT,
    FONT_LABEL,
    FONT_TITLE,
    make_dates,
    save_plot,
    style_ax,
)

# ── GAUL codes ──

ETHIOPIA = 124
SYRIA = 272
SOMALIA = 158
COLOMBIA = 185
SOUTH_SUDAN = 160

COUNTRY_COLORS = {
    "Syria": "#C0392B",
    "Somalia": "#2980B9",
    "Colombia": "#27AE60",
}


# style_ax, save_plot, make_dates — from viz_style


def _country_series(
    grid: object,
    gaul0_idx: int,
    feat_idx: int,
    country_code: int,
    n_t: int,
) -> list[float]:
    """Sum a feature across all cells matching a GAUL country."""
    import numpy as np

    mask = np.asarray(grid[0, :, :, gaul0_idx]) == country_code
    return [
        float(np.asarray(grid[t, :, :, feat_idx])[mask].sum())
        for t in range(n_t)
    ]


def plot_raw_series(
    grid: object,
    features: list[str],
    n_t: int,
    out: Path,
) -> None:
    """1 — Ethiopia raw monthly fatalities."""
    import matplotlib.pyplot as plt

    gaul0_idx = features.index("gaul0_code")
    # Sum all violence types
    sb_idx = features.index("ged_sb_best")
    ns_idx = features.index("ged_ns_best")
    os_idx = features.index("ged_os_best")

    sb = _country_series(grid, gaul0_idx, sb_idx, ETHIOPIA, n_t)
    ns = _country_series(grid, gaul0_idx, ns_idx, ETHIOPIA, n_t)
    os_ = _country_series(grid, gaul0_idx, os_idx, ETHIOPIA, n_t)
    total = [
        s + n + o
        for s, n, o in zip(sb, ns, os_, strict=True)
    ]

    dates = make_dates(n_t)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(dates, total, linewidth=0.6, color=COLOR_ACCENT)
    ax.fill_between(
        dates, total, alpha=0.15, color=COLOR_ACCENT,
    )
    style_ax(
        ax,
        title="Monthly conflict fatalities — Ethiopia, 1989–2026",
        ylabel="Fatalities per month",
    )
    ax.set_xlim(dates[0], dates[-1])
    save_plot(fig, out,"pres_raw_series.png")


def plot_three_conflicts(
    grid: object,
    features: list[str],
    n_t: int,
    out: Path,
) -> None:
    """2 — Syria / Somalia / Colombia side by side."""
    import matplotlib.pyplot as plt
    import numpy as np

    gaul0_idx = features.index("gaul0_code")
    sb_idx = features.index("ged_sb_best")
    ns_idx = features.index("ged_ns_best")
    os_idx = features.index("ged_os_best")

    countries = [
        ("Syria", SYRIA, "#C0392B"),
        ("Somalia", SOMALIA, "#2980B9"),
        ("Colombia", COLOMBIA, "#27AE60"),
    ]

    dates = make_dates(n_t)
    fig, axes = plt.subplots(
        1, 3, figsize=(14, 3.5),
        gridspec_kw={"wspace": 0.3},
    )

    for ax, (name, code, color) in zip(
        axes.flat, countries, strict=True,
    ):
        sb = _country_series(grid, gaul0_idx, sb_idx, code, n_t)
        ns = _country_series(grid, gaul0_idx, ns_idx, code, n_t)
        os_ = _country_series(grid, gaul0_idx, os_idx, code, n_t)
        total = np.array(sb) + np.array(ns) + np.array(os_)

        ax.plot(dates, total, linewidth=0.6, color=color)
        ax.fill_between(dates, total, alpha=0.15, color=color)
        style_ax(ax, title=name)
        ax.set_xlim(dates[0], dates[-1])
        ax.tick_params(axis="x", rotation=30)

    axes[0].set_ylabel(  # type: ignore[union-attr]
        "Fatalities / month", fontsize=FONT_LABEL,
    )
    fig.suptitle(
        "Three conflicts, three patterns — raw monthly data",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    save_plot(fig, out,"pres_three_conflicts.png")


def plot_spatial_context(
    grid: object,
    features: list[str],
    n_t: int,
    out: Path,
) -> None:
    """3 — Global heatmap with annotated countries."""
    import matplotlib.patheffects as mpe
    import matplotlib.pyplot as plt
    import numpy as np

    sb_idx = features.index("ged_sb_best")
    total = np.zeros(
        (grid.shape[1], grid.shape[2]), dtype=np.float64,  # type: ignore[union-attr]
    )
    for t in range(n_t):
        total += np.asarray(grid[t, :, :, sb_idx])

    display = np.log1p(total)
    display[display == 0] = np.nan

    fig, ax = plt.subplots(figsize=(14, 7))
    im = ax.imshow(
        np.flipud(display), cmap="YlOrRd",
        aspect="auto", extent=EXTENT,
    )
    plt.colorbar(im, ax=ax, label="log(1 + fatalities)", shrink=0.7)

    # Annotate countries
    annotations = [
        ("Syria", 38, 20),
        ("Somalia", 46, -5),
        ("Colombia", -74, 15),
        ("Ethiopia", 40, 25),
    ]
    for name, lon, lat in annotations:
        ax.annotate(
            name, (lon, lat),
            fontsize=FONT_ANNOT, fontweight="bold",
            color="white",
            ha="center",
            path_effects=[
                mpe.withStroke(linewidth=2, foreground="black")
            ],
        )

    style_ax(
        ax,
        title="Total conflict fatalities, 1989–2026",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out,"pres_spatial_context.png")


def plot_concentration(
    grid: object,
    features: list[str],
    n_t: int,
    out: Path,
) -> None:
    """4 — Lorenz curve / Gini coefficient."""
    import matplotlib.pyplot as plt
    import numpy as np

    sb_idx = features.index("ged_sb_best")
    gaul0_idx = features.index("gaul0_code")

    # Sum fatalities per cell (land only)
    land_mask = np.asarray(grid[0, :, :, gaul0_idx]) > 0
    total = np.zeros(
        (grid.shape[1], grid.shape[2]), dtype=np.float64,  # type: ignore[union-attr]
    )
    for t in range(n_t):
        total += np.asarray(grid[t, :, :, sb_idx])

    land_totals = total[land_mask].flatten()
    land_totals.sort()
    cum = np.cumsum(land_totals)
    cum_frac = cum / cum[-1] if cum[-1] > 0 else cum
    x = np.linspace(0, 100, len(land_totals))

    # Gini
    n = len(land_totals)
    gini = (
        2 * np.sum((np.arange(1, n + 1)) * land_totals)
        / (n * np.sum(land_totals))
        - (n + 1) / n
    )

    # Concentration stat
    threshold_90 = np.searchsorted(cum_frac, 0.90)
    pct_90 = (1 - threshold_90 / n) * 100

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot(x, cum_frac * 100, "k-", linewidth=2)
    ax.plot([0, 100], [0, 100], "--", color="#AAAAAA", linewidth=1)
    ax.text(
        20, 70, f"Gini = {gini:.3f}",
        fontsize=16, fontweight="bold", color="#333333",
    )
    ax.text(
        20, 60,
        f"{pct_90:.1f}% of cells account\nfor 90% of all fatalities",
        fontsize=FONT_LABEL, color=COLOR_GRAY,
    )
    style_ax(
        ax,
        title="Concentration of conflict fatalities",
        xlabel="Cumulative % of land cells (ranked by fatalities)",
        ylabel="Cumulative % of total fatalities",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    save_plot(fig, out,"pres_concentration.png")


def plot_admin_zoom(
    grid: object,
    features: list[str],
    n_t: int,
    out: Path,
) -> None:
    """5 — Horn of Africa: admin-1 boundaries + conflict."""
    import matplotlib.pyplot as plt
    import numpy as np

    sb_idx = features.index("ged_sb_best")
    gaul1_idx = features.index("gaul1_code")
    gaul0_idx = features.index("gaul0_code")

    # Sum fatalities
    total = np.zeros(
        (grid.shape[1], grid.shape[2]), dtype=np.float64,  # type: ignore[union-attr]
    )
    for t in range(n_t):
        total += np.asarray(grid[t, :, :, sb_idx])

    # Horn of Africa extent: lat -5 to 20, lon 25 to 55
    # Row: (90 - lat) / 0.5 → lat=20 → row=140, lat=-5 → row=190
    # Col: (lon + 180) / 0.5 → lon=25 → col=410, lon=55 → col=470
    r0, r1 = 140, 190
    c0, c1 = 410, 470

    fat_zoom = total[r0:r1, c0:c1]
    adm1_zoom = np.asarray(grid[0, r0:r1, c0:c1, gaul1_idx]).copy()
    adm0_zoom = np.asarray(grid[0, r0:r1, c0:c1, gaul0_idx]).copy()

    # Mask ocean
    ocean = adm0_zoom <= 0
    fat_display = np.log1p(fat_zoom).astype(np.float64)
    fat_display[ocean] = np.nan
    adm1_display = adm1_zoom.astype(np.float64)
    adm1_display[adm1_display <= 0] = np.nan

    horn_extent = [25, 55, -5, 20]

    fig, axes = plt.subplots(
        1, 2, figsize=(12, 5),
        gridspec_kw={"wspace": 0.12},
    )

    # Left: admin-1 boundaries
    ax = axes[0]
    ax.imshow(  # type: ignore[union-attr]
        np.flipud(adm1_display), cmap="tab20",
        aspect="auto", extent=horn_extent,
        interpolation="nearest",
    )
    style_ax(
        ax, title="Admin-1 boundaries",
        xlabel="Longitude", ylabel="Latitude",
    )

    # Right: conflict fatalities
    ax = axes[1]
    im = ax.imshow(  # type: ignore[union-attr]
        np.flipud(fat_display), cmap="YlOrRd",
        aspect="auto", extent=horn_extent,
    )
    plt.colorbar(im, ax=ax, label="log(1 + fatalities)", shrink=0.8)
    style_ax(
        ax, title="Conflict fatalities (1989–2026)",
        xlabel="Longitude",
    )

    fig.suptitle(
        "Horn of Africa — sub-national resolution",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    save_plot(fig, out,"pres_admin_zoom.png")


def main() -> int:
    """Generate presentation support plots."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Presentation support plots"
    )
    parser.add_argument(
        "--input", type=Path, default=Path("data/assembled"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/presentation"),
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        return 1

    import matplotlib
    matplotlib.use("Agg")
    import numpy as np

    from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG

    features = json.loads(
        (args.input / "feature_names.json").read_text()
    )
    grid = np.load(grid_path, mmap_mode="r")
    DEFAULT_GRID_CONFIG.assert_grid_shape(grid)
    n_t = grid.shape[0]

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Grid: {grid.shape}, {len(features)} features")
    print(f"Output: {args.output}")
    print()

    plots = [
        ("Raw series (Ethiopia)", plot_raw_series),
        ("Three conflicts", plot_three_conflicts),
        ("Spatial context", plot_spatial_context),
        ("Concentration", plot_concentration),
        ("Admin zoom (Horn)", plot_admin_zoom),
    ]

    for name, fn in plots:
        print(f"{name}...")
        fn(grid, features, n_t, args.output)

    print(f"\nAll {len(plots)} plots saved to {args.output}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
