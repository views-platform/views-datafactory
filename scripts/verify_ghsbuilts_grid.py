#!/usr/bin/env python3
"""GHS-BUILT-S grid verification — 10 plots + statistical checks
proving spatial, temporal, and structural correctness before release.

Usage:
    uv run python scripts/verify_ghsbuilts_grid.py
    uv run python scripts/verify_ghsbuilts_grid.py --input data/compiled/ghsbuilts

Reads the compiled GHS-BUILT-S grid and produces PNG plots to
``reports/audit_ghsbuilts/`` plus a statistical summary on stdout.

Uses memory-mapped grid loading to avoid large RAM usage.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from viz_style import (  # noqa: I001
    COLOR_ACCENT,
    EXTENT,
    FIG_FULL,
    FIG_HALF,
    FIG_PANEL_1x3,
    FIG_PANEL_4x3,
    FONT_ANNOT,
    FONT_LABEL,
    FONT_TICK,
    FONT_TITLE,
    make_dates,
    save_plot,
    spatial_imshow,
    style_ax,
)

CMAP_BUILT = "YlOrRd"

KNOWN_GLOBAL_BUILT_AREA: dict[int, float] = {
    1975: 2.40e10,
    1980: 2.74e10,
    1985: 3.13e10,
    1990: 3.57e10,
    1995: 4.06e10,
    2000: 4.63e10,
    2005: 5.25e10,
    2010: 5.93e10,
    2015: 6.68e10,
    2020: 7.43e10,
    2025: 8.12e10,
    2030: 8.76e10,
}

REGION_BOUNDS: list[tuple[tuple[int, int], tuple[int, int], str]] = [
    ((32, 42), (30, 45), "Eastern Med"),
    ((5, 15), (33, 43), "East Africa"),
    ((-6, 6), (25, 32), "Central Africa"),
    ((13, 28), (68, 82), "India"),
    ((22, 42), (100, 125), "China"),
    ((30, 38), (125, 135), "Japan/Korea"),
    ((-10, 5), (100, 115), "SE Asia"),
    ((25, 50), (-5, 15), "Europe"),
    ((25, 50), (-130, -60), "N. America"),
    ((-35, 5), (-80, -35), "S. America"),
    ((3, 15), (1, 15), "West Africa"),
]

SPOT_CHECK_LOCATIONS = [
    ("Tokyo", 35.7, 139.7),
    ("Delhi", 28.6, 77.2),
    ("Shanghai", 31.2, 121.5),
    ("Sao Paulo", -23.5, -46.6),
    ("Mexico City", 19.4, -99.1),
    ("Cairo", 30.0, 31.2),
    ("Lagos", 6.5, 3.4),
    ("London", 51.5, -0.1),
    ("New York", 40.7, -74.0),
    ("Sahara", 23.0, 5.0),
    ("Pacific Ocean", 0.0, -160.0),
    ("Amazon interior", -5.0, -65.0),
]


def cell_to_label(
    row: int, col: int, n_h: int, n_w: int,
) -> str:
    lat = -90.0 + (row + 0.5) * (180.0 / n_h)
    lon = -180.0 + (col + 0.5) * (360.0 / n_w)
    for (lat_lo, lat_hi), (lon_lo, lon_hi), name in REGION_BOUNDS:
        if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi:
            return name
    lat_s = f"{abs(lat):.0f}{'N' if lat >= 0 else 'S'}"
    lon_s = f"{abs(lon):.0f}{'E' if lon >= 0 else 'W'}"
    return f"{lat_s}, {lon_s}"


# -- Data loading and precomputation --------------------------------


def _load_ocean_mask(n_h: int, n_w: int) -> np.ndarray:
    import numpy as np

    assembled = Path("data/assembled/grid.npy")
    if assembled.exists():
        feat_path = assembled.parent / "feature_names.json"
        if feat_path.exists():
            feats = json.loads(feat_path.read_text())
            if "landarea" in feats:
                ag = np.load(assembled, mmap_mode="r")
                idx = feats.index("landarea")
                mask = ag[0, :, :, idx] == 0
                print(
                    "  Ocean mask: from assembled grid"
                    " landarea"
                )
                return mask

    print("  Ocean mask: fallback (all-zero cells)")
    return np.zeros((n_h, n_w), dtype=bool)


@dataclasses.dataclass
class PrecomputedData:
    grid: np.ndarray
    features: list[str]
    n_t: int
    n_h: int
    n_w: int
    n_f: int
    ocean_mask: np.ndarray
    dates: list[dt.date]
    start_year: int

    built_idx: int

    monthly_built: np.ndarray
    total_built: np.ndarray
    latest_built: np.ndarray

    epoch_totals: dict[int, float]
    epoch_time_indices: dict[int, int]

    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray

    checks: dict[str, bool | str]


def _detect_epochs(
    monthly_built: np.ndarray, start_year: int,
) -> dict[int, int]:
    import numpy as np

    transitions: dict[int, int] = {}
    transitions[start_year] = 0
    for t in range(1, len(monthly_built)):
        if not np.isclose(
            monthly_built[t], monthly_built[t - 1], rtol=1e-6,
        ):
            year = start_year + t // 12
            transitions[year] = t
    return transitions


def precompute(
    grid: np.ndarray,
    features: list[str],
    start_year: int,
) -> PrecomputedData:
    import numpy as np

    n_t, n_h, n_w, n_f = grid.shape
    built_idx = features.index("ghsbuilts_built_area")

    ocean_mask = _load_ocean_mask(n_h, n_w)

    monthly_built = np.zeros(n_t, dtype=np.float64)
    total_built = np.zeros((n_h, n_w), dtype=np.float64)

    has_nan = False
    has_negative = False

    for t in range(n_t):
        sl = grid[t, :, :, built_idx].astype(np.float64)
        monthly_built[t] = sl.sum()
        total_built += sl
        if np.isnan(sl).any():
            has_nan = True
        if (sl < 0).any():
            has_negative = True

    latest_built = (
        grid[n_t - 1, :, :, built_idx].astype(np.float64)
    )

    epoch_time_indices = _detect_epochs(
        monthly_built, start_year,
    )
    epoch_totals: dict[int, float] = {}
    for year, t_idx in epoch_time_indices.items():
        epoch_totals[year] = float(monthly_built[t_idx])

    flat_idx = np.argsort(latest_built.ravel())[-12:][::-1]
    top_rows = flat_idx // n_w
    top_cols = flat_idx % n_w
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = float(grid[t, r, c, built_idx])

    ocean_built = (
        float(latest_built[ocean_mask].sum())
        if ocean_mask.any()
        else 0.0
    )
    total_latest = float(latest_built.sum())
    ocean_pct = (
        ocean_built / total_latest * 100
        if total_latest > 0
        else 0.0
    )

    antarctic_built = float(latest_built[:60, :].sum())

    sorted_epochs = sorted(epoch_totals.items())
    monotonic = all(
        sorted_epochs[i][1] >= sorted_epochs[i - 1][1]
        for i in range(1, len(sorted_epochs))
    )

    n_land = (
        int((~ocean_mask).sum())
        if ocean_mask.any()
        else n_h * n_w
    )
    n_built = int((latest_built > 0).sum())
    built_coverage = (
        n_built / n_land * 100 if n_land > 0 else 0.0
    )

    checks: dict[str, bool | str] = {
        "no_nan": not has_nan,
        "no_negatives": not has_negative,
        "ocean_built_negligible": ocean_pct < 0.5,
        "no_antarctic_built": antarctic_built < 1e6,
        "monotonic_epoch_growth": monotonic,
        "spatial_coverage": built_coverage > 5.0,
    }
    checks["_ocean_detail"] = (
        f"{ocean_built:,.0f} m² in ocean cells"
        f" ({ocean_pct:.4f}%)"
    )
    checks["_antarctic_detail"] = (
        f"{antarctic_built:,.0f} m² below 60°S"
    )
    checks["_coverage_detail"] = (
        f"{n_built:,} of {n_land:,} land cells have"
        f" built area ({built_coverage:.1f}%)"
    )

    ref_lines = []
    for year, total in sorted_epochs:
        if year in KNOWN_GLOBAL_BUILT_AREA:
            expected = KNOWN_GLOBAL_BUILT_AREA[year]
            ratio = total / expected
            ref_lines.append(
                f"{year}: {total / 1e9:.2f}B m² vs"
                f" {expected / 1e9:.1f}B m²"
                f" (ratio {ratio:.3f})"
            )
    if ref_lines:
        checks["_reference_detail"] = "; ".join(ref_lines)

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t, start_year=start_year),
        start_year=start_year,
        built_idx=built_idx,
        monthly_built=monthly_built,
        total_built=total_built,
        latest_built=latest_built,
        epoch_totals=epoch_totals,
        epoch_time_indices=epoch_time_indices,
        top_rows=top_rows,
        top_cols=top_cols,
        top_ts=top_ts,
        checks=checks,
    )


# -- Plot functions -------------------------------------------------


def plot_built_density(
    d: PrecomputedData, out: Path,
) -> None:
    """01 — Global built-up area density, latest epoch."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.latest_built, d.ocean_mask, CMAP_BUILT,
        log=True,
        cbar_label="log(1 + built area m²)",
        fig=fig,
    )
    latest_year = d.start_year + d.n_t // 12
    style_ax(
        ax,
        title=(
            "GHS-BUILT-S built-up density"
            f" (latest: ~{latest_year})"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    save_plot(fig, out, "01_built_density.png")


def plot_cumulative_density(
    d: PrecomputedData, out: Path,
) -> None:
    """02 — Time-averaged built-up area."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    avg_built = d.total_built / d.n_t
    spatial_imshow(
        ax, avg_built, d.ocean_mask, CMAP_BUILT,
        log=True,
        cbar_label="log(1 + avg monthly built m²)",
        fig=fig,
    )
    style_ax(
        ax,
        title=(
            "GHS-BUILT-S time-averaged built area, "
            f"{d.start_year}–"
            f"{d.start_year + d.n_t // 12}"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    save_plot(fig, out, "02_cumulative_density.png")


def plot_epoch_totals(
    d: PrecomputedData, out: Path,
) -> None:
    """03 — Built-up area by epoch vs JRC reference."""
    import matplotlib.pyplot as plt

    years = sorted(d.epoch_totals.keys())
    totals = [d.epoch_totals[y] for y in years]

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.bar(
        years, [t / 1e9 for t in totals], width=3,
        color=COLOR_ACCENT, alpha=0.8, label="Grid total",
    )

    ref_years = sorted(KNOWN_GLOBAL_BUILT_AREA.keys())
    ref_vals = [
        KNOWN_GLOBAL_BUILT_AREA[y] / 1e9 for y in ref_years
    ]
    ax.plot(
        ref_years, ref_vals, "o--", color="#C0392B",
        linewidth=1.5, markersize=5, label="JRC reference",
    )

    for y, t in zip(years, totals, strict=True):
        ax.text(
            y, t / 1e9 + 0.15, f"{t / 1e9:.1f}B",
            ha="center", fontsize=FONT_ANNOT,
        )

    style_ax(
        ax,
        title=(
            "GHS-BUILT-S epoch totals vs"
            " JRC global estimates"
        ),
        xlabel="Year",
        ylabel="Built-up area (billion m²)",
    )
    ax.legend(fontsize=FONT_LABEL, frameon=False)
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "03_epoch_totals.png")


def plot_monthly_timeseries(
    d: PrecomputedData, out: Path,
) -> None:
    """04 — Monthly global built area showing transitions."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.plot(
        d.dates, d.monthly_built / 1e9,
        color=COLOR_ACCENT, linewidth=1.5,
    )

    for year in sorted(KNOWN_GLOBAL_BUILT_AREA):
        t_idx = (year - d.start_year) * 12
        if 0 < t_idx < d.n_t:
            ax.axvline(
                d.dates[t_idx], color="#C0392B",
                linewidth=0.8, linestyle="--", alpha=0.3,
            )
            ax.text(
                d.dates[t_idx],
                ax.get_ylim()[1] * 0.98,
                f" {year}", fontsize=7, color="#C0392B",
                va="top", rotation=90,
            )

    style_ax(
        ax,
        title="GHS-BUILT-S global built area (monthly)",
        xlabel="Date",
        ylabel="Built-up area (billion m²)",
    )
    ax.set_xlim(d.dates[0], d.dates[-1])
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "04_monthly_timeseries.png")


def plot_epoch_comparison(
    d: PrecomputedData, out: Path,
) -> None:
    """05 — Side-by-side spatial maps for available epochs."""
    import matplotlib.pyplot as plt
    import numpy as np

    end_year = d.start_year + d.n_t // 12
    mid_year = (d.start_year + end_year) // 2
    snapshot_years = [d.start_year, mid_year, end_year - 1]
    selected = [
        (y, (y - d.start_year) * 12)
        for y in snapshot_years
        if 0 <= (y - d.start_year) * 12 < d.n_t
    ]
    n_epochs = len(selected)
    if n_epochs == 0:
        return

    fig, axes = plt.subplots(
        1, n_epochs, figsize=FIG_PANEL_1x3,
    )
    if n_epochs == 1:
        axes = [axes]

    for ax, (year, t_idx) in zip(
        axes, selected, strict=True,
    ):
        built_slice = (
            d.grid[t_idx, :, :, d.built_idx]
            .astype(np.float64)
        )
        total = built_slice.sum()
        spatial_imshow(
            ax, built_slice, d.ocean_mask, CMAP_BUILT,
            log=True, fig=fig,
        )
        style_ax(
            ax, title=f"{year} ({total / 1e9:.1f}B m²)",
        )

    fig.suptitle(
        "GHS-BUILT-S built area across epochs",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "05_epoch_comparison.png")


def plot_growth_map(
    d: PrecomputedData, out: Path,
) -> None:
    """06 — Built-up growth between first and last epoch."""
    import matplotlib.pyplot as plt
    import numpy as np

    sorted_epochs = sorted(d.epoch_time_indices.items())
    if len(sorted_epochs) < 2:
        return

    first_year, first_t = sorted_epochs[0]
    last_year, last_t = sorted_epochs[-1]

    built_first = (
        d.grid[first_t, :, :, d.built_idx]
        .astype(np.float64)
    )
    built_last = (
        d.grid[last_t, :, :, d.built_idx]
        .astype(np.float64)
    )

    growth = built_last - built_first

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    spatial_imshow(
        axes[0], np.maximum(growth, 0), d.ocean_mask,
        "YlOrRd",
        log=True, cbar_label="log(1 + growth m²)",
        fig=fig,
    )
    style_ax(
        axes[0],
        title=(
            f"Built-up growth"
            f" {first_year}–{last_year}"
        ),
    )

    decline = np.maximum(-growth, 0)
    if decline.max() > 0:
        spatial_imshow(
            axes[1], decline, d.ocean_mask, "PuRd",
            log=True,
            cbar_label="log(1 + decline m²)",
            fig=fig,
        )
    else:
        axes[1].text(
            0.5, 0.5, "No decline detected",
            ha="center", va="center", fontsize=14,
            transform=axes[1].transAxes,
        )
        axes[1].set_xlim(*EXTENT[:2])
        axes[1].set_ylim(*EXTENT[2:])

    style_ax(
        axes[1],
        title=(
            f"Built-up decline"
            f" {first_year}–{last_year}"
        ),
    )

    fig.tight_layout()
    save_plot(fig, out, "06_growth_map.png")


def plot_trajectories(
    d: PrecomputedData, out: Path,
) -> None:
    """07 — Top-12 most built-up cells over time."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        4, 3, figsize=FIG_PANEL_4x3, sharex=True,
        gridspec_kw={"hspace": 0.35, "wspace": 0.25},
    )
    for k, ax in enumerate(axes.flat):
        ax.plot(
            d.dates, d.top_ts[k] / 1e6,
            color=COLOR_ACCENT, linewidth=1,
        )
        ax.fill_between(
            d.dates, d.top_ts[k] / 1e6,
            color=COLOR_ACCENT, alpha=0.3, linewidth=0,
        )

        label = cell_to_label(
            int(d.top_rows[k]), int(d.top_cols[k]),
            d.n_h, d.n_w,
        )
        peak = d.top_ts[k].max()
        style_ax(
            ax,
            title=f"{label} ({peak / 1e6:.1f}M m²)",
        )
        ax.set_xlim(d.dates[0], d.dates[-1])
        ax.set_ylim(bottom=0)

    fig.suptitle(
        "GHS-BUILT-S: 12 most built-up cells",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "07_trajectories.png")


def plot_concentration(
    d: PrecomputedData, out: Path,
) -> None:
    """08 — Lorenz curve for spatial built-up concentration."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = np.sort(
        d.latest_built[~d.ocean_mask].ravel(),
    )
    if len(land_vals) == 0 or land_vals.sum() == 0:
        return

    n_land = len(land_vals)
    cum_share = np.cumsum(land_vals) / land_vals.sum()
    x_pct = np.arange(1, n_land + 1) / n_land

    gini = (
        1.0 - 2.0 * np.trapezoid(cum_share, dx=1 / n_land)
    )

    idx_90 = np.searchsorted(cum_share, 0.10)
    pct_cells = (n_land - idx_90) / n_land * 100
    pct_str = (
        f"{pct_cells:.2f}%"
        if pct_cells < 1.0
        else f"{pct_cells:.1f}%"
    )

    fig, ax = plt.subplots(figsize=FIG_HALF)
    ax.plot(
        x_pct * 100, cum_share * 100,
        color="black", linewidth=1.5,
    )
    ax.plot(
        [0, 100], [0, 100], color="#AAAAAA",
        linewidth=0.8, linestyle="--",
    )
    style_ax(
        ax,
        title="Concentration of global built-up area",
        xlabel="Cumulative % of land cells (ranked)",
        ylabel="Cumulative % of total built area",
    )
    ax.text(
        15, 85, f"Gini = {gini:.3f}",
        fontsize=13, fontweight="bold",
    )
    ax.text(
        15, 78,
        f"{pct_str} of cells hold\n"
        "90% of global built-up area",
        fontsize=FONT_LABEL, color="#444444",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    save_plot(fig, out, "08_concentration.png")


def plot_spot_checks(
    d: PrecomputedData, out: Path,
) -> None:
    """09 — Spot-check known locations."""
    import matplotlib.pyplot as plt

    rows_data = []
    for name, lat, lon in SPOT_CHECK_LOCATIONS:
        row = int((lat + 90.0) / (180.0 / d.n_h))
        col = int((lon + 180.0) / (360.0 / d.n_w))
        row = max(0, min(row, d.n_h - 1))
        col = max(0, min(col, d.n_w - 1))

        built = d.latest_built[row, col]
        first_built = d.grid[0, row, col, d.built_idx]

        is_urban = name not in (
            "Sahara", "Pacific Ocean", "Amazon interior",
        )
        if is_urban:
            status = "PASS" if built > 0 else "INVESTIGATE"
        else:
            status = (
                "PASS" if built < 1000 else "INVESTIGATE"
            )

        growth = ""
        if first_built > 0:
            growth = (
                f"{(built / first_built - 1) * 100:+.0f}%"
            )
        elif built > 0:
            growth = "new"

        rows_data.append([
            name,
            f"({row}, {col})",
            f"{built:,.0f}",
            growth,
            status,
        ])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis("off")

    col_labels = [
        "Location", "Cell (r,c)", "Built area (m²)",
        "Growth", "Status",
    ]
    table = ax.table(
        cellText=rows_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    for j, row in enumerate(rows_data):
        status = row[-1]
        color = (
            "#D5F5E3" if status == "PASS" else "#FADBD8"
        )
        for col_idx in range(len(col_labels)):
            table[j + 1, col_idx].set_facecolor(color)

    for col_idx in range(len(col_labels)):
        table[0, col_idx].set_facecolor("#D5DBDB")
        table[0, col_idx].set_text_props(
            fontweight="bold",
        )

    ax.set_title(
        "Spot-check: known locations on PRIO-GRID",
        fontsize=FONT_TITLE, fontweight="bold", pad=20,
    )
    save_plot(fig, out, "09_spot_checks.png")


def plot_calendar_heatmap(
    d: PrecomputedData, out: Path,
) -> None:
    """10 — Year x Month heatmap showing transitions."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_years = (d.n_t + 11) // 12
    cal = np.full((n_years, 12), np.nan, dtype=np.float64)
    for t in range(d.n_t):
        cal[t // 12, t % 12] = d.monthly_built[t] / 1e9

    fig, ax = plt.subplots(figsize=(7, 12))
    im = ax.imshow(
        cal, cmap=CMAP_BUILT,
        aspect="auto", interpolation="nearest",
    )
    ax.set_xticks(range(12))
    ax.set_xticklabels(
        ["J", "F", "M", "A", "M", "J",
         "J", "A", "S", "O", "N", "D"],
        fontsize=FONT_TICK,
    )
    ax.set_yticks(range(n_years))
    ax.set_yticklabels(
        [str(d.start_year + y) for y in range(n_years)],
        fontsize=7,
    )
    style_ax(
        ax,
        title=(
            "GHS-BUILT-S global built area"
            " by calendar month"
        ),
        xlabel="Month",
        ylabel="Year",
    )
    ax.set_xticks(
        [x - 0.5 for x in range(13)], minor=True,
    )
    ax.set_yticks(
        [y - 0.5 for y in range(n_years + 1)], minor=True,
    )
    ax.grid(
        which="minor", color="#DDDDDD", linewidth=0.5,
    )
    ax.tick_params(
        which="minor", bottom=False, left=False,
    )
    plt.colorbar(
        im, ax=ax, shrink=0.4,
        label="Built area (billion m²)",
    )
    save_plot(fig, out, "10_calendar_heatmap.png")


# -- Summary -------------------------------------------------------


def print_summary(d: PrecomputedData) -> bool:
    print()
    print("=" * 60)
    print("GHS-BUILT-S GRID VERIFICATION SUMMARY")
    print("=" * 60)
    print()
    print(
        f"Grid shape:  [{d.n_t}, {d.n_h},"
        f" {d.n_w}, {d.n_f}]"
    )
    print(
        f"Temporal:    {d.start_year}-01 to "
        f"{d.start_year + d.n_t // 12}-12"
    )
    print(f"Features:    {d.features}")
    print()

    print("Epoch totals:")
    for year in sorted(d.epoch_totals):
        total = d.epoch_totals[year]
        expected = KNOWN_GLOBAL_BUILT_AREA.get(year)
        if expected:
            ratio = total / expected
            marker = (
                "ok" if 0.5 <= ratio <= 2.0 else "DRIFT"
            )
            print(
                f"  {year}: {total / 1e9:>7.1f}B m²  "
                f"(ref ~{expected / 1e9:.1f}B m², "
                f"ratio {ratio:.3f} [{marker}])"
            )
        else:
            print(f"  {year}: {total / 1e9:>7.1f}B m²")
    print()

    print("Statistical checks:")
    all_pass = True
    details = {
        k[1:]: v for k, v in d.checks.items()
        if k.startswith("_")
    }
    for name, value in d.checks.items():
        if name.startswith("_"):
            continue
        status = "PASS" if value else "INVESTIGATE"
        marker = "  [+]" if value else "  [!]"
        suffix = ""
        for dk, dv in details.items():
            if dk.startswith(name.split("_")[0]):
                suffix = f" -- {dv}"
                break
        print(f"{marker} {name}: {status}{suffix}")
        if not value:
            all_pass = False

    print()
    if all_pass:
        print("VERDICT: PASS -- all checks passed")
    else:
        print(
            "VERDICT: INVESTIGATE"
            " -- some checks need review"
        )
    print("=" * 60)

    return all_pass


# -- Orchestrator ---------------------------------------------------


PLOTS: list[tuple[str, object]] = [
    ("Built-up Density", plot_built_density),
    ("Cumulative Density", plot_cumulative_density),
    ("Epoch Totals", plot_epoch_totals),
    ("Monthly Time Series", plot_monthly_timeseries),
    ("Epoch Comparison", plot_epoch_comparison),
    ("Growth Map", plot_growth_map),
    ("Trajectories", plot_trajectories),
    ("Concentration", plot_concentration),
    ("Spot Checks", plot_spot_checks),
    ("Calendar Heatmap", plot_calendar_heatmap),
]


def main() -> int:
    sys.stdout.reconfigure(  # type: ignore[attr-defined]
        line_buffering=True,
    )

    parser = argparse.ArgumentParser(
        description=(
            "GHS-BUILT-S grid verification audit"
        ),
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/compiled/ghsbuilts"),
        help="Compiled GHS-BUILT-S grid directory",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/audit_ghsbuilts"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        print(
            "Run the GHS-BUILT-S pipeline first: "
            "python scripts/run_ghsbuilts_pipeline.py"
        )
        return 1

    import matplotlib
    matplotlib.use("Agg")
    import numpy as np

    features = json.loads(
        (args.input / "feature_names.json").read_text(),
    )
    time_steps = np.load(args.input / "time_steps.npy")
    grid = np.load(grid_path, mmap_mode="r")

    start_year = int(str(time_steps[0])[:4])

    print(
        f"Grid: [T={grid.shape[0]}, H={grid.shape[1]}, "
        f"W={grid.shape[2]}, F={grid.shape[3]}]"
    )
    print(f"Features: {features}")
    print(
        f"Temporal: {start_year}-01 to "
        f"{start_year + grid.shape[0] // 12}-12"
    )
    print()

    args.output.mkdir(parents=True, exist_ok=True)

    print(
        "Precomputing aggregates (1 pass over grid)...",
    )
    data = precompute(grid, features, start_year)
    print(
        f"  Latest global built area: "
        f"{data.monthly_built[-1] / 1e9:.1f}B m²"
    )
    print(
        f"  Epochs detected:   "
        f"{sorted(data.epoch_time_indices.keys())}"
    )
    print()

    for i, (name, fn) in enumerate(PLOTS, 1):
        print(f"Plot {i:02d}: {name}...")
        fn(data, args.output)

    all_pass = print_summary(data)

    print()
    print(
        f"All {len(PLOTS)} plots saved to {args.output}/"
    )

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
