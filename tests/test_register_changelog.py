"""Guards for the register header / changelog split (#404).

The risk register header was doing two jobs: it was the *index* that
readers and other guards search, and it was also an append-only
*narrative* of every session plus an append-only *list* of every audit
ever run. Both grew without bound; the index did not.

`test_falsification_merge_readiness.py` requires ``open concerns`` to
appear within the first 8000 characters. Whenever the growing halves
collided with that limit, the resolution was always the same: delete
history to reclaim bytes. On 2026-08-02 two narrative blocks were
retired purely to free 1200 characters — not because they had stopped
being true. That is byte pressure making editorial decisions.

The split moved the narrative and the source list to
``reports/register_changelog.md``. These guards keep them there. The
8000-char guard still exists and is still the contract; these are the
early-warning layer, so drift is caught while it is a sentence rather
than at the cliff edge.
"""

from __future__ import annotations

import re
from pathlib import Path

REGISTER = Path("reports/technical_risk_register.md")
CHANGELOG = Path("reports/register_changelog.md")

# The header's own limit. Deliberately far below the 8000-char guard:
# that one is the contract, this one is the smoke alarm. At the time of
# writing the index sits at ~1670, so this allows roughly a doubling
# before it complains.
HEADER_BUDGET = 3500


def _header() -> str:
    """Everything before the summary table — the index."""
    text = REGISTER.read_text()
    end = text.find("## Open Items Summary")
    assert end != -1, "Register has no '## Open Items Summary' section"
    return text[:end]


class TestChangelogExists:
    """The narrative has somewhere to live, and the register says where."""

    def test_changelog_file_exists(self) -> None:
        assert CHANGELOG.exists(), (
            f"{CHANGELOG} is missing. The register header points at it "
            f"for all narrative history; without it that history is "
            f"gone and the pointer dangles (#404)."
        )

    def test_changelog_is_not_a_stub(self) -> None:
        body = CHANGELOG.read_text()
        assert len(body) > 2000, (
            f"{CHANGELOG} is only {len(body)} chars. It should carry the "
            f"full narrative history moved out of the register header, "
            f"not a placeholder."
        )

    def test_register_links_to_changelog(self) -> None:
        assert "register_changelog.md" in _header(), (
            "The register header must link to register_changelog.md. "
            "Without the link the changelog is unreachable from the "
            "artifact it documents, and the next reader will assume the "
            "history was simply deleted."
        )


class TestHeaderStaysAnIndex:
    """The header's two runaway growth vectors stay moved."""

    def test_header_within_budget(self) -> None:
        size = len(_header())
        assert size <= HEADER_BUDGET, (
            f"Register header is {size} chars, over the {HEADER_BUDGET} "
            f"budget. Something append-only has crept back in. Narrative "
            f"goes in register_changelog.md; audit names go in its "
            f"'Where the findings came from' section. Do NOT fix this by "
            f"deleting history — that is the failure this budget exists "
            f"to prevent (#404)."
        )

    def test_source_line_is_a_pointer_not_a_list(self) -> None:
        """The Source line grew to 71 comma-separated audits (2783 chars).

        The 8000-char guard's own docstring named it as the growth
        vector it was defending against.
        """
        match = re.search(r"^\*\*Source:\*\*.*$", _header(), re.M)
        assert match, "Register header has no **Source:** line"
        line = match.group(0)
        assert len(line) < 600, (
            f"The **Source:** line is {len(line)} chars and is growing "
            f"into a list again. Append new audits to the changelog's "
            f"'Where the findings came from' section instead."
        )

    def test_last_update_is_a_pointer_not_a_history(self) -> None:
        match = re.search(r"^\*\*Last update:\*\*.*$", _header(), re.M)
        assert match, "Register header has no **Last update:** line"
        line = match.group(0)
        assert "Prior:" not in line, (
            "The **Last update:** line has grown a 'Prior:' chain again. "
            "That is the append-only narrative this split removed — it "
            "belongs in register_changelog.md, newest first."
        )
        assert len(line) < 700, (
            f"The **Last update:** line is {len(line)} chars. Keep it to "
            f"one sentence plus the changelog pointer."
        )


class TestNothingWasLostInTheMove:
    """The two blocks retired for byte reasons are actually restored.

    The point of #404 was not tidiness — it was that history had been
    deleted to reclaim space. If the split shipped without those blocks
    coming back, it would have solved the mechanism and kept the damage.
    """

    def test_retired_blocks_restored(self) -> None:
        body = CHANGELOG.read_text()
        for marker in (
            "CI enforcement at the platform",
            "Epic #376",
        ):
            assert marker in body, (
                f"{marker!r} is absent from the changelog. It was "
                f"retired from the register header on 2026-08-02 to "
                f"reclaim characters and was supposed to be restored "
                f"here."
            )
