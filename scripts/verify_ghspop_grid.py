#!/usr/bin/env python3
"""GHS-POP grid verification — 10 plots + statistical checks proving
spatial, temporal, and structural correctness before release tagging.

Usage:
    uv run python scripts/verify_ghspop_grid.py
    uv run python scripts/verify_ghspop_grid.py --input data/compiled/ghspop

Reads the compiled GHS-POP grid and produces PNG plots to
``reports/audit_ghspop/`` plus a statistical summary on stdout.

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

CMAP_POP = "YlGnBu"

KNOWN_WORLD_POP: dict[int, float] = {
    1975: 4.1e9,
    1980: 4.4e9,
    1985: 4.8e9,
    1990: 5.3e9,
    1995: 5.7e9,
    2000: 6.1e9,
    2005: 6.5e9,
    2010: 6.9e9,
    2015: 7.4e9,
    2020: 7.8e9,
    2025: 8.0e9,
    2030: 8.5e9,
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
    ("Amazon", -3.0, -60.0),
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
                print("  Ocean mask: from assembled grid landarea")
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

    pop_idx: int

    monthly_pop: np.ndarray       # (T,) global total each month
    total_pop: np.ndarray          # (H, W) summed over all months
    latest_pop: np.ndarray         # (H, W) last time step

    epoch_pops: dict[int, float]
    epoch_time_indices: dict[int, int]

    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray             # (12, T)

    checks: dict[str, bool | str]


def _detect_epochs(monthly_pop: np.ndarray, start_year: int) -> dict[int, int]:
    """Find time indices where global population changes (step boundaries)."""
    import numpy as np

    transitions: dict[int, int] = {}
    transitions[start_year] = 0
    for t in range(1, len(monthly_pop)):
        if not np.isclose(monthly_pop[t], monthly_pop[t - 1], rtol=1e-6):
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
    pop_idx = features.index("ghspop_pop_count")

    ocean_mask = _load_ocean_mask(n_h, n_w)

    monthly_pop = np.zeros(n_t, dtype=np.float64)
    total_pop = np.zeros((n_h, n_w), dtype=np.float64)

    has_nan = False
    has_negative = False

    for t in range(n_t):
        sl = grid[t, :, :, pop_idx].astype(np.float64)
        monthly_pop[t] = sl.sum()
        total_pop += sl
        if np.isnan(sl).any():
            has_nan = True
        if (sl < 0).any():
            has_negative = True

    latest_pop = grid[n_t - 1, :, :, pop_idx].astype(np.float64)

    epoch_time_indices = _detect_epochs(monthly_pop, start_year)
    epoch_pops: dict[int, float] = {}
    for year, t_idx in epoch_time_indices.items():
        epoch_pops[year] = float(monthly_pop[t_idx])

    flat_idx = np.argsort(latest_pop.ravel())[-12:][::-1]
    top_rows = flat_idx // n_w
    top_cols = flat_idx % n_w
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = float(grid[t, r, c, pop_idx])

    ocean_pop = float(latest_pop[ocean_mask].sum()) if ocean_mask.any() else 0.0
    total_latest = float(latest_pop.sum())
    ocean_pct = ocean_pop / total_latest * 100 if total_latest > 0 else 0.0

    antarctic_pop = float(latest_pop[:60, :].sum())

    pop_sanity = {}
    for year, pop in epoch_pops.items():
        if year in KNOWN_WORLD_POP:
            expected = KNOWN_WORLD_POP[year]
            ratio = pop / expected
            pop_sanity[year] = (pop, expected, ratio)

    pop_within_range = all(
        0.85 <= ratio <= 1.15
        for _, _, ratio in pop_sanity.values()
    )

    n_land = int((~ocean_mask).sum()) if ocean_mask.any() else n_h * n_w
    n_populated = int((latest_pop > 0).sum())
    pop_coverage = n_populated / n_land * 100 if n_land > 0 else 0.0

    checks: dict[str, bool | str] = {
        "no_nan": not has_nan,
        "no_negatives": not has_negative,
        "ocean_pop_negligible": ocean_pct < 0.5,
        "no_antarctic_pop": antarctic_pop < 1e6,
        "pop_sanity_vs_known": pop_within_range,
        "spatial_coverage": pop_coverage > 30.0,
    }
    checks["_ocean_detail"] = (
        f"{ocean_pop:,.0f} persons in ocean cells ({ocean_pct:.4f}%)"
    )
    checks["_antarctic_detail"] = (
        f"{antarctic_pop:,.0f} persons below 60S"
    )
    checks["_coverage_detail"] = (
        f"{n_populated:,} of {n_land:,} land cells populated "
        f"({pop_coverage:.1f}%)"
    )
    if pop_sanity:
        lines = []
        for year in sorted(pop_sanity):
            actual, expected, ratio = pop_sanity[year]
            lines.append(
                f"{year}: {actual/1e9:.2f}B vs {expected/1e9:.1f}B "
                f"(ratio {ratio:.3f})"
            )
        checks["_pop_sanity_detail"] = "; ".join(lines)

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t, start_year=start_year),
        start_year=start_year,
        pop_idx=pop_idx,
        monthly_pop=monthly_pop,
        total_pop=total_pop,
        latest_pop=latest_pop,
        epoch_pops=epoch_pops,
        epoch_time_indices=epoch_time_indices,
        top_rows=top_rows,
        top_cols=top_cols,
        top_ts=top_ts,
        checks=checks,
    )


# -- Plot functions -------------------------------------------------


def plot_pop_density(d: PrecomputedData, out: Path) -> None:
    """01 — Global population density, latest epoch."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.latest_pop, d.ocean_mask, CMAP_POP,
        log=True, cbar_label="log(1 + population)", fig=fig,
    )
    latest_year = d.start_year + d.n_t // 12
    style_ax(
        ax,
        title=f"GHS-POP population density (latest: ~{latest_year})",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "01_pop_density.png")


def plot_cumulative_density(d: PrecomputedData, out: Path) -> None:
    """02 — Time-averaged population density."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    avg_pop = d.total_pop / d.n_t
    spatial_imshow(
        ax, avg_pop, d.ocean_mask, CMAP_POP,
        log=True, cbar_label="log(1 + avg monthly pop)", fig=fig,
    )
    style_ax(
        ax,
        title=(
            f"GHS-POP time-averaged population, "
            f"{d.start_year}–{d.start_year + d.n_t // 12}"
        ),
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "02_cumulative_density.png")


def plot_epoch_populations(d: PrecomputedData, out: Path) -> None:
    """03 — Population by epoch vs known world population."""
    import matplotlib.pyplot as plt

    years = sorted(d.epoch_pops.keys())
    pops = [d.epoch_pops[y] for y in years]

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.bar(years, [p / 1e9 for p in pops], width=3,
           color=COLOR_ACCENT, alpha=0.8, label="GHS-POP grid")

    known_years = sorted(KNOWN_WORLD_POP.keys())
    known_vals = [KNOWN_WORLD_POP[y] / 1e9 for y in known_years]
    ax.plot(known_years, known_vals, "o--", color="#C0392B",
            linewidth=1.5, markersize=5, label="UN estimates")

    for y, p in zip(years, pops, strict=True):
        ax.text(y, p / 1e9 + 0.15, f"{p / 1e9:.2f}B",
                ha="center", fontsize=FONT_ANNOT)

    style_ax(
        ax,
        title="GHS-POP epoch totals vs UN world population",
        xlabel="Year", ylabel="Population (billions)",
    )
    ax.legend(fontsize=FONT_LABEL, frameon=False)
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "03_epoch_populations.png")


def plot_monthly_time_series(d: PrecomputedData, out: Path) -> None:
    """04 — Monthly global population showing step transitions."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.plot(d.dates, d.monthly_pop / 1e9,
            color=COLOR_ACCENT, linewidth=1.5)

    for year, t_idx in d.epoch_time_indices.items():
        if 0 < t_idx < d.n_t:
            ax.axvline(d.dates[t_idx], color="#C0392B",
                       linewidth=0.8, linestyle="--", alpha=0.5)
            ax.text(d.dates[t_idx], ax.get_ylim()[1] * 0.98,
                    f" {year}", fontsize=7, color="#C0392B",
                    va="top", rotation=90)

    style_ax(
        ax,
        title="GHS-POP global population (step interpolation)",
        xlabel="Date", ylabel="Population (billions)",
    )
    ax.set_xlim(d.dates[0], d.dates[-1])
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "04_monthly_timeseries.png")


def plot_epoch_comparison(d: PrecomputedData, out: Path) -> None:
    """05 — Side-by-side spatial maps for available epochs."""
    import matplotlib.pyplot as plt
    import numpy as np

    sorted_epochs = sorted(d.epoch_time_indices.items())
    n_epochs = min(len(sorted_epochs), 3)
    if n_epochs == 0:
        return

    indices = [0, len(sorted_epochs) // 2, len(sorted_epochs) - 1]
    if n_epochs < 3:
        indices = list(range(n_epochs))
    selected = [sorted_epochs[i] for i in indices[:n_epochs]]

    fig, axes = plt.subplots(1, n_epochs, figsize=FIG_PANEL_1x3)
    if n_epochs == 1:
        axes = [axes]

    for ax, (year, t_idx) in zip(axes, selected, strict=True):
        pop_slice = d.grid[t_idx, :, :, d.pop_idx].astype(np.float64)
        total = pop_slice.sum()
        spatial_imshow(
            ax, pop_slice, d.ocean_mask, CMAP_POP,
            log=True, fig=fig,
        )
        style_ax(ax, title=f"{year} ({total / 1e9:.2f}B)")

    fig.suptitle(
        "GHS-POP population across epochs",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "05_epoch_comparison.png")


def plot_growth_map(d: PrecomputedData, out: Path) -> None:
    """06 — Population growth between first and last epoch."""
    import matplotlib.pyplot as plt
    import numpy as np

    sorted_epochs = sorted(d.epoch_time_indices.items())
    if len(sorted_epochs) < 2:
        return

    first_year, first_t = sorted_epochs[0]
    last_year, last_t = sorted_epochs[-1]

    pop_first = d.grid[first_t, :, :, d.pop_idx].astype(np.float64)
    pop_last = d.grid[last_t, :, :, d.pop_idx].astype(np.float64)

    growth = pop_last - pop_first

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    spatial_imshow(
        axes[0], np.maximum(growth, 0), d.ocean_mask, "YlOrRd",
        log=True, cbar_label="log(1 + growth)", fig=fig,
    )
    style_ax(
        axes[0],
        title=f"Population growth {first_year}–{last_year}",
    )

    decline = np.maximum(-growth, 0)
    if decline.max() > 0:
        spatial_imshow(
            axes[1], decline, d.ocean_mask, "PuRd",
            log=True, cbar_label="log(1 + decline)", fig=fig,
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
        title=f"Population decline {first_year}–{last_year}",
    )

    fig.tight_layout()
    save_plot(fig, out, "06_growth_map.png")


def plot_trajectories(d: PrecomputedData, out: Path) -> None:
    """07 — Top-12 most populated cells over time."""
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
        style_ax(ax, title=f"{label} ({peak / 1e6:.1f}M peak)")
        ax.set_xlim(d.dates[0], d.dates[-1])
        ax.set_ylim(bottom=0)

    fig.suptitle(
        "GHS-POP: 12 most populated cells",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "07_trajectories.png")


def plot_concentration(d: PrecomputedData, out: Path) -> None:
    """08 — Lorenz curve for spatial population concentration."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = np.sort(d.latest_pop[~d.ocean_mask].ravel())
    if len(land_vals) == 0 or land_vals.sum() == 0:
        return

    n_land = len(land_vals)
    cum_share = np.cumsum(land_vals) / land_vals.sum()
    x_pct = np.arange(1, n_land + 1) / n_land

    gini = 1.0 - 2.0 * np.trapezoid(cum_share, dx=1 / n_land)

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
        title="Concentration of global population",
        xlabel="Cumulative % of land cells (ranked)",
        ylabel="Cumulative % of total population",
    )
    ax.text(
        15, 85, f"Gini = {gini:.3f}",
        fontsize=13, fontweight="bold",
    )
    ax.text(
        15, 78,
        f"{pct_str} of cells hold\n90% of world population",
        fontsize=FONT_LABEL, color="#444444",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    save_plot(fig, out, "08_concentration.png")


def plot_spot_checks(d: PrecomputedData, out: Path) -> None:
    """09 — Spot-check known locations."""
    import matplotlib.pyplot as plt

    rows_data = []
    for name, lat, lon in SPOT_CHECK_LOCATIONS:
        row = int((lat + 90.0) / (180.0 / d.n_h))
        col = int((lon + 180.0) / (360.0 / d.n_w))
        row = max(0, min(row, d.n_h - 1))
        col = max(0, min(col, d.n_w - 1))

        pop = d.latest_pop[row, col]
        first_pop = d.grid[0, row, col, d.pop_idx]

        is_urban = name not in ("Sahara", "Pacific Ocean", "Amazon")
        if is_urban:
            status = "PASS" if pop > 100_000 else "INVESTIGATE"
        else:
            status = "PASS" if pop < 10_000 else "INVESTIGATE"

        growth = ""
        if first_pop > 0:
            growth = f"{(pop / first_pop - 1) * 100:+.0f}%"
        elif pop > 0:
            growth = "new"

        rows_data.append([
            name,
            f"({row}, {col})",
            f"{pop:,.0f}",
            growth,
            status,
        ])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis("off")

    col_labels = [
        "Location", "Cell (r,c)", "Population",
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
        color = "#D5F5E3" if status == "PASS" else "#FADBD8"
        for col_idx in range(len(col_labels)):
            table[j + 1, col_idx].set_facecolor(color)

    for col_idx in range(len(col_labels)):
        table[0, col_idx].set_facecolor("#D5DBDB")
        table[0, col_idx].set_text_props(fontweight="bold")

    ax.set_title(
        "Spot-check: known locations on PRIO-GRID",
        fontsize=FONT_TITLE, fontweight="bold", pad=20,
    )
    save_plot(fig, out, "09_spot_checks.png")


def plot_calendar_heatmap(d: PrecomputedData, out: Path) -> None:
    """10 — Year x Month heatmap showing step-function transitions."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_years = (d.n_t + 11) // 12
    cal = np.full((n_years, 12), np.nan, dtype=np.float64)
    for t in range(d.n_t):
        cal[t // 12, t % 12] = d.monthly_pop[t] / 1e9

    fig, ax = plt.subplots(figsize=(7, 12))
    im = ax.imshow(
        cal, cmap=CMAP_POP,
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
        title="GHS-POP global population by calendar month",
        xlabel="Month", ylabel="Year",
    )
    ax.set_xticks([x - 0.5 for x in range(13)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(n_years + 1)], minor=True)
    ax.grid(which="minor", color="#DDDDDD", linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    plt.colorbar(
        im, ax=ax, shrink=0.4, label="Population (billions)",
    )
    save_plot(fig, out, "10_calendar_heatmap.png")


# -- Summary -------------------------------------------------------


def print_summary(d: PrecomputedData) -> bool:
    print()
    print("=" * 60)
    print("GHS-POP GRID VERIFICATION SUMMARY")
    print("=" * 60)
    print()
    print(f"Grid shape:  [{d.n_t}, {d.n_h}, {d.n_w}, {d.n_f}]")
    print(f"Temporal:    {d.start_year}-01 to "
          f"{d.start_year + d.n_t // 12}-12")
    print(f"Features:    {d.features}")
    print()

    print("Epoch populations:")
    for year in sorted(d.epoch_pops):
        pop = d.epoch_pops[year]
        expected = KNOWN_WORLD_POP.get(year)
        if expected:
            ratio = pop / expected
            marker = "ok" if 0.85 <= ratio <= 1.15 else "DRIFT"
            print(f"  {year}: {pop / 1e9:>7.2f}B  "
                  f"(expected ~{expected / 1e9:.1f}B, "
                  f"ratio {ratio:.3f} [{marker}])")
        else:
            print(f"  {year}: {pop / 1e9:>7.2f}B")
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
        print("VERDICT: INVESTIGATE -- some checks need review")
    print("=" * 60)

    return all_pass


# -- Orchestrator ---------------------------------------------------


PLOTS: list[tuple[str, object]] = [
    ("Population Density", plot_pop_density),
    ("Cumulative Density", plot_cumulative_density),
    ("Epoch Populations", plot_epoch_populations),
    ("Monthly Time Series", plot_monthly_time_series),
    ("Epoch Comparison", plot_epoch_comparison),
    ("Growth Map", plot_growth_map),
    ("Trajectories", plot_trajectories),
    ("Concentration", plot_concentration),
    ("Spot Checks", plot_spot_checks),
    ("Calendar Heatmap", plot_calendar_heatmap),
]


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="GHS-POP grid verification audit",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/compiled/ghspop"),
        help="Compiled GHS-POP grid directory",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/audit_ghspop"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        print(
            "Run the GHS-POP pipeline first: "
            "python scripts/run_ghspop_pipeline.py"
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

    print(f"Grid: [T={grid.shape[0]}, H={grid.shape[1]}, "
          f"W={grid.shape[2]}, F={grid.shape[3]}]")
    print(f"Features: {features}")
    print(f"Temporal: {start_year}-01 to "
          f"{start_year + grid.shape[0] // 12}-12")
    print()

    args.output.mkdir(parents=True, exist_ok=True)

    print("Precomputing aggregates (1 pass over grid)...")
    data = precompute(grid, features, start_year)
    print(f"  Latest global pop: "
          f"{data.monthly_pop[-1] / 1e9:.2f}B")
    print(f"  Epochs detected:   "
          f"{sorted(data.epoch_time_indices.keys())}")
    print()

    for i, (name, fn) in enumerate(PLOTS, 1):
        print(f"Plot {i:02d}: {name}...")
        fn(data, args.output)

    all_pass = print_summary(data)

    print()
    print(f"All {len(PLOTS)} plots saved to {args.output}/")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
