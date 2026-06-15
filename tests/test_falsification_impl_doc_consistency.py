"""Falsification tests: implementation vs documentation consistency.

Claim: all data source implementations and viewpoints are 100%
consistent with the (updated) documentation.

Audit date: 2026-06-11
Probes: P-1 (temporal routing), P-6 (cross-source deps), P-8 (ACLED filter)
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
BUILDERS = SRC / "datafactory_viewpoint" / "builders"
ADRS = REPO / "docs" / "ADRs"


class TestTemporalModuleRouting:
    """P-1: ADR-014 Principle 5 says the shared temporal implementation
    lives in datafactory_viewpoint.temporal. Builders that expand
    temporal resolution should route through it."""

    def test_vdem_uses_shared_temporal_module(self):
        vdem = BUILDERS / "vdem_v1.py"
        assert vdem.exists()
        source = vdem.read_text()
        has_temporal_import = (
            "from datafactory_viewpoint.temporal import" in source
            or "from datafactory_viewpoint import temporal" in source
        )
        assert has_temporal_import, (
            "vdem_v1.py implements step-function temporal expansion "
            "with inline np.repeat()/np.tile() (lines 257-258) instead "
            "of routing through datafactory_viewpoint.temporal as "
            "prescribed by ADR-014 Principle 5."
        )

    def test_shdi_uses_shared_temporal_module(self):
        shdi = BUILDERS / "shdi_v1.py"
        assert shdi.exists()
        source = shdi.read_text()
        has_temporal_import = (
            "from datafactory_viewpoint.temporal import" in source
            or "from datafactory_viewpoint import temporal" in source
        )
        assert has_temporal_import, (
            "shdi_v1.py implements step-function temporal expansion "
            "with inline np.repeat()/np.tile() (lines 225-226) instead "
            "of routing through datafactory_viewpoint.temporal as "
            "prescribed by ADR-014 Principle 5."
        )


class TestFeatureSourceIndependence:
    """P-6 (revised per ADR-044): feature sources may depend on
    reference sources (PRIO-GRID, GAUL) but must NOT depend on
    other feature sources."""

    FEATURE_BUILDERS: dict[str, str] = {
        "vdem_v1.py": "vdem",
        "shdi_v1.py": "shdi",
        "acled_v1.py": "acled",
        "ghspop_v1.py": "ghspop",
        "ghsbuilts_v1.py": "ghsbuilt",
    }

    FEATURE_DATA_PREFIXES: list[str] = [
        "data/raw/ucdp",
        "data/raw/acled",
        "data/raw/vdem",
        "data/raw/shdi",
        "data/raw/ghspop",
        "data/raw/ghsbuilt",
    ]

    def test_no_feature_reads_other_feature_data(self):
        for builder_file, own_prefix in (
            self.FEATURE_BUILDERS.items()
        ):
            path = BUILDERS / builder_file
            if not path.exists():
                continue
            source = path.read_text()
            for data_prefix in self.FEATURE_DATA_PREFIXES:
                dir_name = data_prefix.split("/")[-1]
                if dir_name.startswith(own_prefix):
                    continue
                assert data_prefix not in source, (
                    f"{builder_file} reads {data_prefix} — "
                    f"feature→feature dependency "
                    f"violates ADR-044"
                )


class TestAcledFilterDocumented:
    """P-8: ACLED builder implements event_type_filter but ADR-028
    does not mention this capability."""

    def test_acled_adr_mentions_filtering(self):
        adr028 = ADRS / "028_acled_consolidation_and_viewpoint.md"
        assert adr028.exists()
        text = adr028.read_text().lower()
        has_filter_doc = (
            "event_type_filter" in text
            or "filter by event type" in text
            or "event type filter" in text
        )
        assert has_filter_doc, (
            "ADR-028 describes ACLED viewpoint behavior but does not "
            "mention the event_type_filter capability implemented in "
            "acled_v1.py (lines 138-151). The filter selects events by "
            "type via PyArrow pc.is_in() — this behavior should be "
            "documented in the architectural decision record."
        )
