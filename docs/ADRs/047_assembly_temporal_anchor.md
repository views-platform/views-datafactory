
# ADR-047: Assembly Temporal Anchor

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** Simon (data engineer)
**Consulted:** Risk register C-286, C-156; ADR-024 (grid invariants), ADR-040 (count conservation)

---

## Context

The assembled grid has shape `[T, H, W, C]` where `T` is the number of monthly time steps. This temporal extent is defined by UCDP's `time_steps.npy` — UCDP is loaded first, and its `n_t` becomes the grid's temporal dimension. Every other source must align to this timeline via `_load_source_grid()` (`scripts/assemble_grid.py`), which:

1. Finds the source's first time step in UCDP's `time_steps` array
2. Computes an integer offset
3. Rejects sources whose start date is not in the UCDP timeline
4. Rejects sources that extend beyond the UCDP timeline
5. Places source data at `assembled[offset:offset+n_source_t, :, :, channels]`

Months outside a source's coverage are zero-filled (the grid is pre-allocated with `np.zeros`). This zero-fill is structurally indistinguishable from months where the source observed zero events.

Two risk register entries identified consequences of this undeclared dependency:

- **C-286 (Tier 3):** If UCDP's temporal range contracts (e.g., early years removed from a release), data from other sources that covered those years is silently dropped. If a new source pre-dates UCDP (before 1989), assembly cannot accommodate it.

- **C-156 (Tier 4):** ACLED covers 2020-present; UCDP covers 1989-present. Pre-2020 ACLED channels are zero-filled. Models consuming ACLED features for 1989-2019 see zeros that represent "source did not exist," not "zero events observed." No metadata distinguished these two cases — only `last_valid_*_month_id` (trailing edge) and `*_temporal_offset` (integer index) were recorded.

---

## Decision

UCDP is the declared temporal anchor for the assembled grid. This ADR documents existing behavior and adds metadata to make the dependency explicit.

### Rules

1. **UCDP defines the timeline.** UCDP's `time_steps.npy` sets `n_t` and the temporal backbone. The assembled grid's first month equals UCDP's first month; its last month equals UCDP's last month.

2. **All sources must fit within the UCDP timeline.** A source whose first time step is not in UCDP's `time_steps` array is rejected (`_load_source_grid` returns `None`). A source that extends beyond `n_t` is rejected.

3. **Partial-coverage sources are zero-filled.** Sources with shorter temporal coverage than UCDP get zeros in months outside their range. This is an inherent consequence of pre-allocating the grid with `np.zeros`.

4. **Both edges of coverage are recorded in provenance.** Each non-UCDP source records `first_valid_*_month_id` (leading edge — where the source's data begins) and `last_valid_*_month_id` (trailing edge — where the source's data ends). UCDP's coverage equals the grid's coverage by definition.

5. **Consumers are warned about zero-fill.** `load_dataset()` emits a `UserWarning` when a query's start month is before a source's `first_valid_*_month_id` and the requested features include that source.

6. **Temporal backbone extension is a manual operator decision.** If a future source pre-dates UCDP (e.g., a dataset starting in 1970), the temporal backbone must be extended by choosing a new anchor or extending UCDP's `time_steps`. This is not automated — it requires an ADR amendment and assembly changes.

### Current source coverage (as of v1.2.29)

| Source | Temporal range | Offset from UCDP |
|--------|---------------|-------------------|
| UCDP (GED) | 1989-01 – present | 0 (anchor) |
| ACLED | 2020-01 – present | ~372 months |
| GHS-POP | 1975 – 2030 (5-year) | varies |
| GHS-BUILT-S | 1975 – 2030 (5-year) | varies |
| V-Dem | 1789 – present (annual) | 0 (pre-dates UCDP, clipped) |
| SHDI | 1990 – 2023 (annual) | ~12 months |

---

## Consequences

- **Positive:** The temporal anchor dependency is now documented. Consumers can inspect `first_valid_*_month_id` in provenance to know where zero-fill begins. The `UserWarning` in `load_dataset()` prevents silent consumption of zero-fill data.

- **Negative:** UCDP remains a single point of failure for the temporal dimension. If UCDP changes its temporal range, all sources are affected. This is accepted — decoupling the temporal backbone from UCDP would require a separate, larger architectural change.

- **Neutral:** Zero-fill remains the gap-filling strategy (not NaN-fill). NaN-fill would be more explicit but would break downstream models that assume float32 without NaN handling. **Revisited by ADR-052 (2026-08-24).** That sentence sat unowned for months and the question was raised twice from outside the repository before it was taken — views-pipeline-core#420 and views-crafdapi (#476), the latter with a delivered month of zeros a partner could not distinguish from observation. ADR-052's answer: zero-fill stays, and both edges of every source's coverage are published so a consumer can tell manufactured months from observed ones. **A deferral with no owner, no trigger and no issue is not a decision postponed — it is a decision avoided, and a downstream consumer pays for it.**

---

## References

- ADR-024: Grid shape invariants (`[T, H, W, C]`)
- ADR-040: Count conservation and hierarchical reconciliation
- C-286: UCDP as implicit temporal anchor (resolved by this ADR)
- C-156: ACLED zero-fill before 2020 in assembled grid (resolved by `first_valid_*_month_id` metadata)
- `scripts/assemble_grid.py`: `_load_source_grid()` (temporal alignment logic)
