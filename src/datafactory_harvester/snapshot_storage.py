"""Source-agnostic event snapshot storage.

Handles Parquet persistence and archiving of raw event snapshots.
No knowledge of specific data sources.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

_PARQUET_COMPRESSION: str = "snappy"

_ARCHIVE_DIRNAME: str = "archive"


def save_event_snapshot(
    events: list[dict],
    path: Path,
) -> None:
    """Persist all raw event fields as a Parquet file.

    Preserves every field from the source — enables event-level
    revision detection and arbitrary re-analysis.

    Atomic (C-233): writes to a temp file in the same directory,
    then renames. A crash mid-write can never leave a truncated
    Parquet at the canonical path — the raw layer is the recovery
    layer, so its snapshots must be uncorruptible.

    Args:
        events: List of raw event dicts.
        path: Output Parquet file path.

    Raises:
        ValueError: If events list is empty.
    """
    if not events:
        err_msg = "No events to save as snapshot"
        logger.error(err_msg)
        raise ValueError(err_msg)

    path.parent.mkdir(parents=True, exist_ok=True)

    # Build column arrays from event dicts
    all_fields = sorted({k for ev in events for k in ev})

    columns: dict[str, list] = {f: [] for f in all_fields}
    for ev in events:
        for f in all_fields:
            columns[f].append(ev.get(f))

    pa_columns: dict[str, pa.Array] = {}
    for name, values in columns.items():
        pa_columns[name] = pa.array(values, from_pandas=True)

    table = pa.table(pa_columns)

    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.close(fd)
        tmp_path = Path(tmp)
        pq.write_table(
            table, tmp_path, compression=_PARQUET_COMPRESSION,
        )
        tmp_path.rename(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

    logger.info(
        "Saved event snapshot to %s (%d events, %d fields)",
        path,
        len(events),
        len(all_fields),
    )


def archive_snapshot(path: Path) -> Path | None:
    """Move an existing snapshot to a dated archive.

    Archives land in an ``archive/`` subdirectory (C-234) so
    consolidation source-file globs structurally cannot pick them
    up — same-directory archives were excluded only by filename
    convention, and tripped spurious year-overlap warnings.

    Uses the current UTC timestamp for the archive suffix.
    Returns the archive path, or None if the source doesn't exist.

    Args:
        path: Path to the existing snapshot.

    Returns:
        Path to the archive, or None if source doesn't exist.
    """
    if not path.exists():
        return None

    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    archive_dir = path.parent / _ARCHIVE_DIRNAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{path.stem}_{stamp}{path.suffix}"
    path.rename(archive_path)

    logger.info(
        "Archived snapshot: %s -> %s/%s",
        path.name, _ARCHIVE_DIRNAME, archive_path.name,
    )
    return archive_path
