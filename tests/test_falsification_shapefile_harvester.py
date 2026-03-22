"""Falsification audit: PRIO-GRID shapefile harvester quality.

Generated 2026-03-22. Two soft falsifications found and resolved:
frozen config class created, CIC created.

CONTESTED → SURVIVED after fixes.
"""

from __future__ import annotations

import os


class TestShapefileHarvesterResolved:

    def test_has_frozen_config(self) -> None:
        """R2 resolved: ShapefileHarvesterConfig exists."""
        from datafactory_priogrid.shapefile_harvester import (
            ShapefileHarvesterConfig,
        )

        cfg = ShapefileHarvesterConfig()
        assert cfg.timeout == 120
        assert cfg.max_retries == 3

    def test_cic_exists(self) -> None:
        """R3 resolved: CIC exists."""
        path = os.path.join(
            os.path.dirname(__file__), "..",
            "docs", "CICs",
            "ShapefileHarvesterConfig.md",
        )
        assert os.path.exists(path)
