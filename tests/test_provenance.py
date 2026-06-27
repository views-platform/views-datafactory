"""Tests for datafactory_provenance provenance utilities.

Covers green (correctness), beige (realistic misuse), and red (adversarial)
categories per ADR-005.
"""

from __future__ import annotations

import json
import unittest.mock
from pathlib import Path

import pytest

from datafactory_provenance import (
    append_ledger_entry,
    compute_content_digest,
    compute_file_digest,
    last_digest,
    last_digest_for_version,
)
from datafactory_provenance.digests_and_ledgers import _rotate_ledger

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

    def test_skips_failed_entries(self, tmp_path: Path) -> None:
        """C-182: failed entries must not count as cached."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "good",
            "outcome": "success",
        })
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "bad",
            "outcome": "failed",
        })
        assert last_digest_for_version(ledger, "25.1") == "good"

    def test_returns_none_when_only_failed(self, tmp_path: Path) -> None:
        """C-182: version with only failed entries returns None."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "bad",
            "outcome": "failed",
        })
        assert last_digest_for_version(ledger, "25.1") is None

    def test_accepts_unchanged_entries(self, tmp_path: Path) -> None:
        """Two-tier cache: 'unchanged' is a valid cache hit."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "same",
            "outcome": "unchanged",
        })
        assert last_digest_for_version(ledger, "25.1") == "same"

    def test_skips_cached_outcome(self, tmp_path: Path) -> None:
        """'cached' entries are informational, not cache hits."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "original",
            "outcome": "success",
        })
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "original",
            "outcome": "cached",
        })
        assert last_digest_for_version(ledger, "25.1") == "original"

    def test_accepts_entries_without_outcome(self, tmp_path: Path) -> None:
        """Backward compat: pre-outcome ledger entries are accepted."""
        ledger = tmp_path / "ledger.jsonl"
        append_ledger_entry(ledger, {
            "version": "25.1", "content_digest": "old_format",
        })
        assert last_digest_for_version(ledger, "25.1") == "old_format"


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


# ============================================================
# compute_file_digest — Green / Beige / Red (#281, C-271)
# ============================================================


class TestComputeFileDigestGreen:
    """File digest: determinism, length, equivalence with content digest."""

    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"deterministic input")
        assert compute_file_digest(f) == compute_file_digest(f)

    def test_length_is_16_hex(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        result = compute_file_digest(f)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_equivalence_with_content_digest(self, tmp_path: Path) -> None:
        payload = b"equivalence check payload"
        f = tmp_path / "data.bin"
        f.write_bytes(payload)
        assert compute_file_digest(f) == compute_content_digest(payload)


class TestComputeFileDigestBeige:
    """File digest boundaries: empty file, large file (multi-chunk)."""

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        result = compute_file_digest(f)
        assert len(result) == 16
        assert result == compute_content_digest(b"")

    def test_large_file_multi_chunk(self, tmp_path: Path) -> None:
        payload = b"X" * (65536 * 3 + 17)  # 3 full chunks + partial
        f = tmp_path / "large.bin"
        f.write_bytes(payload)
        assert compute_file_digest(f) == compute_content_digest(payload)


class TestComputeFileDigestRed:
    """File digest adversarial: missing file, directory, binary content."""

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            compute_file_digest(tmp_path / "nonexistent.bin")

    def test_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises((IsADirectoryError, PermissionError)):
            compute_file_digest(tmp_path)

    def test_binary_content(self, tmp_path: Path) -> None:
        payload = bytes(range(256)) * 10
        f = tmp_path / "binary.bin"
        f.write_bytes(payload)
        result = compute_file_digest(f)
        assert len(result) == 16
        assert result == compute_content_digest(payload)


# ---------------------------------------------------------------------------
# Characterization: ledger rotation (C-270, #197)
# ---------------------------------------------------------------------------


class TestRotateLedgerCharacterization:
    """Pin _rotate_ledger behavior to catch audit-trail regressions."""

    _PATCH_THRESHOLD = unittest.mock.patch(
        "datafactory_provenance.digests_and_ledgers._MAX_LEDGER_BYTES", 1024,
    )
    _LINE = '{"op": "test"}\n'

    def _fill_ledger(self, path: Path, nbytes: int) -> str:
        repeats = (nbytes // len(self._LINE)) + 1
        content = self._LINE * repeats
        path.write_text(content)
        return content

    @_PATCH_THRESHOLD
    def test_rotation_creates_dot1_file(self, tmp_path: Path) -> None:
        ledger = tmp_path / "provenance.jsonl"
        original = self._fill_ledger(ledger, 2048)

        _rotate_ledger(ledger)

        dot1 = tmp_path / "provenance.1.jsonl"
        assert dot1.exists()
        assert dot1.read_text() == original

    @_PATCH_THRESHOLD
    def test_rotation_shifts_existing_backups(self, tmp_path: Path) -> None:
        ledger = tmp_path / "provenance.jsonl"
        self._fill_ledger(ledger, 2048)

        content1 = "backup-1\n"
        content2 = "backup-2\n"
        (tmp_path / "provenance.1.jsonl").write_text(content1)
        (tmp_path / "provenance.2.jsonl").write_text(content2)

        _rotate_ledger(ledger)

        assert (tmp_path / "provenance.2.jsonl").read_text() == content1
        assert (tmp_path / "provenance.3.jsonl").read_text() == content2

    @_PATCH_THRESHOLD
    def test_rotation_caps_at_dot10(self, tmp_path: Path) -> None:
        ledger = tmp_path / "provenance.jsonl"
        self._fill_ledger(ledger, 2048)

        content9 = "backup-9\n"
        (tmp_path / "provenance.9.jsonl").write_text(content9)

        _rotate_ledger(ledger)

        assert (tmp_path / "provenance.10.jsonl").read_text() == content9
        assert not (tmp_path / "provenance.11.jsonl").exists()

    @_PATCH_THRESHOLD
    def test_no_rotation_below_threshold(self, tmp_path: Path) -> None:
        ledger = tmp_path / "provenance.jsonl"
        ledger.write_text(self._LINE)

        append_ledger_entry(ledger, {"op": "small"})

        assert not (tmp_path / "provenance.1.jsonl").exists()

    @_PATCH_THRESHOLD
    def test_original_ledger_absent_after_rotation(self, tmp_path: Path) -> None:
        ledger = tmp_path / "provenance.jsonl"
        self._fill_ledger(ledger, 2048)

        _rotate_ledger(ledger)

        assert not ledger.exists(), (
            "original ledger should be renamed to .1, not left in place"
        )
