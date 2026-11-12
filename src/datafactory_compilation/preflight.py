"""Pre-flight checks for compilation.

Validates disk space before allocating memory-mapped output grids,
and refuses configurations that would silently discard an upstream
allocation. Both fail loudly with actionable messages rather than
producing a cryptic error or a plausible wrong answer.

Ref: ADR-037 (bounded-memory compilation), ADR-003 (declared
semantics beat inferred ones), views-datafactory#552.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def estimate_grid_bytes(
    n_months: int,
    n_features: int,
    *,
    height: int = 360,
    width: int = 720,
    dtype_bytes: int = 4,
) -> int:
    """Estimate output grid size in bytes."""
    return n_months * height * width * n_features * dtype_bytes


def check_disk_space(
    output_dir: Path,
    required_bytes: int,
    *,
    margin: float = 1.2,
) -> None:
    """Fail loudly if insufficient disk space for compilation output.

    Args:
        output_dir: Directory where output will be written.
        required_bytes: Estimated output size in bytes.
        margin: Safety margin multiplier (default 1.2 = 20%).

    Raises:
        RuntimeError: If free space < required_bytes * margin.
    """
    free = shutil.disk_usage(output_dir).free
    needed = int(required_bytes * margin)
    if free < needed:
        raise RuntimeError(
            f"Insufficient disk space in {output_dir}: "
            f"need {needed / 1e9:.1f} GB "
            f"(including {int((margin - 1) * 100)}% margin), "
            f"have {free / 1e9:.1f} GB free. "
            f"Free up space or reduce feature count."
        )
    logger.info(
        "Disk space OK: %.1f GB free, %.1f GB needed",
        free / 1e9,
        required_bytes / 1e9,
    )

#: The column the temporal allocator writes its decision to. A source
#: carrying this column has been through temporal allocation, so binding
#: a compile to any other date column discards that allocation.
ALLOCATED_MONTH_FIELD = "date_month"


def reject_ignored_allocation(
    source: Path, date_field: str
) -> str | None:
    """Refuse to compile allocated data bound to a raw date column.

    ``temporal_distribution`` writes its decision to ``date_month`` and
    leaves ``date_start``/``date_end`` untouched. Compiling such a
    source on ``date_start`` collapses every distributed month back onto
    the event's start month, conserves totals while doing it, and
    reports success -- the temporal twin of the spatial defect that
    discarded the placement of 26.49% of UCDP fatality mass.

    ``CompilationConfig.date_field`` still defaults to ``date_start``
    because the class ships in the wheel and removing the default is a
    breaking change owed to a MAJOR release. This stands in for that at
    the entry points which compile allocated data.

    Reads the parquet schema only, never the data.

    Args:
        source: Parquet the compile will read.
        date_field: Column the compile is bound to.

    Returns:
        A message to print and refuse on, or ``None`` when the
        configuration is sound.
    """
    import pyarrow.parquet as pq

    if ALLOCATED_MONTH_FIELD not in set(pq.read_schema(source).names):
        return None
    if date_field == ALLOCATED_MONTH_FIELD:
        return None
    return (
        f"FAIL: {source} carries '{ALLOCATED_MONTH_FIELD}', so it has "
        f"been temporally allocated, but this compile is bound to "
        f"'{date_field}'.\n"
        f"       Every distributed month would collapse onto its "
        f"event's '{date_field}' value, totals would still conserve, "
        f"and the run would report success.\n"
        f"       Use date_field='{ALLOCATED_MONTH_FIELD}', or point the "
        f"source at a pre-allocation parquet."
    )
