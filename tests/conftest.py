"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_source_registry() -> None:  # type: ignore[misc]
    """Reset source registry after each test, then re-register built-in sources.

    Prevents test-registered sources from polluting other tests while
    keeping auto-registered sources (ucdp_annual, ucdp_candidate) available.
    """
    yield  # type: ignore[misc]
    # Save built-in sources (registered at import time)
    # and only clear if test sources were added
    import datafactory_harvester.sources.ucdp_annual  # noqa: F401
    import datafactory_harvester.sources.ucdp_candidate  # noqa: F401
    import datafactory_harvester.sources.ucdp_dot9  # noqa: F401
    from datafactory_harvester.sources import _SOURCES

    # Remove any test-registered sources by keeping only known ones
    known = {"ucdp_annual", "ucdp_candidate", "ucdp_dot9"}
    test_sources = set(_SOURCES.keys()) - known
    for name in test_sources:
        del _SOURCES[name]
