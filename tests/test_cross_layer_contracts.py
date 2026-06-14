"""Cross-layer schema contract tests (C-288).

Verifies that viewpoint output columns match compilation input
expectations for all 6 sources. Catches schema drift at test time
rather than at runtime during compilation.

Two compilation paths:
- Event-based (UCDP, ACLED): CompilationConfig with lat/lon/date
- Pre-gridded (GHS-POP, GHS-BUILT-S, V-Dem, SHDI):
  PregriddedCompilationConfig with pgid/month_id
"""

from __future__ import annotations

import pytest

from datafactory_compilation.compilation_config import (
    CompilationConfig,
)
from datafactory_compilation.pregridded_compilation import (
    PregriddedCompilationConfig,
    PregriddedFeatureSpec,
)

# ---- Event-based contracts (UCDP, ACLED) ----
#
# Viewpoint output = consolidated columns - STRIPPED_FIELDS + PRODUCED_FIELDS.
# Compilation reads lat_field, lon_field, date_field, plus columns
# referenced by FeatureSpec (filter keys + value_field).
# Contract: none of those may appear in STRIPPED_FIELDS.


UCDP_COMPILATION_COLUMNS: set[str] = {
    CompilationConfig.lat_field,
    CompilationConfig.lon_field,
    "date_month",
    "best",
    "type_of_violence",
    "date_start",
}

ACLED_COMPILATION_COLUMNS: set[str] = {
    "latitude",
    "longitude",
    "event_date",
    "fatalities",
    "event_type",
    "date_month",
}


class TestUcdpViewpointToCompilationContract:
    """UCDP viewpoint output must satisfy CompilationConfig input."""

    def test_date_field_is_produced(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            PRODUCED_FIELDS,
        )

        assert "date_month" in PRODUCED_FIELDS

    def test_lat_lon_not_stripped(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            STRIPPED_FIELDS,
        )

        assert CompilationConfig.lat_field not in STRIPPED_FIELDS
        assert CompilationConfig.lon_field not in STRIPPED_FIELDS

    def test_value_field_not_stripped(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "best" in REQUIRED_CONSOLIDATED_FIELDS
        assert "best" not in STRIPPED_FIELDS

    def test_filter_column_not_stripped(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            STRIPPED_FIELDS,
        )

        assert "type_of_violence" not in STRIPPED_FIELDS

    def test_date_start_available_for_raw_mode(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "date_start" in REQUIRED_CONSOLIDATED_FIELDS
        assert "date_start" not in STRIPPED_FIELDS

    def test_no_compilation_column_is_stripped(self) -> None:
        from datafactory_viewpoint.builders.ucdp_v1 import (
            STRIPPED_FIELDS,
        )

        overlap = UCDP_COMPILATION_COLUMNS & STRIPPED_FIELDS
        assert not overlap, (
            f"Compilation needs {overlap} but viewpoint strips them"
        )


class TestAcledViewpointToCompilationContract:
    """ACLED viewpoint output must satisfy CompilationConfig input."""

    def test_date_field_in_required(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "event_date" in REQUIRED_CONSOLIDATED_FIELDS
        assert "event_date" not in STRIPPED_FIELDS

    def test_lat_lon_in_required(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "latitude" in REQUIRED_CONSOLIDATED_FIELDS
        assert "latitude" not in STRIPPED_FIELDS
        assert "longitude" in REQUIRED_CONSOLIDATED_FIELDS
        assert "longitude" not in STRIPPED_FIELDS

    def test_fatalities_in_required(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "fatalities" in REQUIRED_CONSOLIDATED_FIELDS
        assert "fatalities" not in STRIPPED_FIELDS

    def test_event_type_in_required(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            REQUIRED_CONSOLIDATED_FIELDS,
            STRIPPED_FIELDS,
        )

        assert "event_type" in REQUIRED_CONSOLIDATED_FIELDS
        assert "event_type" not in STRIPPED_FIELDS

    def test_date_month_produced(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            PRODUCED_FIELDS,
        )

        assert "date_month" in PRODUCED_FIELDS

    def test_no_compilation_column_is_stripped(self) -> None:
        from datafactory_viewpoint.builders.acled_v1 import (
            STRIPPED_FIELDS,
        )

        overlap = ACLED_COMPILATION_COLUMNS & STRIPPED_FIELDS
        assert not overlap, (
            f"Compilation needs {overlap} but viewpoint strips them"
        )


# ---- Pre-gridded contracts (GHS-POP, GHS-BUILT-S, V-Dem, SHDI) ----
#
# Viewpoint output is fully explicit: (pgid, month_id, value_columns).
# Compilation expects pgid_field, month_id_field, plus value_field
# from each PregriddedFeatureSpec.


GHSPOP_OUTPUT_COLUMNS: set[str] = {"pgid", "month_id", "pop_count"}
GHSPOP_FEATURES: tuple[PregriddedFeatureSpec, ...] = (
    PregriddedFeatureSpec("ghspop_pop_count", "pop_count"),
)

GHSBUILTS_OUTPUT_COLUMNS: set[str] = {
    "pgid", "month_id", "built_area",
}
GHSBUILTS_FEATURES: tuple[PregriddedFeatureSpec, ...] = (
    PregriddedFeatureSpec("ghsbuilts_built_area", "built_area"),
)


@pytest.mark.parametrize(
    "viewpoint_columns,compilation_features",
    [
        pytest.param(
            GHSPOP_OUTPUT_COLUMNS,
            GHSPOP_FEATURES,
            id="ghspop",
        ),
        pytest.param(
            GHSBUILTS_OUTPUT_COLUMNS,
            GHSBUILTS_FEATURES,
            id="ghsbuilts",
        ),
    ],
)
class TestPregriddedRasterContract:
    """GHS-POP and GHS-BUILT-S viewpoint output must satisfy
    PregriddedCompilationConfig input."""

    def test_structural_columns_present(
        self,
        viewpoint_columns: set[str],
        compilation_features: tuple[PregriddedFeatureSpec, ...],
    ) -> None:
        assert (
            PregriddedCompilationConfig.pgid_field
            in viewpoint_columns
        )
        assert (
            PregriddedCompilationConfig.month_id_field
            in viewpoint_columns
        )

    def test_feature_value_fields_present(
        self,
        viewpoint_columns: set[str],
        compilation_features: tuple[PregriddedFeatureSpec, ...],
    ) -> None:
        for spec in compilation_features:
            assert spec.value_field in viewpoint_columns, (
                f"{spec.name}: value_field '{spec.value_field}' "
                f"not in viewpoint output {viewpoint_columns}"
            )


class TestVdemViewpointToCompilationContract:
    """V-Dem viewpoint output must satisfy PregriddedCompilationConfig."""

    def test_structural_columns(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VDEM_VARIABLES,
        )

        output_columns = {"pgid", "month_id"} | set(
            VDEM_VARIABLES
        )
        assert (
            PregriddedCompilationConfig.pgid_field
            in output_columns
        )
        assert (
            PregriddedCompilationConfig.month_id_field
            in output_columns
        )

    def test_all_compilation_features_in_viewpoint(
        self,
    ) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VDEM_VARIABLES,
        )

        output_columns = {"pgid", "month_id"} | set(
            VDEM_VARIABLES
        )
        vdem_features = (
            PregriddedFeatureSpec("vdem_v2xcl_dmove", "v2xcl_dmove"),
            PregriddedFeatureSpec("vdem_v2xeg_eqdr", "v2xeg_eqdr"),
            PregriddedFeatureSpec(
                "vdem_v2xpe_exlsocgr", "v2xpe_exlsocgr",
            ),
            PregriddedFeatureSpec("vdem_v2x_clphy", "v2x_clphy"),
            PregriddedFeatureSpec(
                "vdem_v2xcl_prpty", "v2xcl_prpty",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_ex_military", "v2x_ex_military",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_ex_party", "v2x_ex_party",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_horacc", "v2x_horacc",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xnp_client", "v2xnp_client",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xnp_regcorr", "v2xnp_regcorr",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xpe_exlgeo", "v2xpe_exlgeo",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_veracc", "v2x_veracc",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xpe_exlpol", "v2xpe_exlpol",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_diagacc", "v2x_diagacc",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_divparctrl", "v2x_divparctrl",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xeg_eqprotec", "v2xeg_eqprotec",
            ),
            PregriddedFeatureSpec(
                "vdem_v2x_genpp", "v2x_genpp",
            ),
            PregriddedFeatureSpec(
                "vdem_v2xpe_exlgender", "v2xpe_exlgender",
            ),
        )
        for spec in vdem_features:
            assert spec.value_field in output_columns, (
                f"{spec.name}: value_field '{spec.value_field}' "
                f"not in viewpoint output columns"
            )

    def test_feature_count_consistency(self) -> None:
        from datafactory_viewpoint.builders.vdem_v1 import (
            VDEM_VARIABLES,
        )

        compilation_value_fields = {
            "v2xcl_dmove", "v2xeg_eqdr", "v2xpe_exlsocgr",
            "v2x_clphy", "v2xcl_prpty", "v2x_ex_military",
            "v2x_ex_party", "v2x_horacc", "v2xnp_client",
            "v2xnp_regcorr", "v2xpe_exlgeo", "v2x_veracc",
            "v2xpe_exlpol", "v2x_diagacc", "v2x_divparctrl",
            "v2xeg_eqprotec", "v2x_genpp", "v2xpe_exlgender",
        }
        assert compilation_value_fields <= set(VDEM_VARIABLES), (
            f"Compilation references variables not in viewpoint: "
            f"{compilation_value_fields - set(VDEM_VARIABLES)}"
        )


class TestShdiViewpointToCompilationContract:
    """SHDI viewpoint output must satisfy PregriddedCompilationConfig."""

    def test_structural_columns(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            SHDI_VARIABLES,
        )

        output_columns = {"pgid", "month_id"} | set(
            SHDI_VARIABLES
        )
        assert (
            PregriddedCompilationConfig.pgid_field
            in output_columns
        )
        assert (
            PregriddedCompilationConfig.month_id_field
            in output_columns
        )

    def test_all_compilation_features_in_viewpoint(
        self,
    ) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            SHDI_VARIABLES,
        )

        output_columns = {"pgid", "month_id"} | set(
            SHDI_VARIABLES
        )
        shdi_features = (
            PregriddedFeatureSpec("shdi_shdi", "shdi"),
            PregriddedFeatureSpec(
                "shdi_healthindex", "healthindex",
            ),
            PregriddedFeatureSpec("shdi_edindex", "edindex"),
            PregriddedFeatureSpec("shdi_incindex", "incindex"),
        )
        for spec in shdi_features:
            assert spec.value_field in output_columns, (
                f"{spec.name}: value_field '{spec.value_field}' "
                f"not in viewpoint output columns"
            )

    def test_feature_count_consistency(self) -> None:
        from datafactory_viewpoint.builders.shdi_v1 import (
            SHDI_VARIABLES,
        )

        compilation_value_fields = {
            "shdi", "healthindex", "edindex", "incindex",
        }
        assert compilation_value_fields <= set(SHDI_VARIABLES), (
            f"Compilation references variables not in viewpoint: "
            f"{compilation_value_fields - set(SHDI_VARIABLES)}"
        )


# ---- Cross-cutting: no source's required fields are stripped ----


class TestNoRequiredFieldsStripped:
    """For event-based sources, compilation-required columns must
    never appear in STRIPPED_FIELDS."""

    @pytest.mark.parametrize(
        "stripped_fields_import,compilation_columns",
        [
            pytest.param(
                "datafactory_viewpoint.builders.ucdp_v1",
                UCDP_COMPILATION_COLUMNS,
                id="ucdp",
            ),
            pytest.param(
                "datafactory_viewpoint.builders.acled_v1",
                ACLED_COMPILATION_COLUMNS,
                id="acled",
            ),
        ],
    )
    def test_no_overlap(
        self,
        stripped_fields_import: str,
        compilation_columns: set[str],
    ) -> None:
        import importlib

        mod = importlib.import_module(stripped_fields_import)
        stripped = mod.STRIPPED_FIELDS
        overlap = compilation_columns & stripped
        assert not overlap, (
            f"Compilation needs {overlap} but viewpoint strips them"
        )
