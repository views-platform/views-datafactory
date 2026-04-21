"""Remote server defaults for the VIEWS data factory.

Centralizes the server address so consumers import a constant
instead of hardcoding the IP. Follows the GridConfig pattern
from datafactory_priogrid.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


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
