"""Source-agnostic consolidated store I/O.

Reads and writes consolidated Parquet stores. The store is a single
Parquet file — simple, queryable, and sufficient at current scale.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_provenance import compute_file_digest, file_lock

logger = logging.getLogger(__name__)

_PARQUET_COMPRESSION: str = "snappy"


def read_store(path: Path) -> pa.Table | None:
    """Read an existing consolidated store.

    Returns:
        A PyArrow Table, or None if the file does not exist.
    """
    if not path.exists():
        return None
    return pq.read_table(path)


def write_store(table: pa.Table, path: Path) -> str:
    """Write a consolidated store to disk.

    Creates parent directories if needed. Computes and returns the
    content digest of the written file.

    Returns:
        Content digest (SHA-256, truncated to 16 hex chars).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        # Atomic write: temp file then rename to prevent corruption on crash
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, suffix=".tmp",
        )
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
    digest = compute_file_digest(path)
    logger.info(
        "Wrote consolidated store: %s (%d rows, digest: %s)",
        path,
        table.num_rows,
        digest,
    )
    return digest
