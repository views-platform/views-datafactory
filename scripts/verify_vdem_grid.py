#!/usr/bin/env python3
"""V-Dem grid verification — 10 plots + statistical checks proving
spatial, temporal, and structural correctness before release.

Usage:
    uv run python scripts/verify_vdem_grid.py
    uv run python scripts/verify_vdem_grid.py --input data/compiled/vdem

Reads the compiled V-Dem grid and produces PNG plots to
``reports/audit_vdem/`` plus a statistical summary on stdout.

V-Dem features use two scales: 17 are bounded [0,1] indices and
5 use interval scale (centered ~0, range approx [-2.3,+2.3]):
v2x_horacc, v2x_veracc, v2x_diagacc, v2x_divparctrl,
v2x_accountability.  NaN means "no V-Dem coverage" and must be
preserved (not converted to 0.0; see C-205, C-213).

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

CMAP_VDEM = "RdYlGn"

INTERVAL_SCALE_FEATURES = {
    "v2x_horacc", "v2x_veracc", "v2x_diagacc",
    "v2x_divparctrl", "v2x_accountability",
}

REPRESENTATIVE_FEATURES = [
    "vdem_v2x_libdem",
    "vdem_v2x_accountability",
    "vdem_v2x_clphy",
    "vdem_v2xcl_rol",
    "vdem_v2x_ex_military",
    "vdem_v2xnp_regcorr",
]

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
    ("Norway", 60.5, 10.7, "high"),
    ("Sweden", 59.3, 18.1, "high"),
    ("Denmark", 55.4, 10.4, "high"),
    ("USA", 38.9, -77.0, "mid"),
    ("India", 28.6, 77.2, "mid"),
    ("Brazil", -15.8, -47.9, "mid"),
    ("Russia", 55.8, 37.6, "low"),
    ("China", 39.9, 116.4, "low"),
    ("Syria", 33.5, 36.3, "low"),
    ("Algeria (Sahara)", 23.0, 5.0, "low"),
    ("Brazil (Amazon)", -5.0, -65.0, "mid"),
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


def _load_country_map() -> dict[int, str]:
    """Load GAUL pgid→ISO3 mapping for trajectory dedup."""
    gaul_path = Path("data/raw/gaul_admin/iso3_code.parquet")
    if not gaul_path.exists():
        return {}
    import pyarrow.parquet as pq

    t = pq.read_table(gaul_path)
    gids = t.column("gid").to_pylist()
    iso3s = t.column("value").to_pylist()
    return dict(zip(gids, iso3s, strict=True))


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

    libdem_idx: int
    last_valid_t: int

    latest_libdem: np.ndarray
    mean_libdem: np.ndarray
    nan_mask: np.ndarray

    monthly_mean: np.ndarray
    monthly_coverage: np.ndarray

    top_rows: np.ndarray
    top_cols: np.ndarray
    top_ts: np.ndarray

    checks: dict[str, bool | str]

    country_values: np.ndarray
    country_values_t0: np.ndarray
    country_iso3: list[str]
    country_cells: dict[str, list[tuple[int, int]]]


def precompute(
    grid: np.ndarray,
    features: list[str],
    start_year: int,
) -> PrecomputedData:
    import numpy as np

    n_t, n_h, n_w, n_f = grid.shape

    libdem_name = "vdem_v2x_libdem"
    if libdem_name not in features:
        libdem_name = features[0]
    libdem_idx = features.index(libdem_name)

    ocean_mask = _load_ocean_mask(n_h, n_w)

    monthly_mean = np.zeros(n_t, dtype=np.float64)
    monthly_coverage = np.zeros(n_t, dtype=np.float64)
    mean_libdem = np.zeros((n_h, n_w), dtype=np.float64)
    count_libdem = np.zeros((n_h, n_w), dtype=np.float64)

    has_out_of_range = False

    for t in range(n_t):
        sl = grid[t, :, :, libdem_idx].astype(np.float64)
        valid = ~np.isnan(sl)
        n_valid = valid.sum()
        if n_valid > 0:
            monthly_mean[t] = float(np.nanmean(sl))
            mean_libdem[valid] += sl[valid]
            count_libdem[valid] += 1
        monthly_coverage[t] = n_valid / (n_h * n_w) * 100
        valid_vals = sl[valid]
        if (
            len(valid_vals) > 0
            and (valid_vals.min() < -0.01 or valid_vals.max() > 1.01)
        ):
            has_out_of_range = True

    with np.errstate(invalid="ignore"):
        mean_libdem = np.where(
            count_libdem > 0,
            mean_libdem / count_libdem,
            np.nan,
        )

    last_valid_t = n_t - 1
    for t in range(n_t - 1, -1, -1):
        sl = grid[t, :, :, libdem_idx].astype(np.float64)
        if (~np.isnan(sl)).sum() > 0:
            last_valid_t = t
            break

    latest_libdem = (
        grid[last_valid_t, :, :, libdem_idx].astype(np.float64)
    )
    nan_mask = np.isnan(latest_libdem)

    variance_ts = np.zeros(n_t, dtype=np.float64)
    for t in range(n_t):
        sl = grid[t, :, :, libdem_idx].astype(np.float64)
        valid = ~np.isnan(sl)
        if valid.sum() > 1:
            variance_ts[t] = float(np.nanvar(sl))

    max_change = np.zeros((n_h, n_w), dtype=np.float64)
    for t in range(1, n_t):
        prev = grid[t - 1, :, :, libdem_idx].astype(np.float64)
        curr = grid[t, :, :, libdem_idx].astype(np.float64)
        diff = np.abs(curr - prev)
        diff = np.where(np.isnan(diff), 0.0, diff)
        max_change = np.maximum(max_change, diff)

    pgid_to_iso3 = _load_country_map()
    sorted_flat = np.argsort(max_change.ravel())[::-1]
    seen_countries: set[str] = set()
    selected: list[int] = []
    for idx in sorted_flat:
        if len(selected) >= 12:
            break
        r, c = int(idx // n_w), int(idx % n_w)
        pgid = r * n_w + c + 1
        iso3 = pgid_to_iso3.get(pgid, "")
        if iso3 and iso3 in seen_countries:
            continue
        if max_change[r, c] <= 0:
            break
        if iso3:
            seen_countries.add(iso3)
        selected.append(int(idx))

    while len(selected) < 12:
        selected.append(selected[-1] if selected else 0)

    top_rows = np.array([s // n_w for s in selected])
    top_cols = np.array([s % n_w for s in selected])
    top_ts = np.zeros((12, n_t), dtype=np.float64)
    for t in range(n_t):
        for k in range(12):
            r, c = int(top_rows[k]), int(top_cols[k])
            top_ts[k, t] = float(grid[t, r, c, libdem_idx])

    # Country-level data for plots 11-15
    iso3_to_cells: dict[str, list[tuple[int, int]]] = {}
    for pgid, iso3_c in pgid_to_iso3.items():
        pr = (pgid - 1) // n_w
        pc = (pgid - 1) % n_w
        if 0 <= pr < n_h and 0 <= pc < n_w:
            iso3_to_cells.setdefault(
                iso3_c, [],
            ).append((pr, pc))

    country_iso3_list = sorted(iso3_to_cells.keys())
    n_ctry = len(country_iso3_list)

    if n_ctry > 0:
        rep_rows = np.array([
            iso3_to_cells[ci][0][0]
            for ci in country_iso3_list
        ])
        rep_cols = np.array([
            iso3_to_cells[ci][0][1]
            for ci in country_iso3_list
        ])

        all_at_lvt = grid[
            last_valid_t, :, :, :,
        ].astype(np.float64)
        feat_last = np.full(
            n_f, last_valid_t, dtype=int,
        )
        for f in range(n_f):
            if np.isnan(all_at_lvt[:, :, f]).all():
                for ts in range(
                    last_valid_t - 1, -1, -1,
                ):
                    if not np.isnan(
                        grid[ts, :, :, f],
                    ).all():
                        feat_last[f] = ts
                        break

        t_to_feats: dict[int, list[int]] = {}
        for f in range(n_f):
            t_to_feats.setdefault(
                int(feat_last[f]), [],
            ).append(f)

        ctry_vals = np.full(
            (n_ctry, n_f), np.nan, dtype=np.float64,
        )
        for t_f, flist in t_to_feats.items():
            sl_t = grid[t_f, :, :, :].astype(
                np.float64,
            )
            for f in flist:
                ctry_vals[:, f] = sl_t[
                    rep_rows, rep_cols, f,
                ]

        sl_zero = grid[0, :, :, :].astype(
            np.float64,
        )
        ctry_vals_t0 = sl_zero[
            rep_rows, rep_cols, :,
        ].astype(np.float64)
    else:
        ctry_vals = np.empty(
            (0, n_f), dtype=np.float64,
        )
        ctry_vals_t0 = np.empty(
            (0, n_f), dtype=np.float64,
        )

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
            prev = grid[t - 1, :, :, libdem_idx].astype(
                np.float64,
            )
            curr = grid[t, :, :, libdem_idx].astype(
                np.float64,
            )
            both_valid = ~np.isnan(prev) & ~np.isnan(curr)
            if both_valid.any():
                diffs = np.abs(curr[both_valid] - prev[both_valid])
                step_violations += int((diffs > 1e-9).sum())

    nan_count = int(np.isnan(grid[:]).sum())
    total_cells = n_t * n_h * n_w * n_f
    nan_pct = nan_count / total_cells * 100

    checks: dict[str, bool | str] = {
        "values_in_range": not has_out_of_range,
        "coverage_adequate": coverage_pct > 30.0,
        "step_function_holds": step_violations == 0,
        "nan_present": nan_pct > 0,
        "mean_libdem_reasonable": (
            0.2 < float(np.nanmean(latest_libdem)) < 0.8
        ),
    }
    checks["_coverage_detail"] = (
        f"{n_covered:,} of {n_land:,} land cells"
        f" covered ({coverage_pct:.1f}%)"
    )
    checks["_step_detail"] = (
        f"{step_violations:,} within-year value changes"
    )
    checks["_nan_detail"] = (
        f"{nan_count:,} NaN cells out of"
        f" {total_cells:,} ({nan_pct:.1f}%)"
    )
    checks["_range_detail"] = (
        "all values in [0, 1]"
        if not has_out_of_range
        else "values found outside [0, 1]"
    )

    return PrecomputedData(
        grid=grid,
        features=features,
        n_t=n_t, n_h=n_h, n_w=n_w, n_f=n_f,
        ocean_mask=ocean_mask,
        dates=make_dates(n_t, start_year=start_year),
        start_year=start_year,
        libdem_idx=libdem_idx,
        last_valid_t=last_valid_t,
        latest_libdem=latest_libdem,
        mean_libdem=mean_libdem,
        nan_mask=nan_mask,
        monthly_mean=monthly_mean,
        monthly_coverage=monthly_coverage,
        top_rows=top_rows,
        top_cols=top_cols,
        top_ts=top_ts,
        checks=checks,
        country_values=ctry_vals,
        country_values_t0=ctry_vals_t0,
        country_iso3=country_iso3_list,
        country_cells=iso3_to_cells,
    )


# -- Plot functions -------------------------------------------------


def plot_libdem_map(
    d: PrecomputedData, out: Path,
) -> None:
    """01 — Liberal democracy index, latest time step."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = d.latest_libdem.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im = ax.imshow(
        display, cmap=CMAP_VDEM, aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    latest_year = d.start_year + d.last_valid_t // 12
    style_ax(
        ax,
        title=(
            f"V-Dem liberal democracy index"
            f" (latest: ~{latest_year})"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax, label="v2x_libdem (0=autocracy, 1=democracy)",
    )
    save_plot(fig, out, "01_libdem_map.png")


def plot_mean_libdem(
    d: PrecomputedData, out: Path,
) -> None:
    """02 — Time-averaged liberal democracy index."""
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = d.mean_libdem.copy()
    display[d.ocean_mask] = np.nan
    display = np.flipud(display)
    im = ax.imshow(
        display, cmap=CMAP_VDEM, aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    style_ax(
        ax,
        title=(
            f"V-Dem time-averaged liberal democracy,"
            f" {d.start_year}"
            f"–{d.start_year + d.n_t // 12}"
        ),
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax, label="Mean v2x_libdem",
    )
    save_plot(fig, out, "02_mean_libdem.png")


def plot_per_feature_maps(
    d: PrecomputedData, out: Path,
) -> None:
    """03 — 2x3 panel of representative V-Dem features."""
    import matplotlib.pyplot as plt
    import numpy as np

    available = [
        f for f in REPRESENTATIVE_FEATURES
        if f in d.features
    ]
    if not available:
        available = d.features[:6]
    n_panels = min(len(available), 6)

    n_rows = 2 if n_panels > 3 else 1
    n_cols = min(n_panels, 3)
    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(14, 5 * n_rows),
    )
    axes = [axes] if n_panels == 1 else axes.flat

    for i, feat_name in enumerate(available[:n_panels]):
        ax = axes[i]
        feat_idx = d.features.index(feat_name)
        sl = (
            d.grid[d.last_valid_t, :, :, feat_idx]
            .astype(np.float64)
        )
        display = sl.copy()
        display[d.ocean_mask] = np.nan
        display = np.flipud(display)
        raw_name = feat_name.replace("vdem_", "")
        if raw_name in INTERVAL_SCALE_FEATURES:
            vabs = max(
                abs(float(np.nanmin(display))),
                abs(float(np.nanmax(display))),
                0.01,
            )
            vmin_f, vmax_f = -vabs, vabs
            cmap = "RdBu_r"
        else:
            vmin_f, vmax_f = 0.0, 1.0
            cmap = CMAP_VDEM
        im = ax.imshow(
            display, cmap=cmap, aspect="auto",
            extent=EXTENT, vmin=vmin_f, vmax=vmax_f,
        )
        short_name = raw_name
        style_ax(ax, title=short_name)
        plt.colorbar(im, ax=ax, shrink=0.7)

    for i in range(n_panels, len(list(axes))):
        axes[i].set_visible(False)

    fig.suptitle(
        "V-Dem: representative features (latest epoch)",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "03_per_feature_maps.png")


def plot_monthly_timeseries(
    d: PrecomputedData, out: Path,
) -> None:
    """04 — Global mean liberal democracy over time."""
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
        title="Global mean liberal democracy (v2x_libdem)",
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
        sl = (
            d.grid[t_idx, :, :, d.libdem_idx]
            .astype(np.float64)
        )
        display = sl.copy()
        display[d.ocean_mask] = np.nan
        display = np.flipud(display)
        mean_val = float(np.nanmean(sl))
        ax.imshow(
            display, cmap=CMAP_VDEM, aspect="auto",
            extent=EXTENT, vmin=0, vmax=1,
        )
        style_ax(ax, title=f"{year} (mean={mean_val:.3f})")

    fig.suptitle(
        "V-Dem liberal democracy across epochs",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "05_epoch_comparison.png")


def plot_change_map(
    d: PrecomputedData, out: Path,
) -> None:
    """06 — Democratic change between first and last year."""
    import matplotlib.pyplot as plt
    import numpy as np

    first_sl = (
        d.grid[0, :, :, d.libdem_idx]
        .astype(np.float64)
    )
    last_sl = (
        d.grid[d.last_valid_t, :, :, d.libdem_idx]
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
    style_ax(
        axes[0],
        title=(
            f"Democratisation"
            f" {d.start_year}"
            f"–{d.start_year + d.n_t // 12}"
        ),
    )
    plt.colorbar(
        im1, ax=axes[0], shrink=0.7,
        label="Δ v2x_libdem",
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
            f"Autocratisation"
            f" {d.start_year}"
            f"–{d.start_year + d.n_t // 12}"
        ),
    )
    plt.colorbar(
        im2, ax=axes[1], shrink=0.7,
        label="Δ v2x_libdem",
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
        "V-Dem: 12 cells with largest change",
        fontsize=FONT_TITLE, fontweight="bold", y=0.98,
    )
    save_plot(fig, out, "07_trajectories.png")


def plot_concentration(
    d: PrecomputedData, out: Path,
) -> None:
    """08 — Lorenz curve for spatial democracy concentration."""
    import matplotlib.pyplot as plt
    import numpy as np

    land_vals = d.latest_libdem[~d.ocean_mask & ~d.nan_mask]
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
        title="Concentration of liberal democracy",
        xlabel=(
            "Cumulative % of covered cells (ranked)"
        ),
        ylabel="Cumulative % of total v2x_libdem",
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

        val = float(d.latest_libdem[row, col])

        if expected == "high":
            status = (
                "PASS" if (not np.isnan(val) and val > 0.6)
                else "INVESTIGATE"
            )
        elif expected == "mid":
            status = (
                "PASS"
                if (not np.isnan(val) and 0.2 < val < 0.9)
                else "INVESTIGATE"
            )
        elif expected == "low":
            status = (
                "PASS" if (not np.isnan(val) and val < 0.5)
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
        "Location", "Cell (r,c)", "v2x_libdem",
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
        "Spot-check: V-Dem scores at known locations",
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
        sl = d.grid[t, :, :, d.libdem_idx].astype(
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
    """11 — 22x22 Pearson correlation heatmap across features."""
    import matplotlib.pyplot as plt
    import numpy as np

    vals = d.country_values
    n_f = vals.shape[1]
    if vals.shape[0] < 3:
        print("  (skipped — too few countries)")
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

    visited = [False] * n_f
    order: list[int] = []
    current = 0
    for _ in range(n_f):
        order.append(current)
        visited[current] = True
        best = -1
        best_r = -2.0
        for j in range(n_f):
            if visited[j] or np.isnan(corr[current, j]):
                continue
            if corr[current, j] > best_r:
                best_r = corr[current, j]
                best = j
        if best == -1:
            for j in range(n_f):
                if not visited[j]:
                    best = j
                    break
        if best == -1:
            break
        current = best

    reordered = corr[np.ix_(order, order)]
    labels = [
        d.features[i].replace("vdem_", "")
        for i in order
    ]

    n_high = 0
    for i in range(n_f):
        for j in range(i + 1, n_f):
            if (
                not np.isnan(reordered[i, j])
                and abs(reordered[i, j]) > 0.9
            ):
                n_high += 1

    fig, ax = plt.subplots(figsize=FIG_PANEL_2x2)
    im = ax.imshow(
        reordered, cmap="RdBu_r",
        vmin=-1, vmax=1, aspect="equal",
    )
    ax.set_xticks(range(n_f))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticks(range(n_f))
    ax.set_yticklabels(labels, fontsize=7)
    plt.colorbar(
        im, ax=ax, shrink=0.8, label="Pearson r",
    )
    style_ax(
        ax,
        title=(
            f"Feature correlation"
            f" ({n_high} pairs with |r| > 0.9)"
        ),
    )
    fig.tight_layout()
    save_plot(fig, out, "11_feature_correlation.png")


def plot_country_distributions(
    d: PrecomputedData, out: Path,
) -> None:
    """12 — Histograms of country-level feature values."""
    import matplotlib.pyplot as plt
    import numpy as np

    targets = [
        "v2x_libdem", "v2x_clphy", "v2xcl_rol",
        "v2xnp_regcorr", "v2x_accountability",
        "v2x_genpp",
    ]

    available: list[tuple[str, int]] = []
    for f in targets:
        full = f"vdem_{f}"
        if full in d.features:
            available.append((f, d.features.index(full)))

    n_panels = min(len(available), 6)
    if n_panels == 0:
        return

    fig, axes = plt.subplots(2, 3, figsize=FIG_PANEL_2x2)

    for i, (name, idx) in enumerate(available[:n_panels]):
        ax = axes.flat[i]
        raw = d.country_values[:, idx]
        valid = raw[~np.isnan(raw)]
        if len(valid) == 0:
            ax.text(
                0.5, 0.5, "No data",
                ha="center", va="center",
                transform=ax.transAxes,
            )
            style_ax(ax, title=name)
            continue

        ax.hist(
            valid, bins=25,
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

        scale = (
            "interval"
            if name in INTERVAL_SCALE_FEATURES
            else "[0,1]"
        )
        style_ax(ax, title=f"{name} ({scale})")
        ax.set_ylabel("Countries")

    for i in range(n_panels, 6):
        axes.flat[i].set_visible(False)

    fig.suptitle(
        "Country-level score distributions"
        " (latest epoch)",
        fontsize=FONT_TITLE, fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, out, "12_country_distributions.png")


def plot_feature_temporal(
    d: PrecomputedData, out: Path,
) -> None:
    """13 — Global mean of each feature over time."""
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

    bounded_idx: list[int] = []
    interval_idx: list[int] = []
    for f, name in enumerate(d.features):
        raw = name.replace("vdem_", "")
        if raw in INTERVAL_SCALE_FEATURES:
            interval_idx.append(f)
        else:
            bounded_idx.append(f)

    cmap = plt.cm.tab20
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 10),
        gridspec_kw={"hspace": 0.35},
    )

    for i, f in enumerate(bounded_idx):
        raw = d.features[f].replace("vdem_", "")
        is_libdem = raw == "v2x_libdem"
        color = (
            "black" if is_libdem
            else cmap(
                i / max(len(bounded_idx) - 1, 1),
            )
        )
        lw = 2.0 if is_libdem else 1.0
        alpha = 1.0 if is_libdem else 0.5
        ax1.plot(
            years, means[:, f],
            color=color, linewidth=lw,
            alpha=alpha, label=raw,
        )

    ax1.axvline(
        2023, color="gray",
        linestyle="--", linewidth=0.8,
    )
    ax1.text(
        2023.3, 0.95, "exl* end",
        fontsize=7, color="gray",
    )
    ax1.set_ylim(0, 1)
    style_ax(
        ax1,
        title=(
            f"Bounded [0,1] features"
            f" ({len(bounded_idx)})"
        ),
        xlabel="Year",
        ylabel="Global mean",
    )
    ax1.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=6, ncol=1,
    )

    for i, f in enumerate(interval_idx):
        raw = d.features[f].replace("vdem_", "")
        color = cmap(
            i / max(len(interval_idx) - 1, 1),
        )
        ax2.plot(
            years, means[:, f],
            color=color, linewidth=1.5, label=raw,
        )

    ax2.axhline(
        0, color="gray",
        linestyle="-", linewidth=0.5,
    )
    style_ax(
        ax2,
        title=(
            f"Interval-scale features"
            f" ({len(interval_idx)})"
        ),
        xlabel="Year",
        ylabel="Global mean",
    )
    ax2.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=7,
    )

    fig.tight_layout()
    save_plot(fig, out, "13_feature_temporal.png")


def plot_broadcast_integrity(
    d: PrecomputedData, out: Path,
) -> None:
    """14 — Within-country std dev (should be zero)."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not d.country_cells:
        print("  (skipped — no GAUL crosswalk)")
        return

    all_vals = d.grid[
        d.last_valid_t, :, :, :,
    ].astype(np.float64)

    std_map = np.full(
        (d.n_h, d.n_w), np.nan, dtype=np.float64,
    )
    country_max_std: dict[str, float] = {}

    for iso3, cells in d.country_cells.items():
        if len(cells) < 2:
            continue

        rows = [rc[0] for rc in cells]
        cols = [rc[1] for rc in cells]
        cell_vals = all_vals[rows, cols, :]

        libdem_v = cell_vals[:, d.libdem_idx]
        valid = ~np.isnan(libdem_v)
        if valid.sum() < 2:
            continue

        std_val = float(np.std(libdem_v[valid]))

        max_std = 0.0
        for f in range(d.n_f):
            fv = cell_vals[:, f]
            fvalid = ~np.isnan(fv)
            if fvalid.sum() >= 2:
                max_std = max(
                    max_std,
                    float(np.std(fv[fvalid])),
                )

        country_max_std[iso3] = max_std
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
        title="Within-country std dev (v2x_libdem)",
    )
    plt.colorbar(
        im, ax=ax1, shrink=0.7, label="Std dev",
    )

    if all_zero:
        ax1.text(
            0.5, 0.5,
            "PASS: within-country\nvariance = 0",
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

    if all_zero or not country_max_std:
        ax2.text(
            0.5, 0.5,
            "PASS: all countries\n"
            "have zero variance",
            transform=ax2.transAxes,
            ha="center", va="center",
            fontsize=14, fontweight="bold",
            color="#27AE60",
        )
        style_ax(
            ax2,
            title="Max within-country std (all features)",
        )
    else:
        top10 = sorted(
            country_max_std.items(),
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
                "Top 10 countries by"
                " max within-country std"
            ),
            xlabel="Std dev",
        )

    fig.tight_layout()
    save_plot(fig, out, "14_broadcast_integrity.png")


def plot_rank_stability(
    d: PrecomputedData, out: Path,
) -> None:
    """15 — Cross-feature rank correlation + rank mobility."""
    import matplotlib.pyplot as plt
    import numpy as np

    vals = d.country_values
    vals_t0 = d.country_values_t0

    if vals.shape[0] < 5:
        print("  (skipped — too few countries)")
        return

    libdem_v = vals[:, d.libdem_idx]
    valid_lib = ~np.isnan(libdem_v)

    rho_list: list[float] = []
    feat_labels: list[str] = []

    for f in range(d.n_f):
        if f == d.libdem_idx:
            continue
        mask = valid_lib & ~np.isnan(vals[:, f])
        if mask.sum() < 5:
            continue

        x = vals[mask, f]
        y = libdem_v[mask]
        rank_x = np.argsort(np.argsort(x)).astype(
            np.float64,
        )
        rank_y = np.argsort(np.argsort(y)).astype(
            np.float64,
        )
        rho = float(np.corrcoef(rank_x, rank_y)[0, 1])
        rho_list.append(rho)
        feat_labels.append(
            d.features[f].replace("vdem_", ""),
        )

    sort_idx = sorted(
        range(len(rho_list)),
        key=lambda i: abs(rho_list[i]),
        reverse=True,
    )
    rho_sorted = [rho_list[i] for i in sort_idx]
    labels_sorted = [
        feat_labels[i] for i in sort_idx
    ]
    colors = [
        "#27AE60" if r >= 0 else "#C0392B"
        for r in rho_sorted
    ]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14, 6),
    )

    ax1.barh(
        range(len(rho_sorted)),
        rho_sorted, color=colors,
    )
    ax1.set_yticks(range(len(labels_sorted)))
    ax1.set_yticklabels(labels_sorted, fontsize=7)
    ax1.invert_yaxis()
    ax1.set_xlim(-1, 1)
    ax1.axvline(0, color="gray", linewidth=0.5)
    style_ax(
        ax1,
        title="Spearman ρ with libdem (country)",
        xlabel="ρ",
    )

    mask_both = (
        ~np.isnan(vals[:, d.libdem_idx])
        & ~np.isnan(vals_t0[:, d.libdem_idx])
    )
    if mask_both.sum() >= 5:
        rank_now = (
            np.argsort(
                np.argsort(-vals[mask_both, d.libdem_idx]),
            ).astype(float) + 1
        )
        rank_t0 = (
            np.argsort(
                np.argsort(
                    -vals_t0[mask_both, d.libdem_idx],
                ),
            ).astype(float) + 1
        )

        rank_change = np.abs(rank_now - rank_t0)
        iso3_both = [
            d.country_iso3[i]
            for i, m in enumerate(mask_both)
            if m
        ]

        scatter = ax2.scatter(
            rank_t0, rank_now,
            c=rank_change, cmap="YlOrRd",
            s=15, alpha=0.7,
        )
        n_pts = int(mask_both.sum())
        ax2.plot(
            [0, n_pts + 1], [0, n_pts + 1],
            color="gray", linewidth=0.8,
            linestyle="--",
        )

        top_movers = np.argsort(rank_change)[-5:]
        for idx in top_movers:
            ax2.annotate(
                iso3_both[idx],
                (rank_t0[idx], rank_now[idx]),
                fontsize=6, ha="left",
            )

        plt.colorbar(
            scatter, ax=ax2, shrink=0.7,
            label="|Rank change|",
        )
        style_ax(
            ax2,
            title=(
                f"Libdem rank: {d.start_year}"
                f" vs latest (n={n_pts})"
            ),
            xlabel=f"Rank in {d.start_year}",
            ylabel="Rank at latest",
        )
    else:
        ax2.text(
            0.5, 0.5, "Insufficient data",
            ha="center", va="center",
            transform=ax2.transAxes,
        )
        style_ax(ax2, title="Libdem rank mobility")

    fig.tight_layout()
    save_plot(fig, out, "15_rank_stability.png")


# -- Summary -------------------------------------------------------


def print_summary(d: PrecomputedData) -> bool:
    print()
    print("=" * 60)
    print("V-DEM GRID VERIFICATION SUMMARY")
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
    nan_features = []
    for feat in d.features:
        idx = d.features.index(feat)
        sl = (
            d.grid[d.last_valid_t, :, :, idx]
            .astype(np.float64)
        )
        n_nan = int(np.isnan(sl).sum())
        n_total = d.n_h * d.n_w
        mean = float(np.nanmean(sl))
        short = feat.replace("vdem_", "")
        raw = short
        scale = (
            "interval"
            if raw in INTERVAL_SCALE_FEATURES
            else "[0,1]"
        )
        suffix = ""
        if n_nan == n_total:
            nan_features.append(short)
            suffix = "  ** ALL NaN at this t **"
        print(
            f"  {short:<25s}  mean={mean:.3f}"
            f"  NaN={n_nan:,}/{n_total:,}"
            f"  {scale}{suffix}"
        )

    if nan_features:
        print()
        print(
            f"  Note: {len(nan_features)} feature(s)"
            f" are all-NaN at t={d.last_valid_t}"
            f" (data ends earlier than libdem):"
        )
        for f in nan_features:
            print(f"    - {f}")
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
    ("Liberal Democracy Map", plot_libdem_map),
    ("Mean Liberal Democracy", plot_mean_libdem),
    ("Per-Feature Maps", plot_per_feature_maps),
    ("Monthly Time Series", plot_monthly_timeseries),
    ("Epoch Comparison", plot_epoch_comparison),
    ("Change Map", plot_change_map),
    ("Trajectories", plot_trajectories),
    ("Concentration", plot_concentration),
    ("Spot Checks", plot_spot_checks),
    ("NaN Coverage", plot_nan_coverage),
    ("Feature Correlation", plot_feature_correlation),
    ("Country Distributions", plot_country_distributions),
    ("Feature Temporal", plot_feature_temporal),
    ("Broadcast Integrity", plot_broadcast_integrity),
    ("Rank Stability", plot_rank_stability),
]


def main() -> int:
    sys.stdout.reconfigure(  # type: ignore[attr-defined]
        line_buffering=True,
    )

    parser = argparse.ArgumentParser(
        description="V-Dem grid verification audit",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/compiled/vdem"),
        help="Compiled V-Dem grid directory",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("reports/audit_vdem"),
        help="Output directory for PNGs",
    )
    args = parser.parse_args()

    grid_path = args.input / "grid.npy"
    if not grid_path.exists():
        print(f"FAIL: {grid_path} not found")
        print(
            "Run the V-Dem pipeline first: "
            "python scripts/run_vdem_pipeline.py"
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
        f"  Latest global mean libdem: "
        f"{data.monthly_mean[-1]:.3f}"
    )
    print(
        f"  Coverage: "
        f"{data.monthly_coverage[-1]:.1f}% of cells"
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
