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


def _check_year_overlap(
    source_files: list[Path],
) -> list[str]:
    """Detect overlapping year ranges among source files."""
    ranges = []
    for p in source_files:
        m = _SNAPSHOT_PATTERN.search(p.name)
        if m:
            ranges.append(
                (int(m.group(1)), int(m.group(2)), p.name)
            )
    warnings = []
    for i, (s1, e1, n1) in enumerate(ranges):
        for s2, e2, n2 in ranges[i + 1 :]:
            if s1 <= e2 and s2 <= e1:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                warnings.append(
                    f"Overlapping year ranges: {n1} "
                    f"({s1}-{e1}) and {n2} ({s2}-{e2}), "
                    f"overlap: {overlap_start}-{overlap_end}"
                )
    return warnings


def _dedup_by_event_id(
    table: pa.Table,
) -> tuple[pa.Table, int]:
    """Deduplicate table on event_id_cnty, keeping latest harvest.

    When the same event appears in multiple source files, keep the
    row with the latest _harvest_timestamp. ACLED has no vintage
    semantics — only the most recent version of each event matters.

    Returns:
        (deduped_table, n_removed)
    """
    eids = table.column("event_id_cnty").to_pylist()
    if len(eids) == len(set(eids)):
        return table, 0

    timestamps = table.column(
        "_harvest_timestamp"
    ).to_pylist()
    seen: dict[str, int] = {}
    for i, (eid, ts) in enumerate(
        zip(eids, timestamps, strict=True)
    ):
        if eid not in seen or ts > timestamps[seen[eid]]:
            seen[eid] = i

    keep_indices = sorted(seen.values())
    n_removed = len(eids) - len(keep_indices)
    logger.warning(
        "Cross-file dedup: %d duplicate events removed, "
        "%d unique events retained",
        n_removed,
        len(keep_indices),
    )
    return table.take(keep_indices), n_removed


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
    event_id_cnty alone — ACLED has no vintage semantics, so
    only the latest version of each event is kept.

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
        sorted(
            p for p in config.source_dir.glob("*.parquet")
            if _SNAPSHOT_PATTERN.search(p.name)
        )
        if config.source_dir.exists()
        else []
    )

    if not source_files:
        err_msg = (
            f"No ACLED Parquet files found in {config.source_dir}"
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    for warning in _check_year_overlap(source_files):
        logger.warning(warning)

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
    n_concat = new_table.num_rows
    new_table, n_dedup_removed = _dedup_by_event_id(new_table)
    n_new_raw = new_table.num_rows

    if n_concat != n_new_raw + n_dedup_removed:
        raise RuntimeError(
            f"Count conservation violation at cross-file dedup: "
            f"concat ({n_concat}) != "
            f"deduped ({n_new_raw}) + removed ({n_dedup_removed})"
        )

    existing = read_store(config.output_path)
    n_replaced = 0
    if existing is not None:
        n_before = existing.num_rows

        existing_eids = existing.column(
            "event_id_cnty"
        ).to_pylist()
        existing_ts = existing.column(
            "_harvest_timestamp"
        ).to_pylist()
        existing_lookup: dict[str, tuple[int, str]] = {}
        for i, (eid, ts) in enumerate(
            zip(existing_eids, existing_ts, strict=True)
        ):
            existing_lookup[eid] = (i, ts)

        new_ids = new_table.column("event_id_cnty").to_pylist()
        new_ts = new_table.column(
            "_harvest_timestamp"
        ).to_pylist()

        new_keep_indices: list[int] = []
        replace_eids: set[str] = set()
        for j, (eid, ts) in enumerate(
            zip(new_ids, new_ts, strict=True)
        ):
            if eid not in existing_lookup:
                new_keep_indices.append(j)
            elif ts > existing_lookup[eid][1]:
                new_keep_indices.append(j)
                replace_eids.add(eid)

        n_replaced = len(replace_eids)

        if replace_eids:
            keep_existing_mask = [
                eid not in replace_eids for eid in existing_eids
            ]
            existing = existing.filter(keep_existing_mask)

        n_new = len(new_keep_indices) - n_replaced

        if new_keep_indices:
            new_filtered = new_table.take(new_keep_indices)
            combined = pa.concat_tables(
                [existing, new_filtered],
                promote_options="default",
            )
        else:
            combined = existing

        logger.info(
            "Dedup: %d raw, %d already in store, "
            "%d replaced, %d new added",
            n_new_raw,
            n_new_raw - len(new_keep_indices),
            n_replaced,
            n_new,
        )
        if n_replaced > 0:
            logger.warning(
                "Cross-run replacement: %d events updated "
                "to newer version",
                n_replaced,
            )
        n_kept_from_new = len(new_keep_indices)
    else:
        combined = new_table
        n_new = n_new_raw
        n_before = 0
        n_kept_from_new = n_new_raw

    expected_total = (n_before - n_replaced) + n_kept_from_new
    if combined.num_rows != expected_total:
        raise RuntimeError(
            f"Count conservation violation at store merge: "
            f"expected ({n_before} - {n_replaced}) + "
            f"{n_kept_from_new} = {expected_total}, "
            f"got {combined.num_rows}"
        )

    output_digest = write_store(combined, config.output_path)

    n_total = combined.num_rows

    schema_cols = sorted(combined.column_names)
    schema_fingerprint = hashlib.sha256(
        ",".join(schema_cols).encode()
    ).hexdigest()[:16]

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "n_sources": len(source_manifest),
        "n_records_concat": n_concat,
        "n_dedup_removed": n_dedup_removed,
        "n_records_before": n_before,
        "n_records_dedup_filtered": n_new_raw - n_new - n_replaced,
        "n_records_replaced": n_replaced,
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
        n_records_before=n_before,
        output_digest=output_digest,
    )


register_consolidator("acled", consolidate_acled)
