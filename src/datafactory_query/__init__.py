"""Data access for training consumers.

Provides temporal + geographic subsetting of the assembled grid
in multiple output formats (FeatureFrame, DataFrame). Sits
downstream in the DAG: imports from priogrid + adapters, reads
assembled output via filesystem.
"""

from datafactory_query.dataset import load_dataset
from datafactory_query.defaults import (
    DEFAULT_REMOTE,
    PARTITIONS,
    RemoteConfig,
    get_last_valid_month_id,
)
from datafactory_query.output_format import (
    CONTRACT_VERSION,
    OutputFormat,
    is_valid_output_format,
)
from datafactory_query.regions import list_regions, load_region_pgids
from datafactory_query.temporal import parse_time_range

__all__ = [
    "CONTRACT_VERSION",
    "DEFAULT_REMOTE",
    "OutputFormat",
    "PARTITIONS",
    "RemoteConfig",
    "get_last_valid_month_id",
    "is_valid_output_format",
    "list_regions",
    "load_dataset",
    "load_region_pgids",
    "parse_time_range",
]
