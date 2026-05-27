"""V-Dem (Varieties of Democracy) harvester — CSV download.

Downloads V-Dem country-year data from the V-Dem distribution,
filters to the 22 variables used by production models, and stores
as Parquet. No authentication required.

Source: V-Dem Institute, University of Gothenburg (CC-BY-SA 4.0)
    https://www.v-dem.net/

Ref: ADR-035 (V-Dem source selection).
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
import requests as _requests

from datafactory_harvester.sources import register_source
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "vdem"

VDEM_VARIABLES: tuple[str, ...] = (
    "v2xcl_dmove",
    "v2xeg_eqdr",
    "v2xpe_exlsocgr",
    "v2x_clphy",
    "v2xcl_prpty",
    "v2x_ex_military",
    "v2x_ex_party",
    "v2x_horacc",
    "v2xnp_client",
    "v2xnp_regcorr",
    "v2xpe_exlgeo",
    "v2x_veracc",
    "v2xpe_exlpol",
    "v2x_diagacc",
    "v2x_divparctrl",
    "v2xeg_eqprotec",
    "v2x_genpp",
    "v2xpe_exlgender",
    "v2x_hosabort",
    "v2x_libdem",
    "v2xcl_rol",
    "v2x_accountability",
)

VDEM_ID_COLUMNS: tuple[str, ...] = (
    "country_text_id",
    "year",
)

DEFAULT_DOWNLOAD_URL = (
    "https://v-dem.net/media/datasets/V-Dem-CY-FullOthers-v16_csv.zip"
)


# ---- Config ----


@dataclass(frozen=True)
class VdemConfig:
    """Configuration for harvesting V-Dem country-year data.

    Downloads the V-Dem CSV (inside ZIP), filters to declared
    variables, and stores as Parquet.
    """

    download_url: str = DEFAULT_DOWNLOAD_URL
    variables: tuple[str, ...] = VDEM_VARIABLES
    data_dir: Path = Path("data/raw/vdem")
    ledger_path: Path = Path(
        "provenance/vdem/ingestion_ledger.jsonl"
    )
    version: str = "v16"
    timeout: int = 300

    def __post_init__(self) -> None:
        if not self.variables:
            msg = "variables must be non-empty"
            raise ValueError(msg)
        if self.timeout < 1:
            msg = f"timeout must be >= 1, got {self.timeout}"
            raise ValueError(msg)
        if not self.version:
            msg = "version must be non-empty"
            raise ValueError(msg)
        seen: set[str] = set()
        for var in self.variables:
            if not var:
                msg = "variables must not contain empty strings"
                raise ValueError(msg)
            if var in seen:
                msg = f"duplicate variable: {var}"
                raise ValueError(msg)
            seen.add(var)

    @property
    def output_path(self) -> Path:
        return self.data_dir / f"vdem_{self.version}.parquet"


# ---- Fetch ----


def fetch_vdem(
    config: VdemConfig | None = None,
    *,
    force_refresh: bool = False,
) -> dict:
    """Download V-Dem CSV and store as filtered Parquet.

    1. Check cache (Parquet exists + ledger has digest) → skip
    2. Download ZIP from V-Dem distribution (~80 MB compressed)
    3. Extract CSV, read only needed columns
    4. Write filtered Parquet to data_dir
    5. Record provenance in ledger

    Args:
        config: Harvest configuration. Defaults to VdemConfig().
        force_refresh: Re-download even if cached.

    Returns:
        Result dict with dataset, version, outcome, content_digest.

    Raises:
        requests.ConnectionError: Network failure (after retries).
        zipfile.BadZipFile: Downloaded content is not a valid ZIP.
        ValueError: CSV missing required columns.
    """
    if config is None:
        config = VdemConfig()

    config.data_dir.mkdir(parents=True, exist_ok=True)

    output_path = config.output_path

    # Cache check
    if not force_refresh and output_path.exists():
        previous = last_digest_for_version(
            config.ledger_path, config.version
        )
        if previous is not None:
            logger.info(
                "V-Dem %s cached (digest: %s)",
                config.version, previous,
            )
            return {
                "dataset": DATASET_ID,
                "version": config.version,
                "outcome": "cached",
                "content_digest": previous,
            }

    # Download
    logger.info(
        "Downloading V-Dem %s from %s ...",
        config.version, config.download_url,
    )
    t0 = time.monotonic()

    try:
        resp = request_with_retry(
            config.download_url, timeout=config.timeout
        )
    except _requests.RequestException:
        logger.error(
            "Download failed for V-Dem %s", config.version
        )
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": config.version,
            "outcome": "failed",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise

    content = resp.content
    elapsed = time.monotonic() - t0
    size_mb = len(content) / 1e6
    logger.info("Downloaded %.0f MB in %.1fs", size_mb, elapsed)

    # Extract CSV from ZIP
    csv_bytes = _extract_csv_from_zip(content, config)

    # Parse CSV and filter columns
    try:
        table = _parse_and_filter(csv_bytes, config)
    except ValueError as exc:
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": config.version,
            "outcome": "failed",
            "reason": str(exc),
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise

    if table.num_rows == 0:
        msg = "V-Dem CSV produced zero rows after filtering"
        logger.error(msg)
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": config.version,
            "outcome": "failed",
            "reason": msg,
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise ValueError(msg)

    # Write Parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path, compression="snappy")

    # Provenance
    content_digest = compute_content_digest(csv_bytes)

    previous = last_digest_for_version(
        config.ledger_path, config.version
    )
    outcome = (
        "unchanged" if previous == content_digest else "success"
    )

    country_col = table.column("country_text_id").to_pylist()
    n_countries = len(set(country_col))
    year_col = table.column("year").to_pylist()
    min_year = int(min(year_col))
    max_year = int(max(year_col))

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "n_rows": table.num_rows,
        "n_variables": len(config.variables),
        "n_countries": n_countries,
        "year_range": [min_year, max_year],
        "content_digest": content_digest,
        "outcome": outcome,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    logger.info(
        "V-Dem %s: %d rows, %d variables, years %d–%d "
        "(digest: %s)",
        config.version,
        table.num_rows,
        len(config.variables),
        min_year, max_year,
        content_digest,
    )

    return {
        "dataset": DATASET_ID,
        "version": config.version,
        "outcome": outcome,
        "content_digest": content_digest,
        "n_rows": table.num_rows,
        "path": str(output_path),
    }


def _extract_csv_from_zip(
    content: bytes,
    config: VdemConfig,
) -> bytes:
    """Extract the CSV file from V-Dem ZIP archive."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        logger.error("Bad ZIP file for V-Dem %s", config.version)
        append_ledger_entry(config.ledger_path, {
            "dataset": DATASET_ID,
            "version": config.version,
            "outcome": "failed",
            "reason": "Bad ZIP file",
            "ledger_version": LEDGER_VERSION,
            "digest_algorithm": DIGEST_SCHEME,
        })
        raise

    with zf:
        csv_files = [
            n for n in zf.namelist()
            if n.endswith(".csv")
        ]
        if not csv_files:
            msg = (
                f"No CSV found in V-Dem ZIP. "
                f"Contents: {zf.namelist()}"
            )
            logger.error(msg)
            append_ledger_entry(config.ledger_path, {
                "dataset": DATASET_ID,
                "version": config.version,
                "outcome": "failed",
                "reason": msg,
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            raise ValueError(msg)

        csv_name = csv_files[0]
        logger.info("Extracting %s from ZIP", csv_name)
        return zf.read(csv_name)


def _parse_and_filter(
    csv_bytes: bytes,
    config: VdemConfig,
) -> pa.Table:
    """Parse V-Dem CSV and filter to requested columns."""
    needed_cols = list(VDEM_ID_COLUMNS) + list(config.variables)

    read_opts = pcsv.ReadOptions(
        column_names=None,
        autogenerate_column_names=False,
    )
    convert_opts = pcsv.ConvertOptions(
        include_columns=needed_cols,
    )

    try:
        table = pcsv.read_csv(
            io.BytesIO(csv_bytes),
            read_options=read_opts,
            convert_options=convert_opts,
        )
    except (pa.ArrowInvalid, pa.ArrowKeyError) as exc:
        msg = f"V-Dem CSV missing required columns: {exc}"
        logger.error(msg)
        raise ValueError(msg) from exc

    return table


# Auto-register
register_source("vdem", fetch_vdem)
