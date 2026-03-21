"""Falsification audit: candidate dataset mutability.

Generated 2026-03-21 from falsification of the claim:
"Candidate datasets get finalized once a month and then
versions are static across time."

HARD FALSIFIED: All 14 candidate versions from 2025-2026
gained exactly +1,000 events in a bulk update between
2026-03-20 and 2026-03-21. Older 2024 versions were stable.
"""

from __future__ import annotations

import pytest


class TestCandidateMutabilityFalsifications:
    """Hard falsification: candidate versions are NOT static."""

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: All 14 candidate versions "
        "(25.0.1-26.0.2) gained exactly +1,000 events each in "
        "a bulk update. 25.0.1 (Jan 2025, 14 months old) "
        "changed from 1,159 to 2,159. Versions are NOT static."
    )
    def test_candidate_versions_are_not_static(self) -> None:
        """Evidence from re-querying API on 2026-03-21.

        Original fetch (2026-03-20):
          25.0.1: 1,159 events
          25.0.2: 897 events
          ...all 14 versions...
          26.0.2: 298 events

        Re-query (~24 hours later):
          25.0.1: 2,159 events (+1,000)
          25.0.2: 1,897 events (+1,000)
          ...all 14 versions...
          26.0.2: 1,298 events (+1,000)

        Every version gained EXACTLY +1,000 events.
        This is a bulk retroactive update, not organic growth.

        Meanwhile, 2024 candidates (24.0.1-24.0.12) were
        completely stable (0 changes across all 12 versions).

        Implications:
        - Provenance digests for 2025-2026 candidates are stale
        - Our consolidated store is missing ~14,000 events
        - The "unchanged" heartbeat detection is only valid
          within a short time window, not across days
        - UCDP has an undocumented version boundary (~1 year?)
          beyond which versions are truly frozen
        """
        pytest.fail(
            "Candidate versions are mutable: "
            "+1,000 events across all 2025-2026 versions"
        )

    @pytest.mark.skip(
        reason="OBSERVATION: 2024 candidates are stable while "
        "2025-2026 are mutable. There appears to be an "
        "undocumented age boundary for version freezing."
    )
    def test_version_freeze_boundary_undocumented(self) -> None:
        """UCDP appears to freeze candidate versions after ~1 year.

        2024 candidates (24.0.1-24.0.12): ALL STABLE (0 changes)
        2025 candidates (25.0.1-25.0.12): ALL CHANGED (+1,000)
        2026 candidates (26.0.1-26.0.2): ALL CHANGED (+1,000)

        This suggests a year-level boundary. Versions from the
        prior calendar year and earlier are frozen. Versions from
        the current and previous year are still mutable.

        This boundary is not documented anywhere — not in UCDP
        API docs, not in codebooks, not in the production notebook.
        """
        pytest.fail(
            "Version freeze boundary is undocumented"
        )
