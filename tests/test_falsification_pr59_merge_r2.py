"""Falsification audit round 2: PR #59 merge readiness.

Claim: "PR #59 is ready to merge to development."
Audit date: 2026-05-21, round 2 (post-F5 fix).

F1: ADR-032 claims all harvesters record "failed" entries —
    shapefile_harvester has no outcome field at all.
F2: ADR-032 Implementation Notes omit last_digest (non-versioned),
    which UCDP annual and shapefile harvester use.
F3: last_digest returns None for a success entry that lacks the
    digest field, shadowing valid earlier entries.
"""

from __future__ import annotations

from pathlib import Path

from datafactory_provenance import (
    append_ledger_entry,
    last_digest,
    last_digest_for_version,
)


class TestF3SuccessWithoutDigestShadows:
    """F3: A success entry missing the digest field should not
    shadow a valid earlier entry."""

    def test_last_digest_skips_success_without_digest(
        self, tmp_path: Path,
    ) -> None:
        """A 'success' entry with no content_digest should be
        skipped, returning the digest from the prior valid entry."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "content_digest": "good_digest",
            "outcome": "success",
        })
        append_ledger_entry(ledger, {
            "outcome": "success",
            # no content_digest field
        })
        result = last_digest(ledger)
        assert result == "good_digest", (
            f"Expected 'good_digest' but got {result!r} — "
            "success entry without digest shadows valid entry"
        )

    def test_last_digest_for_version_skips_success_without_digest(
        self, tmp_path: Path,
    ) -> None:
        """Same shadow bug for last_digest_for_version."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1",
            "content_digest": "good_digest",
            "outcome": "success",
        })
        append_ledger_entry(ledger, {
            "version": "25.1",
            "outcome": "success",
            # no content_digest field
        })
        result = last_digest_for_version(ledger, "25.1")
        assert result == "good_digest", (
            f"Expected 'good_digest' but got {result!r} — "
            "success entry without digest shadows valid entry"
        )
