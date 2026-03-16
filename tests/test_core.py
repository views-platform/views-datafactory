"""Smoke tests for views-datafactory package structure."""

from datafactory_compiler import __all__ as compiler_all
from datafactory_core import __all__ as core_all
from datafactory_core import __version__
from datafactory_grid import __all__ as grid_all
from datafactory_harvester import __all__ as harvester_all
from datafactory_synthetic import __all__ as synthetic_all


def test_version():
    assert __version__ == "0.1.0"


def test_subpackages_importable():
    for exports in (core_all, grid_all, harvester_all, compiler_all, synthetic_all):
        assert isinstance(exports, list)
