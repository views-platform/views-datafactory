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


class TestGridValidationOrder:
    """C-128: assert_grid_shape must precede shape unpacking (ADR-003)."""

    _SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"

    @staticmethod
    def _first_line_containing(
        lines: list[str], needle: str,
    ) -> int | None:
        for i, line in enumerate(lines):
            if needle in line:
                return i
        return None

    def test_assemble_validates_before_unpack(self) -> None:
        lines = (
            self._SCRIPTS_DIR / "assemble_grid.py"
        ).read_text().splitlines()
        validate = self._first_line_containing(
            lines, "assert_grid_shape"
        )
        unpack = self._first_line_containing(
            lines, "= ucdp_grid.shape"
        )
        assert validate is not None
        assert unpack is not None
        assert validate < unpack, (
            "assert_grid_shape must come before .shape unpacking"
        )

    def test_export_dataframe_validates_before_unpack(
        self,
    ) -> None:
        lines = (
            self._SCRIPTS_DIR / "export_dataframe.py"
        ).read_text().splitlines()
        validate = self._first_line_containing(
            lines, "assert_grid_shape"
        )
        unpack = self._first_line_containing(
            lines, "= grid.shape"
        )
        assert validate is not None
        assert unpack is not None
        assert validate < unpack, (
            "assert_grid_shape must come before .shape unpacking"
        )

    def test_export_zarr_validates_before_unpack(self) -> None:
        lines = (
            self._SCRIPTS_DIR / "export_zarr.py"
        ).read_text().splitlines()
        validate = self._first_line_containing(
            lines, "assert_grid_shape"
        )
        unpack = self._first_line_containing(
            lines, "= grid.shape"
        )
        assert validate is not None
        assert unpack is not None
        assert validate < unpack, (
            "assert_grid_shape must come before .shape unpacking"
        )

    def test_compile_validates_before_use(self) -> None:
        lines = (
            self._SCRIPTS_DIR / "compile_grid.py"
        ).read_text().splitlines()
        validate = self._first_line_containing(
            lines, "assert_grid_shape"
        )
        use = self._first_line_containing(
            lines, "grid[:, :, :,"
        )
        assert validate is not None
        assert use is not None
        assert validate < use, (
            "compile_grid: assert_grid_shape already correct"
        )
