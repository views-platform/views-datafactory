"""Remote server defaults for the VIEWS data factory.

Centralizes the server address so consumers import a constant
instead of hardcoding the IP. Follows the GridConfig pattern
from datafactory_priogrid.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.request
from dataclasses import dataclass
from netrc import NetrcParseError, netrc
from pathlib import Path
from types import MappingProxyType
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteConfig:
    """Remote server configuration.

    Frozen dataclass — construct a custom instance to override
    any field (e.g., ``RemoteConfig(scheme="https")``).
    """

    server: str = "204.168.219.108"
    zarr_path: str = "/grid.zarr"
    scheme: str = "http"

    @property
    def zarr_url(self) -> str:
        return f"{self.scheme}://{self.server}{self.zarr_path}"

    @property
    def parquet_url(self) -> str:
        return f"{self.scheme}://{self.server}/dataframe.parquet"


DEFAULT_REMOTE = RemoteConfig()


def get_last_valid_month_id(
    zarr_url: str | None = None,
) -> int | None:
    """Read last_valid_month_id from the zarr store's .zattrs.

    Returns None if the attribute is not present (store was
    exported before this metadata was added).
    """
    url = zarr_url or DEFAULT_REMOTE.zarr_url
    attrs_url = f"{url}/.zattrs"

    parsed = urlparse(attrs_url)
    req = urllib.request.Request(attrs_url)

    try:
        nrc = netrc(str(Path.home() / ".netrc"))
        creds = nrc.authenticators(parsed.hostname or "")
        if creds:
            login, _, password = creds
            encoded = base64.b64encode(
                f"{login}:{password}".encode(),
            ).decode()
            # add_unredirected_header, NOT add_header: urllib copies
            # every header except content-length/content-type onto a
            # redirected request, so add_header would forward this
            # credential to whatever host a 30x points at (#388).
            req.add_unredirected_header(
                "Authorization", f"Basic {encoded}",
            )
    except (FileNotFoundError, NetrcParseError, KeyError):
        pass

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except (URLError, HTTPError, TimeoutError) as exc:
        logger.error(
            "Failed to read .zattrs from %s: %s",
            attrs_url, exc,
        )
        raise

    attrs = json.loads(raw)
    val = attrs.get("last_valid_month_id")
    return int(val) if val is not None else None


# VIEWS operational calendar — single source of truth for partition
# boundaries used by consumer scripts, examples, and tests.
# Forecasting is excluded (computed dynamically from current date).
_partitions_raw: dict[str, dict[str, tuple[int, int]]] = {
    "calibration": {"train": (121, 456), "test": (457, 504)},
    "validation": {"train": (121, 504), "test": (505, 552)},
}
PARTITIONS: MappingProxyType[
    str, MappingProxyType[str, tuple[int, int]]
] = MappingProxyType(
    {k: MappingProxyType(v) for k, v in _partitions_raw.items()}
)
del _partitions_raw
