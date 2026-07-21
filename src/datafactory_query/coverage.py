"""Pre-coverage consumer warnings (ADR-047, ADR-048, C-156).

One responsibility: warn when a query's time range starts before a
source's first valid month, using declared source-feature lists
(never name inference — ADR-003). Split from dataset.py per
ADR-050 screaming-architecture surgery (#346).
"""

from __future__ import annotations

import warnings

_SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "acled": "ACLED",
    "ghspop": "GHS-POP",
    "ghsbuilts": "GHS-BUILT-S",
    "vdem": "V-Dem",
    "shdi": "SHDI",
}


def _warn_pre_coverage(
    query_start_mid: int,
    first_valid_month_ids: dict[str, int],
    requested_features: set[str],
    source_features: dict[str, list[str]],
) -> None:
    """Emit UserWarning for each source whose data starts after
    the query's start month, when the query includes features
    from that source (ADR-047, ADR-048, C-156).

    Uses declared source-feature lists from provenance instead
    of prefix inference (ADR-003 compliance).
    """
    for key, first_mid in first_valid_month_ids.items():
        if query_start_mid >= first_mid:
            continue
        source_key = (
            key.removeprefix("first_valid_")
            .removesuffix("_month_id")
        )
        features_key = f"{source_key}_features"
        src_feats = source_features.get(features_key)
        if src_feats is None:
            continue
        src_set = set(src_feats)
        affected = [
            f for f in requested_features if f in src_set
        ]
        if not affected:
            continue
        source_name = _SOURCE_DISPLAY_NAMES.get(
            source_key, source_key,
        )
        warnings.warn(
            f"{source_name} data begins at month_id "
            f"{first_mid}, but query starts at "
            f"{query_start_mid}. Months "
            f"{query_start_mid}–{first_mid - 1} contain "
            f"zero-fill, not observed data. Affected "
            f"features: {affected}",
            UserWarning,
            stacklevel=3,
        )
