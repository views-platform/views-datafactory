"""Compilation node -- places source data onto the spatiotemporal grid.

Reads harvester/synthetic outputs as files. Produces populated npy arrays.
Tracks provenance: source digests + compilation config -> output digest.
"""

from datafactory_compilation.aggregation import get_strategy
from datafactory_compilation.compilation_config import CompilationConfig
from datafactory_compilation.grid_compilation import compile_grid

__all__ = [
    "CompilationConfig",
    "compile_grid",
    "get_strategy",
]
