"""Falsification stubs: GHS-BUILT-S documentation completeness.

Source: /falsify coverage parity audit 2026-05-22
Verifies catalog card and ADR exist.
"""

from __future__ import annotations

from pathlib import Path


class TestF1CatalogCard:
    """GHS-BUILT-S must have a catalog card."""

    def test_catalog_card_exists(self) -> None:
        card = Path("docs/sources/ghsbuilts.md")
        assert card.exists(), (
            "Missing catalog card docs/sources/ghsbuilts.md "
            "— required by ADR-033"
        )


class TestF2ADR034:
    """GHS-BUILT-S source selection ADR must exist."""

    def test_adr_034_exists(self) -> None:
        adr = Path(
            "docs/ADRs/"
            "034_ghs_built_s_as_built_up_surface_source.md"
        )
        assert adr.exists(), (
            "Missing ADR-034 — source selection rationale "
            "required before code"
        )
