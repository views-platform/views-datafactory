"""Smoke tests for views-datafactory package structure."""

from __future__ import annotations

from importlib.metadata import version

from datafactory_compiler import __all__ as compiler_all
from datafactory_core import __all__ as core_all
from datafactory_core import __version__
from datafactory_grid import __all__ as grid_all
from datafactory_harvester import __all__ as harvester_all
from datafactory_synthetic import __all__ as synthetic_all


def test_version_matches_metadata() -> None:
    """__version__ must match pyproject.toml (single source of truth)."""
    assert __version__ == version("views-datafactory")


def test_subpackages_importable() -> None:
    for exports in (core_all, grid_all, harvester_all, compiler_all, synthetic_all):
        assert isinstance(exports, list)
