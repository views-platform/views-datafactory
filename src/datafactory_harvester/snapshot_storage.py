"""Source-agnostic event snapshot storage.

Handles Parquet persistence and archiving of raw event snapshots.
No knowledge of specific data sources.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

_PARQUET_COMPRESSION: str = "snappy"


def save_event_snapshot(
    events: list[dict],
    path: Path,
) -> None:
    """Persist all raw event fields as a Parquet file.

    Preserves every field from the source — enables event-level
    revision detection and arbitrary re-analysis.

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
    pq.write_table(table, path, compression=_PARQUET_COMPRESSION)

    logger.info(
        "Saved event snapshot to %s (%d events, %d fields)",
        path,
        len(events),
        len(all_fields),
    )


def archive_snapshot(path: Path) -> Path | None:
    """Rename an existing snapshot to a dated archive.

    Uses the current UTC timestamp for the archive suffix.
    Returns the archive path, or None if the source doesn't exist.

    Args:
        path: Path to the existing snapshot.

    Returns:
        Path to the archive, or None if source doesn't exist.
    """
    if not path.exists():
        return None

    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_path = path.with_stem(f"{path.stem}_{stamp}")
    path.rename(archive_path)

    logger.info("Archived snapshot: %s -> %s", path.name, archive_path.name)
    return archive_path
