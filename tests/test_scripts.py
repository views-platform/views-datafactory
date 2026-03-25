"""Tests for consumer-facing scripts.

Verifies that export_dataframe.py and verify_parity.py
exist, are syntactically valid, and have the expected
entry points.
"""

from __future__ import annotations

import ast
from pathlib import Path


class TestExportDataframeGreen:

    def test_script_exists(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "export_dataframe.py"
        )
        assert path.exists()

    def test_script_parses(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "export_dataframe.py"
        )
        source = path.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in func_names

    def test_has_argparse(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "export_dataframe.py"
        )
        content = path.read_text()
        assert "argparse" in content
        assert "--input" in content
        assert "--sparse" in content


class TestVerifyParityGreen:

    def test_script_exists(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "verify_parity.py"
        )
        assert path.exists()

    def test_script_parses(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "verify_parity.py"
        )
        source = path.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in func_names


class TestCheckHealthGreen:

    def test_script_exists(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "check_health.py"
        )
        assert path.exists()

    def test_script_parses(self) -> None:
        path = (
            Path(__file__).parent.parent
            / "scripts"
            / "check_health.py"
        )
        source = path.read_text()
        tree = ast.parse(source)
        func_names = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        ]
        assert "main" in func_names


class TestAllScriptsGreen:

    # Shared modules (not runnable scripts)
    _MODULES = {"viz_style.py"}

    def test_all_scripts_have_main(self) -> None:
        """Every script in scripts/ should have a main()."""
        scripts_dir = (
            Path(__file__).parent.parent / "scripts"
        )
        for script in sorted(scripts_dir.glob("*.py")):
            if script.name in self._MODULES:
                continue
            source = script.read_text()
            tree = ast.parse(source)
            func_names = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]
            assert "main" in func_names, (
                f"{script.name} missing main()"
            )

    def test_all_scripts_have_ifname(self) -> None:
        """Every script should have if __name__ guard."""
        scripts_dir = (
            Path(__file__).parent.parent / "scripts"
        )
        for script in sorted(scripts_dir.glob("*.py")):
            if script.name in self._MODULES:
                continue
            content = script.read_text()
            assert '__name__' in content, (
                f"{script.name} missing __name__ guard"
            )
