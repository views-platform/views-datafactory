"""Falsification audit: candidate dataset coverage claims.

Generated 2026-03-21 from falsification of the claim:
"Candidate datasets are independent monthly (strictly one month)
installments with ZERO overlap between months."

FALSIFIED: Two hard falsifications found.
"""

from __future__ import annotations

import pytest


class TestCandidateCoverageFalsifications:

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: Candidate versions are NOT "
        "strictly one month. 25.0.1 has 1 event from Dec 2024. "
        "25.0.12 has events from Jan, Oct, Nov 2025. 24.0.11 "
        "has events from Jan, Sep, Oct 2024. Every version "
        "checked has 0.1-1.4% events from other months."
    )
    def test_candidates_strictly_one_month(self) -> None:
        """Each candidate version should cover exactly one
        calendar month. Empirically false: every version has
        a small number of events from other months, some
        from many months earlier (24.0.12 has a Jan 2024
        event — 11 months before its primary month).

        The data_streams.md document should be corrected
        from 'strictly one month' to 'primarily one month
        with a small number of events from other months.'
        """
        pytest.fail(
            "Candidate versions span multiple calendar months"
        )

    @pytest.mark.skip(
        reason="HARD FALSIFICATION: Candidate versions 21.0.4 "
        "and 21.0.5 share 606 event IDs (99.7% of 21.0.4). "
        "This is the only overlap across 1,953 version pairs "
        "from 63 versions, likely a data anomaly from early "
        "2021 when UCDP was establishing the candidate system."
    )
    def test_candidates_zero_overlap(self) -> None:
        """No event ID should appear in multiple candidate
        versions. Empirically false: 21.0.4 and 21.0.5
        share 606 IDs with identical values. Version 21.0.4
        appears to have been re-released within 21.0.5.

        The data_streams.md document should note this
        anomaly rather than claiming absolute zero overlap.
        """
        pytest.fail(
            "21.0.4 and 21.0.5 share 606 event IDs"
        )
