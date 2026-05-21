"""Falsification audit: PR #59 merge readiness.

Claim: "PR #59 is ready to merge to development."
Audit date: 2026-05-21.

F5: last_digest (non-versioned) has the same C-182 bug —
returns digest from failed entries, causing ucdp_annual
to skip re-fetch after a validation failure.
"""

from __future__ import annotations

from pathlib import Path

from datafactory_provenance import (
    append_ledger_entry,
    last_digest,
)


class TestLastDigestOutcomeFiltering:
    """F5: last_digest should skip failed entries like
    last_digest_for_version does (C-182 parity)."""

    def test_last_digest_skips_failed_entries(
        self, tmp_path: Path,
    ) -> None:
        """If the last ledger entry is 'failed', last_digest
        should return the digest from the most recent
        successful entry, not the failed one."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "content_digest": "good_digest",
            "outcome": "success",
        })
        append_ledger_entry(ledger, {
            "content_digest": "failed_digest",
            "outcome": "failed",
        })
        assert last_digest(ledger) == "good_digest"

    def test_last_digest_returns_none_when_only_failed(
        self, tmp_path: Path,
    ) -> None:
        """If all entries are failed, last_digest should
        return None (no valid cache)."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "content_digest": "failed_digest",
            "outcome": "failed",
        })
        assert last_digest(ledger) is None
