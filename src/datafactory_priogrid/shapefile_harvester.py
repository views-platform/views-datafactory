"""PRIO-GRID shapefile harvester.

Downloads the reference shapefile ZIP from PRIO and stores it locally
with full provenance. Does NOT parse the shapefile -- reading is deferred
to a pluggable ReferenceGeometryReader (see validation.py).

The shapefile is a one-time critical artifact. If the origin URL goes
dead, the local copy is the fallback.

Provenance uses datafactory_provenance utilities.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest,
)

logger = logging.getLogger(__name__)

DATASET_ID = "priogrid_shapefile"

# Default PRIO-GRID shapefile URL
DEFAULT_SHAPEFILE_URL = (
    "http://file.prio.no/ReplicationData/PRIO-GRID/"
    "priogrid_shapefiles.zip"
)


@dataclass(frozen=True)
class ShapefileHarvesterConfig:
    """Configuration for downloading the PRIO-GRID shapefile.

    The shapefile is grid reference geometry (not a data source).
    Downloaded once and reused for parity validation.
    """

    url: str = DEFAULT_SHAPEFILE_URL
    data_dir: Path = Path("data/priogrid")
    ledger_path: Path = Path(
        "provenance/priogrid/ingestion_ledger.jsonl"
    )
    timeout: int = 120
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.timeout < 1:
            err_msg = (
                f"timeout must be >= 1, got {self.timeout}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        if self.max_retries < 1:
            err_msg = (
                f"max_retries must be >= 1, "
                f"got {self.max_retries}"
            )
            logger.error(err_msg)
            raise ValueError(err_msg)


def _download(
    url: str,
    *,
    timeout: int = 120,
    max_retries: int = 3,
) -> bytes:
    """Download content from a URL with retry and exponential backoff.

    Args:
        url: URL to download.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of attempts.

    Returns:
        Raw response bytes.

    Raises:
        requests.RequestException: After all retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            if attempt == max_retries - 1:
                logger.error(
                    "Download failed after %d attempts: %s",
                    max_retries,
                    url,
                )
                raise
            delay = 2**attempt
            logger.warning(
                "Download attempt %d/%d failed, retrying in %ds",
                attempt + 1,
                max_retries,
                delay,
            )
            time.sleep(delay)
    # Unreachable, but keeps mypy happy
    msg = "Unreachable"
    raise AssertionError(msg)


def _extract_zip(content: bytes, target_dir: Path) -> list[str]:
    """Extract ZIP content to a directory.

    Args:
        content: Raw ZIP bytes.
        target_dir: Directory to extract into.

    Returns:
        Sorted list of extracted filenames.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        zf.extractall(target_dir)
    return sorted(p.name for p in target_dir.rglob("*") if p.is_file())


def fetch_shapefile(
    config: ShapefileHarvesterConfig | None = None,
    *,
    force_refresh: bool = False,
) -> Path:
    """Download and store the PRIO-GRID reference shapefile ZIP.

    Orchestrates: download -> digest -> compare -> extract -> provenance.
    Skips download if files already exist (unless force_refresh).
    Records a heartbeat if content is unchanged.

    Args:
        config: Harvest configuration. Uses defaults if None.
        force_refresh: If True, re-download even if files exist.

    Returns:
        Path to the extraction directory containing .shp files.
    """
    if config is None:
        config = ShapefileHarvesterConfig()

    shp_dir = config.data_dir / "shapefile"

    # Early return: files already on disk
    if (
        not force_refresh
        and shp_dir.exists()
        and any(shp_dir.glob("*.shp"))
    ):
        logger.info("Using existing shapefile: %s", shp_dir)
        return shp_dir

    # Download
    logger.info(
        "Downloading PRIO-GRID shapefile from %s",
        config.url,
    )
    config.data_dir.mkdir(parents=True, exist_ok=True)
    content = _download(
        config.url,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )

    digest = compute_content_digest(content)
    logger.info("Downloaded %d bytes (digest: %s)", len(content), digest)

    # Compare with previous
    previous = last_digest(config.ledger_path)
    changed = previous is None or previous != digest

    base_entry = {
        "dataset": DATASET_ID,
        "url": config.url,
        "size_bytes": len(content),
        "content_digest": digest,
        "previous_digest": previous,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    }

    if not changed and not force_refresh:
        logger.info("Content unchanged (digest: %s), skipping extraction", digest)
        append_ledger_entry(config.ledger_path, {**base_entry, "changed": False})
        return shp_dir

    # Extract and record
    (config.data_dir / "priogrid_shapefiles.zip").write_bytes(content)
    extracted = _extract_zip(content, shp_dir)
    logger.info("Extracted %d files to %s", len(extracted), shp_dir)

    append_ledger_entry(config.ledger_path, {
        **base_entry,
        "changed": changed,
        "extracted_files": extracted,
    })

    return shp_dir
