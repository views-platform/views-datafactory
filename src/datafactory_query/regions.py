"""Region definitions — resolve region names to PRIO-GRID cell sets.

Source of truth: GAUL Parquet files (data/raw/gaul_admin/).
Region groupings are curated mappings of GAUL country names.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import pyarrow.parquet as pq

from datafactory_priogrid.land_mask import fetch_land_pgids

__all__ = ["list_regions", "load_region_pgids"]

logger = logging.getLogger(__name__)

_DEFAULT_GAUL_DIR = Path("data/raw/gaul_admin")

# ── Curated region definitions ─────────────────────────
# Keys: GAUL country/territory names (from gaul0_name.parquet).
# These match FAO GAUL 2024 naming conventions exactly.

_AFRICA: list[str] = [
    "Abyei",  # disputed (Sudan/South Sudan)
    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso",
    "Burundi", "Cameroon", "Central African Republic", "Chad",
    "Comoros", "Congo", "Côte D'Ivoire",
    "Democratic Republic of the Congo", "Djibouti", "Egypt",
    "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia",
    "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau",
    "Hala'Ib Triangle",  # disputed (Egypt/Sudan)
    "Ilemi Triangle",  # disputed (Kenya/South Sudan)
    "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar",
    "Malawi", "Mali", "Mauritania", "Mauritius", "Morocco",
    "Mozambique", "Namibia", "Niger", "Nigeria", "Rwanda",
    "Réunion", "Senegal", "Sierra Leone", "Somalia",
    "South Africa", "South Sudan", "Sudan", "Togo", "Tunisia",
    "Uganda", "United Republic of Tanzania", "Western Sahara",
    "Zambia", "Zimbabwe",
]

_MIDDLE_EAST: list[str] = [
    "Iran (Islamic Republic Of)", "Iraq", "Israel",
    "Jordan", "Kuwait", "Lebanon", "Oman", "Palestine", "Qatar",
    "Saudi Arabia", "Syrian Arab Republic", "Türkiye",
    "United Arab Emirates", "Yemen",
]

_AMERICAS: list[str] = [
    "Argentina", "Bahamas", "Belize",
    "Bolivia (Plurinational State of)", "Brazil", "Canada",
    "Cayman Islands", "Chile", "Colombia", "Costa Rica", "Cuba",
    "Dominican Republic", "Ecuador", "El Salvador",
    "Falkland Islands (Malvinas)", "French Guiana",
    "Greenland", "Guadeloupe", "Guatemala",
    "Guyana", "Haiti", "Honduras", "Jamaica", "Mexico",
    "Nicaragua", "Panama", "Paraguay", "Peru", "Puerto Rico",
    "Saint Vincent and the Grenadines", "Suriname",
    "Trinidad And Tobago",
    "Turks And Caicos Islands", "United States Virgin Islands",
    "United States of America", "Uruguay",
    "Venezuela (Bolivarian Republic Of)",
]

_EUROPE: list[str] = [
    "Albania", "Armenia", "Austria", "Azerbaijan", "Belarus",
    "Belgium",
    "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
    "Czechia", "Denmark", "Estonia", "Finland", "France",
    "Georgia", "Germany", "Greece", "Hungary", "Iceland",
    "Ireland", "Italy", "Jersey", "Kazakhstan", "Kuril Islands",
    "Kyrgyzstan",
    "Latvia", "Lithuania", "Luxembourg", "Montenegro",
    "Netherlands (Kingdom of the)", "North Macedonia", "Norway",
    "Poland", "Portugal", "Republic of Moldova", "Romania",
    "Russian Federation", "Serbia", "Slovakia", "Slovenia",
    "Spain", "Svalbard and Jan Mayen Islands",
    "Sweden", "Switzerland", "Tajikistan",
    "Turkmenistan",
    "Ukraine",
    "United Kingdom of Great Britain and Northern Ireland",
    "Uzbekistan", "Åland Islands",
]

_ASIA_OCEANIA: list[str] = [
    "Afghanistan", "Aksai Chin",  # disputed (China/India)
    "Arunachal Pradesh",  # disputed (India/China)
    "Australia",
    "Bangladesh", "Bhutan", "Brunei Darussalam",
    "Cambodia", "China", "China, Hong Kong SAR", "Cook Islands",
    "Democratic People's Republic of Korea", "Fiji",
    "French Polynesia", "India",
    "Indonesia", "Jammu And Kashmir",  # disputed (India/Pakistan)
    "Japan", "Kiribati",
    "Lao People's Democratic Republic", "Malaysia", "Maldives",
    "Marshall Islands", "Mongolia", "Myanmar", "Nepal",
    "New Caledonia", "New Zealand", "Pakistan", "Papua New Guinea",
    "Philippines", "Republic Of Korea", "Samoa",
    "Solomon Islands", "Sri Lanka",
    "Taiwan Province of China", "Thailand", "Timor-Leste",
    "Vanuatu", "Viet Nam",
]

REGIONS: dict[str, list[str]] = {
    "africa": _AFRICA,
    "middle_east": _MIDDLE_EAST,
    "africa_me": _AFRICA + _MIDDLE_EAST,
    "americas": _AMERICAS,
    "europe": _EUROPE,
    "asia_oceania": _ASIA_OCEANIA,
}


def list_regions() -> list[str]:
    """List available predefined region names.

    Returns region names that can be passed to load_region_pgids().
    Special values "global" and "land" are always available.
    Individual country names (matching GAUL) also work.
    """
    return sorted(["global", "land", *REGIONS.keys()])


@lru_cache(maxsize=1)
def _load_country_pgids(
    gaul_dir: Path,
) -> dict[str, set[int]]:
    """Load country_name → set[pgid] mapping from GAUL Parquets.

    Cached after first call. Reads gaul0_name.parquet.
    """
    name_path = gaul_dir / "gaul0_name.parquet"
    if not name_path.exists():
        msg = (
            f"GAUL data not found at {gaul_dir}. "
            f"Run: uv run python scripts/harvest_gaul.py"
        )
        raise FileNotFoundError(msg)

    table = pq.read_table(name_path)
    gids = table.column("gid").to_pylist()
    names = table.column("value").to_pylist()

    country_pgids: dict[str, set[int]] = {}
    for gid, name in zip(gids, names, strict=True):
        country_pgids.setdefault(name, set()).add(gid)

    logger.info(
        "Loaded %d countries, %d cells from %s",
        len(country_pgids),
        len(gids),
        name_path,
    )
    return country_pgids


def load_region_pgids(
    region: str,
    *,
    gaul_dir: Path = _DEFAULT_GAUL_DIR,
) -> set[int]:
    """Resolve a region name to a set of PRIO-GRID cell IDs.

    Args:
        region: One of:
            - Predefined region: "africa", "middle_east", "africa_me",
              "americas", "europe", "asia_oceania"
            - Special: "global" (all 259,200 cells), "land" (64,818)
            - Country name matching GAUL (e.g., "Ethiopia")
        gaul_dir: Path to GAUL admin Parquet files.

    Returns:
        Set of pgids belonging to the region.

    Raises:
        ValueError: If region name is not recognized.
        FileNotFoundError: If GAUL data is not available.
    """
    if region == "global":
        return set(range(1, 259_201))

    if region == "land":
        return fetch_land_pgids()

    # Predefined macro-region
    if region in REGIONS:
        country_pgids = _load_country_pgids(gaul_dir)
        result: set[int] = set()
        missing = []
        for country in REGIONS[region]:
            pgids = country_pgids.get(country)
            if pgids is not None:
                result |= pgids
            else:
                missing.append(country)
        if missing:
            logger.warning(
                "Region %r: %d countries not found in GAUL: %s",
                region, len(missing), missing,
            )
        return result

    # Try as individual country name
    country_pgids = _load_country_pgids(gaul_dir)
    if region in country_pgids:
        return country_pgids[region]

    # Case-insensitive fallback
    lower_map = {k.lower(): k for k in country_pgids}
    if region.lower() in lower_map:
        return country_pgids[lower_map[region.lower()]]

    available = sorted(
        ["global", "land"] + list(REGIONS.keys())
    )
    msg = (
        f"Unknown region {region!r}. "
        f"Available: {available}. "
        f"Or use a GAUL country name."
    )
    raise ValueError(msg)
