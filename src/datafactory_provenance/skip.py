"""Content-addressed skip decisions for assembly and export.

Encapsulates the logic for deciding whether a pipeline step can be
skipped because its inputs haven't changed since the last successful
run. Each function reads the previous provenance record, compares
digests, and returns a SkipVerdict that callers use for control flow.

No outbound imports to other datafactory_* packages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from datafactory_provenance.digests_and_ledgers import compute_file_digest

__all__ = [
    "SkipVerdict",
    "check_assembly_skip",
    "check_export_skip",
]


@dataclass(frozen=True)
class SkipVerdict:
    """Result of a content-addressed skip check."""

    should_skip: bool
    reason: str
    changed_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]
    output_valid: bool


def check_assembly_skip(
    current_digests: dict[str, str],
    provenance_path: Path,
    output_path: Path,
    *,
    sources_key: str = "sources",
    output_digest_key: str = "output_digest",
) -> SkipVerdict:
    """Decide whether assembly can be skipped.

    Compares *current_digests* (caller-computed input digests) against
    the previous run's provenance record and verifies that the output
    file's content still matches the recorded output digest.

    Args:
        current_digests: Map of digest keys to hex digest strings
            for the current inputs (e.g. ``{"ucdp_digest": "ab12..."}``).
        provenance_path: Path to the previous run's provenance.json.
        output_path: Path to the output file (e.g. grid.npy) whose
            integrity is verified on the skip path.
        sources_key: Key in provenance JSON holding the sources dict.
        output_digest_key: Key in provenance JSON holding the output digest.

    Returns:
        A SkipVerdict describing whether to skip and why.
    """
    if not provenance_path.exists() or not output_path.exists():
        return SkipVerdict(
            should_skip=False,
            reason="no previous run (provenance or output missing)",
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    prov = json.loads(provenance_path.read_text())
    prev_sources = prov.get(sources_key, {})

    prev_digest_keys = {
        k for k in prev_sources
        if k.endswith("_digest") and prev_sources[k] is not None
    }
    current_keys = set(current_digests.keys())

    missing = tuple(sorted(prev_digest_keys - current_keys))
    added = tuple(sorted(current_keys - prev_digest_keys))

    if missing or added:
        return SkipVerdict(
            should_skip=False,
            reason=(
                f"source set changed: "
                f"missing={missing}, added={added}"
            ),
            changed_keys=added,
            missing_keys=missing,
            output_valid=True,
        )

    changed = tuple(sorted(
        k for k, v in current_digests.items()
        if prev_sources.get(k) != v
    ))

    if changed:
        return SkipVerdict(
            should_skip=False,
            reason=f"input digests differ: {changed}",
            changed_keys=changed,
            missing_keys=(),
            output_valid=True,
        )

    recorded_output = prov.get(output_digest_key)
    actual_output = compute_file_digest(output_path)
    output_valid = recorded_output is not None and actual_output == recorded_output

    if not output_valid:
        return SkipVerdict(
            should_skip=False,
            reason=(
                f"output integrity check failed: "
                f"recorded={recorded_output}, actual={actual_output}"
            ),
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    return SkipVerdict(
        should_skip=True,
        reason="all input digests match and output is intact",
        changed_keys=(),
        missing_keys=(),
        output_valid=True,
    )


def check_export_skip(
    provenance_path: Path,
    export_path: Path,
    digest_attr: str = "source_digest",
    *,
    output_digest_key: str = "output_digest",
) -> SkipVerdict:
    """Decide whether an export can be skipped.

    Compares the assembly output digest recorded in provenance against
    the digest stored in the export artifact's metadata.

    Args:
        provenance_path: Path to provenance.json from assembly.
        export_path: Path to the export artifact (e.g. zarr store
            directory). Must contain a ``.zattrs`` file with the
            stored digest.
        digest_attr: Key in ``.zattrs`` holding the stored digest.
        output_digest_key: Key in provenance JSON holding the
            assembly output digest.

    Returns:
        A SkipVerdict describing whether to skip and why.
    """
    zattrs_path = export_path / ".zattrs"

    if not provenance_path.exists() or not export_path.exists():
        return SkipVerdict(
            should_skip=False,
            reason="no previous run (provenance or export missing)",
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    if not zattrs_path.exists():
        return SkipVerdict(
            should_skip=False,
            reason="export has no .zattrs metadata",
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    prov = json.loads(provenance_path.read_text())
    assembly_digest = prov.get(output_digest_key)

    attrs = json.loads(zattrs_path.read_text())
    export_digest = attrs.get(digest_attr)

    if not assembly_digest or not export_digest:
        return SkipVerdict(
            should_skip=False,
            reason="digest not recorded in provenance or export",
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    if assembly_digest != export_digest:
        return SkipVerdict(
            should_skip=False,
            reason=(
                f"digest mismatch: "
                f"assembly={assembly_digest}, export={export_digest}"
            ),
            changed_keys=(),
            missing_keys=(),
            output_valid=False,
        )

    return SkipVerdict(
        should_skip=True,
        reason="export digest matches assembly output",
        changed_keys=(),
        missing_keys=(),
        output_valid=True,
    )
