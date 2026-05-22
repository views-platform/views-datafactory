"""Falsification stubs: GHS-BUILT-S memory safety.

Source: /falsify coverage parity audit 2026-05-22
AST-based structural checks that OOM mitigations are in place.
Does NOT duplicate the AST tests in test_ghsbuilts_viewpoint.py
(those check presence; these check positioning and non-overridability).
"""

from __future__ import annotations

import ast
import inspect


class TestF1DecompressionSafety:
    """_read_geotiff must not expose maxworkers as a parameter."""

    def test_read_geotiff_no_maxworkers_param(self) -> None:
        from datafactory_viewpoint.builders import ghsbuilts_v1

        sig = inspect.signature(ghsbuilts_v1._read_geotiff)
        param_names = list(sig.parameters.keys())
        assert "maxworkers" not in param_names, (
            "_read_geotiff accepts maxworkers as a parameter — "
            "callers could override the safety limit"
        )


class TestF2ListDeletion:
    """del must appear after pa.table() in build_ghsbuilts_v1."""

    def test_del_appears_after_pa_table(self) -> None:
        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(ghsbuilts_v1.build_ghsbuilts_v1)
        tree = ast.parse(source)

        pa_table_line = None
        del_line = None

        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "table"):
                pa_table_line = node.lineno

            if isinstance(node, ast.Delete):
                for target in node.targets:
                    if (isinstance(target, ast.Name)
                            and target.id == "pgid_rows"):
                        del_line = node.lineno

        assert pa_table_line is not None, "pa.table() not found"
        assert del_line is not None, "del pgid_rows not found"
        assert del_line > pa_table_line, (
            f"del (line {del_line}) appears before pa.table() "
            f"(line {pa_table_line}) — lists freed before Arrow "
            f"table created"
        )


class TestF3RawArrayDeletion:
    """del raw must appear in build_ghsbuilts_v1."""

    def test_del_raw_in_build_function(self) -> None:
        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(ghsbuilts_v1.build_ghsbuilts_v1)
        tree = ast.parse(source)

        del_targets: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Delete):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        del_targets.add(target.id)

        assert "raw" in del_targets, (
            "del raw not found in build_ghsbuilts_v1 — "
            "raw raster array stays in memory during aggregation"
        )


class TestF4StripProcessing:
    """_aggregate_with_alignment must delete intermediates."""

    def test_strip_and_aligned_deleted(self) -> None:
        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(
            ghsbuilts_v1._aggregate_with_alignment,
        )
        assert "del strip" in source, (
            "del strip not in _aggregate_with_alignment"
        )
        assert "del aligned" in source, (
            "del aligned not in _aggregate_with_alignment"
        )


class TestF5Float64Intermediates:
    """Aggregation must cast to float64 before summing."""

    def test_aggregation_uses_float64(self) -> None:
        from datafactory_viewpoint.builders import ghsbuilts_v1

        source = inspect.getsource(
            ghsbuilts_v1._aggregate_with_alignment,
        )
        assert ".astype(np.float64)" in source, (
            "Strip not cast to float64 — uint32 sum will overflow "
            "for values > ~1.2M per pixel (3600 pixels/cell)"
        )
