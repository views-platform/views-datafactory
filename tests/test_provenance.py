"""Tests for datafactory_provenance provenance utilities.

Covers green (correctness), beige (realistic misuse), and red (adversarial)
categories per ADR-005.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from datafactory_provenance import (
    append_ledger_entry,
    compute_content_digest,
    last_digest,
    last_digest_for_version,
)

# ============================================================
# Green team — correctness
# ============================================================


class TestComputeContentDigestGreen:
    """Digest computation: determinism, length, correctness."""

    def test_returns_16_char_hex(self) -> None:
        result = compute_content_digest(b"hello world")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        a = compute_content_digest(b"deterministic input")
        b = compute_content_digest(b"deterministic input")
        assert a == b

    def test_different_inputs_differ(self) -> None:
        a = compute_content_digest(b"input A")
        b = compute_content_digest(b"input B")
        assert a != b

    def test_known_sha256_prefix(self) -> None:
        # SHA-256 of empty bytes is e3b0c44298fc1c14...
        result = compute_content_digest(b"")
        assert result == "e3b0c44298fc1c14"

    def test_full_digest_when_truncate_zero(self) -> None:
        result = compute_content_digest(b"test", truncate=0)
        assert len(result) == 64  # Full SHA-256 hex


class TestAppendLedgerEntryGreen:
    """Ledger writing: creates dirs, appends, adds timestamp."""

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        ledger = tmp_path / "deep" / "nested" / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "abc123"})
        assert ledger.exists()

    def test_entry_has_timestamp(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "abc123"})
        entry = json.loads(ledger.read_text().strip())
        assert "timestamp" in entry

    def test_entry_preserves_fields(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "abc123", "dataset": "test"})
        entry = json.loads(ledger.read_text().strip())
        assert entry["content_digest"] == "abc123"
        assert entry["dataset"] == "test"

    def test_appends_not_overwrites(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "first"})
        append_ledger_entry(ledger, {"content_digest": "second"})
        lines = ledger.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["content_digest"] == "first"
        assert json.loads(lines[1])["content_digest"] == "second"

    def test_valid_jsonl_format(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"a": 1})
        append_ledger_entry(ledger, {"b": 2})
        for line in ledger.read_text().strip().splitlines():
            json.loads(line)  # Must not raise


class TestLastDigestGreen:
    """Ledger reading: returns correct digest."""

    def test_single_entry(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "abc123"})
        assert last_digest(ledger) == "abc123"

    def test_returns_most_recent(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "old"})
        append_ledger_entry(ledger, {"content_digest": "new"})
        assert last_digest(ledger) == "new"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "nonexistent.jsonl"
        assert last_digest(ledger) is None

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        ledger.write_text("")
        assert last_digest(ledger) is None


class TestLastDigestForVersionGreen:
    """Version-filtered digest lookup."""

    def test_filters_by_version(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"version": "25.1", "content_digest": "aaa"})
        append_ledger_entry(ledger, {"version": "25.2", "content_digest": "bbb"})
        append_ledger_entry(ledger, {"version": "25.1", "content_digest": "ccc"})
        assert last_digest_for_version(ledger, "25.1") == "ccc"
        assert last_digest_for_version(ledger, "25.2") == "bbb"

    def test_returns_none_for_unknown_version(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"version": "25.1", "content_digest": "aaa"})
        assert last_digest_for_version(ledger, "99.0") is None


# ============================================================
# Beige team — realistic misuse
# ============================================================


class TestComputeContentDigestBeige:
    """Digest misuse: wrong types, edge cases."""

    def test_rejects_str_input(self) -> None:
        with pytest.raises(TypeError, match="bytes"):
            compute_content_digest("not bytes")  # type: ignore[arg-type]

    def test_rejects_int_input(self) -> None:
        with pytest.raises(TypeError, match="bytes"):
            compute_content_digest(42)  # type: ignore[arg-type]

    def test_rejects_negative_truncate(self) -> None:
        with pytest.raises(ValueError, match="truncate"):
            compute_content_digest(b"test", truncate=-1)


class TestAppendLedgerEntryBeige:
    """Ledger misuse: empty entries, odd inputs."""

    def test_empty_dict_gets_timestamp(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {})
        entry = json.loads(ledger.read_text().strip())
        assert "timestamp" in entry

    def test_auto_timestamp_overrides_caller_timestamp(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"timestamp": "1999-01-01T00:00:00"})
        entry = json.loads(ledger.read_text().strip())
        assert "1999" not in entry["timestamp"], (
            "Auto-timestamp must override caller-provided timestamp"
        )

    def test_malformed_trailing_line_skipped(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {"content_digest": "good"})
        # Simulate interrupted write: append partial JSON
        with open(ledger, "a") as f:
            f.write('{"content_digest": "trun')
        # last_digest should return the last VALID entry
        assert last_digest(ledger) == "good"


# ============================================================
# Red team — adversarial
# ============================================================


class TestAppendLedgerEntryRed:
    """Ledger adversarial: permission errors, unserializable data."""

    def test_raises_on_read_only_path(self, tmp_path: Path) -> None:
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        ledger = readonly_dir / "ledger.jsonl"
        with pytest.raises(OSError):
            append_ledger_entry(ledger, {"content_digest": "fail"})
        # Restore permissions for cleanup
        readonly_dir.chmod(0o755)

    def test_raises_on_unserializable_value(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        with pytest.raises(TypeError):
            append_ledger_entry(ledger, {"bad": object()})


class TestADR008Compliance:
    """ADR-008: structural failures must be both logged and raised."""

    _logger = "datafactory_provenance.digests_and_ledgers"

    def test_digest_type_error_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with (
            caplog.at_level(logging.ERROR, logger=self._logger),
            pytest.raises(TypeError),
        ):
            compute_content_digest("not bytes")  # type: ignore[arg-type]
        assert any("bytes" in r.message for r in caplog.records)

    def test_digest_bad_algorithm_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with (
            caplog.at_level(logging.ERROR, logger=self._logger),
            pytest.raises(ValueError),
        ):
            compute_content_digest(b"test", algorithm="fake")
        assert any("fake" in r.message for r in caplog.records)

    def test_ledger_os_error_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        ledger = readonly_dir / "ledger.jsonl"
        with (
            caplog.at_level(logging.ERROR, logger=self._logger),
            pytest.raises(OSError),
        ):
            append_ledger_entry(ledger, {"test": True})
        error_records = [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ]
        assert len(error_records) >= 1
        readonly_dir.chmod(0o755)

    def test_ledger_serialize_error_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        ledger = tmp_path / "ledger.jsonl"
        with (
            caplog.at_level(logging.ERROR, logger=self._logger),
            pytest.raises(TypeError),
        ):
            append_ledger_entry(ledger, {"bad": object()})
        error_records = [
            r for r in caplog.records if r.levelno >= logging.ERROR
        ]
        assert len(error_records) >= 1


class TestComputeContentDigestRed:
    """Digest adversarial: empty input, unknown algorithm."""

    def test_empty_bytes_produces_valid_digest(self) -> None:
        result = compute_content_digest(b"")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_unknown_algorithm_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_content_digest(b"test", algorithm="not_a_real_algo")
