"""ADR-026 §7: every credential has a named owner and a review date.

#392 (þing-02 DF2). None of this repo's credentials expires — Caddy
basic auth has no expiry in the mechanism, the harvest tokens carry
no expiry date, and ACLED's short-lived bearer is minted from
credentials that do not expire. Nothing therefore prompts a rotation,
which is why the GDL token (C-324) sat known-leaked and unrotated.

**What these tests deliberately do NOT do: fail when a review date
has passed.** Two reasons, both load-bearing:

1. Such a test cannot observe the thing it claims to guard. Rotation
   happens in Caddy's config and on globaldatalab.org; the test reads
   a date a human typed into a markdown table. The cheapest way to
   make it green is to edit the date — exactly the neglect it would
   exist to prevent. The repo already ruled on this class of question
   in `test_falsification_deploy_v160.py`, where gates skip with a
   reason when the environment cannot answer.
2. `development` and `main` require these checks to pass with no
   admin override. A date-triggered failure would block every merge,
   including an unrelated incident fix, on a calendar event — C-320's
   lesson that a build red for reasons unrelated to the code under
   test stops carrying information.

The currency question ("is anything overdue?") lives in the release
runbook, `docs/guides/publishing_to_pypi.md`, which is a deliberate
moment where a human is already paying attention.

What IS testable, and what these tests pin: the table exists, is
well-formed, and covers every credential the codebase actually
resolves — so a new credential cannot be added without an owner and
a date.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

ADR = Path("docs/ADRs/026_credential_management.md")

# Env vars the packaged code resolves. Kept explicit rather than
# derived: the point is to notice when code and table drift apart,
# and deriving both from one source would defeat that.
RESOLVED_CREDENTIALS = (
    "UCDP_API_TOKEN",
    "ACLED_USERNAME",
    "ACLED_PASSWORD",
    "GDL_API_TOKEN",
)


def _ownership_rows() -> list[list[str]]:
    """Rows of the ADR-026 §7 credential table."""
    text = ADR.read_text()
    marker = "### 7. Every credential has a named owner"
    assert marker in text, (
        f"ADR-026 has no §7 ownership section. {ADR} is the "
        f"declared home for credential ownership (#392)."
    )
    section = text.split(marker, 1)[1]
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] in ("Credential", "---") or set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


class TestCredentialOwnershipTable:

    def test_table_is_present_and_populated(self) -> None:
        rows = _ownership_rows()
        assert rows, (
            "ADR-026 §7 credential table is empty. Every credential "
            "needs a named owner and a review date (#392)."
        )

    @pytest.mark.parametrize("field_idx,field_name", [
        (1, "location"), (2, "owner"), (3, "review date"),
    ])
    def test_every_row_has_all_fields(
        self, field_idx: int, field_name: str,
    ) -> None:
        for row in _ownership_rows():
            assert row[field_idx], (
                f"Credential {row[0]!r} has no {field_name} in "
                f"ADR-026 §7. A credential without one is how the "
                f"GDL token (C-324) went unrotated after a known leak."
            )

    def test_review_dates_are_parseable_iso(self) -> None:
        """A date nobody can parse is not a date."""
        for row in _ownership_rows():
            raw = row[3]
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw), (
                f"Credential {row[0]!r} has review date {raw!r}, "
                f"which is not ISO YYYY-MM-DD. Use an unambiguous "
                f"format — this table is read by humans under time "
                f"pressure."
            )
            date.fromisoformat(raw)

    def test_every_resolved_credential_appears(self) -> None:
        """Code and table must not drift apart.

        If the harvester resolves an env var that the table does not
        mention, nobody owns it and nobody will review it.
        """
        table = "\n".join("|".join(r) for r in _ownership_rows())
        missing = [c for c in RESOLVED_CREDENTIALS if c not in table]
        assert not missing, (
            f"These credentials are resolved by packaged code but "
            f"absent from ADR-026 §7: {missing}. Add a row with an "
            f"owner and a review date, or stop resolving them."
        )

    def test_owner_is_a_role_not_only_a_person(self) -> None:
        """One operator today does not make ownership meaningful.

        A row naming only a person degrades to nothing when that
        person leaves; a role survives the handover.
        """
        for row in _ownership_rows():
            owner = row[2].lower()
            assert any(
                word in owner
                for word in ("operator", "maintainer", "team", "admin")
            ), (
                f"Credential {row[0]!r} has owner {row[2]!r}, which "
                f"does not name a role. Use a role (e.g. 'Pipeline "
                f"operator'); name the current holder in prose if "
                f"useful."
            )
