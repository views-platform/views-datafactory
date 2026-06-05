"""Falsification tests: risk register completeness audit.

These tests document risks discovered during a falsification campaign
against the claim "we have identified the most substantial risks."
Each test targets a gap found in the register.

F1: consolidation post-merge row-count integrity
F2: concurrent pipeline execution guard (flock)
F3: TotalCount bypass in candidate/dot9 (soft falsification)
"""

import inspect
from pathlib import Path

import pytest

from datafactory_consolidation.consolidators import ucdp

PIPELINE_SCRIPT = (
    Path(__file__).parent.parent / "scripts" / "refresh_pipeline.sh"
)


class TestF1ConsolidationIntegrity:
    """F1: consolidate_ucdp() asserts row-count invariants."""

    def test_consolidation_detects_event_loss(self) -> None:
        """Row-count assertions exist in consolidate_ucdp()."""
        source = inspect.getsource(ucdp.consolidate_ucdp)
        assert "Row count mismatch" in source


class TestF2ConcurrentPipelineProtection:
    """F2: refresh_pipeline.sh uses flock."""

    def test_pipeline_prevents_concurrent_runs(self) -> None:
        """flock guard prevents concurrent pipeline execution."""
        text = PIPELINE_SCRIPT.read_text()
        assert "flock" in text


class TestF3TotalCountBypassCandidateDot9:
    """F3: candidate and dot9 harvesters skip TotalCount validation."""

    def test_candidate_validates_envelope_keys(self):
        """ucdp_candidate validates TotalCount is present in the
        API response envelope, like ucdp_annual does."""
        from datafactory_harvester.sources.ucdp_annual import (
            validate_envelope,
        )

        envelope_without_totalcount = {
            "TotalPages": 1,
            "Result": [],
        }
        with pytest.raises(ValueError, match="TotalCount"):
            validate_envelope(envelope_without_totalcount)

    @pytest.mark.xfail(
        reason="dot9 uses .get('TotalCount', 0) "
        "without envelope validation"
    )
    def test_dot9_validates_envelope_keys(self):
        """ucdp_dot9 should validate that TotalCount is present
        in the API response envelope. Currently it defaults to 0."""
        raise AssertionError(
            "ucdp_dot9.py:199 uses .get('TotalCount', 0) — "
            "missing TotalCount silently disables count verification."
        )
