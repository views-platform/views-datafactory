#!/usr/bin/env python3
"""Conflict data visualization — 14 plots telling the story of
subnational conflict 1989-2026.

Usage:
    uv run python scripts/visualize_audit.py
    uv run python scripts/visualize_audit.py --input data/assembled

Narrative arc:
    01-02  Scale and geography: "How much? Where?"
    03-05  Evolution: "How did it shift? What kinds? Who's chronic?"
    06-07  Concentration: "How unequal? What do hotspots look like?"
    08-09  Time patterns: "When did it start? Is there a rhythm?"
    10-12  Context: "What does the landscape look like?"
    13-14  Data challenge: "Why is this hard to model?"
    15     Admin boundaries: "What political units cover the grid?"

Uses memory-mapped grid loading to avoid 18+ GB RAM usage.
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

# ── Style constants ──────────────────────────────────────────

DPI = 200

FIG_FULL = (14, 7)
FIG_HALF = (7, 7)
FIG_TALL = (7, 12)
FIG_PANEL_2x2 = (14, 9)
FIG_PANEL_1x3 = (14, 5)
FIG_PANEL_4x3 = (14, 10)

FONT_TITLE = 13
FONT_LABEL = 10
FONT_TICK = 8
FONT_ANNOT = 8

CMAP_SEQ = "YlOrRd"
CMAP_DIV = "RdBu_r"
CMAP_HEAT = "Reds"
CMAP_COV = "viridis"
CMAP_ONSET = "plasma"

COLOR_NS = "#4878A8"
COLOR_OS = "#D4752E"
COLOR_SB = "#7A8B3C"
COLOR_ACCENT = "#2C5080"
COLOR_GRAY = "#666666"

EXTENT = [-180, 180, -90, 90]

DECADE_BOUNDS: list[tuple[int, int, str]] = [
    (0, 120, "1989\u20131998"),
    (120, 240, "1999\u20132008"),
    (240, 360, "2009\u20132018"),
    (360, 456, "2019\u20132026"),
]

PEAK_EVENTS: list[tuple[dt.date, str]] = [
    (dt.date(1994, 5, 15), "Rwanda genocide"),
    (dt.date(1999, 6, 15), "Kosovo / E. Timor"),
    (dt.date(2003, 4, 15), "Iraq invasion"),
    (dt.date(2009, 5, 15), "Sri Lanka"),
    (dt.date(2014, 8, 15), "Syria / ISIS"),
    (dt.date(2021, 7, 15), "Tigray"),
    (dt.date(2022, 3, 15), "Ukraine"),
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
    ((0, 8), (-12, 2), "Ivory Coast"),
    ((-5, 0), (28, 32), "Burundi"),
    ((3, 8), (30, 35), "South Sudan"),
    ((-4, 2), (104, 115), "Indonesia"),
    ((30, 42), (55, 65), "Pakistan"),
    ((10, 20), (100, 110), "Cambodia"),
]


# ── Style helpers ────────────────────────────────────────────


def style_ax(
    ax: object,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
) -> None:
    """Apply Tufte-compliant style to an axes."""
    ax.spines["top"].set_visible(False)  # type: ignore[union-attr]
    ax.spines["right"].set_visible(False)  # type: ignore[union-attr]
    ax.tick_params(labelsize=FONT_TICK)  # type: ignore[union-attr]
    if title:
        ax.set_title(  # type: ignore[union-attr]
            title, fontsize=FONT_TITLE, fontweight="bold",
        )
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FONT_LABEL)  # type: ignore[union-attr]
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FONT_LABEL)  # type: ignore[union-attr]


def save_plot(fig: object, output_dir: Path, name: str) -> None:
    """Save figure and close."""
    import matplotlib.pyplot as plt

    fig.savefig(  # type: ignore[union-attr]
        output_dir / name, dpi=DPI, bbox_inches="tight",
    )
    plt.close(fig)  # type: ignore[arg-type]
    print(f"  \u2192 {name}")


def spatial_imshow(
    ax: object,
    data_2d: np.ndarray,
    ocean_mask: np.ndarray,
    cmap: str,
    *,
    vmin: float | None = None,
    vmax: float | None = None,
    log: bool = False,
    cbar_label: str | None = None,
    fig: object | None = None,
) -> object:
    """Mask ocean, flip, imshow. Returns image handle."""
    import numpy as np

    display = data_2d.astype(np.float64).copy()
    display[ocean_mask] = np.nan
    if log:
        display = np.where(
            np.isnan(display), np.nan, np.log1p(display),
        )
    display = np.flipud(display)
    im = ax.imshow(  # type: ignore[union-attr]
        display, cmap=cmap, aspect="auto", extent=EXTENT,
        vmin=vmin, vmax=vmax,
    )
    if cbar_label and fig is not None:
        import matplotlib.pyplot as plt

        plt.colorbar(im, ax=ax, label=cbar_label)
    return im


def make_dates(n_t: int) -> list[dt.date]:
    """Build date list from 1989-01 through n_t months."""
    return [
        dt.date(1989 + t // 12, 1 + t % 12, 15)
        for t in range(n_t)
    ]


def cell_to_label(
    row: int, col: int, n_h: int, n_w: int,
) -> str:
    """Map grid cell to approximate region name."""
    lat = 90.0 - (row + 0.5) * (180.0 / n_h)
    lon = -180.0 + (col + 0.5) * (360.0 / n_w)
    for (lat_lo, lat_hi), (lon_lo, lon_hi), name in REGION_BOUNDS:
        if lat_lo <= lat <= lat_hi and lon_lo <= lon <= lon_hi:
            return name
    lat_s = f"{abs(lat):.0f}\u00b0{'N' if lat >= 0 else 'S'}"
    lon_s = f"{abs(lon):.0f}\u00b0{'E' if lon >= 0 else 'W'}"
    return f"{lat_s}, {lon_s}"


# ── Data loading and precomputation ──────────────────────────


@dataclasses.dataclass
class PrecomputedData:
    """All derived arrays from the assembled grid."""

    # Grid reference (mmap) and metadata
    grid: np.ndarray
    features: list[str]
    n_t: int
    n_h: int
    n_w: int
    n_f: int
    ocean_mask: np.ndarray
    dates: list[dt.date]

    # Feature indices
    ns_idx: int
    os_idx: int
    sb_idx: int
    nc_idx: int
    oc_idx: int
    sc_idx: int

    # Monthly global totals (T,)
    monthly_ns: np.ndarray
    monthly_os: np.ndarray
    monthly_sb: np.ndarray
    monthly_total: np.ndarray

    # Spatial aggregates (H, W)
    total_fat: np.ndarray
    total_ns: np.ndarray
    total_os: np.ndarray
    total_sb: np.ndarray
    active_months: np.ndarray
    first_onset: np.ndarray
    decade_totals: list[np.ndarray]

    # Zero-inflation
    ucdp_features: list[str]
    ucdp_zero_fracs: list[float]
    ucdp_ever_nonzero: list[int]
    n_observations: int

    # Top-12 hotspot trajectories
    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray

    # Feature completeness (H, W)
    completeness: np.ndarray


def precompute(
    grid: np.ndarray,
    features: list[str],
    time_steps: np.ndarray,
) -> PrecomputedData:
    """Single pass over the mmap grid. Returns all derived data."""
    import numpy as np

    n_t, n_h, n_w, n_f = grid.shape

    # Feature indices
    ns_idx = features.index("ged_ns_best")
    os_idx = features.index("ged_os_best")
    sb_idx = features.index("ged_sb_best")
    nc_idx = features.index("ged_ns_count")
    oc_idx = features.index("ged_os_count")
    sc_idx = features.index("ged_sb_count")
    land_idx = features.index("landarea")

    # Ocean mask
    ocean_mask = grid[0, :, :, land_idx] == 0

    # UCDP features for zero-inflation
    ucdp_feats = [f for f in features if f.startswith("ged_")]
    ucdp_indices = [features.index(f) for f in ucdp_feats]
    n_obs = n_t * n_h * n_w
    ucdp_nonzero_counts = [0] * len(ucdp_feats)
    ucdp_cells_ever = [
        np.zeros((n_h, n_w), dtype=bool) for _ in ucdp_feats
    ]

    # Feature completeness
    completeness = np.zeros((n_h, n_w), dtype=np.int32)
    for f_idx in range(6, n_f):
        completeness += (grid[0, :, :, f_idx] != 0).astype(np.int32)

    # Allocate accumulators
    monthly_ns = np.zeros(n_t, dtype=np.float64)
    monthly_os = np.zeros(n_t, dtype=np.float64)
    monthly_sb = np.zeros(n_t, dtype=np.float64)
    total_fat = np.zeros((n_h, n_w), dtype=np.float64)
    total_ns = np.zeros((n_h, n_w), dtype=np.float64)
    total_os = np.zeros((n_h, n_w), dtype=np.float64)
    total_sb = np.zeros((n_h, n_w), dtype=np.float64)
    active_months = np.zeros((n_h, n_w), dtype=np.int32)
    first_onset = np.full((n_h, n_w), np.nan, dtype=np.float64)
    decade_totals = [
        np.zeros((n_h, n_w), dtype=np.float64)
        for _ in DECADE_BOUNDS
    ]

    # === PASS 1: single scan over T ===
    for t in range(n_t):
        ns_v = grid[t, :, :, ns_idx].astype(np.float64)
        os_v = grid[t, :, :, os_idx].astype(np.float64)
        sb_v = grid[t, :, :, sb_idx].astype(np.float64)
        s = ns_v + os_v + sb_v

        monthly_ns[t] = ns_v.sum()
        monthly_os[t] = os_v.sum()
        monthly_sb[t] = sb_v.sum()

        total_ns += ns_v
        total_os += os_v
        total_sb += sb_v
        total_fat += s

        any_event = (
            (grid[t, :, :, nc_idx] > 0)
            | (grid[t, :, :, oc_idx] > 0)
            | (grid[t, :, :, sc_idx] > 0)
        )
        active_months += any_event.astype(np.int32)

        new_onset = any_event & np.isnan(first_onset)
        first_onset[new_onset] = 1989.0 + t / 12

        for i, (t0, t1, _) in enumerate(DECADE_BOUNDS):
            if t0 <= t < t1:
                decade_totals[i] += s
                break

        for j, fidx in enumerate(ucdp_indices):
            sl = grid[t, :, :, fidx]
            ucdp_nonzero_counts[j] += int((sl != 0).sum())
            ucdp_cells_ever[j] |= sl != 0

    monthly_total = monthly_ns + monthly_os + monthly_sb

    # Zero-inflation results
    ucdp_zero_fracs = [
        1.0 - cnt / n_obs for cnt in ucdp_nonzero_counts
    ]
    ucdp_ever_nonzero = [
        int(mask.sum()) for mask in ucdp_cells_ever
    ]

    # UCDP completeness: check if cell ever has data (any UCDP feature)
    ucdp_ever_any = np.zeros((n_h, n_w), dtype=bool)
    for mask in ucdp_cells_ever:
        ucdp_ever_any |= mask
    completeness += ucdp_ever_any.astype(np.int32)

    # === PASS 2: top-12 hotspot time series ===
    flat_idx = np.argsort(total_fat.ravel())[-12:][::-1]
    top_rows = flat_idx // n_w
    top_cols = flat_idx % n_w
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = (
                float(grid[t, r, c, ns_idx])
                + float(grid[t, r, c, os_idx])
                + float(grid[t, r, c, sb_idx])
            )

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t),
        ns_idx=ns_idx, os_idx=os_idx, sb_idx=sb_idx,
        nc_idx=nc_idx, oc_idx=oc_idx, sc_idx=sc_idx,
        monthly_ns=monthly_ns, monthly_os=monthly_os,
        monthly_sb=monthly_sb, monthly_total=monthly_total,
        total_fat=total_fat, total_ns=total_ns,
        total_os=total_os, total_sb=total_sb,
        active_months=active_months,
        first_onset=first_onset,
        decade_totals=decade_totals,
        ucdp_features=ucdp_feats,
        ucdp_zero_fracs=ucdp_zero_fracs,
        ucdp_ever_nonzero=ucdp_ever_nonzero,
        n_observations=n_obs,
        top_rows=top_rows, top_cols=top_cols, top_ts=top_ts,
        completeness=completeness,
    )


# ── Plot functions ───────────────────────────────────────────


def plot_toll(d: PrecomputedData, out: Path) -> None:
    """01 — The Toll: monthly fatalities, broken-axis."""
    import matplotlib.pyplot as plt
    import numpy as np

    clip_y = float(
        np.percentile(d.monthly_total[d.monthly_total > 0], 97)
    )
    stack_kw = {
        "labels": ["State-based", "One-sided", "Non-state"],
        "colors": [COLOR_NS, COLOR_OS, COLOR_SB],
        "alpha": 0.85,
    }

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(14, 7),
        gridspec_kw={"height_ratios": [1, 2.5], "hspace": 0.08},
        sharex=True,
    )

    # Top: full range
    ax_top.stackplot(
        d.dates, d.monthly_ns, d.monthly_os, d.monthly_sb,
        **stack_kw,
    )
    ax_top.set_ylim(bottom=0)
    ax_top.legend(
        loc="upper right", framealpha=0.8,
        fontsize=FONT_ANNOT, ncol=3,
    )
    style_ax(ax_top, title="Monthly conflict fatalities worldwide, 1989\u20132026")
    ax_top.spines["bottom"].set_visible(False)
    ax_top.tick_params(bottom=False)

    # Bottom: clipped for detail
    ax_bot.stackplot(
        d.dates, d.monthly_ns, d.monthly_os, d.monthly_sb,
        **stack_kw,
    )
    ax_bot.set_ylim(0, clip_y)
    ax_bot.set_xlim(d.dates[0], d.dates[-1])
    style_ax(ax_bot, ylabel="Fatalities per month")

    for evt_date, label in PEAK_EVENTS:
        ax_bot.axvline(
            evt_date, color=COLOR_GRAY,
            linewidth=0.5, linestyle=":", zorder=1,
        )
        ax_bot.text(
            evt_date, clip_y * 0.95, label,
            fontsize=6.5, ha="center", va="top",
            color="#333333", rotation=35,
            bbox={
                "boxstyle": "round,pad=0.15",
                "facecolor": "white", "alpha": 0.8, "edgecolor": "none",
            },
        )

    # Break marks
    br = 0.01
    for ax_brk in (ax_top, ax_bot):
        kw = {
            "transform": ax_brk.transAxes, "color": "k",
            "clip_on": False, "linewidth": 0.8,
        }
        y = 0.0 if ax_brk is ax_top else 1.0
        ax_brk.plot((-br, +br), (y - br, y + br), **kw)
        ax_brk.plot((1 - br, 1 + br), (y - br, y + br), **kw)

    save_plot(fig, out, "01_toll.png")


def plot_where(d: PrecomputedData, out: Path) -> None:
    """02 — Where conflict happens: spatial heatmap."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.total_fat, d.ocean_mask, CMAP_SEQ,
        log=True, cbar_label="log(1 + fatalities)", fig=fig,
    )
    style_ax(
        ax, title="Total conflict fatalities, 1989\u20132026",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "02_where.png")


def plot_migration(d: PrecomputedData, out: Path) -> None:
    """03 — Geographic shift by decade."""
    import matplotlib.pyplot as plt
    import numpy as np

    vmax_log = np.log1p(max(dt.max() for dt in d.decade_totals))

    fig, axes = plt.subplots(
        2, 2, figsize=FIG_PANEL_2x2,
        gridspec_kw={"hspace": 0.15, "wspace": 0.05},
    )
    for idx, (ax, (_, _, label), dtotal) in enumerate(
        zip(axes.flat, DECADE_BOUNDS, d.decade_totals, strict=True)
    ):
        spatial_imshow(
            ax, dtotal, d.ocean_mask, CMAP_SEQ,
            log=True, vmin=0, vmax=vmax_log,
        )
        style_ax(ax, title=label)
        if idx % 2 == 1:
            ax.set_yticklabels([])
        if idx < 2:
            ax.set_xticklabels([])

    fig.suptitle(
        "Geographic shift of conflict fatalities by decade",
        fontsize=FONT_TITLE, fontweight="bold", y=0.95,
    )
    cbar = fig.colorbar(
        axes.flat[-1].images[0], ax=axes, shrink=0.6,
        label="log(1 + fatalities)",
    )
    cbar.ax.tick_params(labelsize=FONT_TICK)
    save_plot(fig, out, "03_migration.png")


def plot_violence_types(d: PrecomputedData, out: Path) -> None:
    """04 — Three kinds of violence: decomposition maps."""
    import matplotlib.pyplot as plt
    import numpy as np

    panels = [
        ("State-based (ns)", d.total_ns),
        ("One-sided (os)", d.total_os),
        ("Non-state (sb)", d.total_sb),
    ]
    all_vals = np.concatenate(
        [v[~d.ocean_mask].ravel() for _, v in panels]
    )
    vmax = np.log1p(all_vals.max())

    fig, axes = plt.subplots(1, 3, figsize=FIG_PANEL_1x3)
    for ax, (label, data) in zip(axes, panels, strict=True):
        spatial_imshow(
            ax, data, d.ocean_mask, CMAP_SEQ,
            log=True, vmin=0, vmax=vmax,
        )
        style_ax(ax, title=label)

    fig.suptitle(
        "Fatalities by violence type, 1989\u20132026",
        fontsize=FONT_TITLE, fontweight="bold",
    )
    fig.colorbar(
        axes[-1].images[0], ax=axes.tolist(),
        label="log(1 + fatalities)",
    )
    save_plot(fig, out, "04_violence_types.png")


def plot_persistence(d: PrecomputedData, out: Path) -> None:
    """05 — Chronic hotspots: % of months with conflict."""
    import matplotlib.pyplot as plt

    persistence = d.active_months / d.n_t * 100

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, persistence, d.ocean_mask, CMAP_SEQ,
        vmin=0, vmax=min(50, persistence.max()),
        cbar_label="% months active", fig=fig,
    )
    style_ax(
        ax, title="Conflict persistence (% of months active, 1989\u20132026)",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "05_persistence.png")


def plot_concentration(d: PrecomputedData, out: Path) -> None:
    """06 — Lorenz curve: concentration of fatalities."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = np.sort(d.total_fat[~d.ocean_mask].ravel())
    n_land = len(land_vals)
    cum_share = np.cumsum(land_vals) / land_vals.sum()
    x_pct = np.arange(1, n_land + 1) / n_land

    gini = 1.0 - 2.0 * np.trapezoid(cum_share, dx=1 / n_land)

    idx_90 = np.searchsorted(cum_share, 0.10)
    pct_cells = (n_land - idx_90) / n_land * 100
    pct_str = f"{pct_cells:.2f}%" if pct_cells < 1.0 else f"{pct_cells:.1f}%"

    fig, ax = plt.subplots(figsize=FIG_HALF)
    ax.plot(x_pct * 100, cum_share * 100, color="black", linewidth=1.5)
    ax.plot(
        [0, 100], [0, 100], color="#AAAAAA",
        linewidth=0.8, linestyle="--",
    )
    style_ax(
        ax,
        title="Concentration of conflict fatalities",
        xlabel="Cumulative % of land cells (ranked by fatalities)",
        ylabel="Cumulative % of total fatalities",
    )
    ax.text(15, 85, f"Gini = {gini:.3f}", fontsize=13, fontweight="bold")
    ax.text(
        15, 78,
        f"{pct_str} of cells account\nfor 90% of all fatalities",
        fontsize=FONT_LABEL, color="#444444",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    save_plot(fig, out, "06_concentration.png")


def plot_trajectories(d: PrecomputedData, out: Path) -> None:
    """07 — Small multiples: 12 deadliest grid cells."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        4, 3, figsize=FIG_PANEL_4x3, sharex=True,
        gridspec_kw={"hspace": 0.35, "wspace": 0.25},
    )
    for k, ax in enumerate(axes.flat):
        ax.fill_between(
            d.dates, d.top_ts[k],
            color=COLOR_NS, alpha=0.6, linewidth=0,
        )
        ax.plot(d.dates, d.top_ts[k], color=COLOR_ACCENT, linewidth=0.5)

        label = cell_to_label(
            int(d.top_rows[k]), int(d.top_cols[k]), d.n_h, d.n_w,
        )
        total_k = d.total_fat[d.top_rows[k], d.top_cols[k]]
        style_ax(ax, title=f"{label}  ({total_k:,.0f} total)")
        ax.set_xlim(d.dates[0], d.dates[-1])
        ax.set_ylim(bottom=0)

    fig.suptitle(
        "Conflict trajectories: 12 deadliest grid cells, 1989\u20132026",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "07_trajectories.png")


def plot_onset(d: PrecomputedData, out: Path) -> None:
    """08 — When conflict first arrives: onset map."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    # Don't use spatial_imshow — onset has special NaN semantics
    # (peaceful land stays NaN too, which is what we want)
    import numpy as np

    display = np.flipud(d.first_onset.copy())
    im = ax.imshow(
        display, cmap=CMAP_ONSET, aspect="auto",
        extent=EXTENT, vmin=1989, vmax=2026,
    )
    style_ax(
        ax, title="First conflict event by cell (year of onset)",
        xlabel="Longitude", ylabel="Latitude",
    )
    plt.colorbar(im, ax=ax, label="Year of first event")
    save_plot(fig, out, "08_onset.png")


def plot_calendar(d: PrecomputedData, out: Path) -> None:
    """09 — Year x Month heatmap."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_years = (d.n_t + 11) // 12
    cal = np.full((n_years, 12), np.nan, dtype=np.float64)
    for t in range(d.n_t):
        cal[t // 12, t % 12] = d.monthly_total[t]

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
        [str(1989 + y) for y in range(n_years)],
        fontsize=7,
    )
    style_ax(
        ax, title="Global conflict fatalities by calendar month",
        xlabel="Month", ylabel="Year",
    )
    # Restore subtle cell borders (the one gridline exception)
    ax.set_xticks(np.arange(-0.5, 12, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_years, 1), minor=True)
    ax.grid(which="minor", color="#DDDDDD", linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    plt.colorbar(im, ax=ax, shrink=0.4, label="log(1 + fatalities)")
    save_plot(fig, out, "09_calendar.png")


def plot_covariates(d: PrecomputedData, out: Path) -> None:
    """10 — Terrain and infrastructure: 4 static covariates."""
    import matplotlib.pyplot as plt

    cov_specs = [
        ("landarea", "Land Area (km\u00b2)"),
        ("mountains_mean", "Mountain Coverage (%)"),
        ("ttime_mean", "Travel Time (min)"),
        ("urban_gc", "Urban Coverage (%)"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=FIG_PANEL_2x2)
    for ax, (name, title) in zip(axes.flat, cov_specs, strict=True):
        idx = d.features.index(name)
        data = d.grid[0, :, :, idx].astype("float32")
        spatial_imshow(
            ax, data, d.ocean_mask, CMAP_COV,
            cbar_label=title, fig=fig,
        )
        style_ax(ax, title=title)

    fig.suptitle(
        "PRIO-GRID static covariates",
        fontsize=FONT_TITLE, fontweight="bold",
    )
    save_plot(fig, out, "10_covariates.png")


def plot_correlation(d: PrecomputedData, out: Path) -> None:
    """11 — Covariate correlation matrix."""
    import matplotlib.pyplot as plt
    import numpy as np

    static_names = d.features[6:]
    n_static = len(static_names)
    land_flat = ~d.ocean_mask.ravel()

    static_matrix = np.zeros(
        (int(land_flat.sum()), n_static), dtype=np.float32,
    )
    for i in range(n_static):
        vals = d.grid[0, :, :, 6 + i].ravel()
        static_matrix[:, i] = vals[land_flat]

    corr = np.nan_to_num(np.corrcoef(static_matrix.T), nan=0.0)
    order = np.argsort(np.abs(corr).mean(axis=1))[::-1]
    corr_ordered = corr[np.ix_(order, order)]
    names_ordered = [static_names[i] for i in order]

    fig, ax = plt.subplots(figsize=FIG_PANEL_2x2)
    im = ax.imshow(corr_ordered, cmap=CMAP_DIV, vmin=-1, vmax=1)
    ax.set_xticks(range(n_static))
    ax.set_yticks(range(n_static))
    ax.set_xticklabels(names_ordered, rotation=90, fontsize=FONT_TICK)
    ax.set_yticklabels(names_ordered, fontsize=FONT_TICK)
    style_ax(ax, title="Static covariate correlation (land cells)")
    plt.colorbar(im, ax=ax, label="Pearson r")
    save_plot(fig, out, "11_correlation.png")


def plot_scatter(d: PrecomputedData, out: Path) -> None:
    """12 — Conflict intensity vs static covariates."""
    import matplotlib.pyplot as plt
    import numpy as np

    fat_flat = d.total_fat.ravel()
    land_flat = ~d.ocean_mask.ravel()
    conflict_cells = (fat_flat > 0) & land_flat
    fat_log = np.log1p(fat_flat[conflict_cells])

    scatter_covs = [
        ("landarea", "Land Area (km\u00b2)"),
        ("mountains_mean", "Mountain Coverage"),
        ("ttime_mean", "Travel Time (min)"),
        ("urban_gc", "Urban Coverage (%)"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=FIG_PANEL_2x2)
    for ax, (name, title) in zip(axes.flat, scatter_covs, strict=True):
        idx = d.features.index(name)
        cov_vals = d.grid[0, :, :, idx].ravel()[conflict_cells]
        ax.scatter(
            cov_vals, fat_log,
            alpha=0.15, s=3, c=COLOR_NS,
        )
        style_ax(ax, title=f"Conflict vs {name}", xlabel=title,
                 ylabel="log(1 + fatalities)")

    fig.suptitle(
        "Conflict intensity vs static covariates (conflict cells only)",
        fontsize=FONT_TITLE, fontweight="bold",
    )
    save_plot(fig, out, "12_scatter.png")


def plot_sparsity(d: PrecomputedData, out: Path) -> None:
    """13 — The data challenge: extreme zero-inflation."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_FULL)

    ax1.barh(d.ucdp_features, d.ucdp_zero_fracs, color=COLOR_NS)
    style_ax(ax1, title="Zero-inflation per channel",
             xlabel="Fraction zero")
    ax1.set_xlim(0.99, 1.001)

    ax2.barh(d.ucdp_features, d.ucdp_ever_nonzero, color=COLOR_OS)
    n_cells = d.n_h * d.n_w
    style_ax(ax2, title=f"Active cells (of {n_cells:,} total)",
             xlabel="Cells with any non-zero value")

    fig.suptitle(
        "The data challenge: extreme sparsity in conflict data",
        fontsize=FONT_TITLE, fontweight="bold",
    )
    save_plot(fig, out, "13_sparsity.png")


def plot_coverage(d: PrecomputedData, out: Path) -> None:
    """14 — Feature coverage: how many features are non-zero per cell."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    spatial_imshow(
        ax, d.completeness.astype("float64"), d.ocean_mask,
        CMAP_COV, vmin=0, vmax=float(d.n_f),
        cbar_label="Non-zero features", fig=fig,
    )
    style_ax(
        ax,
        title=f"Feature coverage (0\u2013{d.n_f} non-zero features per cell)",
        xlabel="Longitude", ylabel="Latitude",
    )
    save_plot(fig, out, "14_coverage.png")


def plot_admin_boundaries(
    d: PrecomputedData, out: Path,
) -> None:
    """15 — GAUL admin boundaries: country, province, district."""
    import matplotlib.pyplot as plt
    import numpy as np

    admin_levels = [
        ("gaul0_code", "tab20", "Admin 0 (Country)"),
        ("gaul1_code", "nipy_spectral", "Admin 1 (Province)"),
        ("gaul2_code", "nipy_spectral", "Admin 2 (District)"),
    ]

    # Graceful skip if admin channels not in grid
    if admin_levels[0][0] not in d.features:
        print("  (skipped — no admin channels in grid)")
        return

    fig, axes = plt.subplots(
        1, 3, figsize=FIG_PANEL_1x3,
        gridspec_kw={"wspace": 0.08},
    )

    for ax, (feat, cmap, label) in zip(
        axes.flat, admin_levels, strict=True,
    ):
        idx = d.features.index(feat)
        channel = d.grid[0, :, :, idx].copy().astype(
            np.float64
        )
        # Sentinel: -1 (unassigned) and 0 → NaN
        channel[channel <= 0] = np.nan
        n_unique = len(set(
            channel[~np.isnan(channel)].flatten().tolist()
        ))

        display = np.flipud(channel)
        ax.imshow(  # type: ignore[union-attr]
            display, cmap=cmap, aspect="auto",
            extent=EXTENT, interpolation="nearest",
        )
        style_ax(
            ax, title=f"{label}: {n_unique:,} units",
            xlabel="Longitude",
        )

    axes[0].set_ylabel("Latitude", fontsize=FONT_LABEL)  # type: ignore[union-attr]

    fig.suptitle(
        "GAUL 2024 administrative boundaries on PRIO-GRID",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    save_plot(fig, out, "15_admin_boundaries.png")


# ── Orchestrator ─────────────────────────────────────────────

PLOTS: list[tuple[str, object]] = [
    ("The Toll", plot_toll),
    ("Where", plot_where),
    ("Migration", plot_migration),
    ("Violence Types", plot_violence_types),
    ("Persistence", plot_persistence),
    ("Concentration", plot_concentration),
    ("Trajectories", plot_trajectories),
    ("Onset", plot_onset),
    ("Calendar", plot_calendar),
    ("Covariates", plot_covariates),
    ("Correlation", plot_correlation),
    ("Scatter", plot_scatter),
    ("Sparsity", plot_sparsity),
    ("Coverage", plot_coverage),
    ("Admin Boundaries", plot_admin_boundaries),
]


def main() -> int:
    """Run the visualization audit."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(
        description="Conflict data visualization audit",
    )
    parser.add_argument(
        "--input", type=Path, default=Path("data/assembled"),
        help="Assembled grid directory",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/audit"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        return 1

    import matplotlib
    matplotlib.use("Agg")
    import numpy as np

    features = json.loads(
        (args.input / "feature_names.json").read_text()
    )
    time_steps = np.load(args.input / "time_steps.npy")
    grid = np.load(grid_path, mmap_mode="r")

    print(f"Grid: [T={grid.shape[0]}, H={grid.shape[1]}, "
          f"W={grid.shape[2]}, F={grid.shape[3]}]")

    args.output.mkdir(parents=True, exist_ok=True)

    print("Precomputing aggregates (2 passes over grid)...")
    data = precompute(grid, features, time_steps)
    print(f"  Total fatalities: {data.monthly_total.sum():,.0f}")
    print()

    for i, (name, fn) in enumerate(PLOTS, 1):
        print(f"Plot {i:02d}: {name}...")
        fn(data, args.output)

    print()
    print(f"All {len(PLOTS)} plots saved to {args.output}/")
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
