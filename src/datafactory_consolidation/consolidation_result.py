"""Structured result from a consolidation operation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConsolidationResult:
    """Immutable result of a consolidation run.

    Attributes:
        output_path: Path to the consolidated Parquet store.
        n_sources: Number of source files consolidated.
        n_records_total: Total records in the store after consolidation.
        n_records_new: Records added in this run (0 if idempotent re-run).
        output_digest: SHA-256 content digest of the output file.
        n_records_before: Records in the store before this run.
    """

    output_path: Path
    n_sources: int
    n_records_total: int
    n_records_new: int
    output_digest: str
    n_records_before: int
