"""Smoke tests for views-datafactory package structure."""

from __future__ import annotations

from importlib.metadata import version

from datafactory_compilation import __all__ as compilation_all
from datafactory_consolidation import __all__ as consolidation_all
from datafactory_harvester import __all__ as harvester_all
from datafactory_priogrid import __all__ as priogrid_all
from datafactory_provenance import __all__ as provenance_all
from datafactory_provenance import __version__
from datafactory_synthetic import __all__ as synthetic_all
from datafactory_viewpoint import __all__ as viewpoint_all


def test_version_matches_metadata() -> None:
    """__version__ must match pyproject.toml (single source of truth)."""
    assert __version__ == version("views-datafactory")


def test_subpackages_importable() -> None:
    for exports in (
        provenance_all,
        priogrid_all,
        harvester_all,
        consolidation_all,
        viewpoint_all,
        compilation_all,
        synthetic_all,
    ):
        assert isinstance(exports, list)
