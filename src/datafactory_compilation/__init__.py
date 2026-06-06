"""Compilation node -- places event data onto the spatiotemporal grid.

Reads viewpoint output as files. Produces populated npy arrays.
Tracks provenance: source digests + compilation config -> output digest.
"""

from datafactory_compilation.aggregation import get_strategy
from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.conservation import (
    PlacementAccounting,
    assert_placement_conservation,
)
from datafactory_compilation.grid_compilation import compile_grid
from datafactory_compilation.preflight import (
    check_disk_space,
    estimate_grid_bytes,
)
from datafactory_compilation.pregridded_compilation import (
    PregriddedCompilationConfig,
    PregriddedFeatureSpec,
    compile_pregridded,
)

__all__ = [
    "CompilationConfig",
    "FeatureSpec",
    "PlacementAccounting",
    "PregriddedCompilationConfig",
    "PregriddedFeatureSpec",
    "assert_placement_conservation",
    "check_disk_space",
    "compile_grid",
    "compile_pregridded",
    "estimate_grid_bytes",
    "get_strategy",
]
