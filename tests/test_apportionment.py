"""The five properties of the shared apportionment rounder.

Specified in
``reports/2026-11-04_summary_event_allocation_dossier/11_allocator_spec.md``
section 3. Every allocation strategy composes a weight function with this
rounder, so conservation is proved here once instead of per strategy --
which means these tests carry the weight of ADR-040 Invariant 1 for the
whole allocation layer.

Exhaustive over small supports, randomised over large ones. The exhaustive
half matters: the defect that motivated this module (ranking by weight
rather than by remainder) shows up at ``total=10`` over three cells, which
no plausible hand-written example would have covered.
"""

from __future__ import annotations

import math
import random

import pytest

from datafactory_viewpoint.apportionment import apportion


# Coarse simplex grid: every weight vector on n keys with tenths summing
# to 10. Small enough to enumerate, varied enough to include exact
# integer shares (where boundedness is tightest) and zeros (where P4 is).
def _simplex(n: int, parts: int = 10):
    if n == 1:
        yield (parts,)
        return
    for first in range(parts + 1):
        for rest in _simplex(n - 1, parts - first):
            yield (first, *rest)


def _vectors(n: int):
    for raw in _simplex(n):
        if sum(raw) == 0:
            continue
        yield {i: raw[i] / 10 for i in range(n)}


class TestP1Conservation:
    """sum(result) == total, exactly, always."""

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_exhaustive_small(self, n: int) -> None:
        for total in range(0, 31):
            for w in _vectors(n):
                assert sum(apportion(total, w).values()) == total

    def test_randomised_large(self) -> None:
        rng = random.Random(20261105)
        for _ in range(3000):
            n = rng.randint(1, 40)
            w = {i: rng.random() for i in range(n)}
            total = rng.randint(0, 2_000_000)
            assert sum(apportion(total, w).values()) == total

    def test_the_tigray_magnitude(self) -> None:
        """The real case: 113,368 over the 18 cells of GAUL admin-1 1301."""
        rng = random.Random(1301)
        w = {i: rng.random() for i in range(18)}
        out = apportion(113_368, w)
        assert sum(out.values()) == 113_368
        assert len(out) == 18


class TestP2Boundedness:
    """Each allocation is the floor or the ceiling of its ideal share.

    This is the property the previous weight-ranked implementation broke:
    total=10 over (0.5, 0.25, 0.25) returned (6, 2, 2) when the first
    cell's ideal share is exactly 5.0.
    """

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_exhaustive_small(self, n: int) -> None:
        for total in range(0, 31):
            for w in _vectors(n):
                mass = math.fsum(w.values())
                out = apportion(total, w)
                for key, got in out.items():
                    ideal = total * w[key] / mass
                    assert math.floor(ideal) <= got <= math.ceil(ideal), (
                        f"total={total} w={w} key={key} got={got} "
                        f"ideal={ideal}"
                    )

    def test_the_regression_case(self) -> None:
        out = apportion(10, {0: 0.5, 1: 0.25, 2: 0.25})
        assert out[0] == 5, (
            "key 0's ideal share is exactly 5.0; allocating 6 is the "
            "weight-ranked defect this module replaced"
        )
        assert sum(out.values()) == 10


class TestP3Determinism:
    """Identical input, identical output -- ADR-014 Principle 3."""

    def test_repeated_calls_agree(self) -> None:
        w = {7: 0.31, 3: 0.19, 11: 0.5}
        first = apportion(1_234_567, w)
        for _ in range(5):
            assert apportion(1_234_567, w) == first

    def test_insertion_order_does_not_matter(self) -> None:
        """Needs the LEADING remainder tied, or it proves nothing.

        An earlier version of this test used weights whose largest
        remainder was unique. Python's ``sorted`` is stable, so the
        key tie-break was never exercised and removing it left the
        test green -- a guard that could not fail. The case below ties
        the leaders: 11 over two equal weights leaves remainders of
        0.5 and 0.5, so without an explicit tie-break the winner is
        whichever key was inserted first.
        """
        a = apportion(11, {1: 0.5, 2: 0.5})
        b = apportion(11, {2: 0.5, 1: 0.5})
        assert a == b, "result depends on dict ordering; tie-break is broken"
        assert a == {1: 6, 2: 5}, (
            "a tied remainder must resolve to the lower key, not to "
            "insertion order"
        )

    def test_tied_remainders_resolve_by_key_across_many_sizes(self) -> None:
        for n in (2, 3, 4, 5, 6):
            w = dict.fromkeys(range(n), 1.0)
            for extra in range(1, n):
                out = apportion(n * 10 + extra, w)
                winners = sorted(k for k, v in out.items()
                                 if v == max(out.values()))
                assert winners == list(range(extra)), (
                    f"n={n} extra={extra}: the surplus should go to the "
                    f"lowest keys, got winners {winners}"
                )


class TestP4ZeroPreservation:
    """A support point with no evidence never receives mass.

    This is what makes activity weighting honest rather than smearing: a
    month or cell with zero observed activity gets zero, not a rounding
    crumb.
    """

    @pytest.mark.parametrize("n", [2, 3])
    def test_exhaustive_small(self, n: int) -> None:
        for total in range(0, 31):
            for w in _vectors(n):
                out = apportion(total, w)
                for key, weight in w.items():
                    if weight == 0:
                        assert out[key] == 0, (
                            f"zero weight received {out[key]} "
                            f"(total={total} w={w})"
                        )

    def test_randomised_with_many_zeros(self) -> None:
        rng = random.Random(4)
        for _ in range(2000):
            n = rng.randint(2, 30)
            w = {i: (rng.random() if rng.random() < 0.3 else 0.0)
                 for i in range(n)}
            if math.fsum(w.values()) == 0:
                continue
            total = rng.randint(1, 10_000)
            out = apportion(total, w)
            assert all(out[k] == 0 for k, v in w.items() if v == 0)
            assert sum(out.values()) == total


class TestP5OrderPreservation:
    """Weight at least another's implies allocation at least as large."""

    @pytest.mark.parametrize("n", [2, 3])
    def test_exhaustive_small(self, n: int) -> None:
        for total in range(0, 31):
            for w in _vectors(n):
                out = apportion(total, w)
                for i in w:
                    for j in w:
                        if w[i] > w[j]:
                            assert out[i] >= out[j], (
                                f"w[{i}]={w[i]} > w[{j}]={w[j]} but "
                                f"got {out[i]} < {out[j]} (total={total})"
                            )


class TestTheSparseRegime:
    """total < support size: allocation is subset selection, not a spread.

    Named in the spec as where the surprises live, and the reason
    ``ceil``-based spreading had to go: one death over three months must
    stay one death.
    """

    def test_one_death_over_twelve_months_stays_one(self) -> None:
        w = dict.fromkeys(range(12), 1 / 12)
        out = apportion(1, w)
        assert sum(out.values()) == 1
        assert sum(1 for v in out.values() if v > 0) == 1

    def test_nonzero_count_is_bounded_by_total(self) -> None:
        rng = random.Random(99)
        for _ in range(500):
            n = rng.randint(5, 50)
            total = rng.randint(0, n - 1)
            w = {i: rng.random() for i in range(n)}
            out = apportion(total, w)
            nonzero = sum(1 for v in out.values() if v > 0)
            assert nonzero <= total, (
                "row count must be bounded by min(total, support size)"
            )


class TestGuards:
    """Fail loud, never silently normalise a broken cascade (ADR-011)."""

    def test_empty_support(self) -> None:
        assert apportion(5, {}) == {}

    def test_negative_total(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            apportion(-1, {0: 1.0})

    def test_negative_weight(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            apportion(10, {0: 1.0, 1: -0.5})

    def test_nan_weight(self) -> None:
        with pytest.raises(ValueError, match="not finite"):
            apportion(10, {0: 1.0, 1: float("nan")})

    def test_inf_weight(self) -> None:
        with pytest.raises(ValueError, match="not finite"):
            apportion(10, {0: float("inf")})

    def test_all_zero_weights_with_mass_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="cascade"):
            apportion(10, {0: 0.0, 1: 0.0})

    def test_all_zero_weights_with_no_mass_is_fine(self) -> None:
        assert apportion(0, {0: 0.0, 1: 0.0}) == {0: 0, 1: 0}

    def test_weights_need_not_sum_to_one(self) -> None:
        out = apportion(100, {0: 3.0, 1: 1.0})
        assert out == {0: 75, 1: 25}
