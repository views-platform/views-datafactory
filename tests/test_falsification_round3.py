"""Falsification stub — round 3 audit of "the missing-cells issue is now solved
on the development branch."

Rounds 1-2 found hard falsifications (all fixed). Round 3 found NO hard
falsification: git state is clean and pushed, the land_gaul completeness
contract holds, the three round-2 findings (DF-1/2/3) are genuinely resolved,
and a hunt for a second source defect among the excluded cells came up empty
(the highest-risk island cells all have their correct GAUL unit present).

The one soft finding: the 66 `coastal_resolution_gap` classifications rest on
a distance-to-nearest-polygon discriminator that round 2 PROVED unreliable —
Fuvahmulah sat at 0.33 deg (inside the same band as all 66) yet was a genuine
source defect. The fix corrected that single named cell by hand but never
re-validated the other 66 with a reliable method. Their rationale text still
asserts categorically "this is a grid-resolution artifact, not a source
defect." Correctness is asserted, not verified.

This test FAILS BY DESIGN until the Fuvahmulah-signature cells carry a recorded
per-cell verification that their correct GAUL unit exists.
"""

import json
from pathlib import Path

import pytest

_CLASSIFICATION = Path(
    "reports/investigation_gaul_excluded_cells/excluded_cell_classification.json"
)

# Fuvahmulah's signature: an island-nation cell, OR a cell whose nearest GAUL
# unit reports admin2 == "Administrative Unit Not Available". These are the
# cells where "nearest polygon is 0.3 deg away" is ambiguous between
# "coarse coastal edge of the right unit" and "the right unit is absent".
_ISLAND_NATIONS = {
    "Maldives", "Kiribati", "Marshall Islands", "Tuvalu", "Nauru",
    "Solomon Islands", "Vanuatu", "Fiji", "Seychelles", "Cabo Verde",
    "Sao Tome and Principe", "Comoros", "Tonga", "Samoa", "Palau",
    "Micronesia", "Federated States of Micronesia", "French Polynesia",
}


def _flagged_cells(classification: list[dict]) -> list[dict]:
    out = []
    for e in classification:
        if e["classification"] != "coastal_resolution_gap":
            continue
        if (
            e.get("nearest_country") in _ISLAND_NATIONS
            or e.get("nearest_admin2") == "Administrative Unit Not Available"
        ):
            out.append(e)
    return out


class TestResolutionGapDiscriminatorWasRevalidated:
    """R3 (SOFT): coastal_resolution_gap cells matching the Fuvahmulah
    signature must carry a recorded per-cell verification that their correct
    GAUL unit exists — because the distance discriminator that classified them
    is known-unreliable (it misclassified Fuvahmulah).

    Passes when each flagged entry has a `unit_verified` field (or equivalent)
    recording that GAUL contains a polygon for the unit that should cover the
    cell — i.e. the classification was confirmed by polygon presence, not by
    distance proxy alone.
    """

    def test_fuvahmulah_signature_cells_carry_recorded_unit_verification(self):
        classification = json.loads(_CLASSIFICATION.read_text())
        flagged = _flagged_cells(classification)
        assert flagged, "expected island-nation / unit-absent-signature cells"
        unverified = [
            e["gid"]
            for e in flagged
            if not e.get("unit_verified") and not e.get("verification_note")
        ]
        assert unverified == [], (
            f"{len(unverified)} coastal_resolution_gap cells share Fuvahmulah's "
            f"signature but carry no recorded per-cell verification that their "
            f"correct GAUL unit exists: {unverified}. The distance discriminator "
            f"that classified them is proven unreliable (it misclassified "
            f"Fuvahmulah at the same 0.33 deg). Verify each by polygon presence "
            f"and record the result, or the 'not a source defect' rationale is "
            f"asserted, not established."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
