#!/usr/bin/env python3
"""SHDI grid verification — statistical checks + plots proving
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
import json
import sys
from pathlib import Path

SHDI_FEATURES = (
    "shdi_shdi",
    "shdi_healthindex",
    "shdi_edindex",
    "shdi_incindex",
)

SHDI_START_YEAR = 1990


def main() -> int:
    """Run SHDI grid verification."""
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
    import numpy as np  # noqa: E402
    from viz_style import (  # noqa: I001
        COLOR_ACCENT,
        EXTENT,
        FIG_FULL,
        FONT_TITLE,
        make_dates,
        save_plot,
        style_ax,
    )

    features = json.loads(
        (args.input / "feature_names.json").read_text(),
    )
    time_steps = np.load(args.input / "time_steps.npy")
    grid = np.load(grid_path, mmap_mode="r")

    n_t, n_h, n_w, n_f = grid.shape
    start_year = int(str(time_steps[0])[:4])
    dates = make_dates(n_t, start_year=start_year)

    print("=" * 60)
    print("SHDI GRID VERIFICATION")
    print("=" * 60)
    print()
    print(
        f"Grid shape:  [{n_t}, {n_h}, {n_w}, {n_f}]"
    )
    print(
        f"Temporal:    {start_year}-01 to "
        f"{start_year + n_t // 12}-12"
    )
    print(f"Features:    {features}")
    print()

    args.output.mkdir(parents=True, exist_ok=True)

    # ── Check 1: Feature count ──
    feature_ok = n_f == len(SHDI_FEATURES)
    print(
        f"[{'+'if feature_ok else '!'}] "
        f"Feature count: {n_f}"
        f" (expected {len(SHDI_FEATURES)})"
    )

    # ── Check 2: Value range [0, 1] ──
    has_out_of_range = False
    for f_idx in range(n_f):
        for t in range(n_t):
            sl = grid[t, :, :, f_idx].astype(np.float64)
            valid = sl[~np.isnan(sl)]
            if (
                len(valid) > 0
                and (valid.min() < -0.01 or valid.max() > 1.01)
            ):
                has_out_of_range = True
                break
        if has_out_of_range:
            break
    range_ok = not has_out_of_range
    print(
        f"[{'+'if range_ok else '!'}] "
        f"Value range: "
        f"{'all in [0, 1]' if range_ok else 'OUT OF RANGE'}"
    )

    # ── Check 3: Step function (constant within year) ──
    step_violations = 0
    for t in range(1, n_t):
        if (t % 12) != 0:
            for f_idx in range(n_f):
                prev = grid[
                    t - 1, :, :, f_idx
                ].astype(np.float64)
                curr = grid[
                    t, :, :, f_idx
                ].astype(np.float64)
                both = ~np.isnan(prev) & ~np.isnan(curr)
                if both.any():
                    diffs = np.abs(
                        curr[both] - prev[both]
                    )
                    step_violations += int(
                        (diffs > 1e-9).sum()
                    )
    step_ok = step_violations == 0
    print(
        f"[{'+'if step_ok else '!'}] "
        f"Step function: "
        f"{step_violations:,} within-year changes"
    )

    # ── Check 4: NaN before 1990 ──
    shdi_epoch_offset = (SHDI_START_YEAR - start_year) * 12
    nan_before_ok = True
    if shdi_epoch_offset > 0:
        pre_shdi = grid[:shdi_epoch_offset, :, :, :]
        if not np.all(np.isnan(pre_shdi)):
            nan_before_ok = False
    print(
        f"[{'+'if nan_before_ok else '!'}] "
        f"NaN before {SHDI_START_YEAR}: "
        f"{'yes' if nan_before_ok else 'data found!'}"
    )

    # ── Check 5: Spatial coverage ──
    shdi_idx = 0
    last_valid_t = n_t - 1
    for t in range(n_t - 1, -1, -1):
        sl = grid[t, :, :, shdi_idx].astype(np.float64)
        if (~np.isnan(sl)).sum() > 0:
            last_valid_t = t
            break

    latest = grid[
        last_valid_t, :, :, shdi_idx
    ].astype(np.float64)
    n_valid = int((~np.isnan(latest)).sum())
    total_cells = n_h * n_w
    coverage_pct = n_valid / total_cells * 100
    coverage_ok = coverage_pct > 30.0
    print(
        f"[{'+'if coverage_ok else '!'}] "
        f"Coverage: {n_valid:,}/{total_cells:,} cells"
        f" ({coverage_pct:.1f}%)"
    )

    # ── Check 6: NaN present (not all zeros) ──
    nan_count = int(np.isnan(grid[:]).sum())
    total = n_t * n_h * n_w * n_f
    nan_pct = nan_count / total * 100
    nan_ok = nan_pct > 0
    print(
        f"[{'+'if nan_ok else '!'}] "
        f"NaN present: {nan_count:,}/{total:,}"
        f" ({nan_pct:.1f}%)"
    )

    print()

    # ── Plot 1: Latest SHDI map ──
    print("Plot 01: Latest SHDI map...")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = latest.copy()
    display = np.flipud(display)
    im = ax.imshow(
        display, cmap="RdYlGn", aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    latest_year = start_year + last_valid_t // 12
    style_ax(
        ax,
        title=f"SHDI index (latest: ~{latest_year})",
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax,
        label="SHDI (0=low, 1=high development)",
    )
    save_plot(fig, args.output, "01_shdi_map.png")

    # ── Plot 2: All 4 features ──
    print("Plot 02: Per-feature maps...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for i, ax in enumerate(axes.flat):
        if i >= n_f:
            ax.set_visible(False)
            continue
        sl = grid[
            last_valid_t, :, :, i
        ].astype(np.float64)
        display = np.flipud(sl.copy())
        im = ax.imshow(
            display, cmap="RdYlGn", aspect="auto",
            extent=EXTENT, vmin=0, vmax=1,
        )
        style_ax(ax, title=features[i])
        plt.colorbar(im, ax=ax, shrink=0.7)

    fig.suptitle(
        "SHDI: all features (latest epoch)",
        fontsize=FONT_TITLE, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    save_plot(fig, args.output, "02_per_feature_maps.png")

    # ── Plot 3: Monthly time series ──
    print("Plot 03: Monthly time series...")
    monthly_mean = np.zeros(n_t, dtype=np.float64)
    monthly_coverage = np.zeros(n_t, dtype=np.float64)
    for t in range(n_t):
        sl = grid[t, :, :, shdi_idx].astype(np.float64)
        valid = ~np.isnan(sl)
        if valid.sum() > 0:
            monthly_mean[t] = float(np.nanmean(sl))
        monthly_coverage[t] = valid.sum() / total_cells * 100

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9),
        gridspec_kw={"hspace": 0.35},
    )
    ax1.plot(
        dates, monthly_mean,
        color=COLOR_ACCENT, linewidth=1.5,
    )
    ax1.fill_between(
        dates, monthly_mean,
        color=COLOR_ACCENT, alpha=0.15, linewidth=0,
    )
    style_ax(
        ax1,
        title="Global mean SHDI over time",
        xlabel="Date",
        ylabel="Mean SHDI",
    )
    ax1.set_xlim(dates[0], dates[-1])
    ax1.set_ylim(0, 1)

    ax2.plot(
        dates, monthly_coverage,
        color="#27AE60", linewidth=1.5,
    )
    ax2.fill_between(
        dates, monthly_coverage,
        color="#27AE60", alpha=0.15, linewidth=0,
    )
    style_ax(
        ax2,
        title="Spatial coverage (% of cells with data)",
        xlabel="Date",
        ylabel="Coverage (%)",
    )
    ax2.set_xlim(dates[0], dates[-1])
    ax2.set_ylim(0, 100)

    save_plot(
        fig, args.output, "03_monthly_timeseries.png",
    )

    # ── Plot 4: Feature correlation ──
    print("Plot 04: Feature correlation...")
    vals = grid[
        last_valid_t, :, :, :
    ].astype(np.float64).reshape(-1, n_f)
    mask = ~np.isnan(vals).any(axis=1)
    vals_clean = vals[mask]

    if len(vals_clean) > 10:
        corr = np.corrcoef(vals_clean, rowvar=False)
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(
            corr, cmap="RdBu_r",
            vmin=-1, vmax=1, aspect="equal",
        )
        short_names = [
            f.replace("shdi_", "") for f in features
        ]
        ax.set_xticks(range(n_f))
        ax.set_xticklabels(
            short_names, rotation=45, fontsize=10,
        )
        ax.set_yticks(range(n_f))
        ax.set_yticklabels(short_names, fontsize=10)
        plt.colorbar(
            im, ax=ax, shrink=0.8, label="Pearson r",
        )
        for i in range(n_f):
            for j in range(n_f):
                ax.text(
                    j, i, f"{corr[i, j]:.2f}",
                    ha="center", va="center",
                    fontsize=9,
                )
        style_ax(ax, title="SHDI feature correlation")
        fig.tight_layout()
        save_plot(
            fig, args.output,
            "04_feature_correlation.png",
        )

    # ── Plot 5: NaN coverage ──
    print("Plot 05: NaN coverage...")
    nan_frac = np.zeros((n_h, n_w), dtype=np.float64)
    for t in range(n_t):
        sl = grid[t, :, :, shdi_idx].astype(np.float64)
        nan_frac += np.isnan(sl).astype(np.float64)
    nan_frac /= n_t

    fig, ax = plt.subplots(figsize=FIG_FULL)
    display = np.flipud(nan_frac.copy())
    im = ax.imshow(
        display, cmap="YlOrRd", aspect="auto",
        extent=EXTENT, vmin=0, vmax=1,
    )
    style_ax(
        ax,
        title="SHDI NaN fraction across time",
        xlabel="Longitude",
        ylabel="Latitude",
    )
    plt.colorbar(
        im, ax=ax,
        label="Fraction of months with NaN",
    )
    save_plot(fig, args.output, "05_nan_coverage.png")

    # ── Summary ──
    all_pass = all([
        feature_ok, range_ok, step_ok,
        nan_before_ok, coverage_ok, nan_ok,
    ])

    print()
    print("=" * 60)
    if all_pass:
        print("VERDICT: PASS — all checks passed")
    else:
        print(
            "VERDICT: INVESTIGATE"
            " — some checks need review"
        )
    print("=" * 60)
    print()
    print(f"All plots saved to {args.output}/")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
