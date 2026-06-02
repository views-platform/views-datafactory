"""GDL Subnational HDI (SHDI) harvester — API download.

Downloads SHDI data from the GDL Data API, stores as Parquet,
and builds a spatial join crosswalk mapping GDL regions to
PRIO-GRID cells. GDL shapefiles are downloaded from the PRIO CDN.

Authentication: API token via GDL_API_TOKEN env var (ADR-026).
Free account at globaldatalab.org → "My GDL" → "API Access".

Source: Global Data Lab, Radboud University
    https://globaldatalab.org/shdi/

Ref: ADR-036 (SHDI source selection).
"""

from __future__ import annotations

import logging
import os
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
import requests as _requests
import shapefile as shp
from shapely import STRtree
from shapely.geometry import Point, shape

from datafactory_harvester.sources import register_source
from datafactory_harvester.validation import (
    validate_nonempty_string,
    validate_positive_int,
    validate_string_tuple,
)
from datafactory_http import request_with_retry
from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    last_digest_for_version,
)

logger = logging.getLogger(__name__)

DATASET_ID = "shdi"

SHDI_VARIABLES: tuple[str, ...] = (
    "shdi",
    "healthindex",
    "edindex",
    "incindex",
)

SHDI_ID_COLUMNS: tuple[str, ...] = (
    "GDLCODE",
    "Level",
    "Country",
    "Region",
    "Year",
)

DEFAULT_CENTROID_PATH = Path(
    "data/raw/priogrid/shapefile/priogrid_centroid.shp"
)

DEFAULT_API_BASE_URL = "https://globaldatalab.org"

DEFAULT_SHAPEFILE_URL = (
    "https://cdn.cloud.prio.org/files/"
    "604a306f-80de-49af-8610-948af8e2e474/"
    "GDL%20Shapefiles%20V64.zip"
)


# ---- Credential resolution (ADR-026) ----


def get_gdl_token(token: str | None = None) -> str:
    """Resolve GDL API token from argument or environment.

    Resolution order (per ADR-026):
    1. Function argument (highest priority)
    2. Environment variable GDL_API_TOKEN
    3. Fail-loud with actionable error message

    Returns:
        The API token string.

    Raises:
        ValueError: If no token can be resolved.
    """
    resolved = token or os.environ.get("GDL_API_TOKEN")
    if not resolved:
        msg = (
            "GDL API token required. Set GDL_API_TOKEN "
            "environment variable or pass token= to "
            "fetch_shdi(). Get a free token at "
            "https://globaldatalab.org → My GDL → API Access."
        )
        logger.error(msg)
        raise ValueError(msg)
    return resolved


# ---- Config ----


@dataclass(frozen=True)
class ShdiConfig:
    """Configuration for harvesting GDL SHDI data.

    Downloads SHDI CSV from the GDL Data API, GDL shapefiles
    from PRIO CDN, filters to declared variables, stores as
    Parquet, and builds a GDL→pgid spatial join crosswalk.
    """

    api_base_url: str = DEFAULT_API_BASE_URL
    shapefile_url: str = DEFAULT_SHAPEFILE_URL
    centroid_path: Path = DEFAULT_CENTROID_PATH
    variables: tuple[str, ...] = SHDI_VARIABLES
    data_dir: Path = Path("data/raw/shdi")
    ledger_path: Path = Path(
        "provenance/shdi/ingestion_ledger.jsonl"
    )
    version: str = "v10.2"
    timeout: int = 300

    def __post_init__(self) -> None:
        validate_string_tuple(self.variables, "variables")
        validate_nonempty_string(self.version, "version")
        validate_positive_int(self.timeout, "timeout")

    def indicator_url(self, variable: str) -> str:
        return f"{self.api_base_url}/shdi/download/{variable}/"

    @property
    def output_path(self) -> Path:
        return self.data_dir / f"shdi_{self.version}.parquet"

    @property
    def crosswalk_path(self) -> Path:
        return self.data_dir / "gdl_to_pgid.parquet"

    @property
    def shapefile_cache_path(self) -> Path:
        return self.data_dir / "GDL_Shapefiles.zip"


# ---- Fetch ----


def fetch_shdi(
    config: ShdiConfig | None = None,
    *,
    force_refresh: bool = False,
) -> dict:
    """Download SHDI CSV from GDL API and build GDL→pgid crosswalk.

    1. Check cache (Parquet + crosswalk exist + ledger has digest) → skip
    2. Resolve GDL API token (ADR-026)
    3. Download CSV from GDL Data API
    4. Parse and filter to ID columns + variables
    5. Write filtered Parquet
    6. Download GDL shapefiles from PRIO CDN (if not cached)
    7. Spatial join: GDL polygons × PRIO-GRID centroids → crosswalk
    8. Record provenance in ledger

    Args:
        config: Harvest configuration. Defaults to ShdiConfig().
        force_refresh: Re-download even if cached.

    Returns:
        Result dict with dataset, version, outcome, content_digest.

    Raises:
        ValueError: Missing token, CSV missing columns, or zero rows.
        requests.RequestException: Network failure (after retries).
    """
    if config is None:
        config = ShdiConfig()

    config.data_dir.mkdir(parents=True, exist_ok=True)

    output_path = config.output_path
    crosswalk_path = config.crosswalk_path

    # Cache check
    if (
        not force_refresh
        and output_path.exists()
        and crosswalk_path.exists()
    ):
        previous = last_digest_for_version(
            config.ledger_path, config.version
        )
        if previous is not None:
            logger.info(
                "SHDI %s cached (digest: %s)",
                config.version, previous,
            )
            return {
                "dataset": DATASET_ID,
                "version": config.version,
                "outcome": "cached",
                "content_digest": previous,
            }

    # Resolve token
    token = get_gdl_token()

    # Download each indicator separately (GDL API returns only latest
    # year when multiple indicators are combined in one request).
    logger.info(
        "Downloading SHDI %s — %d indicators ...",
        config.version, len(config.variables),
    )
    t0 = time.monotonic()
    all_csv_bytes: list[bytes] = []

    for var in config.variables:
        url = config.indicator_url(var)
        logger.info("  %s → %s", var, url)
        try:
            resp = request_with_retry(
                url,
                params={"format": "csv", "token": token},
                timeout=config.timeout,
            )
        except _requests.RequestException:
            logger.error(
                "Download failed for SHDI %s (%s)",
                config.version, var,
            )
            append_ledger_entry(config.ledger_path, {
                "dataset": DATASET_ID,
                "version": config.version,
                "outcome": "failed",
                "reason": f"download failed for {var}",
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            raise
        all_csv_bytes.append(resp.content)

    elapsed_dl = time.monotonic() - t0
    total_mb = sum(len(b) for b in all_csv_bytes) / 1e6
    logger.info(
        "Downloaded %d indicators (%.1f MB) in %.1fs",
        len(config.variables), total_mb, elapsed_dl,
    )

    # Parse each indicator CSV and merge on ID columns
    try:
        table = _parse_and_merge(all_csv_bytes, config)
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
        msg = "SHDI CSV produced zero rows after filtering"
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

    # Filter to subnational rows only (level == "Subnat")
    level_col = table.column("Level").to_pylist()
    subnat_mask = [lv == "Subnat" for lv in level_col]
    table = table.filter(pa.array(subnat_mask))

    if table.num_rows == 0:
        msg = "SHDI CSV has no subnational rows (level == 'Subnat')"
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

    # Write data Parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path, compression="snappy")

    elapsed_csv = time.monotonic() - t0
    logger.info(
        "SHDI CSV: %d rows in %.1fs", table.num_rows, elapsed_csv,
    )

    # Download shapefiles from PRIO CDN (if not cached)
    shapefile_path = config.shapefile_cache_path
    if force_refresh or not shapefile_path.exists():
        logger.info("Downloading GDL shapefiles from PRIO CDN...")
        t_shp = time.monotonic()
        try:
            shp_resp = request_with_retry(
                config.shapefile_url, timeout=config.timeout,
            )
        except _requests.RequestException:
            logger.error(
                "Shapefile download failed for SHDI %s",
                config.version,
            )
            append_ledger_entry(config.ledger_path, {
                "dataset": DATASET_ID,
                "version": config.version,
                "outcome": "failed",
                "reason": "shapefile download failed",
                "ledger_version": LEDGER_VERSION,
                "digest_algorithm": DIGEST_SCHEME,
            })
            raise
        shapefile_path.write_bytes(shp_resp.content)
        logger.info(
            "Shapefiles: %.1f MB in %.1fs",
            len(shp_resp.content) / 1e6,
            time.monotonic() - t_shp,
        )

    # Spatial join: GDL shapefiles → PRIO-GRID centroids
    t1 = time.monotonic()
    crosswalk = _build_crosswalk(
        shapefile_path, config.centroid_path,
    )

    crosswalk_table = pa.table({
        "gid": pa.array(
            [gid for gid, _ in crosswalk], type=pa.int32()
        ),
        "gdl_code": pa.array(
            [code for _, code in crosswalk], type=pa.string()
        ),
    })
    pq.write_table(
        crosswalk_table, crosswalk_path, compression="snappy",
    )

    elapsed_xwalk = time.monotonic() - t1
    n_pgids = len(crosswalk_table)
    gdl_codes_mapped = len(
        set(crosswalk_table.column("gdl_code").to_pylist())
    )
    logger.info(
        "Crosswalk: %d pgids, %d GDL codes in %.1fs",
        n_pgids, gdl_codes_mapped, elapsed_xwalk,
    )

    # Provenance — digest covers all indicator CSVs concatenated
    content_digest = compute_content_digest(b"".join(all_csv_bytes))

    previous = last_digest_for_version(
        config.ledger_path, config.version
    )
    outcome = (
        "unchanged" if previous == content_digest else "success"
    )

    gdl_col = table.column("GDLCODE").to_pylist()
    n_regions = len(set(gdl_col))
    year_col = table.column("Year").to_pylist()
    min_year = int(min(year_col))
    max_year = int(max(year_col))

    append_ledger_entry(config.ledger_path, {
        "dataset": DATASET_ID,
        "version": config.version,
        "n_rows": table.num_rows,
        "n_variables": len(config.variables),
        "n_regions": n_regions,
        "year_range": [min_year, max_year],
        "n_pgids_mapped": n_pgids,
        "n_gdl_codes_mapped": gdl_codes_mapped,
        "content_digest": content_digest,
        "outcome": outcome,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    })

    elapsed = time.monotonic() - t0
    logger.info(
        "SHDI %s: %d rows, %d regions, years %d–%d, "
        "%d pgids mapped (%.1fs total, digest: %s)",
        config.version,
        table.num_rows, n_regions,
        min_year, max_year,
        n_pgids, elapsed,
        content_digest,
    )

    return {
        "dataset": DATASET_ID,
        "version": config.version,
        "outcome": outcome,
        "content_digest": content_digest,
        "n_rows": table.num_rows,
        "n_regions": n_regions,
        "n_pgids_mapped": n_pgids,
        "path": str(output_path),
        "crosswalk_path": str(crosswalk_path),
    }


# ---- CSV parsing ----


def _parse_and_merge(
    csv_list: list[bytes],
    config: ShdiConfig,
) -> pa.Table:
    """Parse per-indicator CSVs and merge on ID columns.

    Each CSV has ID columns + one indicator column. We parse each,
    keep only ID + that indicator, then join them together.
    """
    if len(csv_list) != len(config.variables):
        msg = (
            f"Expected {len(config.variables)} CSVs, "
            f"got {len(csv_list)}"
        )
        raise ValueError(msg)

    id_cols = list(SHDI_ID_COLUMNS)
    tables: list[pa.Table] = []

    for csv_bytes, var in zip(csv_list, config.variables, strict=True):
        needed = id_cols + [var]
        convert_opts = pcsv.ConvertOptions(include_columns=needed)
        try:
            tbl = pcsv.read_csv(
                pa.py_buffer(csv_bytes),
                convert_options=convert_opts,
            )
        except (pa.ArrowInvalid, pa.ArrowKeyError) as exc:
            msg = f"SHDI CSV missing required columns for {var}: {exc}"
            logger.error(msg)
            raise ValueError(msg) from exc
        tables.append(tbl)

    if tables[0].num_rows == 0:
        return tables[0]

    expected_rows = tables[0].num_rows
    result = tables[0]
    for i, tbl in enumerate(tables[1:], start=1):
        result = result.join(tbl, keys=id_cols, join_type="inner")
        if result.num_rows < expected_rows:
            dropped = expected_rows - result.num_rows
            var = config.variables[i]
            msg = (
                f"SHDI inner join lost {dropped} rows "
                f"({dropped / expected_rows:.1%}) merging {var} — "
                f"indicator coverage mismatch"
            )
            logger.error(msg)
            raise ValueError(msg)

    return result


# ---- Spatial join crosswalk ----


def _load_centroids(
    centroid_path: Path,
) -> list[tuple[int, float, float]]:
    """Load PRIO-GRID centroids from shapefile.

    Returns list of (gid, lon, lat) tuples.
    """
    if not centroid_path.exists():
        msg = f"Centroid shapefile not found: {centroid_path}"
        raise FileNotFoundError(msg)

    centroids: list[tuple[int, float, float]] = []
    with shp.Reader(str(centroid_path)) as sf:
        fields = [f[0] for f in sf.fields[1:]]
        gid_idx = fields.index("gid")
        for sr in sf.iterShapeRecords():
            gid = int(sr.record[gid_idx])
            lon, lat = sr.shape.points[0]
            centroids.append((gid, lon, lat))

    logger.info("Loaded %d centroids", len(centroids))
    return centroids


def _extract_shapefile(
    shapefile_path: Path,
    extract_dir: Path,
) -> Path:
    """Extract GDL shapefile ZIP and return path to .shp file."""
    with zipfile.ZipFile(shapefile_path) as zf:
        zf.extractall(extract_dir)

    shp_files = list(extract_dir.rglob("*.shp"))
    if not shp_files:
        msg = (
            f"No .shp found in {shapefile_path}. "
            f"Contents: {list(extract_dir.rglob('*'))}"
        )
        raise FileNotFoundError(msg)

    return shp_files[0]


def _build_crosswalk(
    shapefile_path: Path,
    centroid_path: Path,
) -> list[tuple[int, str]]:
    """Build GDL-code → pgid crosswalk via spatial join.

    Joins PRIO-GRID centroids against GDL admin polygons using
    STRtree spatial indexing.

    Args:
        shapefile_path: Path to GDL shapefiles ZIP.
        centroid_path: Path to PRIO-GRID centroid shapefile.

    Returns:
        List of (gid, gdl_code) tuples.
    """
    centroids = _load_centroids(centroid_path)

    extract_dir = shapefile_path.parent / "_gdl_shp_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if shapefile_path.suffix == ".zip":
        shp_path = _extract_shapefile(shapefile_path, extract_dir)
    else:
        shp_path = shapefile_path

    logger.info("Reading GDL shapefile %s ...", shp_path.name)
    polygons = []
    gdl_codes: list[str] = []

    with shp.Reader(str(shp_path)) as sf:
        dbf_fields = [f[0] for f in sf.fields[1:]]

        gdl_field = _find_gdl_code_field(dbf_fields)
        gdl_idx = dbf_fields.index(gdl_field)

        for sr in sf.iterShapeRecords():
            geo = sr.shape.__geo_interface__
            if geo["type"] == "Null":
                continue
            polygons.append(shape(geo))
            gdl_codes.append(str(sr.record[gdl_idx]))

    logger.info(
        "Loaded %d GDL polygons, building spatial index...",
        len(polygons),
    )

    tree = STRtree(polygons)

    result: list[tuple[int, str]] = []
    n_matched = 0
    n_unmatched = 0

    t0 = time.monotonic()
    for gid, lon, lat in centroids:
        pt = Point(lon, lat)
        indices = tree.query(pt, predicate="intersects")
        if len(indices) > 0:
            idx = int(indices[0])
            result.append((gid, gdl_codes[idx]))
            n_matched += 1
        else:
            n_unmatched += 1

    elapsed = time.monotonic() - t0
    logger.info(
        "Spatial join: %d matched, %d unmatched (%.1fs)",
        n_matched, n_unmatched, elapsed,
    )

    return result


_GDL_CODE_CANDIDATES = (
    "GDLcode", "GDLCODE", "gdlcode", "GDL_Code", "gdl_code",
)


def _find_gdl_code_field(dbf_fields: list[str]) -> str:
    """Find the GDL code field in shapefile attributes.

    Tries known candidate names case-insensitively.
    """
    fields_lower = {f.lower(): f for f in dbf_fields}
    for candidate in _GDL_CODE_CANDIDATES:
        if candidate.lower() in fields_lower:
            return fields_lower[candidate.lower()]

    msg = (
        f"No GDL code field found in shapefile. "
        f"Tried: {_GDL_CODE_CANDIDATES}. "
        f"Available: {dbf_fields}"
    )
    raise ValueError(msg)


# Auto-register
register_source("shdi", fetch_shdi)
