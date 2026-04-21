"""Remote server defaults for the VIEWS data factory.

Centralizes the server address so consumers import a constant
instead of hardcoding the IP. Follows the GridConfig pattern
from datafactory_priogrid.
"""

from __future__ import annotations

from dataclasses import dataclass


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
