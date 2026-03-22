"""Compilation node -- places event data onto the spatiotemporal grid.

Reads viewpoint output as files. Produces populated npy arrays.
Tracks provenance: source digests + compilation config -> output digest.
"""

from datafactory_compilation.aggregation import get_strategy
from datafactory_compilation.compilation_config import (
    CompilationConfig,
    FeatureSpec,
)
from datafactory_compilation.grid_compilation import compile_grid

__all__ = [
    "CompilationConfig",
    "FeatureSpec",
    "compile_grid",
    "get_strategy",
]
