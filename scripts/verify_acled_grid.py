#!/usr/bin/env python3
"""ACLED grid verification — 13 plots + statistical checks proving
spatial, temporal, and structural correctness before release tagging.

Usage:
    uv run python scripts/verify_acled_grid.py
    uv run python scripts/verify_acled_grid.py --input data/compiled/acled

Reads the compiled ACLED grid and produces PNG plots to
``reports/audit_acled/`` plus a statistical summary on stdout.

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
    CMAP_HEAT,
    CMAP_SEQ,
    COLOR_ACCENT,
    COLOR_BATTLES,
    COLOR_EXPLOSIONS,
    COLOR_GRAY,
    COLOR_PROTESTS,
    COLOR_RIOTS,
    COLOR_STRATEGIC,
    COLOR_VAC,
    EXTENT,
    FIG_FULL,
    FIG_HALF,
    FIG_PANEL_4x3,
    FIG_TALL,
    FONT_ANNOT,
    FONT_LABEL,
    FONT_TICK,
    FONT_TITLE,
    make_dates,
    save_plot,
    spatial_imshow,
    style_ax,
)

ACLED_TYPE_NAMES = [
    "Battles",
    "Explosions",
    "VaC",
    "Protests",
    "Riots",
    "Strategic",
]

ACLED_TYPE_COLORS = [
    COLOR_BATTLES,
    COLOR_EXPLOSIONS,
    COLOR_VAC,
    COLOR_PROTESTS,
    COLOR_RIOTS,
    COLOR_STRATEGIC,
]

REGION_BOUNDS: list[tuple[tuple[int, int], tuple[int, int], str]] = [
    ((32, 38), (35, 42), "Syria"),
    ((29, 36), (42, 48), "Iraq"),
    ((5, 15), (33, 43), "Ethiopia"),
    ((-6, 6), (25, 32), "DRC"),
    ((-2, 12), (41, 52), "Somalia"),
    ((13, 28), (68, 82), "India"),
    ((30, 38), (64, 72), "Afghanistan"),
    ((15, 25), (93, 102), "Myanmar"),
    ((-5, 12), (-80, -72), "Colombia"),
    ((3, 15), (1, 15), "Nigeria"),
    ((10, 20), (40, 50), "Yemen"),
    ((-20, -10), (28, 42), "Mozambique"),
    ((3, 8), (30, 35), "South Sudan"),
    ((30, 42), (55, 65), "Pakistan"),
    ((46, 52), (28, 40), "Ukraine"),
    ((-15, -5), (28, 36), "Madagascar"),
    ((0, 10), (-5, 5), "Ghana/Togo"),
    ((4, 14), (2, 12), "Cameroon"),
]

SPOT_CHECK_LOCATIONS = [
    ("Mogadishu", 2.05, 45.3),
    ("Aleppo", 36.2, 37.15),
    ("Kabul", 34.5, 69.2),
    ("Lagos", 6.5, 3.4),
    ("Kyiv", 50.4, 30.5),
    ("Bogota", 4.6, -74.1),
    ("Bamako", 12.6, -8.0),
    ("Khartoum", 15.6, 32.5),
]


def cell_to_label(
    row: int, col: int, n_h: int, n_w: int,
) -> str:
    """Map grid cell to approximate region name."""
    lat = -90.0 + (row + 0.5) * (180.0 / n_h)
    lon = -180.0 + (col + 0.5) * (360.0 / n_w)
    for (lat_lo, lat_hi), (lon_lo, lon_hi), name in REGION_BOUNDS:
        if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi:
            return name
    lat_s = f"{abs(lat):.0f}°{'N' if lat >= 0 else 'S'}"
    lon_s = f"{abs(lon):.0f}°{'E' if lon >= 0 else 'W'}"
    return f"{lat_s}, {lon_s}"


# ── Data loading and precomputation ──────────────────────────


def _load_ocean_mask(n_h: int, n_w: int) -> np.ndarray:
    """Load ocean mask from assembled grid landarea or fallback."""
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
    """All derived arrays from the compiled ACLED grid."""

    grid: np.ndarray
    features: list[str]
    n_t: int
    n_h: int
    n_w: int
    n_f: int
    ocean_mask: np.ndarray
    dates: list[dt.date]
    start_year: int

    # Feature indices
    count_idx: int
    battles_idx: int
    explosions_idx: int
    vac_idx: int
    protests_idx: int
    riots_idx: int
    strategic_idx: int
    fatalities_idx: int

    # Monthly global totals (T,)
    monthly_count: np.ndarray
    monthly_types: np.ndarray  # (T, 6)
    monthly_fatalities: np.ndarray

    # Spatial aggregates (H, W)
    total_count: np.ndarray
    total_fatalities: np.ndarray
    spatial_types: np.ndarray  # (6, H, W)

    # Structural invariant residual (H, W)
    type_sum_residual: np.ndarray

    # Top-12 hotspot trajectories
    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray  # (12, T)

    # Statistical checks
    checks: dict[str, bool]


def precompute(
    grid: np.ndarray,
    features: list[str],
    start_year: int,
) -> PrecomputedData:
    """Single pass over the mmap grid."""
    import numpy as np

    n_t, n_h, n_w, n_f = grid.shape

    count_idx = features.index("acled_count")
    battles_idx = features.index("acled_battles")
    explosions_idx = features.index("acled_explosions")
    vac_idx = features.index("acled_vac")
    protests_idx = features.index("acled_protests")
    riots_idx = features.index("acled_riots")
    strategic_idx = features.index("acled_strategic")
    fatalities_idx = features.index("acled_fatalities")

    type_indices = [
        battles_idx, explosions_idx, vac_idx,
        protests_idx, riots_idx, strategic_idx,
    ]

    ocean_mask = _load_ocean_mask(n_h, n_w)

    monthly_count = np.zeros(n_t, dtype=np.float64)
    monthly_fatalities = np.zeros(n_t, dtype=np.float64)
    monthly_types = np.zeros((n_t, 6), dtype=np.float64)

    total_count = np.zeros((n_h, n_w), dtype=np.float64)
    total_fatalities = np.zeros((n_h, n_w), dtype=np.float64)
    spatial_types = np.zeros((6, n_h, n_w), dtype=np.float64)

    type_sum_residual = np.zeros((n_h, n_w), dtype=np.float64)

    has_nan = False
    has_negative = False

    for t in range(n_t):
        cnt = grid[t, :, :, count_idx].astype(np.float64)
        fat = grid[t, :, :, fatalities_idx].astype(np.float64)

        monthly_count[t] = cnt.sum()
        monthly_fatalities[t] = fat.sum()
        total_count += cnt
        total_fatalities += fat

        type_sum = np.zeros((n_h, n_w), dtype=np.float64)
        for j, tidx in enumerate(type_indices):
            tv = grid[t, :, :, tidx].astype(np.float64)
            monthly_types[t, j] = tv.sum()
            spatial_types[j] += tv
            type_sum += tv

        type_sum_residual += np.abs(type_sum - cnt)

        sl = grid[t, :, :, :]
        if np.isnan(sl).any():
            has_nan = True
        if (sl < 0).any():
            has_negative = True

    # Top-12 hotspot cells by total event count
    flat_idx = np.argsort(total_count.ravel())[-12:][::-1]
    top_rows = flat_idx // n_w
    top_cols = flat_idx % n_w
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = float(grid[t, r, c, count_idx])

    # Statistical checks
    invariant_ok = float(type_sum_residual.sum()) == 0.0

    ocean_events = 0
    ocean_cells = 0
    if ocean_mask.any():
        ocean_count = total_count[ocean_mask]
        ocean_events = int(ocean_count.sum())
        ocean_cells = int((ocean_count > 0).sum())

    antarctic_events = int(total_count[:60, :].sum())

    annual_counts = []
    months_per_year = 12
    for y_offset in range(n_t // months_per_year):
        t0 = y_offset * months_per_year
        t1 = t0 + months_per_year
        annual_counts.append(monthly_count[t0:t1].sum())

    annual_in_range = all(
        50_000 <= ac <= 500_000 for ac in annual_counts
        if ac > 0
    )

    active_range = monthly_count > 0
    empty_in_active = False
    if active_range.any():
        first_active = int(np.argmax(active_range))
        last_active = n_t - 1 - int(
            np.argmax(active_range[::-1])
        )
        for t in range(first_active, last_active + 1):
            if monthly_count[t] == 0:
                empty_in_active = True
                break

    continent_rows = {
        "Africa": (110, 255),
        "Europe": (250, 325),
        "Asia": (180, 340),
        "Americas": (70, 350),
    }
    continents_with_events = 0
    for _, (r0, r1) in continent_rows.items():
        r0c = max(0, min(r0, n_h))
        r1c = max(0, min(r1, n_h))
        if total_count[r0c:r1c, :].sum() > 0:
            continents_with_events += 1

    total_events = float(monthly_count.sum())
    ocean_pct = (
        ocean_events / total_events * 100
        if total_events > 0 else 0.0
    )

    checks = {
        "no_nan": not has_nan,
        "no_negatives": not has_negative,
        "type_sum_invariant": invariant_ok,
        "ocean_events_negligible": ocean_pct < 1.0,
        "no_antarctic_events": antarctic_events < 100,
        "annual_count_range": annual_in_range,
        "no_empty_months": not empty_in_active,
        "spatial_extent": continents_with_events >= 4,
    }

    checks["_ocean_detail"] = (  # type: ignore[assignment]
        f"{ocean_events:,} events in {ocean_cells} cells "
        f"({ocean_pct:.2f}%)"
    )
    checks["_antarctic_detail"] = (  # type: ignore[assignment]
        f"{antarctic_events} events below -60° lat"
    )

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t, start_year=start_year),
        start_year=start_year,
        count_idx=count_idx,
        battles_idx=battles_idx,
        explosions_idx=explosions_idx,
        vac_idx=vac_idx,
        protests_idx=protests_idx,
        riots_idx=riots_idx,
        strategic_idx=strategic_idx,
        fatalities_idx=fatalities_idx,
        monthly_count=monthly_count,
        monthly_types=monthly_types,
        monthly_fatalities=monthly_fatalities,
        total_count=total_count,
        total_fatalities=total_fatalities,
        spatial_types=spatial_types,
        type_sum_residual=type_sum_residual,
        top_rows=top_rows,
        top_cols=top_cols,
        top_ts=top_ts,
        checks=checks,
    )


# ── Plot functions ───────────────────────────────────────────


def plot_event_density(d: PrecomputedData, out: Path) -> None:
    """01 — Global event density heatmap."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.total_count, d.ocean_mask, CMAP_SEQ,
        log=True, cbar_label="log(1 + events)", fig=fig,
    )
    yr_end = d.start_year + d.n_t // 12
    style_ax(
        ax,
        title=f"ACLED total events, {d.start_year}–{yr_end}",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "01_event_density.png")


def plot_fatalities_spatial(
    d: PrecomputedData, out: Path,
) -> None:
    """02 — Fatalities spatial heatmap."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.total_fatalities, d.ocean_mask, CMAP_HEAT,
        log=True, cbar_label="log(1 + fatalities)", fig=fig,
    )
    yr_end = d.start_year + d.n_t // 12
    style_ax(
        ax,
        title=(
            f"ACLED fatalities, {d.start_year}–{yr_end}"
        ),
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "02_fatalities_spatial.png")


def plot_per_type_spatial(
    d: PrecomputedData, out: Path,
) -> None:
    """03 — Per-type spatial maps (2x3 panel)."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    for j, (ax, name, _color) in enumerate(
        zip(axes.flat, ACLED_TYPE_NAMES, ACLED_TYPE_COLORS,
            strict=True),
    ):
        spatial_imshow(
            ax, d.spatial_types[j], d.ocean_mask, CMAP_SEQ,
            log=True, fig=fig,
        )
        total = d.spatial_types[j].sum()
        style_ax(
            ax,
            title=f"{name} ({total:,.0f} total)",
        )

    yr_end = d.start_year + d.n_t // 12
    fig.suptitle(
        f"ACLED events by type, {d.start_year}–{yr_end}",
        fontsize=FONT_TITLE, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    save_plot(fig, out, "03_per_type_spatial.png")


def plot_monthly_counts(
    d: PrecomputedData, out: Path,
) -> None:
    """04 — Monthly event counts, stacked by type."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.stackplot(
        d.dates,
        [d.monthly_types[:, j] for j in range(6)],
        labels=ACLED_TYPE_NAMES,
        colors=ACLED_TYPE_COLORS,
        alpha=0.85,
    )
    style_ax(
        ax,
        title="ACLED monthly events by type",
        xlabel="Date", ylabel="Event count",
    )
    ax.legend(
        loc="upper left", fontsize=FONT_ANNOT, frameon=False,
    )
    ax.set_xlim(d.dates[0], d.dates[-1])
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "04_monthly_counts.png")


def plot_monthly_fatalities(
    d: PrecomputedData, out: Path,
) -> None:
    """05 — Monthly fatalities time series."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.fill_between(
        d.dates, d.monthly_fatalities,
        color=COLOR_BATTLES, alpha=0.6, linewidth=0,
    )
    ax.plot(
        d.dates, d.monthly_fatalities,
        color=COLOR_ACCENT, linewidth=0.5,
    )
    style_ax(
        ax,
        title="ACLED monthly fatalities (all types)",
        xlabel="Date", ylabel="Fatalities",
    )
    ax.set_xlim(d.dates[0], d.dates[-1])
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "05_monthly_fatalities.png")


def plot_annual_scale(
    d: PrecomputedData, out: Path,
) -> None:
    """06 — Annual event totals with expected range."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_years = d.n_t // 12
    annual = np.zeros(n_years, dtype=np.float64)
    for y in range(n_years):
        t0 = y * 12
        annual[y] = d.monthly_count[t0:t0 + 12].sum()

    years = list(range(d.start_year, d.start_year + n_years))

    fig, ax = plt.subplots(figsize=FIG_FULL)
    ax.bar(years, annual, color=COLOR_ACCENT, alpha=0.8)

    ax.axhspan(
        50_000, 500_000, color="#2ECC71", alpha=0.08,
        label="Expected range (50k–500k)",
    )
    for y_idx, count in enumerate(annual):
        if count > 0:
            ax.text(
                years[y_idx], count + annual.max() * 0.02,
                f"{count:,.0f}",
                ha="center", fontsize=7, rotation=45,
            )

    style_ax(
        ax,
        title="ACLED annual event totals",
        xlabel="Year", ylabel="Total events",
    )
    ax.legend(fontsize=FONT_ANNOT, frameon=False)
    ax.set_ylim(bottom=0)
    save_plot(fig, out, "06_annual_scale.png")


def plot_type_proportions(
    d: PrecomputedData, out: Path,
) -> None:
    """07 — Relative share of each event type."""
    import matplotlib.pyplot as plt
    import numpy as np

    totals = np.array([
        d.monthly_types[:, j].sum() for j in range(6)
    ])
    grand_total = totals.sum()
    if grand_total == 0:
        return
    pcts = totals / grand_total * 100

    fig, ax = plt.subplots(figsize=(10, 5))
    y_pos = np.arange(6)
    ax.barh(
        y_pos, pcts, color=ACLED_TYPE_COLORS, alpha=0.85,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ACLED_TYPE_NAMES, fontsize=FONT_LABEL)
    for j, (pct, total) in enumerate(zip(pcts, totals, strict=True)):
        ax.text(
            pct + 0.5, j,
            f"{pct:.1f}% ({total:,.0f})",
            va="center", fontsize=FONT_ANNOT,
        )
    style_ax(
        ax,
        title="ACLED event type distribution (all time)",
        xlabel="Share (%)",
    )
    ax.set_xlim(0, max(pcts) * 1.3)
    save_plot(fig, out, "07_type_proportions.png")


def plot_fatality_correlation(
    d: PrecomputedData, out: Path,
) -> None:
    """08 — Correlation of fatalities with each type."""
    import matplotlib.pyplot as plt
    import numpy as np

    land = ~d.ocean_mask
    fat_flat = d.total_fatalities[land].ravel()

    if fat_flat.sum() == 0:
        return

    correlations = []
    for j in range(6):
        type_flat = d.spatial_types[j][land].ravel()
        if type_flat.std() > 0 and fat_flat.std() > 0:
            r = float(np.corrcoef(fat_flat, type_flat)[0, 1])
        else:
            r = 0.0
        correlations.append(r)

    fig, ax = plt.subplots(figsize=(10, 5))
    y_pos = list(range(6))
    colors = [
        "#C0392B" if abs(r) > 0.3 and j >= 3
        else "#2ECC71" if j < 3
        else ACLED_TYPE_COLORS[j]
        for j, r in enumerate(correlations)
    ]
    ax.barh(y_pos, correlations, color=colors, alpha=0.85)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ACLED_TYPE_NAMES, fontsize=FONT_LABEL)
    for j, r in enumerate(correlations):
        ax.text(
            r + 0.01 if r >= 0 else r - 0.05, j,
            f"r={r:.3f}", va="center", fontsize=FONT_ANNOT,
        )
    style_ax(
        ax,
        title="Correlation: cell-level fatalities vs event type count",
        xlabel="Pearson r",
    )
    ax.axvline(0, color=COLOR_GRAY, linewidth=0.5)
    save_plot(fig, out, "08_fatality_correlation.png")


def plot_structural_invariant(
    d: PrecomputedData, out: Path,
) -> None:
    """09 — Type sum == total count invariant check."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=FIG_FULL)
    residual_sum = d.type_sum_residual.sum()

    if residual_sum == 0.0:
        display = np.flipud(
            np.where(d.ocean_mask, np.nan, 0.0),
        )
        ax.imshow(
            display, cmap="Greens", aspect="auto",
            extent=EXTENT, vmin=0, vmax=1,
        )
        ax.text(
            0, 0, "PASS: invariant holds everywhere",
            ha="center", va="center",
            fontsize=16, fontweight="bold", color="#27AE60",
            transform=ax.transAxes,
        )
    else:
        spatial_imshow(
            ax, d.type_sum_residual, d.ocean_mask,
            "RdYlGn_r", fig=fig,
            cbar_label="abs(sum_types - total)",
        )

    style_ax(
        ax,
        title="Structural invariant: sum(6 types) == total_count",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "09_structural_invariant.png")


def plot_calendar_heatmap(
    d: PrecomputedData, out: Path,
) -> None:
    """10 — Year x Month heatmap of global event count."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_years = (d.n_t + 11) // 12
    cal = np.full((n_years, 12), np.nan, dtype=np.float64)
    for t in range(d.n_t):
        cal[t // 12, t % 12] = d.monthly_count[t]

    fig, ax = plt.subplots(figsize=FIG_TALL)
    im = ax.imshow(
        np.log1p(cal), cmap=CMAP_HEAT,
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
        title="ACLED global events by calendar month",
        xlabel="Month", ylabel="Year",
    )
    ax.set_xticks([x - 0.5 for x in range(13)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(n_years + 1)], minor=True)
    ax.grid(which="minor", color="#DDDDDD", linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    plt.colorbar(
        im, ax=ax, shrink=0.4, label="log(1 + events)",
    )
    save_plot(fig, out, "10_calendar_heatmap.png")


def plot_trajectories(
    d: PrecomputedData, out: Path,
) -> None:
    """11 — Top-12 hotspot cell trajectories."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        4, 3, figsize=FIG_PANEL_4x3, sharex=True,
        gridspec_kw={"hspace": 0.35, "wspace": 0.25},
    )
    for k, ax in enumerate(axes.flat):
        ax.fill_between(
            d.dates, d.top_ts[k],
            color=COLOR_BATTLES, alpha=0.6, linewidth=0,
        )
        ax.plot(
            d.dates, d.top_ts[k],
            color=COLOR_ACCENT, linewidth=0.5,
        )

        label = cell_to_label(
            int(d.top_rows[k]), int(d.top_cols[k]),
            d.n_h, d.n_w,
        )
        total_k = d.total_count[
            d.top_rows[k], d.top_cols[k]
        ]
        style_ax(ax, title=f"{label}  ({total_k:,.0f} total)")
        ax.set_xlim(d.dates[0], d.dates[-1])
        ax.set_ylim(bottom=0)

    yr_end = d.start_year + d.n_t // 12
    fig.suptitle(
        f"ACLED hotspots: 12 most active cells, "
        f"{d.start_year}–{yr_end}",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "11_trajectories.png")


def plot_concentration(
    d: PrecomputedData, out: Path,
) -> None:
    """12 — Lorenz curve for spatial concentration."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = np.sort(d.total_count[~d.ocean_mask].ravel())
    if len(land_vals) == 0 or land_vals.sum() == 0:
        return

    n_land = len(land_vals)
    cum_share = np.cumsum(land_vals) / land_vals.sum()
    x_pct = np.arange(1, n_land + 1) / n_land

    _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    gini = 1.0 - 2.0 * _trapz(
        cum_share, dx=1 / n_land,
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
        title="Concentration of ACLED events",
        xlabel="Cumulative % of land cells (ranked by events)",
        ylabel="Cumulative % of total events",
    )
    ax.text(
        15, 85, f"Gini = {gini:.3f}",
        fontsize=13, fontweight="bold",
    )
    ax.text(
        15, 78,
        f"{pct_str} of cells account\n"
        f"for 90% of all events",
        fontsize=FONT_LABEL, color="#444444",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    save_plot(fig, out, "12_concentration.png")


def plot_spot_checks(
    d: PrecomputedData, out: Path,
) -> None:
    """13 — Spot-check known conflict locations."""
    import matplotlib.pyplot as plt
    import numpy as np

    rows_data = []
    for name, lat, lon in SPOT_CHECK_LOCATIONS:
        row = int((lat + 90.0) / (180.0 / d.n_h))
        col = int((lon + 180.0) / (360.0 / d.n_w))
        row = max(0, min(row, d.n_h - 1))
        col = max(0, min(col, d.n_w - 1))

        count = d.total_count[row, col]
        fat = d.total_fatalities[row, col]

        type_counts = [
            d.spatial_types[j][row, col]
            for j in range(6)
        ]
        top_type_idx = int(np.argmax(type_counts))
        top_type = (
            ACLED_TYPE_NAMES[top_type_idx]
            if type_counts[top_type_idx] > 0
            else "None"
        )

        rows_data.append([
            name,
            f"({row}, {col})",
            f"{count:,.0f}",
            f"{fat:,.0f}",
            top_type,
            "PASS" if count > 0 else "FAIL",
        ])

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.axis("off")

    col_labels = [
        "Location", "Cell (r,c)", "Events",
        "Fatalities", "Top Type", "Status",
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
        "Spot-check: known conflict locations on PRIO-GRID",
        fontsize=FONT_TITLE, fontweight="bold", pad=20,
    )
    save_plot(fig, out, "13_spot_checks.png")


# ── Summary ──────────────────────────────────────────────────


def print_summary(d: PrecomputedData) -> bool:
    """Print verification summary. Returns True if all pass."""
    print()
    print("=" * 60)
    print("ACLED GRID VERIFICATION SUMMARY")
    print("=" * 60)
    print()
    print(f"Grid shape:  [{d.n_t}, {d.n_h}, {d.n_w}, {d.n_f}]")
    print(f"Temporal:    {d.start_year}-01 to "
          f"{d.start_year + d.n_t // 12}-12")
    print(f"Features:    {d.features}")
    print()

    total_events = d.monthly_count.sum()
    total_fat = d.monthly_fatalities.sum()
    print(f"Total events:     {total_events:,.0f}")
    print(f"Total fatalities: {total_fat:,.0f}")
    print()

    print("Per-type breakdown:")
    type_totals = [d.monthly_types[:, j].sum() for j in range(6)]
    grand = sum(type_totals)
    for j, name in enumerate(ACLED_TYPE_NAMES):
        pct = type_totals[j] / grand * 100 if grand > 0 else 0
        print(f"  {name:20s} {type_totals[j]:>12,.0f}  "
              f"({pct:5.1f}%)")
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
                suffix = f" — {dv}"
                break
        print(f"{marker} {name}: {status}{suffix}")
        if not value:
            all_pass = False

    print()
    if all_pass:
        print("VERDICT: PASS — all checks passed")
    else:
        print("VERDICT: INVESTIGATE — some checks need review")
    print("=" * 60)

    return all_pass


# ── Orchestrator ─────────────────────────────────────────────


PLOTS: list[tuple[str, object]] = [
    ("Event Density", plot_event_density),
    ("Fatalities Spatial", plot_fatalities_spatial),
    ("Per-Type Spatial", plot_per_type_spatial),
    ("Monthly Counts", plot_monthly_counts),
    ("Monthly Fatalities", plot_monthly_fatalities),
    ("Annual Scale", plot_annual_scale),
    ("Type Proportions", plot_type_proportions),
    ("Fatality Correlation", plot_fatality_correlation),
    ("Structural Invariant", plot_structural_invariant),
    ("Calendar Heatmap", plot_calendar_heatmap),
    ("Trajectories", plot_trajectories),
    ("Concentration", plot_concentration),
    ("Spot Checks", plot_spot_checks),
]


def main() -> int:
    """Run the ACLED grid verification."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="ACLED grid verification audit",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/compiled/acled"),
        help="Compiled ACLED grid directory",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/audit_acled"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        print(
            "Run the ACLED pipeline first: "
            "python scripts/run_acled_pipeline.py"
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
    print(f"  Total events:     {data.monthly_count.sum():,.0f}")
    print(f"  Total fatalities: "
          f"{data.monthly_fatalities.sum():,.0f}")
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
