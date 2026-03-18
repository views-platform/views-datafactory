"""Compilation node -- places source data onto the spatiotemporal grid.

Reads harvester/synthetic outputs as files. Produces populated npy arrays.
Tracks provenance: source digests + compilation config -> output digest.
"""

from datafactory_compiler.compiler import compile_grid
from datafactory_compiler.config import CompilationConfig
from datafactory_compiler.strategies import get_strategy

__all__ = [
    "CompilationConfig",
    "compile_grid",
    "get_strategy",
]
