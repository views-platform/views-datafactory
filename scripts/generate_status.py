#!/usr/bin/env python3
"""Generate a static HTML pipeline status page.

Usage:
    uv run python scripts/generate_status.py
    uv run python scripts/generate_status.py \
        --output data/status.html

Reads provenance ledgers and checks filesystem artifacts to produce
a source-by-stage matrix. Each cell shows whether the artifact
exists, is fresh (within SLO), stale, or missing. ADR-003, ADR-011.
"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from datafactory_provenance.health import SOURCE_SLO, read_last_entries
from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    get_all_features,
)

__all__ = [
    "ALL_STAGES",
    "SOURCE_STAGES",
    "StageArtifact",
    "check_stage",
    "generate_html",
]

ALL_STAGES = (
    "harvest", "consolidation", "viewpoint",
    "compilation", "assembly", "zarr",
)


@dataclass(frozen=True)
class StageArtifact:
    data_glob: str | None = None
    artifact: str | None = None
    ledger: str | None = None
    features: tuple[str, ...] = ()


def _source_features(name: str) -> tuple[str, ...]:
    src = [s for s in PIPELINE_SOURCES if s.name == name]
    return src[0].features if src else ()


_REPO_URL = (
    "https://github.com/views-platform/views-datafactory"
)

_SOURCE_CARDS: dict[str, str] = {
    "UCDP": "docs/sources/ucdp.md",
    "ACLED": "docs/sources/acled.md",
    "GHS-POP": "docs/sources/ghspop.md",
    "GHS-BUILT-S": "docs/sources/ghsbuilts.md",
    "V-Dem": "docs/sources/vdem.md",
    "PRIO-GRID Static": "docs/sources/priogrid_static.md",
    "GAUL Admin": "docs/sources/gaul_admin.md",
    "SHDI": "docs/sources/shdi.md",
}


def _get_latest_tag() -> str:
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            capture_output=True, text=True, timeout=5,
        )
        tags = result.stdout.strip().splitlines()
        if tags:
            return tags[0]
    except (subprocess.SubprocessError, IndexError):
        pass
    print(
        "Warning: no git tags found, "
        "data card links will point to main",
        file=sys.stderr,
    )
    return "main"


SOURCE_STAGES: dict[str, dict[str, StageArtifact | str | None]] = {
    "UCDP": {
        "harvest": StageArtifact(
            data_glob="raw/ucdp_annual/*.parquet",
            ledger="ucdp_annual/ingestion_ledger.jsonl",
        ),
        "consolidation": StageArtifact(
            artifact="consolidated/ucdp_store.parquet",
            ledger="consolidation/ledger.jsonl",
        ),
        "viewpoint": StageArtifact(
            artifact="viewpoint/production_parity.parquet",
            ledger="viewpoint/ledger.jsonl",
        ),
        "compilation": StageArtifact(
            artifact="compiled/grid.npy",
            ledger="compilation/ledger.jsonl",
        ),
        "assembly": StageArtifact(features=_source_features("UCDP Annual")),
        "zarr": StageArtifact(features=_source_features("UCDP Annual")),
    },
    "ACLED": {
        "harvest": StageArtifact(
            data_glob="raw/acled/*.parquet",
            ledger="acled/ingestion_ledger.jsonl",
        ),
        "consolidation": StageArtifact(
            artifact="consolidated/acled/acled_store.parquet",
            ledger="consolidation/acled_ledger.jsonl",
        ),
        "viewpoint": StageArtifact(
            artifact="viewpoint/acled_v1.parquet",
            ledger="viewpoint/acled_v1_ledger.jsonl",
        ),
        "compilation": StageArtifact(
            artifact="compiled/acled/grid.npy",
            ledger="compilation/acled_ledger.jsonl",
        ),
        "assembly": StageArtifact(features=_source_features("ACLED")),
        "zarr": StageArtifact(features=_source_features("ACLED")),
    },
    "GHS-POP": {
        "harvest": StageArtifact(
            data_glob="raw/ghspop/*.tif",
            ledger="ghspop/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": StageArtifact(
            artifact="viewpoint/ghspop_v1.parquet",
            ledger="viewpoint/ghspop_v1_ledger.jsonl",
        ),
        "compilation": StageArtifact(
            artifact="compiled/ghspop/grid.npy",
            ledger="compilation/ghspop_ledger.jsonl",
        ),
        "assembly": StageArtifact(
            features=_source_features("GHS-POP"),
        ),
        "zarr": StageArtifact(
            features=_source_features("GHS-POP"),
        ),
    },
    "GHS-BUILT-S": {
        "harvest": StageArtifact(
            data_glob="raw/ghsbuilts/*.tif",
            ledger="ghsbuilts/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": StageArtifact(
            artifact="viewpoint/ghsbuilts_v1.parquet",
            ledger="viewpoint/ghsbuilts_v1_ledger.jsonl",
        ),
        "compilation": StageArtifact(
            artifact="compiled/ghsbuilts/grid.npy",
            ledger="compilation/ghsbuilts_ledger.jsonl",
        ),
        "assembly": StageArtifact(
            features=_source_features("GHS-BUILT-S"),
        ),
        "zarr": StageArtifact(
            features=_source_features("GHS-BUILT-S"),
        ),
    },
    "V-Dem": {
        "harvest": StageArtifact(
            data_glob="raw/vdem/*.parquet",
            ledger="vdem/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": StageArtifact(
            artifact="viewpoint/vdem_v1.parquet",
            ledger="viewpoint/vdem_v1_ledger.jsonl",
        ),
        "compilation": StageArtifact(
            artifact="compiled/vdem/grid.npy",
            ledger="compilation/vdem_ledger.jsonl",
        ),
        "assembly": StageArtifact(
            features=_source_features("V-Dem"),
        ),
        "zarr": StageArtifact(
            features=_source_features("V-Dem"),
        ),
    },
    "PRIO-GRID Static": {
        "harvest": StageArtifact(
            data_glob="raw/priogrid_static/*.parquet",
            ledger="priogrid_static/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": None,
        "compilation": None,
        "assembly": StageArtifact(
            features=_source_features("PRIO-GRID Static"),
        ),
        "zarr": StageArtifact(
            features=_source_features("PRIO-GRID Static"),
        ),
    },
    "GAUL Admin": {
        "harvest": StageArtifact(
            data_glob="raw/gaul_admin/*.parquet",
            ledger="gaul_admin/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": None,
        "compilation": None,
        "assembly": StageArtifact(
            features=_source_features("GAUL Admin"),
        ),
        "zarr": StageArtifact(
            features=_source_features("GAUL Admin"),
        ),
    },
    "SHDI": {
        "harvest": StageArtifact(
            data_glob="raw/shdi/*.parquet",
            ledger="shdi/ingestion_ledger.jsonl",
        ),
        "consolidation": None,
        "viewpoint": "not_yet_integrated",
        "compilation": "not_yet_integrated",
        "assembly": "not_yet_integrated",
        "zarr": "not_yet_integrated",
    },
}


def check_stage(
    *,
    artifact: StageArtifact | str | None,
    data_dir: Path,
    provenance_dir: Path,
    now: datetime,
    slo_hours: int | None,
) -> dict:
    if artifact is None:
        return {"status": "not_applicable"}
    if isinstance(artifact, str):
        return {"status": artifact}

    present = False
    timestamp: str | None = None

    if artifact.data_glob is not None:
        matches = glob.glob(str(data_dir / artifact.data_glob))
        present = len(matches) > 0
    elif artifact.artifact is not None:
        present = (data_dir / artifact.artifact).exists()
    elif artifact.features:
        fn_path = data_dir / "assembled" / "feature_names.json"
        if fn_path.exists():
            names = json.loads(fn_path.read_text())
            present = all(f in names for f in artifact.features)
        else:
            present = False

    if artifact.ledger is not None:
        entries = read_last_entries(
            provenance_dir / artifact.ledger, n=1,
        )
        if entries:
            timestamp = entries[0].get("timestamp")

    if not present:
        return {
            "status": "missing",
            "timestamp": timestamp,
        }

    if timestamp and slo_hours is not None:
        try:
            ts = datetime.fromisoformat(timestamp)
            age_hours = (now - ts).total_seconds() / 3600
            if age_hours > slo_hours:
                return {
                    "status": "stale",
                    "timestamp": timestamp[:19],
                }
        except (ValueError, TypeError):
            pass

    return {
        "status": "ok",
        "timestamp": timestamp[:19] if timestamp else None,
    }


_LEGEND = (
    ("ok", "#2ecc40", "&#x25cf;", "OK"),
    ("stale", "#ffdc00", "&#x25cf;", "Stale"),
    ("missing", "#ff4136", "&#x25cf;", "Missing"),
    ("not_yet_integrated", "#ccc", "&#x25cb;", "Not yet integrated"),
    ("not_applicable", "#aaa", "&#x25cf;", "N/A"),
)

_STATUS_COLORS = {key: color for key, color, _, _ in _LEGEND}
_STATUS_SYMBOLS = {key: sym for key, _, sym, _ in _LEGEND}


def generate_html(
    results: dict[str, dict[str, dict]],
    now: datetime,
    tag: str = "main",
) -> str:
    n_features = len(get_all_features())
    ts = now.isoformat()[:19] + "Z"

    rows = ""
    for source, stages in results.items():
        cells = ""
        for stage in ALL_STAGES:
            cell = stages.get(stage, {"status": "not_applicable"})
            status = cell.get("status", "not_applicable")
            color = _STATUS_COLORS.get(status, "#aaa")
            symbol = _STATUS_SYMBOLS.get(status, "&mdash;")
            stamp = cell.get("timestamp", "")
            title = f"{status}: {stamp}" if stamp else status
            cells += (
                f'<td style="text-align:center" title="{title}">'
                f'<span style="color:{color};font-size:1.4em">'
                f"{symbol}</span>"
            )
            if stamp:
                cells += (
                    f'<br><small style="color:#666">'
                    f"{stamp[:10]}</small>"
                )
            cells += "</td>"
        card = _SOURCE_CARDS.get(source)
        if card:
            url = f"{_REPO_URL}/blob/{tag}/{card}"
            label = (
                f'<a href="{url}" style="color:inherit">'
                f"{source}</a>"
            )
        else:
            label = source
        rows += f"<tr><td><b>{label}</b></td>{cells}</tr>\n"

    headers = "".join(
        f"<th>{s.capitalize()}</th>" for s in ALL_STAGES
    )

    legend_items = []
    for _, color, sym, label in _LEGEND:
        legend_items.append(
            f'<span class="legend-item">'
            f'<span style="color:{color};font-size:1.2em">'
            f"{sym}</span> {label}</span>"
        )
    legend = "\n".join(legend_items)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VIEWS Data Factory — Pipeline Status</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2em; background: #fafafa; }}
h1 {{ margin-bottom: 0.2em; }}
.banner {{ color: #555; margin-bottom: 1.5em; }}
table {{ border-collapse: collapse; width: 100%; max-width: 900px; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; }}
th {{ background: #f0f0f0; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.legend {{ display: flex; gap: 1.5em; flex-wrap: wrap; }}
.legend-item {{ display: inline-flex; align-items: center; gap: 0.3em; }}
</style>
</head>
<body>
<h1>VIEWS Data Factory &mdash; Pipeline Status</h1>
<p class="banner">{n_features} features assembled &middot; Generated {ts}</p>
<table>
<tr><th>Source</th>{headers}</tr>
{rows}</table>
<div class="legend">
{legend}
</div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate pipeline status page",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data"),
    )
    parser.add_argument(
        "--provenance-dir", type=Path, default=Path("provenance"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("status.html"),
    )
    args = parser.parse_args()

    now = datetime.now(tz=UTC)
    results: dict[str, dict[str, dict]] = {}

    for source, stages in SOURCE_STAGES.items():
        slo = SOURCE_SLO.get(source)
        results[source] = {}
        for stage_name, sa in stages.items():
            results[source][stage_name] = check_stage(
                artifact=sa,
                data_dir=args.data_dir,
                provenance_dir=args.provenance_dir,
                now=now,
                slo_hours=slo,
            )

    tag = _get_latest_tag()
    html = generate_html(results, now, tag=tag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"Status page written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
