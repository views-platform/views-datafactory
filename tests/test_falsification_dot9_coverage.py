"""Falsification audit: .9 dataset coverage claims.

Generated 2026-03-21 from falsification of the claim:
"The .9 dataset is always a rolling 13-month window with ~88%
overlap and ~2,600 exclusive events per version."

FALSIFIED: Three hard falsifications. All three quantitative
claims are false when tested across the full 78-version history.
"""

from __future__ import annotations

import pytest


class TestDot9CoverageFalsifications:

    @pytest.mark.falsification(
        reason="HARD FALSIFICATION: 8 of 78 .9 versions are NOT "
        "13 months. 5 are 14 months, 2 are 15 months, and "
        "21.9.1 spans 25 months (Jan 2019 – Jan 2021). "
        "data_streams.md must be corrected."
    )
    def test_dot9_always_13_months(self) -> None:
        """70 of 78 versions (89.7%) are 13 months. But 8 are
        not: 5 span 14 months, 2 span 15 months, and 21.9.1
        spans 25 months. The 'always' claim is false.

        Corrected: 'typically 13 months (~90%), with occasional
        14-15 month windows and one 25-month anomaly (21.9.1).'
        """
        pytest.fail("8 of 78 .9 versions are not 13 months")

    @pytest.mark.falsification(
        reason="HARD FALSIFICATION: Consecutive .9 overlap ranges "
        "from 41.5% (21.9.1→21.9.2) to 100% (18.9.1→18.9.2). "
        "The ~88% figure only holds for 2022-2024 data."
    )
    def test_dot9_always_88_percent_overlap(self) -> None:
        """Overlap varies by year and version:
        - 2018: ~100% (early versions fully contained)
        - 2019-2020: ~90-91%
        - 2021: 41.5% (21.9.1 anomaly)
        - 2022-2024: 88-93% (matches claim)

        Corrected: 'typically 88-93% overlap for recent years,
        but varies significantly in early years and anomalous
        periods.'
        """
        pytest.fail("Overlap ranges from 41.5% to 100%")

    @pytest.mark.falsification(
        reason="HARD FALSIFICATION: Exclusive event count ranges "
        "from 364 (20.9.6) to 2,593 (24.9.6) — a 7x range. "
        "The ~2,600 figure only applies to the most recent year."
    )
    def test_dot9_always_2600_exclusive(self) -> None:
        """Exclusive events (not in annual v25.1) per .9 version:
        - 18.9.6: 1,195 (11.5%)
        - 19.9.6: 1,156 (10.1%)
        - 20.9.6: 364 (3.3%)
        - 21.9.6: 1,531 (9.8%)
        - 22.9.6: 1,287 (7.6%)
        - 23.9.6: 1,660 (8.0%)
        - 24.9.6: 2,593 (9.2%)

        Corrected: 'exclusive events range from ~350 to ~2,600
        per version (3-12% of content), varying by year and
        conflict levels.'
        """
        pytest.fail(
            "Exclusive events range from 364 to 2,593"
        )
