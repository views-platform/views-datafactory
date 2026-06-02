"""Falsification stubs: SHDI sprint ordering.

Source: /falsify 2026-05-29
Claim: B → A → C ordering (bounded-memory → harvest correctness →
    WET extraction) is still correct with SHDI as next source.
Verdict: FALSIFIED (2 hard, 1 soft).

F-1 (hard): SHDI compile (4 features, 1.8 GB) does not trigger C-223.
    B-first prerequisite is invalid — SHDI fits in 16 GB RAM without
    any bounded-memory work.
F-2 (hard): SHDI is admin-1 resolution, not country-level. V-Dem's
    ISO3→pgid crosswalk does not apply. A gaul1-based crosswalk is
    the actual integration prerequisite, not addressed by B, A, or C.
F-3 (soft): SHDI is 6th pipeline source — C-164 trigger fires again.
    C-last means copying ~1,430 lines of patterns.
"""

from __future__ import annotations


class TestF1ShdiCompileMemory:
    """SHDI at 4 features should compile in <2 GB — no bounded-memory
    prerequisite."""

    def test_shdi_compile_fits_in_ram(self) -> None:
        """4 features × 0.44 GB/feature = 1.8 GB, well within 16 GB."""
        t, h, w = 456, 360, 720
        dtype_bytes = 4
        shdi_features = 4
        compile_gb = t * h * w * dtype_bytes * shdi_features / (1024**3)
        server_ram_gb = 16
        assert compile_gb < server_ram_gb, (
            f"SHDI compile ({compile_gb:.1f} GB) exceeds "
            f"server RAM ({server_ram_gb} GB) — bounded-memory "
            f"IS a prerequisite. Falsification F-1 is wrong."
        )


class TestF2ShdiCrosswalkNotCountryLevel:
    """SHDI needs admin-1 → pgid crosswalk, not ISO3 → pgid."""

    def test_gaul1_crosswalk_exists(self) -> None:
        """gaul1_code.parquet must exist for admin-1 mapping."""
        from pathlib import Path

        import pytest

        gaul1 = Path("data/raw/gaul_admin/gaul1_code.parquet")
        if not gaul1.exists():
            pytest.skip(
                "gaul1_code.parquet not found — requires harvested data"
            )
        assert gaul1.stat().st_size > 0

    def test_no_admin1_viewpoint_builder_exists(self) -> None:
        """No viewpoint builder handles admin-1 resolution yet.
        V-Dem builder uses ISO3 (country). SHDI needs admin-1."""
        from pathlib import Path

        builders_dir = Path(
            "src/datafactory_viewpoint/builders"
        )
        builder_files = [
            f.stem
            for f in builders_dir.glob("*.py")
            if not f.name.startswith("_")
        ]
        admin1_builders = [
            b for b in builder_files if "admin1" in b or "shdi" in b
        ]
        assert not admin1_builders, (
            f"Admin-1 builder found: {admin1_builders} — "
            f"falsification F-2 is resolved"
        )


class TestF3SixthPipelineSourceWetDebt:
    """SHDI is the 6th pipeline source — C-164 trigger fires."""

    def test_c164_trigger_mentions_6th_source(self) -> None:
        from pathlib import Path

        register = Path(
            "reports/technical_risk_register.md"
        ).read_text()
        c164_start = register.index("### C-164")
        next_h = register.find("\n### ", c164_start + 10)
        c164_text = register[c164_start:next_h]
        assert "6th" in c164_text.lower(), (
            "C-164 trigger does not mention 6th source"
        )
