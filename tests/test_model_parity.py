"""Model parity tests — factory output vs VIEWSER gold set.

Verifies that the factory processing pipeline (consolidation →
viewpoint → compilation → assembly → query) produces the same
output as VIEWSER for all 3 model configurations:

1. PGM africa_me_legacy (13,110 cells) — direct comparison
2. PGM land (64,818 cells) — overlap comparison + structural check
3. CM global — per-month totals derived from gold set

Gold set: data/gold/viewser_pgm_africa_me.parquet (VIEWSER output,
africa_me_legacy PGM, months 121-555). Place the gold set at that
path to run these tests; they skip cleanly if it's missing.

Gated behind --run-consumer (requires assembled grid + gold set).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from gold_set_config import (
    DATA_DIR,
    FACTORY_FEATURES,
    FEATURE_RENAME,
    GAUL_DIR,
    GOLD_PGM_AFRICA_ME,
    MONTH_ID_EPOCH,
    PARITY_FEATURES,
    PARITY_THRESHOLD,
)

from datafactory_priogrid.grid_config import DEFAULT_GRID_CONFIG
from datafactory_query import load_dataset

NCOL = DEFAULT_GRID_CONFIG.ncol
PARITY_COLS = ["row", "col"] + PARITY_FEATURES
SUM_GAP_THRESHOLD = 0.005  # 0.5% — sum accumulates per-cell diffs
CM_SUM_GAP_THRESHOLD = 0.05  # 5% — CM drops ~603 unmapped coastal cells


def _build_parity_df(df: pd.DataFrame) -> pd.DataFrame:
    """Transform factory DataFrame into gold set format."""
    result = df[list(FEATURE_RENAME.keys())].rename(
        columns=FEATURE_RENAME,
    )
    pgids = result.index.get_level_values("priogrid_gid")
    result = result.copy()
    result["row"] = ((pgids - 1) // NCOL + 1).astype(np.float64)
    result["col"] = ((pgids - 1) % NCOL + 1).astype(np.float64)
    result = result[PARITY_COLS].fillna(0.0).astype(np.float64)
    return result.sort_index()


def _align_gold(gold: pd.DataFrame) -> pd.DataFrame:
    """Select only parity columns from gold set."""
    return gold[PARITY_COLS].sort_index()


def _assert_feature_parity(
    result: pd.DataFrame,
    reference: pd.DataFrame,
    features: list[str],
    threshold: float = PARITY_THRESHOLD,
) -> None:
    """Assert per-cell and global-sum parity for feature columns."""
    n_total = len(result)
    for col in features:
        rv = result[col].values
        gv = reference[col].values
        diff = np.abs(rv - gv)
        n_mismatch = int((diff > 1e-5).sum())
        rate = n_mismatch / n_total
        assert rate <= threshold, (
            f"{col}: {n_mismatch:,} mismatches ({rate:.4%}) "
            f"exceeds {threshold:.2%}"
        )

        r_total = float(rv.sum())
        g_total = float(gv.sum())
        if g_total > 0:
            gap = abs(r_total - g_total) / g_total
            assert gap <= SUM_GAP_THRESHOLD, (
                f"{col}: sum gap {gap:.4%} — "
                f"factory={r_total:,.0f}, gold={g_total:,.0f}"
            )


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def gold_df() -> pd.DataFrame:
    if not GOLD_PGM_AFRICA_ME.exists():
        pytest.skip(
            f"Gold set not found: {GOLD_PGM_AFRICA_ME}\n"
            "Place viewser_pgm_africa_me.parquet in data/gold/"
        )
    return _align_gold(pd.read_parquet(GOLD_PGM_AFRICA_ME))


@pytest.fixture(scope="module")
def gold_month_range(gold_df: pd.DataFrame) -> tuple[int, int]:
    months = gold_df.index.get_level_values("month_id")
    return int(months.min()), int(months.max())


@pytest.fixture(scope="module")
def gold_pgids(gold_df: pd.DataFrame) -> set[int]:
    return set(
        gold_df.index.get_level_values("priogrid_gid").unique()
    )


# ── Test 1a: PGM africa_me_legacy ────────────────────────


@pytest.mark.consumer
class TestPGMAfricaMeParity:
    """Direct comparison: factory africa_me_legacy vs gold set."""

    @pytest.fixture(scope="class")
    def factory_df(
        self, gold_month_range: tuple[int, int],
    ) -> pd.DataFrame:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")
        start, end = gold_month_range
        df = load_dataset(
            region="africa_me_legacy",
            start=start,
            end=end,
            features=FACTORY_FEATURES,
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )
        return _build_parity_df(df)

    def test_shape(
        self,
        factory_df: pd.DataFrame,
        gold_df: pd.DataFrame,
    ) -> None:
        assert factory_df.shape == gold_df.shape, (
            f"Shape: factory={factory_df.shape}, "
            f"gold={gold_df.shape}"
        )

    def test_month_range(
        self,
        factory_df: pd.DataFrame,
        gold_df: pd.DataFrame,
    ) -> None:
        f_months = sorted(
            factory_df.index.get_level_values("month_id").unique()
        )
        g_months = sorted(
            gold_df.index.get_level_values("month_id").unique()
        )
        assert f_months == g_months, (
            f"Month range: factory {f_months[0]}-{f_months[-1]} "
            f"({len(f_months)}), "
            f"gold {g_months[0]}-{g_months[-1]} ({len(g_months)})"
        )

    def test_pgid_set(
        self,
        factory_df: pd.DataFrame,
        gold_pgids: set[int],
    ) -> None:
        f_pgids = set(
            factory_df.index.get_level_values("priogrid_gid").unique()
        )
        assert f_pgids == gold_pgids, (
            f"PGIDs: factory={len(f_pgids)}, gold={len(gold_pgids)}, "
            f"missing={len(gold_pgids - f_pgids)}, "
            f"extra={len(f_pgids - gold_pgids)}"
        )

    def test_row_col_exact(
        self,
        factory_df: pd.DataFrame,
        gold_df: pd.DataFrame,
    ) -> None:
        np.testing.assert_array_equal(
            factory_df["row"].values, gold_df["row"].values,
        )
        np.testing.assert_array_equal(
            factory_df["col"].values, gold_df["col"].values,
        )

    def test_feature_parity(
        self,
        factory_df: pd.DataFrame,
        gold_df: pd.DataFrame,
    ) -> None:
        _assert_feature_parity(
            factory_df, gold_df, PARITY_FEATURES,
        )


# ── Test 1b: PGM land ────────────────────────────────────


@pytest.mark.consumer
class TestPGMLandParity:
    """Partial comparison: factory land overlapping cells vs gold set,
    plus structural checks on the remaining cells."""

    @pytest.fixture(scope="class")
    def factory_land_df(
        self, gold_month_range: tuple[int, int],
    ) -> pd.DataFrame:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")
        start, end = gold_month_range
        df = load_dataset(
            region="land",
            start=start,
            end=end,
            features=FACTORY_FEATURES,
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )
        return _build_parity_df(df)

    def test_land_is_superset_of_gold(
        self,
        factory_land_df: pd.DataFrame,
        gold_pgids: set[int],
    ) -> None:
        f_pgids = set(
            factory_land_df.index.get_level_values(
                "priogrid_gid"
            ).unique()
        )
        missing = gold_pgids - f_pgids
        assert not missing, (
            f"{len(missing)} gold set pgids missing from factory land"
        )

    def test_overlap_parity(
        self,
        factory_land_df: pd.DataFrame,
        gold_df: pd.DataFrame,
        gold_pgids: set[int],
    ) -> None:
        mask = factory_land_df.index.get_level_values(
            "priogrid_gid"
        ).isin(gold_pgids)
        overlap = factory_land_df.loc[mask].sort_index()
        assert overlap.shape == gold_df.shape, (
            f"Overlap shape: {overlap.shape} vs gold {gold_df.shape}"
        )
        _assert_feature_parity(
            overlap, gold_df, PARITY_FEATURES,
        )

    def test_land_cell_count(
        self, factory_land_df: pd.DataFrame,
    ) -> None:
        n_pgids = factory_land_df.index.get_level_values(
            "priogrid_gid"
        ).nunique()
        assert n_pgids == 64818, f"Expected 64,818 land cells, got {n_pgids}"

    def test_non_overlap_structural(
        self,
        factory_land_df: pd.DataFrame,
        gold_pgids: set[int],
    ) -> None:
        mask = ~factory_land_df.index.get_level_values(
            "priogrid_gid"
        ).isin(gold_pgids)
        rest = factory_land_df.loc[mask]

        rest_pgids = rest.index.get_level_values("priogrid_gid")
        assert rest_pgids.min() >= 1
        assert rest_pgids.max() <= 259200

        for col in PARITY_FEATURES:
            assert (rest[col] >= 0).all(), (
                f"Negative values in {col} outside gold set region"
            )

        nonzero_sb = (rest["lr_sb_best"] > 0).sum()
        assert nonzero_sb > 0, (
            "No conflict events outside africa_me — "
            "Americas/Europe/Asia should have events"
        )


# ── Test 1c: CM parity ───────────────────────────────────


@pytest.mark.consumer
class TestCMParity:
    """Country-month parity — derived from PGM gold set.

    The gold set has VIEWSER c_id (range 40-254); the factory uses
    GAUL codes. Some PGM cells (~603 in africa_me_legacy) have no
    GAUL match (coastal/island cells whose centroids fall outside
    any GAUL polygon). These cells are included in PGM output but
    correctly excluded from CM aggregation since they cannot be
    attributed to a country. Per-month totals are compared with a
    tolerance that accounts for this structural gap, and internal
    consistency is verified by filtering PGM to gaul0_code > 0.
    """

    @pytest.fixture(scope="class")
    def gold_cm_totals(
        self, gold_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Per-month totals from the gold set."""
        return gold_df.groupby("month_id")[
            PARITY_FEATURES
        ].sum()

    @pytest.fixture(scope="class")
    def factory_cm_df(
        self, gold_month_range: tuple[int, int],
    ) -> pd.DataFrame:
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")
        start, end = gold_month_range
        return load_dataset(
            region="africa_me_legacy",
            start=start,
            end=end,
            features=FACTORY_FEATURES,
            output_format="country_month",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )

    @pytest.fixture(scope="class")
    def factory_cm_totals(
        self, factory_cm_df: pd.DataFrame,
    ) -> pd.DataFrame:
        renamed = factory_cm_df.rename(columns=FEATURE_RENAME)
        return renamed.groupby("month_id")[
            PARITY_FEATURES
        ].sum()

    def test_per_month_totals(
        self,
        factory_cm_totals: pd.DataFrame,
        gold_cm_totals: pd.DataFrame,
    ) -> None:
        """Most months have small per-month diffs (< 100 fatalities)."""
        common_months = sorted(
            set(factory_cm_totals.index)
            & set(gold_cm_totals.index)
        )
        assert len(common_months) > 400, (
            f"Only {len(common_months)} common months"
        )

        for col in PARITY_FEATURES:
            fv = factory_cm_totals.loc[common_months, col].values
            gv = gold_cm_totals.loc[common_months, col].values
            diff = np.abs(fv - gv)
            n_large = int((diff > 100).sum())
            rate = n_large / len(common_months)
            assert rate <= 0.25, (
                f"CM {col}: {n_large}/{len(common_months)} "
                f"months differ by >100 ({rate:.4%})"
            )

    def test_global_sum_parity(
        self,
        factory_cm_totals: pd.DataFrame,
        gold_cm_totals: pd.DataFrame,
    ) -> None:
        """CM totals within tolerance of gold set."""
        for col in PARITY_FEATURES:
            f_total = float(factory_cm_totals[col].sum())
            g_total = float(gold_cm_totals[col].sum())
            if g_total == 0:
                continue
            gap = abs(f_total - g_total) / g_total
            assert gap <= CM_SUM_GAP_THRESHOLD, (
                f"CM {col}: total gap {gap:.4%} — "
                f"factory={f_total:,.0f}, gold={g_total:,.0f}"
            )

    def test_pgm_cm_internal_consistency(
        self,
        factory_cm_df: pd.DataFrame,
        gold_month_range: tuple[int, int],
    ) -> None:
        """Factory PGM (gaul0_code > 0) grouped by country == Factory CM."""
        if not DATA_DIR.exists():
            pytest.skip(f"Assembled grid not found: {DATA_DIR}")
        start, end = gold_month_range
        pgm = load_dataset(
            region="africa_me_legacy",
            start=start,
            end=end,
            features=FACTORY_FEATURES + ["gaul0_code"],
            output_format="dataframe",
            data_dir=DATA_DIR,
            gaul_dir=GAUL_DIR,
            month_id_epoch=MONTH_ID_EPOCH,
        )
        pgm = pgm.fillna(0.0)
        pgm = pgm[pgm["gaul0_code"] > 0]
        pgm_agg = pgm.groupby(
            [pgm.index.get_level_values("month_id"), "gaul0_code"]
        )[FACTORY_FEATURES].sum()
        pgm_agg.index.names = ["month_id", "country_id"]
        pgm_agg = pgm_agg.sort_index()

        cm = factory_cm_df.sort_index()
        cm_features = cm[FACTORY_FEATURES].fillna(0.0)

        pgm_totals = pgm_agg.groupby("month_id").sum()
        cm_totals = cm_features.groupby("month_id").sum()

        common = sorted(
            set(pgm_totals.index) & set(cm_totals.index)
        )
        for col in FACTORY_FEATURES:
            pv = pgm_totals.loc[common, col].values.astype(np.float64)
            cv = cm_totals.loc[common, col].values.astype(np.float64)
            np.testing.assert_allclose(
                pv, cv, rtol=1e-4, atol=1.0,
                err_msg=(
                    f"PGM→CM inconsistency in {col}: "
                    "grouped PGM totals != CM totals"
                ),
            )
