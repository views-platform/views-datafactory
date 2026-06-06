"""ADR-040 count conservation for the compilation layer.

Invariant 1: placed + skipped_spatial + skipped_temporal = input_rows.

Uses if/raise RuntimeError — assert is stripped with -O, which is
unacceptable for a Tier 2 silent-corruption guard.
"""

from __future__ import annotations

import dataclasses

__all__ = ["PlacementAccounting", "assert_placement_conservation"]


@dataclasses.dataclass(frozen=True)
class PlacementAccounting:
    """Immutable record of event placement outcomes."""

    n_input: int
    n_placed: int
    n_skipped_spatial: int
    n_skipped_temporal: int


def assert_placement_conservation(acc: PlacementAccounting) -> None:
    """Verify placed + skipped_spatial + skipped_temporal = input_rows."""
    total = acc.n_placed + acc.n_skipped_spatial + acc.n_skipped_temporal
    if total != acc.n_input:
        raise RuntimeError(
            f"Count conservation violated (ADR-040): "
            f"{acc.n_placed} placed + "
            f"{acc.n_skipped_spatial} spatial + "
            f"{acc.n_skipped_temporal} temporal "
            f"= {total} != {acc.n_input} input rows"
        )
