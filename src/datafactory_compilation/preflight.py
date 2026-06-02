"""Pre-flight resource checks for compilation.

Validates disk space before allocating memory-mapped output grids.
Prevents cryptic ENOSPC errors by failing loudly with actionable
messages.

Ref: ADR-037 (bounded-memory compilation).
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
