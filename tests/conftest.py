"""Shared test fixtures and data factories."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register gated test CLI options."""
    parser.addoption(
        "--run-falsification",
        action="store_true",
        default=False,
        help="Show falsification stubs (skipped by default)",
    )
    parser.addoption(
        "--run-consumer",
        action="store_true",
        default=False,
        help="Run consumer parity tests (skipped by default)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],
) -> None:
    """Deselect gated markers unless their flag is passed."""
    run_falsification = config.getoption("--run-falsification")
    run_consumer = config.getoption("--run-consumer")
    kept: list[pytest.Item] = []
    for item in items:
        if "falsification" in item.keywords and not run_falsification:
            continue
        if "consumer" in item.keywords and not run_consumer:
            continue
        kept.append(item)
    items[:] = kept


def make_ucdp_event(
    event_id: int = 1,
    *,
    source_type: str = "annual",
    source_version: str = "25.1",
    date_start: str = "2023-06-15",
    date_end: str | None = None,
    date_prec: int = 1,
    best: int = 10,
    low: int = 5,
    high: int = 15,
    latitude: float = 4.0,
    longitude: float = 31.5,
    priogrid_gid: int | None = None,
    type_of_violence: int = 1,
    where_prec: int = 1,
) -> dict:
    """Create a single UCDP-like event dict with consolidation metadata.

    Shared factory for viewpoint, consolidation, and compiler tests.
    """
    ev: dict = {
        "id": event_id,
        "country_id": 200,
        "country": "Sudan",
        "latitude": latitude,
        "longitude": longitude,
        "date_start": date_start,
        "date_end": date_end or date_start,
        "date_prec": date_prec,
        "best": best,
        "low": low,
        "high": high,
        "type_of_violence": type_of_violence,
        "where_prec": where_prec,
        "_source_type": source_type,
        "_source_version": source_version,
        "_ingested_at": "2026-03-21T10:00:00Z",
    }
    if priogrid_gid is not None:
        ev["priogrid_gid"] = priogrid_gid
    return ev


def write_test_parquet(path: Path, events: list[dict]) -> Path:
    """Write events to a Parquet file. Shared across test modules."""
    if not events:
        table = pa.table({
            "id": pa.array([], type=pa.int64()),
            "latitude": pa.array([], type=pa.float64()),
            "longitude": pa.array([], type=pa.float64()),
            "date_start": pa.array([], type=pa.string()),
            "best": pa.array([], type=pa.int64()),
        })
    else:
        all_fields = sorted({k for ev in events for k in ev})
        columns = {
            f: [ev.get(f) for ev in events] for f in all_fields
        }
        pa_columns = {
            n: pa.array(v, from_pandas=True)
            for n, v in columns.items()
        }
        table = pa.table(pa_columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


@pytest.fixture(autouse=True)
def _clean_source_registry() -> None:  # type: ignore[misc]
    """Reset source registry after each test, then re-register built-in sources.

    Prevents test-registered sources from polluting other tests while
    keeping auto-registered sources (ucdp_annual, ucdp_candidate) available.
    """
    yield  # type: ignore[misc]
    # Save built-in sources (registered at import time)
    # and only clear if test sources were added
    import datafactory_harvester.sources.acled  # noqa: F401
    import datafactory_harvester.sources.priogrid_static  # noqa: F401
    import datafactory_harvester.sources.ucdp_annual  # noqa: F401
    import datafactory_harvester.sources.ucdp_candidate  # noqa: F401
    import datafactory_harvester.sources.ucdp_dot9  # noqa: F401
    from datafactory_harvester.sources import _SOURCES

    # Remove any test-registered sources by keeping only known ones
    known = {
        "acled", "ucdp_annual", "ucdp_candidate", "ucdp_dot9",
        "priogrid_static",
    }
    test_sources = set(_SOURCES.keys()) - known
    for name in test_sources:
        del _SOURCES[name]
