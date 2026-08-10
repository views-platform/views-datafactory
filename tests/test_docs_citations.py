"""Guards: documentation must cite code that exists, by name not by line.

The base-docs audit (2026-08-02) found the same failure repeatedly: docs
describing a world that had changed underneath them.

- Ten ``file.py:NNN`` citations across the ADRs. Three pointed at blank
  lines or the wrong construct — ADR-026 cited ``ucdp_annual.py:132-142``
  for ``get_ucdp_token()`` and line 132 had become empty. Line numbers
  rot on the next edit and nothing notices; views-frames reached the same
  conclusion and switched to names (their #212).
- ADR-006 and ADR-010 cited ``lab_grid/``, a package **views-metric-lab
  deleted** in their commit 6e1a34d. Neither repository noticed.
- A CIC cited ``tests/test_grid_to_country_month.py``; the file is
  ``tests/test_country_month.py``.

These guards make the class of error detectable rather than relying on
someone reading 88 documents again.

Deliberately NOT enforced here: that every referenced path exists. Docs
legitimately reference generated artifacts (``feature_names.json``),
files in sibling repositories (``config_queryset.py`` in views-models),
and files whose absence is the point (ADR-026 says ``credentials.toml``
must not exist). A guard that cannot tell those apart would either be
noise or would teach people to delete true references — which is the
mistake this audit nearly made about ``audit_data_parity.py``, a file
that does exist, in another repo.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

DOCS = Path("docs")
SEARCH_ROOTS = (
    "",
    "src/",
    "scripts/",
    "tests/",
    "src/datafactory_harvester/",
    "src/datafactory_harvester/sources/",
    "src/datafactory_viewpoint/",
    "src/datafactory_consolidation/",
    "src/datafactory_compilation/",
    "src/datafactory_provenance/",
    "src/datafactory_priogrid/",
    "src/datafactory_adapters/",
    "src/datafactory_query/",
    "src/datafactory_http/",
)

# file.py:123 or file.py:123-456 — and file.sh:123 since 2026-08-10.
#
# `.sh` was added because two shell citations rotted unseen for exactly
# as long as this pattern said ".py" only: ADR-018 cited a line range in
# refresh_pipeline.sh that had drifted ~55 lines, and ADR-051 cited
# three line numbers of which one had never been right. A guard whose
# scope is narrower than the drift it is meant to catch reports success
# while checking nothing (C-336). Both were fixed in the same PR that
# widened this, so it starts green.
LINE_CITATION = re.compile(r"[A-Za-z0-9_/]+\.(?:py|sh):\d+(?:[-–]\d+)?")


def _markdown_files() -> list[Path]:
    return sorted(DOCS.rglob("*.md"))


class TestNoLineNumberCitations:
    """Cite code by symbol name; line numbers rot silently."""

    def test_no_line_number_citations_in_docs(self) -> None:
        offenders: dict[str, list[str]] = {}
        for doc in _markdown_files():
            hits = LINE_CITATION.findall(doc.read_text())
            if hits:
                offenders[str(doc)] = sorted(set(hits))
        assert not offenders, (
            "Documentation cites code by line number. Line numbers go "
            "stale on the next edit to the file and nothing detects it — "
            "three of the ten citations this guard replaced already "
            "pointed at blank lines. Cite the symbol instead:\n"
            "  BAD   `ucdp_annual.py:132-142`\n"
            "  GOOD  `get_ucdp_token()` in `ucdp_annual.py`\n"
            + "\n".join(f"  {f}: {h}" for f, h in offenders.items())
        )


class TestCitedTestFilesExist:
    """A CIC's Test Alignment table is a promise about what is covered.

    Pointing at a test file that does not exist claims coverage that
    cannot be checked. Found in this audit: a CIC cited
    ``tests/test_grid_to_country_month.py``; the real file is
    ``tests/test_country_month.py``. Two more wrong citations were caught
    in the load_dataset CIC *while writing it*, which is a fair
    illustration of how easily this happens.
    """

    def test_referenced_test_files_exist(self) -> None:
        pattern = re.compile(r"`(tests/[A-Za-z0-9_/]+\.py)(?:::[A-Za-z0-9_]+)?`")
        missing: dict[str, list[str]] = {}
        for doc in _markdown_files():
            bad = [
                m for m in sorted(set(pattern.findall(doc.read_text())))
                if not Path(m).exists()
            ]
            if bad:
                missing[str(doc)] = bad
        assert not missing, (
            "Docs reference test files that do not exist. A Test "
            "Alignment table naming a missing file asserts coverage "
            "nobody can verify:\n"
            + "\n".join(f"  {f}: {b}" for f, b in missing.items())
        )


class TestCitedSymbolsExist:
    """Symbols cited as ``name()`` in ``file.py`` must be defined there."""

    @staticmethod
    def _resolve(filename: str) -> Path | None:
        for root in SEARCH_ROOTS:
            candidate = Path(root + filename)
            if candidate.exists():
                return candidate
        return None

    def test_symbol_in_file_citations_resolve(self) -> None:
        # Matches: `some_symbol()` in `path/to/file.py`
        pattern = re.compile(
            r"`([A-Za-z_][A-Za-z0-9_]*)\(\)`\s+in\s+`([A-Za-z0-9_/]+\.py)`"
        )
        broken: list[str] = []
        for doc in _markdown_files():
            for symbol, filename in pattern.findall(doc.read_text()):
                path = self._resolve(filename)
                if path is None:
                    broken.append(f"{doc}: {filename} not found")
                    continue
                try:
                    tree = ast.parse(path.read_text())
                except SyntaxError:  # pragma: no cover - unparseable source
                    continue
                names = {
                    n.name
                    for n in ast.walk(tree)
                    if isinstance(
                        n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                }
                if symbol not in names:
                    broken.append(
                        f"{doc}: `{symbol}()` is not defined in {path}"
                    )
        assert not broken, (
            "Docs cite symbols that are not defined where the doc says "
            "they are. This is the line-number problem wearing a better "
            "disguise — the citation looks durable but the symbol moved "
            "or was renamed:\n" + "\n".join(f"  {b}" for b in broken)
        )


class TestPublicEntryPointHasAContract:
    """ADR-006 requires a CIC for anything downstream models consume.

    ``load_dataset`` is the primary consumer entry point and the surface
    ADR-050 declares a public contract. It had no CIC until 2026-08-02
    while 32 config dataclasses did — the contracts had been written for
    the classes that were easy to describe rather than the ones most
    depended upon.
    """

    def test_load_dataset_cic_exists_and_is_substantive(self) -> None:
        cic = DOCS / "CICs" / "load_dataset.md"
        assert cic.exists(), (
            "docs/CICs/load_dataset.md is missing. load_dataset is the "
            "public consumer contract (ADR-050) and meets ADR-006's "
            "criterion for a required intent contract."
        )
        body = cic.read_text()
        for section in ("## 1. Purpose", "## 2. Non-Goals", "## 6. Failure Modes"):
            assert section in body, f"load_dataset CIC is missing {section!r}"

    def test_cic_documents_the_storage_options_seam(self) -> None:
        """Added in v1.10.0 (#394); the contract must know about it."""
        body = (DOCS / "CICs" / "load_dataset.md").read_text()
        assert "storage_options" in body, (
            "The load_dataset CIC does not mention storage_options, "
            "added to the signature in v1.10.0 (#394). A contract that "
            "omits a public parameter is out of date the moment it ships."
        )


@pytest.mark.parametrize(
    "doc_name",
    [
        "006_intent_contracts_for_non_trivial_classes.md",
        "010_gridconfig_spatial_only.md",
    ],
)
def test_lab_grid_references_are_marked_historical(doc_name: str) -> None:
    """views-metric-lab deleted ``src/lab_grid/`` in commit 6e1a34d.

    These two ADRs describe classes that originated there. The lineage is
    worth keeping — an ADR that quietly drops its own premise stops being
    a record of a decision — but a bare reference reads as a live path.
    So the requirement is that the reference is *annotated*, not removed.
    """
    body = (DOCS / "ADRs" / doc_name).read_text()
    if "lab_grid" not in body:
        return  # removed entirely; also acceptable
    assert "6e1a34d" in body, (
        f"{doc_name} references lab_grid without noting that "
        f"views-metric-lab deleted that package (commit 6e1a34d). A bare "
        f"reference reads as a live path to a reader who has not checked."
    )
