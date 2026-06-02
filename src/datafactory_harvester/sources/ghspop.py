"""GHS-POP population grid harvester — GeoTIFF download from JRC.

Downloads GHS-POP R2023A population grids as GeoTIFF files from
the EU Joint Research Centre (JRC/Copernicus). Each epoch is a
single global WGS84 raster at 30-arcsecond (~1 km) resolution.

Files are downloaded as ZIP archives, extracted to data_dir with
original JRC filenames, and recorded in the provenance ledger.

Source: EU JRC Global Human Settlement Layer (CC-BY-4.0)
    https://human-settlement.emergency.copernicus.eu/

Ref: ADR-029 (GHS-POP source selection), ADR-030 (tifffile tooling).
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests as _requests

from datafactory_harvester.sources import register_source
from datafactory_harvester.validation import validate_positive_int
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    compute_file_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "ghspop"

KNOWN_EPOCHS = (
    1975, 1980, 1985, 1990, 1995,
    2000, 2005, 2010, 2015, 2020, 2025, 2030,
)

BASE_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL"
    "/GHS_POP_GLOBE_R2023A"
)


# ---- Config ----


@dataclass(frozen=True)
class GhsPopConfig:
    """Configuration for harvesting GHS-POP population grids.

    Each epoch is a single global GeoTIFF (WGS84, 30 arcsec).
    Downloaded as ZIP from JRC, extracted with original filename.
    """

    epochs: tuple[int, ...] = KNOWN_EPOCHS
    resolution: str = "30ss"
    crs: str = "4326"
    release: str = "R2023A"
    data_dir: Path = Path("data/raw/ghspop")
    ledger_path: Path = Path(
        "provenance/ghspop/ingestion_ledger.jsonl"
    )
    timeout: int = 600

    def __post_init__(self) -> None:
        for epoch in self.epochs:
            if epoch not in KNOWN_EPOCHS:
                msg = (
                    f"Unknown epoch {epoch}. "
                    f"Valid epochs: {KNOWN_EPOCHS}"
                )
                raise ValueError(msg)
        validate_positive_int(self.timeout, "timeout")

    def _stem(self, epoch: int) -> str:
        return (
            f"GHS_POP_E{epoch}_GLOBE"
            f"_{self.release}_{self.crs}_{self.resolution}"
        )

    def download_url(self, epoch: int) -> str:
        stem = self._stem(epoch)
        return f"{BASE_URL}/{stem}/V1-0/{stem}_V1_0.zip"

    def tif_filename(self, epoch: int) -> str:
        return f"{self._stem(epoch)}_V1_0.tif"


# ---- Fetch ----


def fetch_ghspop(
    config: GhsPopConfig | None = None,
    *,
    force_refresh: bool = False,
) -> list[dict]:
    """Download GHS-POP GeoTIFF files from JRC.

    For each epoch in config.epochs:
    1. Check cache (TIF exists + ledger has digest) → skip
    2. Download ZIP archive (~450 MB per epoch)
    3. Extract TIF to config.data_dir
    4. Record provenance in ledger

    Args:
        config: Harvest configuration. Defaults to GhsPopConfig().
        force_refresh: Re-download even if cached.

    Returns:
        List of result dicts, one per epoch. Each contains
        dataset, epoch, outcome, and content_digest.

    Raises:
        requests.ConnectionError: Network failure (after retries).
        zipfile.BadZipFile: Downloaded content is not a valid ZIP.
    """
    if config is None:
        config = GhsPopConfig()

    config.data_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for epoch in config.epochs:
        result = _fetch_epoch(config, epoch, force_refresh)
        results.append(result)

    return results


def _fetch_epoch(
    config: GhsPopConfig,
    epoch: int,
    force_refresh: bool,
) -> dict:
    """Fetch a single GHS-POP epoch."""
    tif_name = config.tif_filename(epoch)
    tif_path = config.data_dir / tif_name
    version = f"E{epoch}"

    # Cache check: file exists + ledger digest + file integrity
    if not force_refresh and tif_path.exists():
        previous = last_digest_for_version(
            config.ledger_path, version
        )
        if previous is not None:
            actual = compute_file_digest(tif_path)
            if actual == previous:
                logger.info(
                    "Epoch %d cached (digest: %s)",
                    epoch, previous,
                )
                return {
                    "dataset": DATASET_ID,
                    "epoch": epoch,
                    "outcome": "cached",
                    "content_digest": previous,
                }
            logger.warning(
                "Epoch %d cached file digest mismatch "
                "(expected %s, got %s) — re-downloading",
                epoch, previous, actual,
            )

    # Download
    url = config.download_url(epoch)
    logger.info("Downloading epoch %d from %s ...", epoch, url)
    t0 = time.monotonic()

    try:
        resp = request_with_retry(url, timeout=config.timeout)
    except _requests.RequestException:
        logger.error("Download failed for epoch %d: %s", epoch, url)
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": version,
            "outcome": "failed",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise

    content = resp.content
    elapsed = time.monotonic() - t0
    size_mb = len(content) / 1e6
    logger.info(
        "Downloaded %.0f MB in %.1fs", size_mb, elapsed
    )

    # Extract TIF from ZIP
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        logger.error("Bad ZIP file for epoch %d: %s", epoch, url)
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": version,
            "outcome": "failed",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise

    with zf:
        if tif_name not in zf.namelist():
            append_ledger_entry(config.ledger_path, {
                "dataset": DATASET_ID,
                "version": version,
                "outcome": "failed",
                "reason": (
                    f"Expected {tif_name} in ZIP but found: "
                    f"{zf.namelist()}"
                ),
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            msg = (
                f"Expected {tif_name} in ZIP for epoch {epoch} "
                f"but found: {zf.namelist()} — "
                f"JRC naming convention may have changed"
            )
            logger.error(msg)
            raise ValueError(msg)

        tif_data = zf.read(tif_name)

    tif_path.parent.mkdir(parents=True, exist_ok=True)
    tif_path.write_bytes(tif_data)

    # Provenance
    content_digest = compute_content_digest(tif_data)

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": version,
        "epoch": epoch,
        "content_digest": content_digest,
        "outcome": "success",
        "size_bytes": len(tif_data),
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "Epoch %d: %s (%.1f MB, digest %s)",
        epoch, tif_path, len(tif_data) / 1e6, content_digest,
    )

    return {
        "dataset": DATASET_ID,
        "epoch": epoch,
        "outcome": "success",
        "content_digest": content_digest,
    }


# Auto-register
register_source("ghspop", fetch_ghspop)
