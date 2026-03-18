"""Shared provenance utilities — content digests and JSONL ledger operations.

Every datafactory_* operation that produces output must record provenance.
This module provides the shared primitives. Each consuming module defines
its own entry structure (dict fields); this module handles serialization,
timestamping, and append.

No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "compute_content_digest",
    "append_ledger_entry",
    "last_digest",
    "last_digest_for_version",
]

logger = logging.getLogger(__name__)


def compute_content_digest(
    data: bytes,
    *,
    algorithm: str = "sha256",
    truncate: int = 16,
) -> str:
    """Compute a content digest from raw bytes.

    Args:
        data: Raw bytes to hash. Caller is responsible for serialization.
        algorithm: Hash algorithm name (passed to hashlib).
        truncate: Number of hex characters to keep. 0 for full digest.

    Returns:
        Hex digest string, truncated to ``truncate`` characters.

    Raises:
        TypeError: If data is not bytes.
    """
    if not isinstance(data, bytes):
        err_msg = f"data must be bytes, got {type(data).__name__}"
        logger.error(err_msg)
        raise TypeError(err_msg)
    if truncate < 0:
        err_msg = f"truncate must be >= 0, got {truncate}"
        logger.error(err_msg)
        raise ValueError(err_msg)
    try:
        h = hashlib.new(algorithm, data)
    except ValueError:
        err_msg = f"Unknown hash algorithm: {algorithm}"
        logger.error(err_msg)
        raise
    hexdigest = h.hexdigest()
    if truncate > 0:
        return hexdigest[:truncate]
    return hexdigest


def append_ledger_entry(
    ledger_path: Path,
    entry: dict[str, Any],
) -> None:
    """Append a provenance entry to a JSONL ledger file.

    Adds an ISO 8601 UTC timestamp to the entry automatically.
    Creates parent directories if they don't exist.
    Writes to a temp file before appending to reduce risk from
    serialization failures. The ledger append itself is not atomic;
    ``_read_ledger_entries`` tolerates malformed trailing lines.

    Args:
        ledger_path: Path to the JSONL ledger file.
        entry: Dict of entry fields. Must be JSON-serializable.

    Raises:
        OSError: If the ledger file cannot be written.
        TypeError: If entry contains non-serializable values.
    """
    stamped = {
        **entry,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    try:
        line = json.dumps(stamped, sort_keys=True) + "\n"
    except TypeError as exc:
        err_msg = f"Entry is not JSON-serializable: {exc}"
        logger.error(err_msg)
        raise

    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=ledger_path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(line)
            tmp_path = Path(tmp.name)

        with open(ledger_path, "a") as ledger:
            ledger.write(tmp_path.read_text())

        tmp_path.unlink()
    except OSError as exc:
        err_msg = f"Failed to write ledger entry to {ledger_path}: {exc}"
        logger.error(err_msg)
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def _read_ledger_entries(ledger_path: Path) -> list[dict[str, Any]]:
    """Read all valid JSONL entries from a ledger file.

    Skips malformed lines (e.g., partial writes from interrupted appends)
    with a warning log.
    """
    if not ledger_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for i, line in enumerate(ledger_path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed ledger line %d in %s", i, ledger_path)
    return entries


def last_digest(
    ledger_path: Path,
    *,
    digest_field: str = "content_digest",
) -> str | None:
    """Return the most recent content digest from a ledger.

    Args:
        ledger_path: Path to the JSONL ledger file.
        digest_field: Name of the digest field in ledger entries.

    Returns:
        The digest string from the last entry, or None if the ledger
        is empty, missing, or the last entry lacks the digest field.
    """
    entries = _read_ledger_entries(ledger_path)
    if not entries:
        return None
    return entries[-1].get(digest_field)


def last_digest_for_version(
    ledger_path: Path,
    version: str,
    *,
    version_field: str = "version",
    digest_field: str = "content_digest",
) -> str | None:
    """Return the most recent content digest for a specific version.

    Scans the ledger in reverse for the first entry matching the
    requested version.

    Args:
        ledger_path: Path to the JSONL ledger file.
        version: Version string to match.
        version_field: Name of the version field in ledger entries.
        digest_field: Name of the digest field in ledger entries.

    Returns:
        The digest string, or None if no matching entry is found.
    """
    entries = _read_ledger_entries(ledger_path)
    for entry in reversed(entries):
        if entry.get(version_field) == version:
            return entry.get(digest_field)
    return None
