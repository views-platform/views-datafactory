"""PRIO-GRID shapefile harvester.

Downloads the reference shapefile ZIP from PRIO and stores it locally
with full provenance. Does NOT parse the shapefile -- reading is deferred
to a pluggable ReferenceGeometryReader (see validation.py).

The shapefile is a one-time critical artifact. If the origin URL goes
dead, the local copy is the fallback.

Unlike the metric lab version, this module does not read paths or URLs
from GridConfig. All I/O parameters are injected at call sites.
Provenance uses datafactory_core utilities (not private reimplementations).
"""

import io
import logging
import zipfile
from pathlib import Path

import requests

from datafactory_core import append_ledger_entry, compute_content_digest, last_digest

logger = logging.getLogger(__name__)

# Default PRIO-GRID shapefile URL
DEFAULT_SHAPEFILE_URL = (
    "http://file.prio.no/ReplicationData/PRIO-GRID/"
    "priogrid_shapefiles.zip"
)


def fetch_shapefile(
    url: str = DEFAULT_SHAPEFILE_URL,
    *,
    data_dir: Path = Path("data/priogrid"),
    ledger_path: Path = Path("provenance/priogrid/ingestion_ledger.jsonl"),
    force_refresh: bool = False,
) -> Path:
    """Download and store the PRIO-GRID reference shapefile ZIP.

    Args:
        url: URL to the shapefile ZIP archive.
        data_dir: Directory to store the downloaded and extracted files.
        ledger_path: Path to the provenance JSONL ledger.
        force_refresh: If True, re-download even if files exist.

    Returns:
        Path to the extraction directory containing .shp files.
    """
    shp_dir = data_dir / "shapefile"
    zip_path = data_dir / "priogrid_shapefiles.zip"

    # Check if already downloaded
    if not force_refresh and shp_dir.exists() and any(shp_dir.glob("*.shp")):
        logger.info("Using existing shapefile: %s", shp_dir)
        return shp_dir

    # Download
    logger.info("Downloading PRIO-GRID shapefile from %s", url)
    data_dir.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    content = resp.content
    content_digest = compute_content_digest(content)
    logger.info(
        "Downloaded %d bytes (digest: %s)",
        len(content),
        content_digest,
    )

    # Check if content has changed
    previous_digest = last_digest(ledger_path)
    if previous_digest == content_digest and not force_refresh:
        logger.info(
            "Content unchanged (digest: %s), skipping extraction",
            content_digest,
        )
        # Record heartbeat
        append_ledger_entry(
            ledger_path,
            {
                "dataset": "priogrid_shapefile",
                "url": url,
                "size_bytes": len(content),
                "content_digest": content_digest,
                "previous_digest": previous_digest,
                "changed": False,
            },
        )
        return shp_dir

    # Save ZIP
    zip_path.write_bytes(content)

    # Extract
    shp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        zf.extractall(shp_dir)

    extracted = sorted(p.name for p in shp_dir.rglob("*") if p.is_file())
    logger.info("Extracted %d files to %s", len(extracted), shp_dir)

    # Provenance
    append_ledger_entry(
        ledger_path,
        {
            "dataset": "priogrid_shapefile",
            "url": url,
            "size_bytes": len(content),
            "content_digest": content_digest,
            "previous_digest": previous_digest,
            "changed": previous_digest is None or previous_digest != content_digest,
            "extracted_files": extracted,
        },
    )

    return shp_dir
