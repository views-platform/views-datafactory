"""Structured result from a viewpoint build operation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ViewpointResult:
    """Immutable result of a viewpoint build.

    Attributes:
        output_path: Path to the viewpoint Parquet.
        n_events_input: Events in the consolidated store.
        n_events_output: Rows in the viewpoint output (may differ
            due to survivorship dedup and summary event expansion).
        n_summary_expanded: Summary events that were expanded.
        n_spatially_distributed: Events spatially distributed
            across polygon cells (ADR-049).
        n_filtered: Events removed by filters.
        output_digest: SHA-256 content digest of the output file.
        version: Viewpoint version tag from config.
    """

    output_path: Path
    n_events_input: int
    n_events_output: int
    n_summary_expanded: int
    n_spatially_distributed: int
    n_filtered: int
    output_digest: str
    version: str
