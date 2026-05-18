#!/usr/bin/env python3
"""Generate schema reference from actual smoke test data.

Usage:
    uv run python scripts/generate_schema_ref.py

Reads Parquet files from data/raw/ and generates
reports/schema_reference.md. Always accurate — generated from
real data, not manually maintained.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq


def _schema_table(table: pq.lib.Table, label: str) -> str:
    """Generate a markdown table describing a Parquet schema."""
    lines = [
        f"### {label} ({table.num_rows:,} rows, "
        f"{len(table.column_names)} columns)",
        "",
        "| Column | Type | Nulls | Sample |",
        "|--------|------|-------|--------|",
    ]
    for name in sorted(table.column_names):
        col = table.column(name)
        pa_type = table.schema.field(name).type
        null_count = col.null_count
        # Sample: first non-null value
        values = col.to_pylist()
        sample = next(
            (str(v)[:40] for v in values if v is not None), "—"
        )
        lines.append(
            f"| `{name}` | {pa_type} | {null_count:,} | {sample} |"
        )
    lines.append("")
    return "\n".join(lines)


def _drift_check(
    tables: dict[str, pq.lib.Table],
) -> str:
    """Compare column sets across tables, flag differences."""
    lines = ["## Schema Drift Check", ""]
    names = list(tables.keys())
    base_name = names[0]
    base_cols = set(tables[base_name].column_names)

    all_match = True
    for name in names[1:]:
        other_cols = set(tables[name].column_names)
        only_base = base_cols - other_cols
        only_other = other_cols - base_cols
        if only_base or only_other:
            all_match = False
            if only_base:
                lines.append(
                    f"- Columns in **{base_name}** but not "
                    f"**{name}**: `{sorted(only_base)}`"
                )
            if only_other:
                lines.append(
                    f"- Columns in **{name}** but not "
                    f"**{base_name}**: `{sorted(only_other)}`"
                )

    if all_match:
        lines.append(
            f"All {len(tables)} datasets share identical "
            f"column sets ({len(base_cols)} columns)."
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Generate schema reference from smoke test data."""
    data_dir = Path("data/raw")
    output_path = Path("reports/schema_reference.md")

    # Discover available data files
    datasets: dict[str, Path] = {}

    annual_files = sorted(
        (data_dir / "ucdp_annual").glob("*.parquet")
    )
    if annual_files:
        datasets["Annual (v25.1)"] = annual_files[0]

    candidate_files = sorted(
        (data_dir / "ucdp_candidate").glob("*.parquet")
    )
    if candidate_files:
        datasets["Candidate (first)"] = candidate_files[0]

    dot9_files = sorted(
        (data_dir / "ucdp_dot9").glob("*.parquet")
    )
    if dot9_files:
        datasets[".9 (25.9.11)"] = dot9_files[0]

    consolidated = data_dir / "consolidated" / "ucdp_store.parquet"
    if consolidated.exists():
        datasets["Consolidated store"] = consolidated

    viewpoint = data_dir / "viewpoint" / "ucdp_v1.parquet"
    if viewpoint.exists():
        datasets["Viewpoint output"] = viewpoint

    if not datasets:
        print("No data files found in data/raw/")
        print("Harvest data first:")
        print("  uv run python scripts/harvest_ucdp.py")
        return 1

    # Load all tables
    tables = {name: pq.read_table(path) for name, path in datasets.items()}

    # Generate reference
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Schema Reference (Generated)",
        "",
        f"*Auto-generated on {now}*",
        "*Do not edit — regenerate with: "
        "`uv run python scripts/generate_schema_ref.py`*",
        "",
        f"**Datasets examined:** {len(datasets)}",
        "",
        "---",
        "",
    ]

    # UCDP source schemas (annual, candidate, .9)
    source_tables = {}
    for name in ["Annual (v25.1)", "Candidate (first)", ".9 (25.9.11)"]:
        if name in tables:
            lines.append(_schema_table(tables[name], name))
            source_tables[name] = tables[name]

    # Drift check across UCDP sources
    if len(source_tables) > 1:
        lines.append(_drift_check(source_tables))
        lines.append("---\n")

    # Consolidated store
    if "Consolidated store" in tables:
        lines.append(
            _schema_table(tables["Consolidated store"], "Consolidated Store")
        )

        # Highlight metadata columns
        cons_cols = set(tables["Consolidated store"].column_names)
        if source_tables:
            first_source = next(iter(source_tables.values()))
            src_cols = set(first_source.column_names)
            meta_cols = sorted(cons_cols - src_cols)
            if meta_cols:
                lines.append(
                    f"**Consolidation metadata columns "
                    f"({len(meta_cols)}):** "
                    f"`{'`, `'.join(meta_cols)}`\n"
                )
        lines.append("---\n")

    # Viewpoint output
    if "Viewpoint output" in tables:
        lines.append(
            _schema_table(tables["Viewpoint output"], "Viewpoint Output")
        )

        # Highlight what changed vs consolidated
        if "Consolidated store" in tables:
            vp_cols = set(tables["Viewpoint output"].column_names)
            cons_cols = set(
                tables["Consolidated store"].column_names
            )
            added = sorted(vp_cols - cons_cols)
            removed = sorted(cons_cols - vp_cols)
            if added:
                lines.append(
                    f"**Added by viewpoint:** `{'`, `'.join(added)}`"
                )
            if removed:
                lines.append(
                    f"**Stripped by viewpoint:** "
                    f"`{'`, `'.join(removed)}`"
                )
            lines.append("")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Schema reference written to {output_path}")
    print(f"  Datasets: {len(datasets)}")
    for name, path in datasets.items():
        t = tables[name]
        print(
            f"    {name}: {t.num_rows:,} rows, "
            f"{len(t.column_names)} cols — {path}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
