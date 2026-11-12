"""Shared output writing for compilation modules."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from datafactory_provenance import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_file_digest,
)

logger = logging.getLogger(__name__)


def write_compilation_output(
    *,
    grid_array: np.ndarray,
    pgids_2d: np.ndarray,
    time_steps: np.ndarray,
    feature_names: list[str],
    output_dir: Path,
    ledger_path: Path,
    dataset_id: str,
    source_path: Path,
    source_digest: str,
    n_placed: int | None = None,
    n_skipped_spatial: int | None = None,
    n_skipped_temporal: int | None = None,
    placement: dict[str, Any] | None = None,
) -> str:
    """Write grid output files, provenance, and ledger entry.

    The three n_* parameters are pregridded-compilation diagnostics.
    They are included in the ledger entry only when not None.

    ``placement`` records which columns decided each event's cell and
    month, and goes into ``provenance.json`` so the artifact says how
    it was produced. This matters more here than it usually would: a
    grid whose events were placed from stale coordinates instead of
    their declared cells is **indistinguishable from a correct one by
    any total** -- country sums, coverage counts and conservation all
    reconcile either way. Without this, nothing on disk answers "was
    the declaration honoured when this was built?".

    It is deliberately not added to the ledger entry: the rule at
    ``digests_and_ledgers`` is to bump ``LEDGER_VERSION`` on a ledger
    schema change, and that constant is shared with the viewpoint
    builders, so an additive field in one layer would version every
    ledger in the platform.

    Returns the output digest string.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    grid_path = output_dir / "grid.npy"
    np.save(grid_path, grid_array)
    np.save(output_dir / "pgids.npy", pgids_2d)
    np.save(output_dir / "time_steps.npy", time_steps)
    (output_dir / "feature_names.json").write_text(
        json.dumps(feature_names)
    )

    output_digest = compute_file_digest(grid_path)

    provenance: dict[str, Any] = {
        "source_path": str(source_path),
        "source_digest": source_digest,
        "grid_shape": list(grid_array.shape),
        "feature_names": feature_names,
        "output_digest": output_digest,
    }
    if placement is not None:
        provenance["placement"] = placement
    provenance_path = output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2))

    ledger_entry: dict[str, Any] = {
        "dataset": dataset_id,
        "source_path": str(source_path),
        "source_digest": source_digest,
        "grid_shape": list(grid_array.shape),
        "feature_names": feature_names,
        "output_dir": str(output_dir),
        "output_digest": output_digest,
        "ledger_version": LEDGER_VERSION,
        "digest_algorithm": DIGEST_SCHEME,
    }
    if n_placed is not None:
        ledger_entry["n_placed"] = n_placed
    if n_skipped_spatial is not None:
        ledger_entry["n_skipped_spatial"] = n_skipped_spatial
    if n_skipped_temporal is not None:
        ledger_entry["n_skipped_temporal"] = n_skipped_temporal
    append_ledger_entry(ledger_path, ledger_entry)

    return output_digest
