"""Provenance tracking — content digests and JSONL ledger operations.

Every datafactory_* operation that produces output must record provenance.
This module provides the shared primitives. Each consuming module defines
its own entry structure (dict fields); this module handles serialization,
timestamping, and append.

No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "compute_content_digest",
    "compute_file_digest",
    "append_ledger_entry",
    "file_lock",
    "last_digest",
    "last_digest_for_version",
]

logger = logging.getLogger(__name__)

# ---- Provenance infrastructure constants ----
# These define the ledger schema and digest scheme used across all modules.
# Change here = change everywhere. Bump LEDGER_VERSION when ledger schema changes.

LEDGER_VERSION: int = 1
DIGEST_ALGORITHM: str = "sha256"
DIGEST_TRUNCATE: int = 16
DIGEST_SCHEME: str = f"{DIGEST_ALGORITHM}_{DIGEST_TRUNCATE}"

# I/O buffer sizes — tune for throughput vs. memory tradeoff.
_FILE_CHUNK_SIZE: int = 65536  # 64 KB — file digest streaming reads
_LEDGER_READ_CHUNK: int = 4096  # 4 KB — reverse-read for last_digest


def compute_content_digest(
    data: bytes,
    *,
    algorithm: str = DIGEST_ALGORITHM,
    truncate: int = DIGEST_TRUNCATE,
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


def compute_file_digest(
    path: Path,
    *,
    algorithm: str = DIGEST_ALGORITHM,
    truncate: int = DIGEST_TRUNCATE,
    chunk_size: int = _FILE_CHUNK_SIZE,
) -> str:
    """Compute a content digest from a file without loading it all.

    Reads the file in chunks to avoid doubling memory usage for
    large files (e.g., 50MB+ Parquet stores).

    Args:
        path: Path to the file to hash.
        algorithm: Hash algorithm name (passed to hashlib).
        truncate: Number of hex characters to keep. 0 for full.
        chunk_size: Bytes to read per iteration (default 64KB).

    Returns:
        Hex digest string, truncated to ``truncate`` characters.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    hexdigest = h.hexdigest()
    return hexdigest[:truncate] if truncate > 0 else hexdigest


_STALE_LOCK_SECONDS: int = 300  # 5 minutes


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Advisory file lock via fcntl.flock.

    Creates a .lock file alongside the target path and holds an
    exclusive lock for the duration of the context. Other processes
    using file_lock on the same path will block until the lock is
    released.

    If the lock file is older than 5 minutes (indicating a crashed
    process), it is removed with a warning before acquiring.

    Args:
        path: Path to the file being protected.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # Check for stale lock file from a crashed process
    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
            if age > _STALE_LOCK_SECONDS:
                logger.warning(
                    "Removing stale lock file %s (age: %.0fs)",
                    lock_path,
                    age,
                )
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass  # Race with another process; proceed to flock

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


_MAX_LEDGER_BYTES: int = 10 * 1024 * 1024  # 10 MB


def _rotate_ledger(ledger_path: Path) -> None:
    """Rotate ledger: current → .1, .1 → .2, etc. (max 9)."""
    stem = ledger_path.stem
    parent = ledger_path.parent
    suffix = ledger_path.suffix
    for i in range(9, 0, -1):
        old = parent / f"{stem}.{i}{suffix}"
        new_path = parent / f"{stem}.{i + 1}{suffix}"
        if old.exists():
            old.rename(new_path)
    ledger_path.rename(parent / f"{stem}.1{suffix}")
    logger.info("Rotated ledger %s (exceeded %d bytes)", ledger_path, _MAX_LEDGER_BYTES)


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

        with file_lock(ledger_path):
            with open(ledger_path, "a") as ledger:
                ledger.write(tmp_path.read_text())

            # Rotate if ledger exceeds size threshold
            if (
                ledger_path.exists()
                and ledger_path.stat().st_size > _MAX_LEDGER_BYTES
            ):
                _rotate_ledger(ledger_path)

        tmp_path.unlink()
    except OSError as exc:
        err_msg = (
            f"Failed to write ledger entry to {ledger_path}: {exc}"
        )
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


def _read_last_line(path: Path) -> str | None:
    """Read the last non-empty line from a file without loading it all.

    Seeks to the end and reads backwards in 4KB chunks until a
    complete non-empty line is found. O(1) for typical JSONL files.
    """
    with open(path, "rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        if pos == 0:
            return None
        buf = b""
        while pos > 0:
            read_size = min(_LEDGER_READ_CHUNK, pos)
            pos -= read_size
            f.seek(pos)
            buf = f.read(read_size) + buf
            lines = buf.split(b"\n")
            for line in reversed(lines):
                stripped = line.strip()
                if stripped:
                    return stripped.decode("utf-8")
    return None


def last_digest(
    ledger_path: Path,
    *,
    digest_field: str = "content_digest",
) -> str | None:
    """Return the most recent content digest from a ledger.

    Uses reverse-read for O(1) performance on the common case.
    Falls back to full read if the last line is malformed.

    Args:
        ledger_path: Path to the JSONL ledger file.
        digest_field: Name of the digest field in ledger entries.

    Returns:
        The digest string from the last entry, or None if the ledger
        is empty, missing, or the last entry lacks the digest field.
    """
    if not ledger_path.exists():
        return None
    last_line = _read_last_line(ledger_path)
    if last_line is None:
        return None
    try:
        entry = json.loads(last_line)
        result: str | None = entry.get(digest_field)
        return result
    except json.JSONDecodeError:
        # Fall back to full read if last line is malformed
        entries = _read_ledger_entries(ledger_path)
        result = entries[-1].get(digest_field) if entries else None
        return result


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
