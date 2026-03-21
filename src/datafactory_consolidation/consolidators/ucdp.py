"""UCDP consolidator — annual + candidate snapshots into event store.

Reads all Parquet snapshots from the harvester's annual and candidate
directories, tags each with source metadata (_source_type, _source_version,
_ingested_at, _harvest_digest, _harvest_timestamp), and writes a single
consolidated Parquet store.

Vintage-aware (ADR-017): deduplicates on content digest, not just
version number. Two fetches of the same version that return different
data are preserved as distinct vintages.

No survivorship decisions. No temporal distribution. No field dropping.
Those belong to the viewpoint layer (Layer 3).

Implements ADR-013 (consolidation principles), ADR-015 (UCDP specifics),
and ADR-017 (vintage-aware consolidation).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa

from datafactory_consolidation.consolidation_result import (
    ConsolidationResult,
)
from datafactory_consolidation.consolidators import register_consolidator
from datafactory_consolidation.event_store import read_store, write_store
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "ucdp_consolidation"

# ---- Boundary declarations (ADR-009) ----
# What this layer REQUIRES from source Parquet files
REQUIRED_SOURCE_FIELDS: set[str] = {"id"}

# What this layer PRODUCES (metadata columns added during consolidation)
PRODUCED_METADATA: tuple[str, ...] = (
    "_source_type",
    "_source_version",
    "_ingested_at",
    "_harvest_digest",
    "_harvest_timestamp",
)

# Filename patterns for version extraction
_ANNUAL_PATTERN = re.compile(
    r"ucdp_ged_v([\d.]+)_\d+_\d+\.parquet$"
)
_CANDIDATE_PATTERN = re.compile(
    r"ucdp_ged_candidate_([\d.]+)\.parquet$"
)


def _extract_annual_version(path: Path) -> str:
    """Extract version string from annual snapshot filename.

    Example: ucdp_ged_v25.1_1989_2024.parquet → "25.1"

    Raises:
        ValueError: If filename does not match expected pattern.
    """
    match = _ANNUAL_PATTERN.search(path.name)
    if not match:
        err_msg = (
            f"Cannot extract version from annual filename: "
            f"{path.name}. Expected pattern: "
            f"ucdp_ged_v<version>_<start>_<end>.parquet"
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
            f"Cannot extract version from candidate filename: "
            f"{path.name}. Expected pattern: "
            f"ucdp_ged_candidate_<version>.parquet"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    return match.group(1)


def _build_harvest_index(
    ledger_path: Path,
) -> dict[str, tuple[str, str]]:
    """Build version → (digest, timestamp) lookup from harvest ledger.

    Reads the harvest JSONL ledger and returns the latest successful
    entry per version. This connects the consolidator to the
    harvester's provenance chain (ADR-017).

    Returns:
        Dict mapping version string to (content_digest, timestamp).
        Empty dict if ledger doesn't exist.
    """
    if not ledger_path.exists():
        return {}

    index: dict[str, tuple[str, str]] = {}
    for line in ledger_path.read_text().strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        outcome = entry.get("outcome")
        if outcome not in ("success", "unchanged"):
            continue

        version = entry.get("version")
        digest = entry.get("content_digest")
        timestamp = entry.get("timestamp")

        if version and digest and timestamp:
            index[version] = (digest, timestamp)

    return index


def _get_harvest_metadata(
    version: str,
    harvest_index: dict[str, tuple[str, str]],
    fallback_path: Path,
) -> tuple[str, str]:
    """Get harvest digest and timestamp for a source version.

    Looks up the version in the harvest index (from ledger).
    Falls back to computing digest from the file itself if
    the ledger doesn't have an entry (graceful degradation).
    """
    if version in harvest_index:
        return harvest_index[version]

    # Fallback: compute from file
    digest = compute_content_digest(fallback_path.read_bytes())
    timestamp = datetime.fromtimestamp(
        fallback_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    logger.info(
        "No ledger entry for version %s — using file digest %s",
        version, digest,
    )
    return digest, timestamp


def _tag_table(
    table: pa.Table,
    *,
    source_type: str,
    source_version: str,
    ingested_at: str,
    harvest_digest: str,
    harvest_timestamp: str,
) -> pa.Table:
    """Add consolidation metadata columns to a PyArrow table.

    Adds _source_type, _source_version, _ingested_at,
    _harvest_digest, and _harvest_timestamp columns without
    removing any existing columns (lossless per ADR-013).
    Vintage-aware per ADR-017.
    """
    n = table.num_rows
    return (
        table.append_column(
            "_source_type",
            pa.array([source_type] * n, type=pa.string()),
        )
        .append_column(
            "_source_version",
            pa.array([source_version] * n, type=pa.string()),
        )
        .append_column(
            "_ingested_at",
            pa.array([ingested_at] * n, type=pa.string()),
        )
        .append_column(
            "_harvest_digest",
            pa.array([harvest_digest] * n, type=pa.string()),
        )
        .append_column(
            "_harvest_timestamp",
            pa.array([harvest_timestamp] * n, type=pa.string()),
        )
    )


# ---- Config ----


@dataclass(frozen=True)
class UcdpConsolidationConfig:
    """Configuration for UCDP consolidation.

    Paths to harvester output directories, harvest ledgers,
    and consolidated store output. Directory and ledger existence
    is checked at consolidation time, not config time.
    """

    annual_dir: Path = Path("data/ucdp_annual")
    candidate_dir: Path = Path("data/ucdp_candidate")
    annual_ledger_path: Path = Path(
        "provenance/ucdp_annual/ingestion_ledger.jsonl"
    )
    candidate_ledger_path: Path = Path(
        "provenance/ucdp_candidate/ingestion_ledger.jsonl"
    )
    output_path: Path = Path(
        "data/consolidated/ucdp_store.parquet"
    )
    ledger_path: Path = Path(
        "provenance/consolidation/ucdp_ledger.jsonl"
    )


# ---- Consolidation ----


def consolidate_ucdp(
    config: UcdpConsolidationConfig | None = None,
) -> ConsolidationResult:
    """Consolidate UCDP annual + candidate snapshots.

    Vintage-aware (ADR-017): tags each record with the harvest
    content digest and timestamp. Deduplicates on
    (id, _source_type, _source_version, _harvest_digest) so
    identical re-fetches are skipped but updated versions are
    preserved as distinct vintages.

    Args:
        config: Consolidation configuration. Uses defaults if None.

    Returns:
        ConsolidationResult with record counts and output digest.

    Raises:
        FileNotFoundError: If no source Parquet files are found.
        ValueError: If a source filename doesn't match patterns.
    """
    if config is None:
        config = UcdpConsolidationConfig()

    ingested_at = datetime.now(tz=timezone.utc).isoformat()

    # Build harvest indexes from ledgers
    annual_index = _build_harvest_index(config.annual_ledger_path)
    candidate_index = _build_harvest_index(
        config.candidate_ledger_path
    )

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
        h_digest, h_timestamp = _get_harvest_metadata(
            version, annual_index, path
        )
        table = pa.parquet.read_table(path)
        tagged = _tag_table(
            table,
            source_type="annual",
            source_version=version,
            ingested_at=ingested_at,
            harvest_digest=h_digest,
            harvest_timestamp=h_timestamp,
        )
        tagged_tables.append(tagged)
        source_manifest.append({
            "path": str(path),
            "source_type": "annual",
            "version": version,
            "n_records": table.num_rows,
            "harvest_digest": h_digest,
            "harvest_timestamp": h_timestamp,
        })
        logger.info(
            "Read annual: %s (v%s, %d records, digest %s)",
            path.name, version, table.num_rows, h_digest,
        )

    for path in candidate_files:
        version = _extract_candidate_version(path)
        h_digest, h_timestamp = _get_harvest_metadata(
            version, candidate_index, path
        )
        table = pa.parquet.read_table(path)
        tagged = _tag_table(
            table,
            source_type="candidate",
            source_version=version,
            ingested_at=ingested_at,
            harvest_digest=h_digest,
            harvest_timestamp=h_timestamp,
        )
        tagged_tables.append(tagged)
        source_manifest.append({
            "path": str(path),
            "source_type": "candidate",
            "version": version,
            "n_records": table.num_rows,
            "harvest_digest": h_digest,
            "harvest_timestamp": h_timestamp,
        })
        logger.info(
            "Read candidate: %s (v%s, %d records, digest %s)",
            path.name, version, table.num_rows, h_digest,
        )

    # Concatenate new records
    new_table = pa.concat_tables(
        tagged_tables, promote_options="default"
    )
    n_new_raw = new_table.num_rows

    # Read existing store and deduplicate (vintage-aware, ADR-017)
    existing = read_store(config.output_path)
    if existing is not None:
        n_before = existing.num_rows

        # Dedup key includes harvest_digest (ADR-017)
        existing_keys = set(
            zip(
                existing.column("id").to_pylist(),
                existing.column("_source_type").to_pylist(),
                existing.column("_source_version").to_pylist(),
                existing.column("_harvest_digest").to_pylist(),
                strict=True,
            )
        )

        new_ids = new_table.column("id").to_pylist()
        new_types = new_table.column("_source_type").to_pylist()
        new_vers = new_table.column("_source_version").to_pylist()
        new_digests = new_table.column(
            "_harvest_digest"
        ).to_pylist()

        keep_mask = [
            (eid, etype, ever, edigest) not in existing_keys
            for eid, etype, ever, edigest in zip(
                new_ids, new_types, new_vers, new_digests,
                strict=True,
            )
        ]
        new_filtered = new_table.filter(keep_mask)
        n_new = new_filtered.num_rows

        if n_new > 0:
            combined = pa.concat_tables(
                [existing, new_filtered],
                promote_options="default",
            )
        else:
            combined = existing

        logger.info(
            "Dedup: %d raw, %d already in store, %d new added",
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
        "Consolidation complete: %d sources, %d new, %d total",
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
