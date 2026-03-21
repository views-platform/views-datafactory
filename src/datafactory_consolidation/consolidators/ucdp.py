"""UCDP consolidator — annual + candidate snapshots into event store.

Reads all Parquet snapshots from the harvester's annual and candidate
directories, tags each with source metadata (_source_type, _source_version,
_ingested_at), and writes a single consolidated Parquet store.

No survivorship decisions. No temporal distribution. No field dropping.
Those belong to the viewpoint layer (Layer 3).

Implements ADR-013 (consolidation principles) and ADR-015 (UCDP specifics).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa

from datafactory_consolidation.consolidation_result import ConsolidationResult
from datafactory_consolidation.consolidators import register_consolidator
from datafactory_consolidation.store_io import read_store, write_store
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
)

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_consolidation"

# Filename patterns for version extraction
_ANNUAL_PATTERN = re.compile(r"ucdp_ged_v([\d.]+)_\d+_\d+\.parquet$")
_CANDIDATE_PATTERN = re.compile(r"ucdp_ged_candidate_([\d.]+)\.parquet$")


def _extract_annual_version(path: Path) -> str:
    """Extract version string from annual snapshot filename.

    Example: ucdp_ged_v25.1_1989_2024.parquet → "25.1"

    Raises:
        ValueError: If filename does not match expected pattern.
    """
    match = _ANNUAL_PATTERN.search(path.name)
    if not match:
        err_msg = (
            f"Cannot extract version from annual filename: {path.name}. "
            f"Expected pattern: ucdp_ged_v<version>_<start>_<end>.parquet"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    return match.group(1)


def _extract_candidate_version(path: Path) -> str:
    """Extract version string from candidate snapshot filename.

    Example: ucdp_ged_candidate_25.0.3.parquet → "25.0.3"

    Raises:
        ValueError: If filename does not match expected pattern.
    """
    match = _CANDIDATE_PATTERN.search(path.name)
    if not match:
        err_msg = (
            f"Cannot extract version from candidate filename: {path.name}. "
            f"Expected pattern: ucdp_ged_candidate_<version>.parquet"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    return match.group(1)


def _tag_table(
    table: pa.Table,
    *,
    source_type: str,
    source_version: str,
    ingested_at: str,
) -> pa.Table:
    """Add consolidation metadata columns to a PyArrow table.

    Adds _source_type, _source_version, and _ingested_at columns
    without removing any existing columns (lossless per ADR-013).
    """
    n = table.num_rows
    return table.append_column(
        "_source_type", pa.array([source_type] * n, type=pa.string())
    ).append_column(
        "_source_version", pa.array([source_version] * n, type=pa.string())
    ).append_column(
        "_ingested_at", pa.array([ingested_at] * n, type=pa.string())
    )


# ---- Config ----


@dataclass(frozen=True)
class UcdpConsolidationConfig:
    """Configuration for UCDP consolidation.

    Paths to harvester output directories and consolidated store output.
    Directory existence is checked at consolidation time, not config time.
    """

    annual_dir: Path = Path("data/ucdp_annual")
    candidate_dir: Path = Path("data/ucdp_candidate")
    output_path: Path = Path("data/consolidated/ucdp_store.parquet")
    ledger_path: Path = Path(
        "provenance/consolidation/ucdp_ledger.jsonl"
    )


# ---- Consolidation ----


def consolidate_ucdp(
    config: UcdpConsolidationConfig | None = None,
) -> ConsolidationResult:
    """Consolidate UCDP annual + candidate snapshots into a lossless event store.

    Reads all Parquet files from the annual and candidate directories,
    tags each with source metadata, deduplicates against the existing
    store (if any), and writes the consolidated output.

    Args:
        config: Consolidation configuration. Uses defaults if None.

    Returns:
        ConsolidationResult with record counts and output digest.

    Raises:
        FileNotFoundError: If no source Parquet files are found.
        ValueError: If a source filename doesn't match expected patterns.
    """
    if config is None:
        config = UcdpConsolidationConfig()

    ingested_at = datetime.now(tz=timezone.utc).isoformat()

    # Discover source files
    annual_files = (
        sorted(config.annual_dir.glob("*.parquet"))
        if config.annual_dir.exists()
        else []
    )
    candidate_files = (
        sorted(config.candidate_dir.glob("*.parquet"))
        if config.candidate_dir.exists()
        else []
    )

    if not annual_files and not candidate_files:
        err_msg = (
            f"No source Parquet files found in "
            f"{config.annual_dir} or {config.candidate_dir}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # Read and tag each source
    tagged_tables: list[pa.Table] = []
    source_manifest: list[dict] = []

    for path in annual_files:
        version = _extract_annual_version(path)
        table = pa.parquet.read_table(path)
        tagged = _tag_table(
            table,
            source_type="annual",
            source_version=version,
            ingested_at=ingested_at,
        )
        tagged_tables.append(tagged)
        source_manifest.append({
            "path": str(path),
            "source_type": "annual",
            "version": version,
            "n_records": table.num_rows,
        })
        logger.info(
            "Read annual snapshot: %s (v%s, %d records)",
            path.name, version, table.num_rows,
        )

    for path in candidate_files:
        version = _extract_candidate_version(path)
        table = pa.parquet.read_table(path)
        tagged = _tag_table(
            table,
            source_type="candidate",
            source_version=version,
            ingested_at=ingested_at,
        )
        tagged_tables.append(tagged)
        source_manifest.append({
            "path": str(path),
            "source_type": "candidate",
            "version": version,
            "n_records": table.num_rows,
        })
        logger.info(
            "Read candidate snapshot: %s (v%s, %d records)",
            path.name, version, table.num_rows,
        )

    # Concatenate new records
    new_table = pa.concat_tables(tagged_tables, promote_options="default")
    n_new_raw = new_table.num_rows

    # Read existing store and deduplicate
    existing = read_store(config.output_path)
    if existing is not None:
        n_before = existing.num_rows

        # Build dedup key from existing: (id, _source_type, _source_version)
        existing_keys = set(
            zip(
                existing.column("id").to_pylist(),
                existing.column("_source_type").to_pylist(),
                existing.column("_source_version").to_pylist(),
                strict=True,
            )
        )

        # Filter new records to only those not already in store
        new_ids = new_table.column("id").to_pylist()
        new_types = new_table.column("_source_type").to_pylist()
        new_versions = new_table.column("_source_version").to_pylist()

        keep_mask = [
            (eid, etype, ever) not in existing_keys
            for eid, etype, ever in zip(
                new_ids, new_types, new_versions, strict=True
            )
        ]
        new_filtered = new_table.filter(keep_mask)
        n_new = new_filtered.num_rows

        if n_new > 0:
            combined = pa.concat_tables(
                [existing, new_filtered], promote_options="default"
            )
        else:
            combined = existing

        logger.info(
            "Dedup: %d new raw, %d already in store, %d new records added",
            n_new_raw, n_new_raw - n_new, n_new,
        )
    else:
        combined = new_table
        n_new = n_new_raw
        n_before = 0

    # Write consolidated store
    output_digest = write_store(combined, config.output_path)

    n_total = combined.num_rows

    # Record provenance
    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "n_sources": len(source_manifest),
        "n_records_before": n_before,
        "n_records_new": n_new,
        "n_records_total": n_total,
        "source_manifest": source_manifest,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Consolidation complete: %d sources, %d new records, %d total",
        len(source_manifest), n_new, n_total,
    )

    return ConsolidationResult(
        output_path=config.output_path,
        n_sources=len(source_manifest),
        n_records_total=n_total,
        n_records_new=n_new,
        output_digest=output_digest,
    )


# Auto-register
register_consolidator("ucdp", consolidate_ucdp)
