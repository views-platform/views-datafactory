"""Falsification stubs: claim 'the try/finally fix covers all exit paths.'

Round 4 audit, 2026-06-10. Two findings:

P-1 (Hard): Assembly finally has mkdir OUTSIDE contextlib.suppress.
If mkdir raises (path is a file, permission denied, disk full),
its exception replaces the propagating work-phase exception —
masking the original error. Export's finally is correct (no mkdir).

P-2 (Soft): The mkdir is redundant — append_ledger_entry already
creates ledger_path.parent internally (digests_and_ledgers.py:211).
The redundant call adds masking risk for zero benefit.
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestP1MkdirMaskingRisk:
    """P-1: mkdir in assembly finally must be inside suppress."""

    def test_mkdir_inside_suppress_or_absent(self) -> None:
        """The mkdir call in assembly's finally block must be inside
        the contextlib.suppress context manager, or removed entirely,
        so it cannot mask the original exception."""
        source = Path("scripts/assemble_grid.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.finalbody:
                self._check_no_bare_mkdir(handler)

    def _check_no_bare_mkdir(self, node: ast.AST) -> None:
        """Recursively check that mkdir calls are inside With nodes."""
        if isinstance(node, ast.If):
            for child in node.body + node.orelse:
                self._check_no_bare_mkdir(child)
            return

        if isinstance(node, ast.Expr) and isinstance(
            node.value, ast.Call
        ):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr == "mkdir":
                raise AssertionError(
                    "assembly finally has mkdir() outside "
                    "contextlib.suppress — can mask the original "
                    "exception on disk-full / permission-denied / "
                    "path-is-file scenarios"
                )

        if isinstance(node, ast.With):
            return


class TestP2MkdirRedundancy:
    """P-2: mkdir in finally is redundant with append_ledger_entry."""

    def test_no_mkdir_in_finally(self) -> None:
        """append_ledger_entry already creates ledger_path.parent.
        The explicit mkdir in the finally adds masking risk for
        zero benefit — it should be removed."""
        source = Path("scripts/assemble_grid.py").read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for stmt in ast.walk(ast.Module(body=node.finalbody, type_ignores=[])):
                if (
                    isinstance(stmt, ast.Attribute)
                    and stmt.attr == "mkdir"
                ):
                    raise AssertionError(
                        "assembly finally contains mkdir() — redundant "
                        "with append_ledger_entry's internal "
                        "ledger_path.parent.mkdir(). Remove to "
                        "eliminate exception masking risk (P-1)."
                    )
