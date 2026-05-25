"""ACLED consolidator — raw harvester snapshots into event store.

Reads ACLED Parquet snapshots from the harvester output directory,
tags each with source metadata (_source_type, _ingested_at,
_harvest_digest, _harvest_timestamp), and writes a single
consolidated Parquet store.

Simpler than the UCDP consolidator: ACLED has one source type
(no annual/candidate/dot9 split) and no vintage complexity.

Implements ADR-013 (consolidation principles).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from datafactory_consolidation.consolidation_result import (
    ConsolidationResult,
)
from datafactory_consolidation.consolidators import register_consolidator
from datafactory_consolidation.event_store import read_store, write_store
from datafactory_consolidation.tagging import tag_table
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "acled_consolidation"

REQUIRED_SOURCE_FIELDS: set[str] = {"event_id_cnty"}

PRODUCED_METADATA: tuple[str, ...] = (
    "_source_type",
    "_source_version",
    "_ingested_at",
    "_harvest_digest",
    "_harvest_timestamp",
)

_SNAPSHOT_PATTERN = re.compile(
    r"acled_(\d+)_(\d+)\.parquet$"
)


def _extract_version(path: Path) -> str:
    """Extract version string from ACLED snapshot filename.

    Example: acled_1997_2025.parquet → "1997_2025"
    """
    match = _SNAPSHOT_PATTERN.search(path.name)
    if not match:
        err_msg = (
            f"Cannot extract version from ACLED filename: "
            f"{path.name}. Expected: acled_<start>_<end>.parquet"
        )
        logger.error(err_msg)
        raise ValueError(err_msg)
    return f"{match.group(1)}_{match.group(2)}"


def _build_harvest_index(
    ledger_path: Path,
) -> dict[str, tuple[str, str]]:
    """Build (digest, timestamp) lookup from harvest ledger."""
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

        if entry.get("outcome") not in ("success", "unchanged"):
            continue

        digest = entry.get("content_digest")
        timestamp = entry.get("timestamp")
        start = entry.get("start_year")
        end = entry.get("end_year")

        if digest and timestamp and start is not None and end is not None:
            version_key = f"{start}_{end}"
            index[version_key] = (digest, timestamp)

    return index


def _get_harvest_metadata(
    version: str,
    harvest_index: dict[str, tuple[str, str]],
    fallback_path: Path,
) -> tuple[str, str]:
    """Get harvest digest and timestamp for a version."""
    if version in harvest_index:
        return harvest_index[version]

    digest = compute_content_digest(fallback_path.read_bytes())
    timestamp = datetime.fromtimestamp(
        fallback_path.stat().st_mtime, tz=UTC
    ).isoformat()
    logger.info(
        "No ledger entry for version %s — using file digest %s",
        version,
        digest,
    )
    return digest, timestamp


@dataclass(frozen=True)
class AcledConsolidationConfig:
    """Configuration for ACLED consolidation."""

    source_dir: Path = Path("data/raw/acled")
    harvest_ledger_path: Path = Path(
        "provenance/acled/ingestion_ledger.jsonl"
    )
    output_path: Path = Path(
        "data/consolidated/acled/acled_store.parquet"
    )
    ledger_path: Path = Path(
        "provenance/consolidation/acled_ledger.jsonl"
    )


def consolidate_acled(
    config: AcledConsolidationConfig | None = None,
) -> ConsolidationResult:
    """Consolidate ACLED harvester snapshots into a single store.

    Tags each record with source metadata. Deduplicates on
    (event_id_cnty, _harvest_digest) so identical re-fetches
    are skipped but updated snapshots are preserved.

    Args:
        config: Consolidation configuration. Uses defaults if None.

    Returns:
        ConsolidationResult with record counts and output digest.

    Raises:
        FileNotFoundError: If no source Parquet files are found.
    """
    if config is None:
        config = AcledConsolidationConfig()

    ingested_at = datetime.now(tz=UTC).isoformat()

    harvest_index = _build_harvest_index(
        config.harvest_ledger_path
    )

    source_files = (
        sorted(config.source_dir.glob("*.parquet"))
        if config.source_dir.exists()
        else []
    )

    if not source_files:
        err_msg = (
            f"No ACLED Parquet files found in {config.source_dir}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    tagged_tables: list[pa.Table] = []
    source_manifest: list[dict] = []

    for path in source_files:
        version = _extract_version(path)
        h_digest, h_timestamp = _get_harvest_metadata(
            version, harvest_index, path
        )
        table = pq.read_table(path)

        missing = REQUIRED_SOURCE_FIELDS - set(table.column_names)
        if missing:
            err_msg = (
                f"{path.name}: missing required fields "
                f"{sorted(missing)}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)

        tagged = tag_table(
            table,
            source_type="acled",
            source_version=version,
            ingested_at=ingested_at,
            harvest_digest=h_digest,
            harvest_timestamp=h_timestamp,
        )
        tagged_tables.append(tagged)

        dates = (
            [
                d
                for d in table.column("event_date").to_pylist()
                if d
            ]
            if "event_date" in table.column_names
            else []
        )
        source_manifest.append({
            "path": str(path),
            "source_type": "acled",
            "version": version,
            "n_records": table.num_rows,
            "min_date": min(dates) if dates else None,
            "max_date": max(dates) if dates else None,
            "harvest_digest": h_digest,
            "harvest_timestamp": h_timestamp,
        })
        logger.info(
            "Read ACLED: %s (v%s, %d records, digest %s)",
            path.name,
            version,
            table.num_rows,
            h_digest,
        )

    new_table = pa.concat_tables(
        tagged_tables, promote_options="default"
    )
    n_new_raw = new_table.num_rows

    existing = read_store(config.output_path)
    if existing is not None:
        n_before = existing.num_rows

        existing_keys = set(
            zip(
                existing.column("event_id_cnty").to_pylist(),
                existing.column("_harvest_digest").to_pylist(),
                strict=True,
            )
        )

        new_ids = new_table.column("event_id_cnty").to_pylist()
        new_digests = new_table.column(
            "_harvest_digest"
        ).to_pylist()

        keep_mask = [
            (eid, edigest) not in existing_keys
            for eid, edigest in zip(
                new_ids, new_digests, strict=True
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
            n_new_raw,
            n_new_raw - n_new,
            n_new,
        )
    else:
        combined = new_table
        n_new = n_new_raw
        n_before = 0

    output_digest = write_store(combined, config.output_path)

    n_total = combined.num_rows

    schema_cols = sorted(combined.column_names)
    schema_fingerprint = hashlib.sha256(
        ",".join(schema_cols).encode()
    ).hexdigest()[:16]

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "n_sources": len(source_manifest),
        "n_records_before": n_before,
        "n_records_new": n_new,
        "n_records_total": n_total,
        "source_manifest": source_manifest,
        "output_path": str(config.output_path),
        "output_digest": output_digest,
        "schema_fingerprint": schema_fingerprint,
        "schema_columns": schema_cols,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "ACLED consolidation complete: %d sources, %d new, %d total",
        len(source_manifest),
        n_new,
        n_total,
    )

    return ConsolidationResult(
        output_path=config.output_path,
        n_sources=len(source_manifest),
        n_records_total=n_total,
        n_records_new=n_new,
        output_digest=output_digest,
    )


register_consolidator("acled", consolidate_acled)
