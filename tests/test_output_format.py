"""Tests for the public output-format contract (ADR-050, #345)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datafactory_query import (
    CONTRACT_VERSION,
    OutputFormat,
    is_valid_output_format,
)
from datafactory_query.dataset import _VALID_FORMATS

CONTRACT_PATH = (
    Path(__file__).parent
    / "fixtures" / "feature_frame_contract" / "contract.json"
)


class TestThreeWayAgreement:
    """The contract has one source of truth and two projections —
    they may never disagree."""

    def test_enum_matches_contract_json(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text())
        assert [f.value for f in OutputFormat] == contract[
            "output_formats"
        ]

    def test_enum_matches_internal_alias(self) -> None:
        assert tuple(f.value for f in OutputFormat) == _VALID_FORMATS

    def test_contract_version_matches_contract_json(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text())
        assert contract["contract_version"] == CONTRACT_VERSION


class TestOutputFormatGreen:

    def test_members(self) -> None:
        assert OutputFormat.FEATURE_FRAME == "feature_frame"
        assert OutputFormat.DATAFRAME == "dataframe"
        assert OutputFormat.COUNTRY_MONTH == "country_month"

    def test_str_compatibility(self) -> None:
        """StrEnum members interoperate with plain strings —
        existing callers passing strings keep working."""
        assert OutputFormat.DATAFRAME in _VALID_FORMATS
        assert f"{OutputFormat.FEATURE_FRAME}" == "feature_frame"

    def test_importable_from_package_root(self) -> None:
        import datafactory_query

        assert "OutputFormat" in datafactory_query.__all__
        assert "CONTRACT_VERSION" in datafactory_query.__all__
        assert (
            "is_valid_output_format" in datafactory_query.__all__
        )


class TestIsValidOutputFormat:

    @pytest.mark.parametrize(
        "value", ["feature_frame", "dataframe", "country_month"],
    )
    def test_valid(self, value: str) -> None:
        assert is_valid_output_format(value)

    @pytest.mark.parametrize(
        "value", ["", "FeatureFrame", "csv", "feature_frame "],
    )
    def test_invalid(self, value: str) -> None:
        assert not is_valid_output_format(value)


class TestLoadDatasetValidationUnchanged:

    def test_unknown_format_error_shape(self) -> None:
        """Error behavior identical to pre-ADR-050: ValueError
        naming the invalid value and listing valid ones."""
        from datafactory_query import load_dataset

        with pytest.raises(
            ValueError, match="Unknown format 'nonsense'",
        ):
            load_dataset(output_format="nonsense")

    def test_enum_accepted_where_string_was(self) -> None:
        """Passing the enum member itself must behave like the
        string (StrEnum) — invalid-path check via a missing data
        dir proves validation passed."""
        from datafactory_query import load_dataset

        with pytest.raises(FileNotFoundError):
            load_dataset(
                output_format=OutputFormat.DATAFRAME,
                data_dir="/nonexistent/nowhere",
            )
