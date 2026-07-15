#!/usr/bin/env python3
"""Consumer contract verification — the C-313/C-314 detector (#323).

Verifies what consumers actually receive from the served zarr,
through the same path they use (``load_dataset``):

1. Contract: a views-frames FeatureFrame with features and index.
2. Content freshness: each monthly-updating source has a recent
   month with nonzero data (catches C-313 — consumers received
   zeros for all 2026 ACLED months while 900+ internal tests
   passed).
3. Plausibility: monthly global sums within a tolerant band of
   their trailing window (flags C-314-class anomalies). WARN ONLY,
   never a failure — C-311 taught us source data is allowed to be
   strange, and the Jan-2026 Iran spike (1,627x a 17-death/month
   baseline) is a true event that must be flagged, not suppressed.

Unlike verify_remote_data.py, this script never compares against a
local grid copy — the operator's local data may be stale (it
produced 62 false MISMATCHes on 2026-07-05 while missing C-313).

Usage:
    uv run python scripts/verify_consumer_contract.py
    uv run python scripts/verify_consumer_contract.py \
        --zarr-url http://204.168.219.108/grid.zarr

Requires ~/.netrc credentials for the zarr server.
"""

from __future__ import annotations

import argparse
import datetime
import sys

import numpy as np

# Last nonzero month must be within N months of the current month.
# ACLED publishes biweekly and the pipeline compiles monthly: 3
# months absorbs release lag + one missed cycle. UCDP monthly
# coverage comes from candidate releases (~1-2 month lag): 4
# months. Bounded staleness per ADR-018.
FRESHNESS_SLO_MONTHS: dict[str, int] = {
    "acled_fatalities": 3,
    "ged_sb_best": 4,
}

# Annual or static sources: must be nonzero somewhere in the
# window, but have no monthly freshness expectation.
PRESENCE_FEATURES: tuple[str, ...] = (
    "ghspop_pop_count",
    "ghsbuilts_built_area",
    "vdem_v2x_libdem",
    "shdi_shdi",
    "landarea",
)

# Plausibility: warn when a monthly global sum exceeds
# RATIO x max(median of trailing window, FLOOR). The floor keeps
# near-zero baselines from making the ratio meaningless — Iran's
# 2025 baseline was 17 deaths/month, so any floor-less per-country
# ratio gate would drown in noise while a min-baseline filter
# would have excluded it entirely (falsification audit, #320).
# RATIO calibration (2026-07-15, live data): the confirmed true
# positive — Jan 2026, 46,426 vs trailing median ~15.6k — is
# exactly 3.0x at global level; 2.5 keeps it firing with margin
# while normal months sit at or below ~1.5x.
PLAUSIBILITY_RATIO: float = 2.5
PLAUSIBILITY_FLOOR: float = 2_000.0
PLAUSIBILITY_WINDOW_MONTHS: int = 12

# Freshness and plausibility look at the trailing 24 months.
# The PULL window is longer: annual sources publish with multi-year
# lag (SHDI's coverage currently ends 2023), so presence is judged
# over 48 months — if a source has published nothing usable in 4
# years, flagging it IS the correct bounded-staleness signal
# (ADR-018), not a false alarm.
WINDOW_MONTHS: int = 48

_MONTH_EPOCH_YEAR: int = 1980  # VIEWS month_id convention


def current_month_id(
    now: datetime.datetime | None = None,
) -> int:
    """VIEWS month_id for the current UTC month."""
    now = now or datetime.datetime.now(tz=datetime.UTC)
    return (now.year - _MONTH_EPOCH_YEAR) * 12 + now.month


def month_id_str(month_id: int) -> str:
    """Human-readable YYYY-MM for a VIEWS month_id."""
    year = _MONTH_EPOCH_YEAR + (month_id - 1) // 12
    month = (month_id - 1) % 12 + 1
    return f"{year}-{month:02d}"


def monthly_sums(
    times: np.ndarray, values: np.ndarray,
) -> dict[int, float]:
    """Global sum per month_id for one feature column."""
    sums: dict[int, float] = {}
    for t in np.unique(times):
        sums[int(t)] = float(
            np.nansum(values[times == t])
        )
    return sums


def check_freshness(
    sums: dict[int, float],
    feature: str,
    slo_months: int,
    now_month: int,
) -> str | None:
    """Return a failure message if the feature is stale.

    Stale = no month with nonzero data within slo_months of the
    current month. This is the C-313 detector: a source whose
    recent months are all zero while the pipeline reports success.
    """
    nonzero = [m for m, v in sums.items() if v > 0]
    if not nonzero:
        return f"{feature}: no nonzero month in window"
    last = max(nonzero)
    age = now_month - last
    if age > slo_months:
        return (
            f"{feature}: last nonzero month is "
            f"{month_id_str(last)} ({age} months old, "
            f"SLO {slo_months})"
        )
    return None


def check_presence(
    sums: dict[int, float], feature: str,
) -> str | None:
    """Return a failure message if the feature is absent."""
    if not any(v != 0 for v in sums.values()):
        return f"{feature}: all-zero in window"
    return None


def check_plausibility(
    sums: dict[int, float],
    feature: str,
    ratio: float = PLAUSIBILITY_RATIO,
    floor: float = PLAUSIBILITY_FLOOR,
    window: int = PLAUSIBILITY_WINDOW_MONTHS,
) -> list[str]:
    """Return warnings for implausibly large monthly sums.

    Each of the trailing `window` months is compared against the
    median of that window: warn when it exceeds
    ratio * max(median, floor). Warnings never fail the pipeline.

    Trailing all-zero months (padding after the last observed
    month) are excluded — they drag the median down and made the
    check fire on ordinary months while missing real anomalies.
    """
    months = sorted(sums)
    while months and sums[months[-1]] == 0:
        months.pop()
    tail = months[-window:]
    if len(tail) < 3:
        return []
    med = float(np.median([sums[m] for m in tail]))
    threshold = ratio * max(med, floor)
    warnings = []
    for m in tail:
        if sums[m] > threshold:
            warnings.append(
                f"{feature}: {month_id_str(m)} sum "
                f"{sums[m]:,.0f} exceeds {ratio:g}x "
                f"max(median {med:,.0f}, floor {floor:,.0f}) "
                f"— verify against the source before training"
            )
    return warnings


def largest_jump(
    sums: dict[int, float], feature: str,
) -> str | None:
    """Info line: largest absolute month-over-month change."""
    months = sorted(sums)
    if len(months) < 2:
        return None
    jumps = [
        (abs(sums[b] - sums[a]), a, b)
        for a, b in zip(months, months[1:], strict=False)
    ]
    delta, a, b = max(jumps)
    return (
        f"{feature}: largest MoM change "
        f"{month_id_str(a)}->{month_id_str(b)}: "
        f"{sums[a]:,.0f} -> {sums[b]:,.0f} (delta {delta:,.0f})"
    )


def main() -> int:
    """Run the consumer contract verification."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    from datafactory_query import load_dataset
    from datafactory_query.defaults import DEFAULT_REMOTE

    parser = argparse.ArgumentParser(
        description="Verify the served data at the consumer boundary"
    )
    parser.add_argument(
        "--zarr-url",
        default=f"http://{DEFAULT_REMOTE.server}/grid.zarr",
        help="Zarr store URL (default: production server)",
    )
    parser.add_argument(
        "--slo-months",
        type=int,
        default=None,
        help=(
            "Override every freshness SLO (months). For fire "
            "drills: --slo-months 0 must FAIL on real data, "
            "proving the detector is live."
        ),
    )
    args = parser.parse_args()

    slos = dict(FRESHNESS_SLO_MONTHS)
    if args.slo_months is not None:
        slos = dict.fromkeys(slos, args.slo_months)

    now_month = current_month_id()
    start = month_id_str(now_month - WINDOW_MONTHS)
    features = sorted(
        {*FRESHNESS_SLO_MONTHS, *PRESENCE_FEATURES}
    )

    print("=" * 60)
    print("CONSUMER CONTRACT VERIFICATION (#323)")
    print(f"Store: {args.zarr_url}")
    print(f"Window: {start} .. {month_id_str(now_month)}")
    print("=" * 60)

    ff = load_dataset(
        region="global",
        start=start,
        end=month_id_str(now_month),
        features=features,
        data_dir=args.zarr_url,
    )

    type_name = f"{type(ff).__module__}.{type(ff).__name__}"
    if "FeatureFrame" not in type_name:
        print(f"FAIL: expected FeatureFrame, got {type_name}")
        return 1
    print(f"Contract: {type_name}, rows={ff.n_rows:,}, "
          f"features={ff.n_features}")

    times = np.asarray(ff.index.time)
    values = np.asarray(ff.values)
    if values.ndim == 3:
        values = values[:, :, 0]
    fi = {f: i for i, f in enumerate(ff.feature_names)}

    failures: list[str] = []
    warnings: list[str] = []

    for feature, slo in slos.items():
        if feature not in fi:
            failures.append(f"{feature}: missing from store")
            continue
        sums = monthly_sums(times, values[:, fi[feature]])
        fail = check_freshness(sums, feature, slo, now_month)
        if fail:
            failures.append(fail)
        else:
            last = max(m for m, v in sums.items() if v > 0)
            print(f"Fresh: {feature} through {month_id_str(last)}")
        warnings.extend(check_plausibility(sums, feature))
        info = largest_jump(sums, feature)
        if info:
            print(f"Info: {info}")

    for feature in PRESENCE_FEATURES:
        if feature not in fi:
            failures.append(f"{feature}: missing from store")
            continue
        sums = monthly_sums(times, values[:, fi[feature]])
        fail = check_presence(sums, feature)
        if fail:
            failures.append(fail)
        else:
            print(f"Present: {feature}")

    print("-" * 60)
    for w in warnings:
        print(f"WARN: {w}")
    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        print(f"CONSUMER CONTRACT: FAIL ({len(failures)} failure(s), "
              f"{len(warnings)} warning(s))")
        return 1
    print(f"CONSUMER CONTRACT: PASS ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
