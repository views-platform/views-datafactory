"""Remote server defaults for the VIEWS data factory.

Centralizes the server address so consumers import a constant
instead of hardcoding the IP. Follows the GridConfig pattern
from datafactory_priogrid.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from types import MappingProxyType

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

    import base64
    import urllib.request
    from netrc import netrc
    from pathlib import Path
    from urllib.parse import urlparse

    parsed = urlparse(attrs_url)
    req = urllib.request.Request(attrs_url)

    try:
        nrc = netrc(str(Path.home() / ".netrc"))
        creds = nrc.authenticators(parsed.hostname)
        if creds:
            login, _, password = creds
            encoded = base64.b64encode(
                f"{login}:{password}".encode(),
            ).decode()
            req.add_header("Authorization", f"Basic {encoded}")
    except Exception:
        pass

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            attrs = json.loads(resp.read())
        val = attrs.get("last_valid_month_id")
        return int(val) if val is not None else None
    except Exception as exc:
        logger.warning(
            "Could not read last_valid_month_id from %s: %s",
            attrs_url, exc,
        )
        return None


# VIEWS operational calendar — single source of truth for partition
# boundaries used by consumer scripts, examples, and tests.
# Forecasting is excluded (computed dynamically from current date).
_partitions_raw: dict[str, dict[str, tuple[int, int]]] = {
    "calibration": {"train": (121, 444), "test": (445, 492)},
    "validation": {"train": (121, 492), "test": (493, 540)},
}
PARTITIONS: MappingProxyType[
    str, MappingProxyType[str, tuple[int, int]]
] = MappingProxyType(
    {k: MappingProxyType(v) for k, v in _partitions_raw.items()}
)
del _partitions_raw
