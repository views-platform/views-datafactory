"""Pipeline consistency — internal checks across processing stages.

Verifies that no events are lost or duplicated between pipeline
stages, that PGM→CM aggregation is deterministic, and that
individual events can be traced from the consolidated store
through to query output.

Gated behind --run-consumer (requires local data at each stage).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from gold_set_config import (
    COMPILED_DIR,
    CONSOLIDATED_DIR,
    DATA_DIR,
    FACTORY_FEATURES,
    GAUL_DIR,
    MONTH_ID_EPOCH,
    VIEWPOINT_DIR,
)

from datafactory_priogrid import to_views_month_id
from datafactory_query import load_dataset

# ── Viewpoint → Grid conservation ────────────────────────


@pytest.mark.consumer
class TestViewpointToGridConservation:
    """Fatality totals in viewpoint parquet == totals in compiled grid.

    The compiler sums event-level fatalities into grid cells. If this
    total doesn't match, events are being lost or duplicated during
    compilation.
    """

    @pytest.fixture(scope="class")
    def viewpoint_monthly_sums(self) -> pd.DataFrame:
        vp_path = VIEWPOINT_DIR / "production_parity.parquet"
        if not vp_path.exists():
            pytest.skip(f"Viewpoint parquet not found: {vp_path}")
        vp = pq.read_table(vp_path).to_pandas()
        vp["date_month"] = pd.to_datetime(vp["date_month"])
        month_ids = to_views_month_id(
            vp["date_month"].values.astype("datetime64[M]")
        )
        vp["month_id"] = month_ids

        type_groups = {
            "ged_sb_best": 1,
            "ged_ns_best": 2,
            "ged_os_best": 3,
        }
        result_rows = []
        for month_id in sorted(vp["month_id"].unique()):
            month_data = vp[vp["month_id"] == month_id]
            row = {"month_id": month_id}
            for feature, tov in type_groups.items():
                subset = month_data[
                    month_data["type_of_violence"] == tov
                ]
                row[feature] = float(subset["best"].sum())
            result_rows.append(row)
        return pd.DataFrame(result_rows).set_index("month_id")

    @pytest.fixture(scope="class")
    def grid_monthly_sums(self) -> pd.DataFrame:
        grid_path = COMPILED_DIR / "grid.npy"
        if not grid_path.exists():
            pytest.skip(f"Compiled grid not found: {grid_path}")

        grid = np.load(grid_path, mmap_mode="r")
        time_steps = np.load(COMPILED_DIR / "time_steps.npy")
        with open(COMPILED_DIR / "feature_names.json") as f:
            feature_names = json.load(f)

        month_ids = to_views_month_id(
            time_steps.astype("datetime64[M]")
        )

        result_rows = []
        for t_idx, mid in enumerate(month_ids):
            row = {"month_id": int(mid)}
            for f_idx, fname in enumerate(feature_names):
                if fname in FACTORY_FEATURES:
                    row[fname] = float(
                        grid[t_idx, :, :, f_idx].sum()
                    )
            result_rows.append(row)
        return pd.DataFrame(result_rows).set_index("month_id")

    def test_fatality_totals_preserved(
        self,
        viewpoint_monthly_sums: pd.DataFrame,
        grid_monthly_sums: pd.DataFrame,
    ) -> None:
        common = sorted(
            set(viewpoint_monthly_sums.index)
            & set(grid_monthly_sums.index)
        )
        assert len(common) > 100, (
            f"Only {len(common)} common months between "
            "viewpoint and grid"
        )

        for col in FACTORY_FEATURES:
            if col not in viewpoint_monthly_sums.columns:
                continue
            if col not in grid_monthly_sums.columns:
                continue
            vp_vals = viewpoint_monthly_sums.loc[common, col].values
            grid_vals = grid_monthly_sums.loc[common, col].values
            np.testing.assert_allclose(
                grid_vals, vp_vals,
                atol=1.0,
                err_msg=(
                    f"{col}: viewpoint→grid totals differ. "
                    "Compilation may be dropping or duplicating events."
                ),
            )


# ── PGM ↔ CM aggregation ─────────────────────────────────


@pytest.mark.consumer
class TestPGMCMAggregation:
    """Factory PGM (gaul0_code > 0) grouped by country == Factory CM.

    CM aggregation drops cells without a valid GAUL code, so the PGM
    side must also be filtered to gaul0_code > 0 for a fair comparison.
    """

    def test_pgm_sums_equal_cm(self) -> None:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")

        features_with_gaul = FACTORY_FEATURES + ["gaul0_code"]

        pgm = load_dataset(
            region="land",
            start=121,
            end=492,
            features=features_with_gaul,
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )
        pgm = pgm.fillna(0.0)
        pgm = pgm[pgm["gaul0_code"] > 0]

        cm = load_dataset(
            region="land",
            start=121,
            end=492,
            features=FACTORY_FEATURES,
            output_format="country_month",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )
        cm = cm.fillna(0.0)

        pgm_month_totals = pgm.groupby(
            pgm.index.get_level_values("month_id"),
        )[FACTORY_FEATURES].sum()
        cm_month_totals = cm.groupby("month_id")[
            FACTORY_FEATURES
        ].sum()

        common = sorted(
            set(pgm_month_totals.index)
            & set(cm_month_totals.index)
        )
        for col in FACTORY_FEATURES:
            pv = pgm_month_totals.loc[common, col].values
            cv = cm_month_totals.loc[common, col].values
            np.testing.assert_allclose(
                pv, cv, atol=1e-3,
                err_msg=(
                    f"{col}: PGM monthly totals != CM monthly "
                    "totals. grid_to_country_month aggregation "
                    "may be incorrect."
                ),
            )


# ── Event traceability ────────────────────────────────────


@pytest.mark.consumer
class TestEventTraceability:
    """Trace specific events from consolidated store through pipeline.

    Picks real events from the consolidated store and verifies they
    appear in the viewpoint and the final query output with correct
    values.
    """

    @pytest.fixture(scope="class")
    def consolidated(self) -> pd.DataFrame:
        path = CONSOLIDATED_DIR / "ucdp_store.parquet"
        if not path.exists():
            pytest.skip(f"Consolidated store not found: {path}")
        return pq.read_table(path).to_pandas()

    @pytest.fixture(scope="class")
    def viewpoint(self) -> pd.DataFrame:
        path = VIEWPOINT_DIR / "production_parity.parquet"
        if not path.exists():
            pytest.skip(f"Viewpoint parquet not found: {path}")
        return pq.read_table(path).to_pandas()

    @pytest.fixture(scope="class")
    def sample_events(
        self, consolidated: pd.DataFrame,
    ) -> list[dict]:
        """Pick 5 diverse events from the consolidated store."""
        events = []

        single = consolidated[
            (consolidated["date_prec"] != 5)
            & (consolidated["best"] > 0)
            & (consolidated["priogrid_gid"] > 0)
            & (consolidated["type_of_violence"].isin([1, 2, 3]))
            & (consolidated["_source_type"] == "annual")
        ]
        if len(single) > 0:
            events.append(single.iloc[0].to_dict())

        dot9 = consolidated[
            (consolidated["_source_type"] == "dot9")
            & (consolidated["best"] > 0)
            & (consolidated["priogrid_gid"] > 0)
        ]
        if len(dot9) > 0:
            events.append(dot9.iloc[0].to_dict())

        summary = consolidated[
            (consolidated["date_prec"] == 5)
            & (consolidated["best"] > 2)
        ]
        if len(summary) > 0:
            events.append(summary.iloc[0].to_dict())

        tov2 = consolidated[
            (consolidated["type_of_violence"] == 2)
            & (consolidated["best"] > 0)
            & (consolidated["priogrid_gid"] > 0)
        ]
        if len(tov2) > 0:
            events.append(tov2.iloc[0].to_dict())

        tov3 = consolidated[
            (consolidated["type_of_violence"] == 3)
            & (consolidated["best"] > 0)
            & (consolidated["priogrid_gid"] > 0)
        ]
        if len(tov3) > 0:
            events.append(tov3.iloc[0].to_dict())

        assert len(events) >= 3, (
            f"Only found {len(events)} suitable events"
        )
        return events

    def test_events_in_viewpoint(
        self,
        sample_events: list[dict],
        viewpoint: pd.DataFrame,
    ) -> None:
        """Each event ID appears in the viewpoint output."""
        vp_ids = set(viewpoint["id"].unique())
        for event in sample_events:
            eid = event["id"]
            tov = event.get("type_of_violence", 0)
            if tov > 3:
                continue
            if event.get("where_prec") in (4, 6):
                continue
            if event.get("priogrid_gid", 0) < 1:
                continue
            assert eid in vp_ids, (
                f"Event {eid} (tov={tov}, best={event['best']}) "
                "missing from viewpoint"
            )

    def test_event_month_assignment(
        self,
        sample_events: list[dict],
        viewpoint: pd.DataFrame,
    ) -> None:
        """Non-summary events assigned to date_end month."""
        for event in sample_events:
            if event.get("date_prec") == 5:
                continue
            eid = event["id"]
            vp_rows = viewpoint[viewpoint["id"] == eid]
            if vp_rows.empty:
                continue

            date_end = str(
                event.get("date_end") or event.get("date_start")
            )
            expected_month = date_end[:7] + "-01"

            actual_months = set(vp_rows["date_month"].astype(str))
            assert expected_month in actual_months, (
                f"Event {eid}: date_end={date_end}, "
                f"expected month={expected_month}, "
                f"got {actual_months}"
            )

    def test_event_value_in_query(
        self, sample_events: list[dict],
    ) -> None:
        """A known nonzero event contributes to the query output."""
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")

        event = sample_events[0]
        date_end = str(
            event.get("date_end") or event.get("date_start")
        )
        dt = np.datetime64(date_end[:7], "M")
        month_id = int(to_views_month_id(dt).item())
        pgid = int(event["priogrid_gid"])
        tov = int(event.get("type_of_violence", 1))

        feature_map = {1: "ged_sb_best", 2: "ged_ns_best", 3: "ged_os_best"}
        feature = feature_map.get(tov)
        if feature is None:
            pytest.skip(f"Unknown type_of_violence: {tov}")

        df = load_dataset(
            region="global",
            start=month_id,
            end=month_id,
            features=[feature],
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )

        if (month_id, pgid) in df.index:
            value = df.loc[(month_id, pgid), feature]
            assert value > 0, (
                f"Event {event['id']} at ({month_id}, {pgid}): "
                f"{feature}={value}, expected > 0"
            )
        else:
            pytest.fail(
                f"Event {event['id']} at ({month_id}, {pgid}) "
                "not found in query output"
            )
