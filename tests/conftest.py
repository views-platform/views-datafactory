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


#: Marker -> the flag that includes it. Gated markers are withheld from
#: a default run; the flag is what a reader needs in order to get the
#: coverage back, so it is reported alongside the count.
_GATED_MARKERS: dict[str, str] = {
    "falsification": "--run-falsification",
    "consumer": "--run-consumer",
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],
) -> None:
    """Deselect gated markers unless their flag is passed.

    **Why this now reports.** Until 2026-11-12 the removed items simply
    vanished: they were dropped from ``items`` without telling pytest,
    so they did not appear in the run's counts at all -- not as passed,
    not as failed, not even as skipped. Two whole markers of coverage
    were withheld and no line of output said so. That is the same class
    of failure as the defect epic #547 exists to fix: coverage that
    stops happening and leaves no trace.

    ``pytest_deselected`` is the hook pytest provides for exactly this,
    and calling it makes the items appear as *deselected* in the
    summary. ``pytest_terminal_summary`` below then names the count and
    the flag that would include them (#554).
    """
    withheld: dict[str, list[pytest.Item]] = {
        marker: [] for marker in _GATED_MARKERS
    }
    kept: list[pytest.Item] = []
    for item in items:
        for marker, flag in _GATED_MARKERS.items():
            if marker in item.keywords and not config.getoption(flag):
                withheld[marker].append(item)
                break
        else:
            kept.append(item)
    items[:] = kept

    removed = [item for group in withheld.values() for item in group]
    if removed:
        config.hook.pytest_deselected(items=removed)

    # Read back by pytest_terminal_summary. Stashed on config because
    # that is the object both hooks are handed.
    config.stash[_WITHHELD] = {
        marker: len(group)
        for marker, group in withheld.items()
        if group
    }


_WITHHELD: pytest.StashKey[dict[str, int]] = pytest.StashKey()


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Say out loud how much coverage this run withheld, and how to get it.

    One line per gated marker. A reader of CI output can now see that
    coverage was withheld deliberately, rather than having to know that
    ``conftest.py`` removes two markers and that no workflow passes
    either flag.
    """
    counts = config.stash.get(_WITHHELD, {})
    if not counts:
        return
    terminalreporter.write_sep("-", "coverage withheld by marker")
    for marker, count in sorted(counts.items()):
        terminalreporter.write_line(
            f"{count} {marker} test(s) deselected -- pass "
            f"{_GATED_MARKERS[marker]} to run them"
        )


def load_synthetic_generator():  # type: ignore[no-untyped-def]
    """Import ``scripts/generate_synthetic_data.py`` as a module.

    ``scripts/`` is not a package, so it cannot be imported by name.
    ``tests/test_synthetic_pipeline.py`` has loaded it this way since
    the synthetic path was built; it now has three callers, which is
    why the loader lives here rather than being copied a third time.

    Exposing the generator to tests is deliberate: its planted
    constants are the expected answers, so a test asserts against the
    same numbers the fixture was written from rather than against a
    golden file on disk.
    """
    import importlib.util

    path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "generate_synthetic_data.py"
    )
    spec = importlib.util.spec_from_file_location(
        "generate_synthetic_data", path,
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


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
    import datafactory_harvester.sources.ghsbuilts  # noqa: F401
    import datafactory_harvester.sources.ghspop  # noqa: F401
    import datafactory_harvester.sources.priogrid_static  # noqa: F401
    import datafactory_harvester.sources.shdi  # noqa: F401
    import datafactory_harvester.sources.ucdp_annual  # noqa: F401
    import datafactory_harvester.sources.ucdp_candidate  # noqa: F401
    import datafactory_harvester.sources.ucdp_dot9  # noqa: F401
    import datafactory_harvester.sources.vdem  # noqa: F401
    from datafactory_harvester.sources import _SOURCES

    # Remove any test-registered sources by keeping only known ones
    known = {
        "acled", "ghsbuilts", "ghspop", "shdi", "ucdp_annual",
        "ucdp_candidate", "ucdp_dot9", "priogrid_static",
        "vdem",
    }
    test_sources = set(_SOURCES.keys()) - known
    for name in test_sources:
        del _SOURCES[name]
