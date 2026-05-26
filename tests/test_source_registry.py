"""Tests for the source registry (ADR-003, ADR-009).

The source registry is the single source of truth for pipeline
sources. These tests verify structural invariants, validation
logic, and the pre-flight check function.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    SourceEntry,
    get_all_features,
    get_required_env_vars,
    get_source_slo,
    validate_preflight,
)


class TestSourceEntry:
    """SourceEntry frozen dataclass validation."""

    def test_valid_construction(self) -> None:
        entry = SourceEntry(
            name="test",
            required_env_vars=("TOKEN",),
            features=("feat_a",),
            slo_hours=744,
        )
        assert entry.name == "test"
        assert entry.required_env_vars == ("TOKEN",)

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            SourceEntry(name="")

    def test_empty_env_var_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            SourceEntry(name="x", required_env_vars=("",))

    def test_empty_feature_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            SourceEntry(name="x", features=("",))

    def test_negative_slo_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SourceEntry(name="x", slo_hours=-1)

    def test_zero_slo_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SourceEntry(name="x", slo_hours=0)

    def test_frozen_immutability(self) -> None:
        entry = SourceEntry(name="x")
        with pytest.raises(AttributeError):
            entry.name = "y"  # type: ignore[misc]

    def test_none_slo_allowed(self) -> None:
        entry = SourceEntry(name="static", slo_hours=None)
        assert entry.slo_hours is None


class TestPipelineSources:
    """Structural invariants on PIPELINE_SOURCES."""

    def test_no_duplicate_names(self) -> None:
        names = [s.name for s in PIPELINE_SOURCES]
        assert len(names) == len(set(names)), (
            f"duplicate names: "
            f"{[n for n in names if names.count(n) > 1]}"
        )

    def test_no_duplicate_features(self) -> None:
        all_feats: list[str] = []
        for s in PIPELINE_SOURCES:
            all_feats.extend(s.features)
        dupes = [f for f in set(all_feats) if all_feats.count(f) > 1]
        assert not dupes, f"duplicate features: {dupes}"

    def test_feature_count_is_75(self) -> None:
        """6 UCDP + 8 ACLED + 1 GHS-POP + 1 GHS-BUILT-S
        + 22 V-Dem + 34 static + 3 admin = 75."""
        assert len(get_all_features()) == 75

    def test_ucdp_features_first(self) -> None:
        feats = get_all_features()
        assert feats[0] == "ged_sb_count"
        assert feats[5] == "ged_os_best"

    def test_acled_features_after_ucdp(self) -> None:
        feats = get_all_features()
        assert feats[6] == "acled_count"
        assert feats[13] == "acled_fatalities"

    def test_admin_features_last(self) -> None:
        feats = get_all_features()
        assert feats[-1] == "gaul2_code"
        assert feats[-3] == "gaul0_code"

    def test_all_sources_have_names(self) -> None:
        for s in PIPELINE_SOURCES:
            assert s.name

    def test_sources_with_credentials(self) -> None:
        cred_sources = [
            s for s in PIPELINE_SOURCES if s.required_env_vars
        ]
        assert len(cred_sources) >= 4  # UCDP × 3 + ACLED

    def test_at_least_one_source_per_slo_category(self) -> None:
        slos = {s.slo_hours for s in PIPELINE_SOURCES}
        assert None in slos  # static sources
        assert 744 in slos   # monthly sources
        assert 8760 in slos  # yearly sources


class TestGetSourceSlo:
    """get_source_slo() derives SLO dict from registry."""

    def test_returns_dict_with_all_names(self) -> None:
        slo = get_source_slo()
        names = {s.name for s in PIPELINE_SOURCES}
        assert set(slo.keys()) == names

    def test_static_sources_are_none(self) -> None:
        slo = get_source_slo()
        assert slo["PRIO-GRID Static"] is None
        assert slo["PRIO-GRID Shapefile"] is None

    def test_monthly_sources_are_744(self) -> None:
        slo = get_source_slo()
        assert slo["ACLED"] == 744
        assert slo["Compilation"] == 744


class TestGetAllFeatures:
    """get_all_features() returns ordered feature tuple."""

    def test_returns_tuple(self) -> None:
        feats = get_all_features()
        assert isinstance(feats, tuple)

    def test_custom_sources(self) -> None:
        sources = (
            SourceEntry(name="a", features=("x", "y")),
            SourceEntry(name="b", features=("z",)),
        )
        assert get_all_features(sources) == ("x", "y", "z")


class TestGetRequiredEnvVars:
    """get_required_env_vars() collects all credential env vars."""

    def test_includes_ucdp_token(self) -> None:
        assert "UCDP_API_TOKEN" in get_required_env_vars()

    def test_includes_acled_creds(self) -> None:
        env_vars = get_required_env_vars()
        assert "ACLED_USERNAME" in env_vars
        assert "ACLED_PASSWORD" in env_vars


class TestValidatePreflight:
    """validate_preflight() checks env vars."""

    def test_all_ok_when_vars_set(self) -> None:
        sources = (
            SourceEntry(
                name="test",
                required_env_vars=("TEST_VAR",),
            ),
        )
        with patch.dict(os.environ, {"TEST_VAR": "value"}):
            results = validate_preflight(sources)
        assert len(results) == 1
        assert results[0]["status"] == "OK"
        assert results[0]["source"] == "test"

    def test_fail_when_var_missing(self) -> None:
        sources = (
            SourceEntry(
                name="test",
                required_env_vars=("MISSING_VAR_XYZ",),
            ),
        )
        env = os.environ.copy()
        env.pop("MISSING_VAR_XYZ", None)
        with patch.dict(os.environ, env, clear=True):
            results = validate_preflight(sources)
        assert len(results) == 1
        assert results[0]["status"] == "FAIL"
        assert "~/.profile" in results[0]["detail"]

    def test_fail_when_var_empty(self) -> None:
        sources = (
            SourceEntry(
                name="test",
                required_env_vars=("EMPTY_VAR",),
            ),
        )
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            results = validate_preflight(sources)
        assert results[0]["status"] == "FAIL"

    def test_deduplicates_env_vars(self) -> None:
        sources = (
            SourceEntry(
                name="a",
                required_env_vars=("SHARED_TOKEN",),
            ),
            SourceEntry(
                name="b",
                required_env_vars=("SHARED_TOKEN",),
            ),
        )
        with patch.dict(os.environ, {"SHARED_TOKEN": "val"}):
            results = validate_preflight(sources)
        assert len(results) == 1
