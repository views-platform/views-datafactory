"""Falsification audit: zarr staleness detection + zero-padding safety.

Claim: "The zarr store on Hetzner will not go stale, and if it goes
stale we will know about it. Also we are not at risk of accidentally
training on empty months filled with zeros without warning."

P1 (hard): No external cron monitoring — if cron dies, staleness is
undetected until manual check_health.py run.

P3 (hard): check_export_freshness() only checks export_timestamp,
not last_valid_month_id. A pipeline that runs but ingests no new
UCDP data updates the timestamp while actual data stays stale.

P5 (hard): Remote zarr store lacks last_valid_month_id attr — all
remote consumers get no warning (pending redeploy).

P4 (soft): Warning bypassed when end is a string date.

P6 (soft): Warning bypassed when end=None (load full dataset).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


class TestP3HealthCheckDataValidity:
    """P3 (hard): check_export_freshness should validate
    last_valid_month_id, not just export_timestamp."""

    def test_check_export_freshness_reports_data_recency(self) -> None:
        from datafactory_provenance.health import check_export_freshness

        zarr_path = Path("data/assembled/grid.zarr")
        if not zarr_path.exists():
            pytest.skip("local zarr store not found")

        now = datetime.now(tz=UTC)
        result = check_export_freshness(zarr_path, now)

        assert "last_valid_month_id" in result, (
            "check_export_freshness does not report last_valid_month_id — "
            "a pipeline run that ingests no new UCDP data would update "
            "export_timestamp while actual data stays stale"
        )


class TestP5RemoteZarrAttr:
    """P5 (hard): Remote zarr store must have last_valid_month_id
    in .zattrs for the warning to function."""

    def test_remote_zarr_has_last_valid_month_id(self) -> None:
        from datafactory_query.defaults import get_last_valid_month_id

        result = get_last_valid_month_id()
        assert result is not None, (
            "Remote zarr store .zattrs missing last_valid_month_id — "
            "all remote consumers get no zero-padding warning. "
            "Redeploy to Hetzner to fix."
        )


class TestP4StringEndBypass:
    """P4 (soft): Warning must fire for string end dates that
    exceed last valid data."""

    def test_warning_fires_for_string_end(self) -> None:
        prov_path = Path("data/assembled/provenance.json")
        if not prov_path.exists():
            pytest.skip("assembled data not found")

        prov = json.loads(prov_path.read_text())
        last_valid = prov.get("last_valid_month_id")
        if last_valid is None:
            pytest.skip("last_valid_month_id not in provenance")

        from datafactory_query import load_dataset

        with pytest.warns(UserWarning, match="exceeds last observed"):
            load_dataset(
                region="africa_me_legacy",
                features=["ged_sb_best"],
                output_format="dataframe",
                start="2026-01",
                end="2027-06",
            )


class TestP6NoneEndBypass:
    """P6 (soft): Warning must fire when end=None and returned data
    extends beyond last valid month."""

    def test_warning_fires_for_none_end(self) -> None:
        prov_path = Path("data/assembled/provenance.json")
        if not prov_path.exists():
            pytest.skip("assembled data not found")

        prov = json.loads(prov_path.read_text())
        last_valid = prov.get("last_valid_month_id")
        if last_valid is None:
            pytest.skip("last_valid_month_id not in provenance")

        from datafactory_query import load_dataset

        with pytest.warns(UserWarning, match="exceeds last observed"):
            load_dataset(
                region="africa_me_legacy",
                features=["ged_sb_best"],
                output_format="dataframe",
                start=last_valid - 2,
            )
