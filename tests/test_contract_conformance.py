"""Conformance tests for the FeatureFrame contract fixture (ADR-050, #344).

The committed fixture is the executable layout spec. These tests are
the drift alarm: a views-frames upgrade that changes the on-disk
layout fails test_regeneration_is_byte_identical at the version-bump
PR — which is the intended behavior, not a nuisance (see the fixture
README and ADR-050 before "fixing" it).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).parent.parent
FIXTURE_DIR = _REPO / "tests" / "fixtures" / "feature_frame_contract"
FRAME_DIR = FIXTURE_DIR / "frame"
CONTRACT_PATH = FIXTURE_DIR / "contract.json"

_SPEC = importlib.util.spec_from_file_location(
    "generate_contract_fixture",
    _REPO / "scripts" / "generate_contract_fixture.py",
)
gcf = importlib.util.module_from_spec(_SPEC)
sys.modules["generate_contract_fixture"] = gcf
_SPEC.loader.exec_module(gcf)


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


class TestFixtureIntegrity:

    def test_fixture_digest_matches_contract(self) -> None:
        """Tamper/drift guard: committed bytes == pinned digest."""
        assert gcf.fixture_digest(FRAME_DIR) == _contract()[
            "fixture_digest"
        ]

    def test_layout_files_match_contract(self) -> None:
        """The directory contains exactly the declared files."""
        assert sorted(
            p.name for p in FRAME_DIR.iterdir()
        ) == sorted(_contract()["layout_files"])

    def test_regeneration_is_byte_identical(
        self, tmp_path: Path,
    ) -> None:
        """Re-running the generator reproduces the committed bytes.

        Fails when a views-frames upgrade changes the layout — the
        drift alarm (ADR-050). Review, bump contract_version,
        re-pin; never regenerate without review.
        """
        regen = tmp_path / "frame"
        gcf.generate(regen)
        for name in _contract()["layout_files"]:
            assert (regen / name).read_bytes() == (
                FRAME_DIR / name
            ).read_bytes(), f"{name} drifted from committed fixture"


class TestFixtureRoundTrip:

    def test_load_round_trips_contractual_properties(self) -> None:
        """load() recovers dtype, shape, identifiers, features."""
        from views_frames import FeatureFrame

        ff = FeatureFrame.load(FRAME_DIR)
        values = np.asarray(ff.values)
        assert values.dtype == np.float32, "dtype is contractual"
        assert values.shape == (6, 2, 1)
        assert ff.feature_names == [
            "ged_sb_best", "acled_fatalities",
        ]
        assert list(np.asarray(ff.index.time)) == [
            541, 541, 541, 542, 542, 542,
        ]
        assert list(np.asarray(ff.index.unit)) == [
            149426, 150146, 150866,
            149426, 150146, 150866,
        ]
        assert values[0, 0, 0] == 1.0
        assert values[5, 1, 0] == 60.0

    def test_loaded_frame_matches_generator_output(self) -> None:
        """Committed fixture == what the generator builds today."""
        from views_frames import FeatureFrame

        committed = FeatureFrame.load(FRAME_DIR)
        built = gcf.build_contract_frame()
        assert np.array_equal(
            np.asarray(committed.values),
            np.asarray(built.values),
        )


class TestContractDocument:

    def test_output_formats_match_load_dataset_vocabulary(
        self,
    ) -> None:
        """contract.json formats == the vocabulary load_dataset
        validates against. Story 2 (#345) upgrades this to the
        three-way test including OutputFormat."""
        from datafactory_query.dataset import _VALID_FORMATS

        assert tuple(_contract()["output_formats"]) == tuple(
            _VALID_FORMATS
        )

    def test_contract_version_present_and_semver(self) -> None:
        version = _contract()["contract_version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)
