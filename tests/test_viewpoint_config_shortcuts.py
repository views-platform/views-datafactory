"""Tests for viewpoint config from_shortcuts() classmethods.

Taxonomy: green (contract verification).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---- UCDP ViewpointConfig ----


class TestViewpointConfigFromShortcuts:

    def test_sets_consolidated_path(self) -> None:
        from datafactory_viewpoint.viewpoint_config import (
            ViewpointConfig,
        )

        p = Path("data/consolidated/ucdp/store.parquet")
        cfg = ViewpointConfig.from_shortcuts(consolidated_path=p)
        assert cfg.consolidated_path == p

    def test_uses_defaults(self) -> None:
        from datafactory_viewpoint.viewpoint_config import (
            ViewpointConfig,
        )

        p = Path("data/consolidated/ucdp/store.parquet")
        cfg = ViewpointConfig.from_shortcuts(consolidated_path=p)
        assert cfg.output_path == Path(
            "data/viewpoint/ucdp_v1.parquet"
        )
        assert cfg.survivorship_strategy == "annual_wins"
        assert cfg.distribution_strategy == "even_split"

    def test_returns_frozen_instance(self) -> None:
        from datafactory_viewpoint.viewpoint_config import (
            ViewpointConfig,
        )

        p = Path("data/consolidated/ucdp/store.parquet")
        cfg = ViewpointConfig.from_shortcuts(consolidated_path=p)
        with pytest.raises(AttributeError):
            cfg.version = "changed"  # type: ignore[misc]


# ---- ACLED ----


class TestAcledConfigFromShortcuts:

    def test_sets_consolidated_path(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
        )

        p = Path("data/consolidated/acled/store.parquet")
        cfg = AcledViewpointConfig.from_shortcuts(
            consolidated_path=p,
        )
        assert cfg.consolidated_path == p
        assert cfg.version == "acled_v1"

    def test_uses_defaults(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            AcledViewpointConfig,
        )

        p = Path("data/consolidated/acled/store.parquet")
        cfg = AcledViewpointConfig.from_shortcuts(
            consolidated_path=p,
        )
        assert cfg.output_path == Path(
            "data/viewpoint/acled_v1.parquet"
        )
        assert cfg.event_type_filter is None


# ---- GHS-POP ----


class TestGhsPopConfigFromShortcuts:

    def test_sets_source_dir(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        d = Path("data/raw/ghspop")
        cfg = GhsPopViewpointConfig.from_shortcuts(source_dir=d)
        assert cfg.source_dir == d
        assert cfg.version == "ghspop_v1"

    def test_uses_defaults(self) -> None:
        from datafactory_viewpoint.builders.ghspop_v1 import (
            GhsPopViewpointConfig,
        )

        d = Path("data/raw/ghspop")
        cfg = GhsPopViewpointConfig.from_shortcuts(source_dir=d)
        assert cfg.epochs == (
            1975, 1980, 1985, 1990, 1995,
            2000, 2005, 2010, 2015, 2020, 2025, 2030,
        )
        assert cfg.temporal_interpolation == "linear"


# ---- GHS-BUILT-S ----


class TestGhsBuiltSConfigFromShortcuts:

    def test_sets_source_dir(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        d = Path("data/raw/ghsbuilts")
        cfg = GhsBuiltSViewpointConfig.from_shortcuts(
            source_dir=d,
        )
        assert cfg.source_dir == d
        assert cfg.version == "ghsbuilts_v1"

    def test_uses_defaults(self) -> None:
        from datafactory_viewpoint.builders.ghsbuilts_v1 import (
            GhsBuiltSViewpointConfig,
        )

        d = Path("data/raw/ghsbuilts")
        cfg = GhsBuiltSViewpointConfig.from_shortcuts(
            source_dir=d,
        )
        assert cfg.epochs == (
            1975, 1980, 1985, 1990, 1995,
            2000, 2005, 2010, 2015, 2020, 2025, 2030,
        )
        assert cfg.temporal_interpolation == "linear"


# ---- V-Dem ----


class TestVdemConfigFromShortcuts:

    def test_accepts_source_only(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        p = Path("data/raw/vdem/vdem_v16.parquet")
        cfg = VdemViewpointConfig.from_shortcuts(source_path=p)
        assert cfg.source_path == p
        assert cfg.crosswalk_path == Path(
            "data/raw/gaul_admin/iso3_code.parquet"
        )

    def test_accepts_both_paths(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        sp = Path("data/raw/vdem/vdem_v16.parquet")
        cp = Path("custom/crosswalk.parquet")
        cfg = VdemViewpointConfig.from_shortcuts(
            source_path=sp,
            crosswalk_path=cp,
        )
        assert cfg.source_path == sp
        assert cfg.crosswalk_path == cp

    def test_uses_all_defaults(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VdemViewpointConfig,
        )

        cfg = VdemViewpointConfig.from_shortcuts()
        assert cfg.source_path == Path(
            "data/raw/vdem/vdem_v16.parquet"
        )
        assert cfg.crosswalk_path == Path(
            "data/raw/gaul_admin/iso3_code.parquet"
        )
        assert cfg.version == "vdem_v1"
