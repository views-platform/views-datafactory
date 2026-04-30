"""Structural invariants — encoding, regions, partitions, feature contracts.

These tests require no assembled data or gold sets. They verify
properties that must hold regardless of data content: month_id
encoding, region set cardinalities, partition boundary alignment
across the 5 integrated models, and feature contract consistency.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest

from datafactory_priogrid import from_views_month_id, to_views_month_id
from datafactory_query.regions import load_region_pgids

MODELS_ROOT = (
    Path(__file__).resolve().parents[1]
    / ".."
    / "views-models"
    / "models"
)

ALL_MODELS = [
    "bright_starship",
    "heavy_freighter",
    "heavy_strider",
    "light_strider",
    "shining_codex",
]


class TestMonthIdEncoding:
    """VIEWS month_id epoch and boundary correctness."""

    @pytest.mark.parametrize(
        "month_id,year,month",
        [
            (1, 1980, 1),
            (12, 1980, 12),
            (13, 1981, 1),
            (121, 1990, 1),
            (444, 2016, 12),
            (445, 2017, 1),
            (492, 2020, 12),
            (493, 2021, 1),
            (540, 2024, 12),
            (555, 2026, 3),
        ],
    )
    def test_month_id_to_datetime(
        self, month_id: int, year: int, month: int,
    ) -> None:
        dt = from_views_month_id(month_id).item()
        assert dt == np.datetime64(f"{year}-{month:02d}", "M")

    @pytest.mark.parametrize(
        "year,month,expected_id",
        [
            (1980, 1, 1),
            (1990, 1, 121),
            (2017, 1, 445),
            (2020, 12, 492),
            (2021, 1, 493),
            (2024, 12, 540),
        ],
    )
    def test_datetime_to_month_id(
        self, year: int, month: int, expected_id: int,
    ) -> None:
        dt = np.datetime64(f"{year}-{month:02d}", "M")
        result = to_views_month_id(dt).item()
        assert result == expected_id

    def test_roundtrip(self) -> None:
        ids = np.array([1, 121, 444, 445, 492, 540, 555])
        roundtripped = to_views_month_id(from_views_month_id(ids))
        np.testing.assert_array_equal(roundtripped, ids)


class TestRegionInvariants:
    """Region definitions are internally consistent."""

    def test_land_cardinality(self) -> None:
        land = load_region_pgids("land")
        assert len(land) == 64818

    def test_africa_me_legacy_cardinality(self) -> None:
        legacy = load_region_pgids("africa_me_legacy")
        assert len(legacy) == 13110

    def test_global_cardinality(self) -> None:
        global_set = load_region_pgids("global")
        assert len(global_set) == 259200

    def test_africa_me_subset_of_land(self) -> None:
        land = load_region_pgids("land")
        legacy = load_region_pgids("africa_me_legacy")
        missing = legacy - land
        assert not missing, (
            f"{len(missing)} africa_me_legacy pgids not in land"
        )

    def test_land_subset_of_global(self) -> None:
        land = load_region_pgids("land")
        global_set = load_region_pgids("global")
        missing = land - global_set
        assert not missing, (
            f"{len(missing)} land pgids not in global"
        )

    def test_pgid_range(self) -> None:
        land = load_region_pgids("land")
        assert min(land) >= 1
        assert max(land) <= 259200


class TestPartitionAlignment:
    """Factory partition boundaries match model configs."""

    @pytest.fixture(scope="class")
    def factory_partitions(self) -> dict:
        from datafactory_query.defaults import PARTITIONS
        return dict(PARTITIONS)

    @pytest.fixture(scope="class")
    def model_partitions(self) -> dict[str, dict]:
        results = {}
        for model in ALL_MODELS:
            config_path = MODELS_ROOT / model / "configs"
            if not config_path.exists():
                continue
            partition_file = config_path / "config_partitions.py"
            if not partition_file.exists():
                continue
            spec = _import_module_from_path(
                f"{model}_partitions", partition_file,
            )
            results[model] = spec.generate()
        return results

    def test_at_least_one_model_found(
        self, model_partitions: dict,
    ) -> None:
        assert model_partitions, (
            "No model config_partitions.py found — "
            f"checked {MODELS_ROOT}"
        )

    def test_calibration_train_matches(
        self,
        factory_partitions: dict,
        model_partitions: dict,
    ) -> None:
        f_train = factory_partitions["calibration"]["train"]
        for model, parts in model_partitions.items():
            m_train = parts["calibration"]["train"]
            assert f_train == m_train, (
                f"{model} calibration train {m_train} != "
                f"factory {f_train}"
            )

    def test_calibration_test_matches(
        self,
        factory_partitions: dict,
        model_partitions: dict,
    ) -> None:
        f_test = factory_partitions["calibration"]["test"]
        for model, parts in model_partitions.items():
            m_test = parts["calibration"]["test"]
            assert f_test == m_test, (
                f"{model} calibration test {m_test} != "
                f"factory {f_test}"
            )

    def test_validation_train_matches(
        self,
        factory_partitions: dict,
        model_partitions: dict,
    ) -> None:
        f_train = factory_partitions["validation"]["train"]
        for model, parts in model_partitions.items():
            m_train = parts["validation"]["train"]
            assert f_train == m_train, (
                f"{model} validation train {m_train} != "
                f"factory {f_train}"
            )

    def test_validation_test_matches(
        self,
        factory_partitions: dict,
        model_partitions: dict,
    ) -> None:
        f_test = factory_partitions["validation"]["test"]
        for model, parts in model_partitions.items():
            m_test = parts["validation"]["test"]
            assert f_test == m_test, (
                f"{model} validation test {m_test} != "
                f"factory {f_test}"
            )

    def test_no_gaps_between_partitions(
        self, factory_partitions: dict,
    ) -> None:
        cal_test_end = factory_partitions["calibration"]["test"][1]
        val_test_start = factory_partitions["validation"]["test"][0]
        assert cal_test_end + 1 == val_test_start, (
            f"Gap: calibration test ends {cal_test_end}, "
            f"validation test starts {val_test_start}"
        )


class TestFeatureContract:
    """Factory produces exactly the features models expect."""

    @pytest.mark.parametrize("model", ALL_MODELS)
    def test_queryset_exists(self, model: str) -> None:
        path = MODELS_ROOT / model / "configs" / "config_queryset.py"
        if not path.exists():
            pytest.skip(f"{model} not available at {MODELS_ROOT}")
        assert path.exists()

    @pytest.mark.parametrize(
        "model,expected_features",
        [
            ("bright_starship", {"ged_sb_best", "ged_ns_best", "ged_os_best"}),
            ("heavy_freighter", {"ged_sb_best", "ged_ns_best", "ged_os_best"}),
            ("heavy_strider", {"ged_sb_best", "ged_ns_best", "ged_os_best"}),
            ("light_strider", {"ged_sb_best", "ged_ns_best", "ged_os_best"}),
            ("shining_codex", {"ged_sb_best", "ged_ns_best", "ged_os_best"}),
        ],
    )
    def test_factory_features_present(
        self, model: str, expected_features: set,
    ) -> None:
        path = MODELS_ROOT / model / "configs" / "config_queryset.py"
        if not path.exists():
            pytest.skip(f"{model} not available")
        spec = _import_module_from_path(
            f"{model}_queryset", path,
        )
        descriptor = spec.generate()
        rename_map = descriptor["features"]
        assert set(rename_map.keys()) >= expected_features

    def test_shining_codex_uses_lr_ged_sb(self) -> None:
        path = (
            MODELS_ROOT / "shining_codex" / "configs"
            / "config_queryset.py"
        )
        if not path.exists():
            pytest.skip("shining_codex not available")
        spec = _import_module_from_path(
            "shining_codex_queryset", path,
        )
        descriptor = spec.generate()
        assert descriptor["features"]["ged_sb_best"] == "lr_ged_sb"
        assert descriptor["loa"] == "country_month"

    def test_pgm_models_use_lr_sb_best(self) -> None:
        for model in [
            "bright_starship", "heavy_freighter",
            "heavy_strider", "light_strider",
        ]:
            path = (
                MODELS_ROOT / model / "configs"
                / "config_queryset.py"
            )
            if not path.exists():
                continue
            spec = _import_module_from_path(
                f"{model}_queryset", path,
            )
            descriptor = spec.generate()
            assert descriptor["features"]["ged_sb_best"] == "lr_sb_best", (
                f"{model} renames ged_sb_best to "
                f"{descriptor['features']['ged_sb_best']}"
            )
            assert descriptor["loa"] == "priogrid_month"


def _import_module_from_path(name: str, path: Path):
    """Import a Python module from an arbitrary file path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
