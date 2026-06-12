#!/usr/bin/env python3
"""SHDI grid verification — 14 plots + statistical checks proving
spatial, temporal, and structural correctness before release.

Usage:
    uv run python scripts/verify_shdi_grid.py
    uv run python scripts/verify_shdi_grid.py --input data/compiled/shdi

Reads the compiled SHDI grid and produces PNG plots to
``reports/audit_shdi/`` plus a statistical summary on stdout.

All 4 SHDI features are bounded [0, 1] indices (ADR-040:
intensive quantities — sums are meaningless). NaN means
"no GDL coverage" and must be preserved (not converted to 0.0).
Annual data broadcast to monthly via step function — values
must be constant within each calendar year.

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
    FIG_PANEL_2x2,
    FIG_PANEL_4x3,
    FONT_TICK,
    FONT_TITLE,
    make_dates,
    save_plot,
    style_ax,
)

CMAP_SHDI = "RdYlGn"

SHDI_FEATURES = (
    "shdi_shdi",
    "shdi_healthindex",
    "shdi_edindex",
    "shdi_incindex",
)

SHDI_START_YEAR = 1990

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
    ("Oslo, Norway", 60.5, 10.7, "high"),
    ("Stockholm, Sweden", 59.3, 18.1, "high"),
    ("Washington DC, USA", 38.9, -77.0, "high"),
    ("Beijing, China", 39.9, 116.4, "mid"),
    ("New Delhi, India", 28.6, 77.2, "mid"),
    ("Brasilia, Brazil", -15.8, -47.9, "mid"),
    ("Addis Ababa, Ethiopia", 9.0, 38.7, "mid"),
    ("Moscow, Russia", 55.8, 37.6, "mid"),
    ("Niamey, Niger", 13.5, 2.1, "low"),
    ("N'Djamena, Chad", 12.1, 15.0, "low"),
    ("Juba, South Sudan", 4.9, 31.6, "low"),
    ("Pacific Ocean", 0.0, -160.0, "nan"),
    ("Southern Ocean", -60.0, 0.0, "nan"),
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


def _load_gdl_crosswalk() -> dict[int, str]:
    """Load GDL pgid -> gdl_code mapping for region-level analysis."""
    path = Path("data/raw/shdi/gdl_to_pgid.parquet")
    if not path.exists():
        return {}
    import pyarrow.parquet as pq

    t = pq.read_table(path)
    gids = t.column("gid").to_pylist()
    codes = t.column("gdl_code").to_pylist()
    return dict(zip(gids, codes, strict=True))


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

    shdi_idx: int
    last_valid_t: int

    latest_shdi: np.ndarray
    mean_shdi: np.ndarray
    nan_mask: np.ndarray

    monthly_mean: np.ndarray
    monthly_coverage: np.ndarray

    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray

    checks: dict[str, bool | str]

    region_values: np.ndarray
    region_values_t0: np.ndarray
    region_codes: list[str]
    region_cells: dict[str, list[tuple[int, int]]]


def precompute(
    grid: np.ndarray,
    features: list[str],
    start_year: int,
) -> PrecomputedData:
    import numpy as np

    n_t, n_h, n_w, n_f = grid.shape

    shdi_name = "shdi_shdi"
    if shdi_name not in features:
        shdi_name = features[0]
    shdi_idx = features.index(shdi_name)

    ocean_mask = _load_ocean_mask(n_h, n_w)

    monthly_mean = np.zeros(n_t, dtype=np.float64)
    monthly_coverage = np.zeros(n_t, dtype=np.float64)
    mean_shdi = np.zeros((n_h, n_w), dtype=np.float64)
    count_shdi = np.zeros((n_h, n_w), dtype=np.float64)

    has_out_of_range = False

    for t in range(n_t):
        sl = grid[t, :, :, shdi_idx].astype(np.float64)
        valid = ~np.isnan(sl)
        n_valid = valid.sum()
        if n_valid > 0:
            monthly_mean[t] = float(np.nanmean(sl))
            mean_shdi[valid] += sl[valid]
            count_shdi[valid] += 1
        monthly_coverage[t] = n_valid / (n_h * n_w) * 100
        valid_vals = sl[valid]
        if (
            len(valid_vals) > 0
            and (valid_vals.min() < -0.01 or valid_vals.max() > 1.01)
        ):
            has_out_of_range = True

    with np.errstate(invalid="ignore"):
        mean_shdi = np.where(
            count_shdi > 0,
            mean_shdi / count_shdi,
            np.nan,
        )

    last_valid_t = n_t - 1
    for t in range(n_t - 1, -1, -1):
        sl = grid[t, :, :, shdi_idx].astype(np.float64)
        if (~np.isnan(sl)).sum() > 0:
            last_valid_t = t
            break

    latest_shdi = (
        grid[last_valid_t, :, :, shdi_idx].astype(np.float64)
    )
    nan_mask = np.isnan(latest_shdi)

    # Top-12 most-changed cells (deduped by GDL region)
    max_change = np.zeros((n_h, n_w), dtype=np.float64)
    for t in range(1, n_t):
        prev = grid[t - 1, :, :, shdi_idx].astype(np.float64)
        curr = grid[t, :, :, shdi_idx].astype(np.float64)
        diff = np.abs(curr - prev)
        diff = np.where(np.isnan(diff), 0.0, diff)
        max_change = np.maximum(max_change, diff)

    pgid_to_gdl = _load_gdl_crosswalk()
    sorted_flat = np.argsort(max_change.ravel())[::-1]
    seen_regions: set[str] = set()
    selected: list[int] = []
    for idx in sorted_flat:
        if len(selected) >= 12:
            break
        r, c = int(idx // n_w), int(idx % n_w)
        pgid = r * n_w + c + 1
        gdl_code = pgid_to_gdl.get(pgid, "")
        if gdl_code and gdl_code in seen_regions:
            continue
        if max_change[r, c] <= 0:
            break
        if gdl_code:
            seen_regions.add(gdl_code)
        selected.append(int(idx))

    while len(selected) < 12:
        selected.append(selected[-1] if selected else 0)

    top_rows = np.array([s // n_w for s in selected])
    top_cols = np.array([s % n_w for s in selected])
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = float(grid[t, r, c, shdi_idx])

    # GDL-region-level data for distribution/broadcast plots
    gdl_to_cells: dict[str, list[tuple[int, int]]] = {}
    for pgid, gdl_code in pgid_to_gdl.items():
        pr = (pgid - 1) // n_w
        pc = (pgid - 1) % n_w
        if 0 <= pr < n_h and 0 <= pc < n_w:
            gdl_to_cells.setdefault(
                gdl_code, [],
            ).append((pr, pc))

    region_codes_list = sorted(gdl_to_cells.keys())
    n_regions = len(region_codes_list)

    if n_regions > 0:
        rep_rows = np.array([
            gdl_to_cells[rc][0][0]
            for rc in region_codes_list
        ])
        rep_cols = np.array([
            gdl_to_cells[rc][0][1]
            for rc in region_codes_list
        ])

        sl_latest = grid[
            last_valid_t, :, :, :,
        ].astype(np.float64)
        region_vals = sl_latest[
            rep_rows, rep_cols, :,
        ].astype(np.float64)

        # Find first valid time step for SHDI
        first_valid_t = 0
        shdi_epoch_offset = (SHDI_START_YEAR - start_year) * 12
        if shdi_epoch_offset > 0:
            first_valid_t = shdi_epoch_offset

        sl_first = grid[
            first_valid_t, :, :, :,
        ].astype(np.float64)
        region_vals_t0 = sl_first[
            rep_rows, rep_cols, :,
        ].astype(np.float64)
    else:
        region_vals = np.empty(
            (0, n_f), dtype=np.float64,
        )
        region_vals_t0 = np.empty(
            (0, n_f), dtype=np.float64,
        )

    # Statistical checks
    n_land = (
        int((~ocean_mask).sum())
        if ocean_mask.any()
        else n_h * n_w
    )
    n_covered = int((~nan_mask & ~ocean_mask).sum())
    coverage_pct = (
        n_covered / n_land * 100 if n_land > 0 else 0.0
    )

    step_violations = 0
    for t in range(1, n_t):
        if (t % 12) != 0:
            prev = grid[t - 1, :, :, shdi_idx].astype(
                np.float64,
            )
            curr = grid[t, :, :, shdi_idx].astype(
                np.float64,
            )
            both_valid = ~np.isnan(prev) & ~np.isnan(curr)
            if both_valid.any():
                diffs = np.abs(curr[both_valid] - prev[both_valid])
                step_violations += int((diffs > 1e-9).sum())

    nan_count = int(np.isnan(grid[:]).sum())
    total_cells = n_t * n_h * n_w * n_f
    nan_pct = nan_count / total_cells * 100

    shdi_epoch_offset = (SHDI_START_YEAR - start_year) * 12
    nan_before_ok = True
    if shdi_epoch_offset > 0:
        pre_shdi = grid[:shdi_epoch_offset, :, :, :]
        if not np.all(np.isnan(pre_shdi)):
            nan_before_ok = False

    mean_val = float(np.nanmean(latest_shdi))

    checks: dict[str, bool | str] = {
        "feature_count_correct": n_f == len(SHDI_FEATURES),
        "values_in_range": not has_out_of_range,
        "coverage_adequate": coverage_pct > 30.0,
        "step_function_holds": step_violations == 0,
        "nan_before_1990": nan_before_ok,
        "nan_present": nan_pct > 0,
        "mean_shdi_reasonable": 0.3 < mean_val < 0.8,
    }
    detail_map: dict[str, str] = {
        "feature_count_correct": (
            f"{n_f} features"
            f" (expected {len(SHDI_FEATURES)})"
        ),
        "values_in_range": (
            "all values in [0, 1]"
            if not has_out_of_range
            else "values found outside [0, 1]"
        ),
        "coverage_adequate": (
            f"{n_covered:,} of {n_land:,} land cells"
            f" covered ({coverage_pct:.1f}%)"
        ),
        "step_function_holds": (
            f"{step_violations:,} within-year value"
            f" changes"
        ),
        "nan_before_1990": (
            f"{'all NaN' if nan_before_ok else 'data found'}"
            f" before {SHDI_START_YEAR}"
        ),
        "nan_present": (
            f"{nan_count:,} NaN cells out of"
            f" {total_cells:,} ({nan_pct:.1f}%)"
        ),
        "mean_shdi_reasonable": (
            f"global mean SHDI = {mean_val:.3f}"
        ),
    }
    checks["_details"] = detail_map  # type: ignore[assignment]

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t, start_year=start_year),
        start_year=start_year,
        shdi_idx=shdi_idx,
        last_valid_t=last_valid_t,
        latest_shdi=latest_shdi,
        mean_shdi=mean_shdi,
        nan_mask=nan_mask,
        monthly_mean=monthly_mean,
        monthly_coverage=monthly_coverage,
        top_rows=top_rows,
        top_cols=top_cols,
        top_ts=top_ts,
        checks=checks,
        region_values=region_vals,
        region_values_t0=region_vals_t0,
        region_codes=region_codes_list,
        region_cells=gdl_to_cells,
    )


# -- Plot functions -------------------------------------------------


def plot_shdi_map(
    d: PrecomputedData, out: Path,
) -> None:
    """01 — SHDI composite index, latest time step."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = d.latest_shdi.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im = ax.imshow(
        display, cmap=CMAP_SHDI, aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    latest_year = d.start_year + d.last_valid_t // 12
    style_ax(
        ax,
        title=(
            f"SHDI composite index"
            f" (latest: ~{latest_year})"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax,
        label="SHDI (0=low, 1=high development)",
    )
    save_plot(fig, out, "01_shdi_map.png")


def plot_mean_shdi(
    d: PrecomputedData, out: Path,
) -> None:
    """02 — Time-averaged SHDI composite index."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = d.mean_shdi.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im = ax.imshow(
        display, cmap=CMAP_SHDI, aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    style_ax(
        ax,
        title=(
            f"SHDI time-averaged composite,"
            f" {d.start_year}"
            f"–{d.start_year + d.n_t // 12}"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax, label="Mean SHDI",
    )
    save_plot(fig, out, "02_mean_shdi.png")


def plot_per_feature_maps(
    d: PrecomputedData, out: Path,
) -> None:
    """03 — 2x2 panel of all 4 SHDI features."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_panels = min(d.n_f, 4)
    fig, axes = plt.subplots(
        2, 2, figsize=FIG_PANEL_2x2,
    )

    for i, ax in enumerate(axes.flat):
        if i >= n_panels:
            ax.set_visible(False)
            continue
        sl = (
            d.grid[d.last_valid_t, :, :, i]
            .astype(np.float64)
        )
        display = sl.copy()
        display[d.ocean_mask] = np.nan
        display = np.flipud(display)
        im = ax.imshow(
            display, cmap=CMAP_SHDI, aspect="auto",
            extent=EXTENT, vmin=0, vmax=1,
        )
        short_name = d.features[i].replace("shdi_", "")
        style_ax(ax, title=short_name)
        plt.colorbar(im, ax=ax, shrink=0.7)

    fig.suptitle(
        "SHDI: all features (latest epoch)",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "03_per_feature_maps.png")


def plot_monthly_timeseries(
    d: PrecomputedData, out: Path,
) -> None:
    """04 — Global mean SHDI over time + coverage."""
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9),
        gridspec_kw={"hspace": 0.35},
    )

    ax1.plot(
        d.dates, d.monthly_mean,
        color=COLOR_ACCENT, linewidth=1.5,
    )
    ax1.fill_between(
        d.dates, d.monthly_mean,
        color=COLOR_ACCENT, alpha=0.15, linewidth=0,
    )
    style_ax(
        ax1,
        title="Global mean SHDI over time",
        xlabel="Date",
        ylabel="Mean index value",
    )
    ax1.set_xlim(d.dates[0], d.dates[-1])
    ax1.set_ylim(0, 1)

    ax2.plot(
        d.dates, d.monthly_coverage,
        color="#27AE60", linewidth=1.5,
    )
    ax2.fill_between(
        d.dates, d.monthly_coverage,
        color="#27AE60", alpha=0.15, linewidth=0,
    )
    style_ax(
        ax2,
        title="Spatial coverage (% of grid cells with data)",
        xlabel="Date",
        ylabel="Coverage (%)",
    )
    ax2.set_xlim(d.dates[0], d.dates[-1])
    ax2.set_ylim(0, 100)

    save_plot(fig, out, "04_monthly_timeseries.png")


def plot_epoch_comparison(
    d: PrecomputedData, out: Path,
) -> None:
    """05 — Side-by-side spatial maps at start/mid/end."""
    import matplotlib.pyplot as plt
    import numpy as np

    last_data_year = d.start_year + d.last_valid_t // 12
    snapshot_years = [SHDI_START_YEAR, 2006, last_data_year]
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
        sl = (
            d.grid[t_idx, :, :, d.shdi_idx]
            .astype(np.float64)
        )
        display = sl.copy()
        display[d.ocean_mask] = np.nan
        display = np.flipud(display)
        mean_val = float(np.nanmean(sl))
        ax.imshow(
            display, cmap=CMAP_SHDI, aspect="auto",
            extent=EXTENT, vmin=0, vmax=1,
        )
        style_ax(ax, title=f"{year} (mean={mean_val:.3f})")

    fig.suptitle(
        "SHDI composite across epochs",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "05_epoch_comparison.png")


def plot_change_map(
    d: PrecomputedData, out: Path,
) -> None:
    """06 — Development gains vs losses (first to last)."""
    import matplotlib.pyplot as plt
    import numpy as np

    shdi_epoch_offset = (SHDI_START_YEAR - d.start_year) * 12
    first_t = max(0, shdi_epoch_offset)

    first_sl = (
        d.grid[first_t, :, :, d.shdi_idx]
        .astype(np.float64)
    )
    last_sl = (
        d.grid[d.last_valid_t, :, :, d.shdi_idx]
        .astype(np.float64)
    )
    change = last_sl - first_sl

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    gain = np.where(
        np.isnan(change), np.nan,
        np.maximum(change, 0),
    )
    display_gain = gain.copy()
    display_gain[d.ocean_mask] = np.nan
    display_gain = np.flipud(display_gain)
    vmax_gain = float(np.nanmax(gain)) if not np.all(
        np.isnan(gain),
    ) else 0.5
    im1 = axes[0].imshow(
        display_gain, cmap="Greens", aspect="auto",
        extent=EXTENT, vmin=0,
        vmax=max(vmax_gain, 0.01),
    )
    first_year = d.start_year + first_t // 12
    last_year = d.start_year + d.last_valid_t // 12
    style_ax(
        axes[0],
        title=(
            f"Development gains"
            f" {first_year}–{last_year}"
        ),
    )
    plt.colorbar(
        im1, ax=axes[0], shrink=0.7,
        label="Δ SHDI",
    )

    loss = np.where(
        np.isnan(change), np.nan,
        np.maximum(-change, 0),
    )
    display_loss = loss.copy()
    display_loss[d.ocean_mask] = np.nan
    display_loss = np.flipud(display_loss)
    vmax_loss = float(np.nanmax(loss)) if not np.all(
        np.isnan(loss),
    ) else 0.5
    im2 = axes[1].imshow(
        display_loss, cmap="Reds", aspect="auto",
        extent=EXTENT, vmin=0,
        vmax=max(vmax_loss, 0.01),
    )
    style_ax(
        axes[1],
        title=(
            f"Development losses"
            f" {first_year}–{last_year}"
        ),
    )
    plt.colorbar(
        im2, ax=axes[1], shrink=0.7,
        label="Δ SHDI",
    )

    fig.tight_layout()
    save_plot(fig, out, "06_change_map.png")


def plot_trajectories(
    d: PrecomputedData, out: Path,
) -> None:
    """07 — Top-12 most-changed cells over time."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(
        4, 3, figsize=FIG_PANEL_4x3, sharex=True,
        gridspec_kw={"hspace": 0.35, "wspace": 0.25},
    )
    for k, ax in enumerate(axes.flat):
        ts = d.top_ts[k]
        ax.plot(
            d.dates, ts,
            color=COLOR_ACCENT, linewidth=1,
        )
        ax.fill_between(
            d.dates, ts,
            color=COLOR_ACCENT, alpha=0.3, linewidth=0,
        )

        label = cell_to_label(
            int(d.top_rows[k]), int(d.top_cols[k]),
            d.n_h, d.n_w,
        )
        delta = float(np.nanmax(ts) - np.nanmin(ts))
        style_ax(
            ax,
            title=f"{label} (Δ={delta:.2f})",
        )
        ax.set_xlim(d.dates[0], d.dates[-1])
        ax.set_ylim(0, 1)

    fig.suptitle(
        "SHDI: 12 cells with largest change"
        " (1 per GDL region)",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "07_trajectories.png")


def plot_concentration(
    d: PrecomputedData, out: Path,
) -> None:
    """08 — Lorenz curve for SHDI development inequality."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = d.latest_shdi[~d.ocean_mask & ~d.nan_mask]
    land_vals = np.sort(land_vals.ravel())
    if len(land_vals) == 0 or land_vals.sum() == 0:
        return

    n_land = len(land_vals)
    cum_share = np.cumsum(land_vals) / land_vals.sum()
    x_pct = np.arange(1, n_land + 1) / n_land

    gini = (
        1.0 - 2.0 * np.trapezoid(cum_share, dx=1 / n_land)
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
        title="Concentration of SHDI values",
        xlabel=(
            "Cumulative % of covered cells (ranked)"
        ),
        ylabel="Cumulative % of total SHDI",
    )
    ax.text(
        15, 85, f"Gini = {gini:.3f}",
        fontsize=13, fontweight="bold",
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
    import numpy as np

    rows_data = []
    for name, lat, lon, expected in SPOT_CHECK_LOCATIONS:
        row = int((lat + 90.0) / (180.0 / d.n_h))
        col = int((lon + 180.0) / (360.0 / d.n_w))
        row = max(0, min(row, d.n_h - 1))
        col = max(0, min(col, d.n_w - 1))

        val = float(d.latest_shdi[row, col])

        if expected == "high":
            status = (
                "PASS" if (not np.isnan(val) and val > 0.8)
                else "INVESTIGATE"
            )
        elif expected == "mid":
            status = (
                "PASS"
                if (not np.isnan(val) and 0.4 < val < 0.95)
                else "INVESTIGATE"
            )
        elif expected == "low":
            status = (
                "PASS" if (not np.isnan(val) and val < 0.6)
                else "INVESTIGATE"
            )
        else:
            status = (
                "PASS" if np.isnan(val) else "INVESTIGATE"
            )

        val_str = (
            f"{val:.3f}" if not np.isnan(val) else "NaN"
        )
        rows_data.append([
            name,
            f"({row}, {col})",
            val_str,
            expected,
            status,
        ])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis("off")

    col_labels = [
        "Location", "Cell (r,c)", "SHDI",
        "Expected", "Status",
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
        "Spot-check: SHDI values at known locations",
        fontsize=FONT_TITLE, fontweight="bold", pad=20,
    )
    save_plot(fig, out, "09_spot_checks.png")


def plot_nan_coverage(
    d: PrecomputedData, out: Path,
) -> None:
    """10 — NaN coverage map + calendar heatmap."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14, 5),
    )

    nan_frac = np.zeros((d.n_h, d.n_w), dtype=np.float64)
    for t in range(d.n_t):
        sl = d.grid[t, :, :, d.shdi_idx].astype(
            np.float64,
        )
        nan_frac += np.isnan(sl).astype(np.float64)
    nan_frac /= d.n_t

    display = nan_frac.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im1 = ax1.imshow(
        display, cmap="YlOrRd", aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    style_ax(
        ax1,
        title="NaN fraction across time",
    )
    plt.colorbar(
        im1, ax=ax1, shrink=0.7,
        label="Fraction of months with NaN",
    )

    n_years = (d.n_t + 11) // 12
    cal = np.full(
        (n_years, 12), np.nan, dtype=np.float64,
    )
    for t in range(d.n_t):
        cal[t // 12, t % 12] = d.monthly_coverage[t]

    im2 = ax2.imshow(
        cal, cmap="YlGn",
        aspect="auto", interpolation="nearest",
        vmin=0, vmax=100,
    )
    ax2.set_xticks(range(12))
    ax2.set_xticklabels(
        ["J", "F", "M", "A", "M", "J",
         "J", "A", "S", "O", "N", "D"],
        fontsize=FONT_TICK,
    )
    ax2.set_yticks(range(0, n_years, max(1, n_years // 15)))
    ax2.set_yticklabels(
        [
            str(d.start_year + y)
            for y in range(
                0, n_years, max(1, n_years // 15),
            )
        ],
        fontsize=7,
    )
    style_ax(
        ax2,
        title="Coverage by calendar month",
        xlabel="Month",
        ylabel="Year",
    )
    plt.colorbar(
        im2, ax=ax2, shrink=0.7,
        label="Coverage (%)",
    )

    fig.tight_layout()
    save_plot(fig, out, "10_nan_coverage.png")


def plot_feature_correlation(
    d: PrecomputedData, out: Path,
) -> None:
    """11 — 4x4 Pearson correlation heatmap."""
    import matplotlib.pyplot as plt
    import numpy as np

    vals = d.region_values
    n_f = vals.shape[1]
    if vals.shape[0] < 3:
        print("  (skipped — too few regions)")
        return

    corr = np.full((n_f, n_f), np.nan)
    for i in range(n_f):
        corr[i, i] = 1.0
        for j in range(i + 1, n_f):
            mask = (
                ~np.isnan(vals[:, i])
                & ~np.isnan(vals[:, j])
            )
            if mask.sum() < 3:
                continue
            xi = vals[mask, i]
            xj = vals[mask, j]
            if np.std(xi) < 1e-12 or np.std(xj) < 1e-12:
                continue
            r = float(np.corrcoef(xi, xj)[0, 1])
            corr[i, j] = r
            corr[j, i] = r

    labels = [
        d.features[i].replace("shdi_", "")
        for i in range(n_f)
    ]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(
        corr, cmap="RdBu_r",
        vmin=-1, vmax=1, aspect="equal",
    )
    ax.set_xticks(range(n_f))
    ax.set_xticklabels(labels, rotation=45, fontsize=10)
    ax.set_yticks(range(n_f))
    ax.set_yticklabels(labels, fontsize=10)
    plt.colorbar(
        im, ax=ax, shrink=0.8, label="Pearson r",
    )

    for i in range(n_f):
        for j in range(n_f):
            if not np.isnan(corr[i, j]):
                ax.text(
                    j, i, f"{corr[i, j]:.2f}",
                    ha="center", va="center",
                    fontsize=11, fontweight="bold",
                )

    n_high = sum(
        1 for i in range(n_f) for j in range(i + 1, n_f)
        if not np.isnan(corr[i, j]) and abs(corr[i, j]) > 0.9
    )
    style_ax(
        ax,
        title=(
            f"SHDI feature correlation"
            f" ({n_high} pairs with |r| > 0.9)"
        ),
    )
    fig.tight_layout()
    save_plot(fig, out, "11_feature_correlation.png")


def plot_region_distributions(
    d: PrecomputedData, out: Path,
) -> None:
    """12 — Histograms of GDL-region-level feature values."""
    import matplotlib.pyplot as plt
    import numpy as np

    n_panels = min(d.n_f, 4)
    if d.region_values.shape[0] == 0:
        print("  (skipped — no GDL crosswalk)")
        return

    fig, axes = plt.subplots(2, 2, figsize=FIG_PANEL_2x2)

    for i in range(n_panels):
        ax = axes.flat[i]
        raw = d.region_values[:, i]
        valid = raw[~np.isnan(raw)]
        if len(valid) == 0:
            ax.text(
                0.5, 0.5, "No data",
                ha="center", va="center",
                transform=ax.transAxes,
            )
            short = d.features[i].replace("shdi_", "")
            style_ax(ax, title=short)
            continue

        ax.hist(
            valid, bins=30,
            color=COLOR_ACCENT,
            edgecolor="white", alpha=0.9,
        )
        median = float(np.median(valid))
        ax.axvline(
            median, color="red",
            linestyle="--", linewidth=1.5,
        )

        q25 = float(np.percentile(valid, 25))
        q75 = float(np.percentile(valid, 75))
        iqr = q75 - q25
        mean_v = float(np.mean(valid))
        std_v = float(np.std(valid))
        skew = (
            3.0 * (mean_v - median) / std_v
            if std_v > 1e-12 else 0.0
        )

        ax.text(
            0.97, 0.95,
            f"n={len(valid)}\n"
            f"med={median:.2f}\n"
            f"IQR={iqr:.2f}\n"
            f"skew={skew:.2f}",
            transform=ax.transAxes,
            ha="right", va="top", fontsize=7,
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "white",
                "alpha": 0.8,
            },
        )

        short = d.features[i].replace("shdi_", "")
        style_ax(ax, title=f"{short} [0,1]")
        ax.set_ylabel("GDL regions")

    for i in range(n_panels, 4):
        axes.flat[i].set_visible(False)

    fig.suptitle(
        f"GDL-region score distributions"
        f" ({len(d.region_codes)} regions,"
        f" latest epoch)",
        fontsize=FONT_TITLE, fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "12_region_distributions.png")


def plot_feature_temporal(
    d: PrecomputedData, out: Path,
) -> None:
    """13 — Global mean of each feature over time (annual)."""
    import matplotlib.pyplot as plt
    import numpy as np

    years = list(
        range(d.start_year, d.start_year + d.n_t // 12),
    )
    n_years = len(years)
    means = np.full(
        (n_years, d.n_f), np.nan, dtype=np.float64,
    )

    for y_idx, year in enumerate(years):
        t = (year - d.start_year) * 12
        if not (0 <= t < d.n_t):
            continue
        sl = d.grid[t, :, :, :].astype(np.float64)
        for f in range(d.n_f):
            fsl = sl[:, :, f]
            if not np.isnan(fsl).all():
                means[y_idx, f] = float(
                    np.nanmean(fsl),
                )

    colors = ["black", "#E74C3C", "#3498DB", "#27AE60"]

    fig, ax = plt.subplots(figsize=(14, 6))

    for f in range(d.n_f):
        raw = d.features[f].replace("shdi_", "")
        is_composite = raw == "shdi"
        lw = 2.5 if is_composite else 1.5
        alpha = 1.0 if is_composite else 0.7
        color = colors[f % len(colors)]
        ax.plot(
            years, means[:, f],
            color=color, linewidth=lw,
            alpha=alpha, label=raw,
        )

    ax.set_ylim(0, 1)
    style_ax(
        ax,
        title=f"SHDI features over time ({d.n_f} features)",
        xlabel="Year",
        ylabel="Global mean",
    )
    ax.legend(
        loc="lower right",
        fontsize=10,
    )

    fig.tight_layout()
    save_plot(fig, out, "13_feature_temporal.png")


def plot_broadcast_integrity(
    d: PrecomputedData, out: Path,
) -> None:
    """14 — Within-GDL-region std dev (should be zero)."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not d.region_cells:
        print("  (skipped — no GDL crosswalk)")
        return

    all_vals = d.grid[
        d.last_valid_t, :, :, :,
    ].astype(np.float64)

    std_map = np.full(
        (d.n_h, d.n_w), np.nan, dtype=np.float64,
    )
    region_max_std: dict[str, float] = {}

    for gdl_code, cells in d.region_cells.items():
        if len(cells) < 2:
            continue

        rows = [rc[0] for rc in cells]
        cols = [rc[1] for rc in cells]
        cell_vals = all_vals[rows, cols, :]

        shdi_v = cell_vals[:, d.shdi_idx]
        valid = ~np.isnan(shdi_v)
        if valid.sum() < 2:
            continue

        std_val = float(np.std(shdi_v[valid]))

        max_std = 0.0
        for f in range(d.n_f):
            fv = cell_vals[:, f]
            fvalid = ~np.isnan(fv)
            if fvalid.sum() >= 2:
                max_std = max(
                    max_std,
                    float(np.std(fv[fvalid])),
                )

        region_max_std[gdl_code] = max_std
        for r_i, c_i in cells:
            std_map[r_i, c_i] = std_val

    max_any = (
        float(np.nanmax(std_map))
        if not np.all(np.isnan(std_map))
        else 0.0
    )
    all_zero = max_any < 1e-12

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14, 5),
    )

    display = std_map.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im = ax1.imshow(
        display, cmap="Reds", aspect="auto",
        extent=EXTENT, vmin=0, vmax=0.01,
    )
    style_ax(
        ax1,
        title="Within-GDL-region std dev (SHDI)",
    )
    plt.colorbar(
        im, ax=ax1, shrink=0.7, label="Std dev",
    )

    if all_zero:
        ax1.text(
            0.5, 0.5,
            "PASS: within-region\nvariance = 0",
            transform=ax1.transAxes,
            ha="center", va="center",
            fontsize=14, fontweight="bold",
            color="#27AE60",
            bbox={
                "boxstyle": "round,pad=0.5",
                "facecolor": "white",
                "alpha": 0.8,
            },
        )

    if all_zero or not region_max_std:
        ax2.text(
            0.5, 0.5,
            "PASS: all GDL regions\n"
            "have zero variance",
            transform=ax2.transAxes,
            ha="center", va="center",
            fontsize=14, fontweight="bold",
            color="#27AE60",
        )
        style_ax(
            ax2,
            title=(
                "Max within-region std (all features)"
            ),
        )
    else:
        top10 = sorted(
            region_max_std.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        names = [c[0] for c in top10]
        stds = [c[1] for c in top10]
        ax2.barh(
            range(len(names)), stds, color="#C0392B",
        )
        ax2.set_yticks(range(len(names)))
        ax2.set_yticklabels(names, fontsize=8)
        ax2.invert_yaxis()
        style_ax(
            ax2,
            title=(
                "Top 10 GDL regions by"
                " max within-region std"
            ),
            xlabel="Std dev",
        )

    fig.tight_layout()
    save_plot(fig, out, "14_broadcast_integrity.png")


# -- Summary -------------------------------------------------------


def print_summary(d: PrecomputedData) -> bool:
    print()
    print("=" * 60)
    print("SHDI GRID VERIFICATION SUMMARY")
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

    import numpy as np
    print(
        f"Feature summary (t={d.last_valid_t},"
        f" ~{d.start_year + d.last_valid_t // 12}):"
    )
    for feat in d.features:
        idx = d.features.index(feat)
        sl = (
            d.grid[d.last_valid_t, :, :, idx]
            .astype(np.float64)
        )
        n_nan = int(np.isnan(sl).sum())
        n_total = d.n_h * d.n_w
        mean = float(np.nanmean(sl))
        short = feat.replace("shdi_", "")
        print(
            f"  {short:<18s}  mean={mean:.3f}"
            f"  NaN={n_nan:,}/{n_total:,}"
            f"  [0,1]"
        )

    if d.region_codes:
        print(
            f"\n  GDL regions: {len(d.region_codes)}"
        )

    print()
    print("Statistical checks:")
    all_pass = True
    detail_map = d.checks.get("_details", {})
    for name, value in d.checks.items():
        if name.startswith("_"):
            continue
        status = "PASS" if value else "INVESTIGATE"
        marker = "  [+]" if value else "  [!]"
        detail = detail_map.get(name, "")  # type: ignore[union-attr]
        suffix = f" -- {detail}" if detail else ""
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
    ("SHDI Map", plot_shdi_map),
    ("Mean SHDI", plot_mean_shdi),
    ("Per-Feature Maps", plot_per_feature_maps),
    ("Monthly Time Series", plot_monthly_timeseries),
    ("Epoch Comparison", plot_epoch_comparison),
    ("Change Map", plot_change_map),
    ("Trajectories", plot_trajectories),
    ("Concentration", plot_concentration),
    ("Spot Checks", plot_spot_checks),
    ("NaN Coverage", plot_nan_coverage),
    ("Feature Correlation", plot_feature_correlation),
    ("Region Distributions", plot_region_distributions),
    ("Feature Temporal", plot_feature_temporal),
    ("Broadcast Integrity", plot_broadcast_integrity),
]


def main() -> int:
    sys.stdout.reconfigure(  # type: ignore[attr-defined]
        line_buffering=True,
    )

    parser = argparse.ArgumentParser(
        description="SHDI grid verification audit",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/compiled/shdi"),
        help="Compiled SHDI grid directory",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/audit_shdi"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        print(
            "Run the SHDI pipeline first: "
            "python scripts/run_shdi_pipeline.py"
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
    lvt = data.last_valid_t
    print(
        f"  Latest global mean SHDI (t={lvt}): "
        f"{data.monthly_mean[lvt]:.3f}"
    )
    print(
        f"  Coverage: "
        f"{data.monthly_coverage[lvt]:.1f}% of cells"
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
