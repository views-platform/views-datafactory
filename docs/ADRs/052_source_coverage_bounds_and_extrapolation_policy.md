# ADR-052: Coverage bounds are published per source, and extrapolation stays where it is

**Status:** Accepted
**Date:** 2026-08-24
**Deciders:** Simon (operator), views-datafactory maintainers
**Consulted:** ADR-011 (fail-loud), ADR-014 §5 (temporal interpolation policy — the precedent this
applies), ADR-042 (SHDI preserves NaN — forward-fill evaluated and rejected), ADR-047 (assembly
temporal anchor — **this ADR answers its line 68**), ADR-040 (count conservation),
views-pipeline-core ADR-040, CRAF'd ADR-025
**Supersedes:** nothing. **Discharges** ADR-047's deferred question.

---

## Context

ADR-047 closes with a sentence that was never assigned:

> Zero-fill remains the gap-filling strategy (not NaN-fill)… **A future ADR may revisit this.**

That deferral was raised twice from outside this repository within a month.

**views-pipeline-core (#420)** filed it as an unowned decision: they audited their own
`fillna(0.0)`, fixed their half so a manufactured zero is logged rather than silent, and stated they
will not build gap-detection on a schema that cannot carry the distinction — *"inferring 'nobody
looked' from a run of zeros is exactly the kind of semantic guess our ADR-040 forbids."*

**CRAF'd, via views-crafdapi (#476)**, filed it as a live defect with a measurement. The historical
artifact they serve carried a complete, zero-filled month for a month nobody had reported:

```
RAW month 557 (May 2026): rows=64742  sum(lr_ged_sb)=3705.0
RAW month 558 (Jun 2026): rows=64742  sum(lr_ged_sb)=2974.0
RAW month 559 (Jul 2026): rows=64742  sum(lr_ged_sb)=0.0
```

Their ADR-025 requires `NaN` for months with no actuals. They shipped `0.0` for 2,432 admin-1 units,
so a consumer scoring forecasts reads *"no fatalities anywhere"* where the truth is *"July has not
been reported"*.

## What investigation found

**The metadata already existed and was discarded.** The provenance-writing block in
`scripts/assemble_grid.py` computes and records into `provenance.json` the trailing bound for
every non-anchor source —
`last_valid_acled_month_id`, `last_valid_ghspop_month_id`, `last_valid_ghsbuilts_month_id`,
`last_valid_vdem_month_id`, `last_valid_shdi_month_id`. `scripts/export_zarr.py` then mirrored
provenance into the published store with a filter matching `first_valid_`. **None of the five
matched.** The work was done every run and thrown away one step before a consumer could read it.

Verified against the live store: `first_valid_month_ids` carried 5 entries, `last_valid_month_id`
carried 1. A consumer could see when ACLED *starts* and not when it *stops*.

**The parquet path published neither.** `scripts/generate_consumer_data.py` wrote a manifest of
digests and filenames with no coverage bounds at all — and FAO and CRAF'd consume that path, not the
zarr.

**ADR-014 §5 already required this, one layer down.** It permits interpolating between a source's own
observations on two conditions, the second being that *"interpolated values must be distinguishable
from source-observed values in provenance."* Assembly's zero-fill is manufactured values under
another name. The principle was settled; it had not been carried up to assembly.

## Decision

### 1. Both edges of every source's coverage are published, on both paths

`last_valid_month_ids` is published in the zarr attributes, symmetric with the existing
`first_valid_month_ids`, and both are copied into the consumer manifest.

**Month-level, per source. No per-cell mask.** A mask would be a second array the size of the grid,
and neither consumer asked for one — #420 asks to be able to tell the difference, #476 asks for one
month-level flag. Minimum machinery that answers the question actually asked.

### 2. `last_valid_month_id` (singular) is untouched

It keeps its name, its value and its meaning. views-postprocessing reads it by that exact name
(`_read_historical_frame` in `crafd/managers/crafd.py` and its `unfao` twin) to decide which
months are labelled **fabricated in the delivery to FAO**, and views-models gates liveness on it.

**C-352 is open on what it should mean** — it is computed from `ged_*` features alone while being
generally named, so it is UCDP's frontier, not the store's. That question is with
views-postprocessing (views-postprocessing#292) and is not answered here. Renaming or re-scoping it
before they answer would break two repositories to fix a name.

### 3. The published bound is INFERRED, not declared, and this ADR says so

`export_zarr.py` marks a month valid when `ucdp_slice.sum(...) > 0`. Two consequences follow
directly, and neither is hypothetical:

- **A genuinely all-zero month reads as unobserved.** This is the same inference #420 calls
  illegitimate, performed by the producer rather than the consumer.
- **A partially-reported month reads as complete.** The live store, exported **2026-08-21**, declared
  `last_valid_month_id = 560` — August 2026, *the month the export ran in*, three weeks old and
  impossible to have fully reported.

**Declaring coverage from harvest provenance is the correct fix and is deliberately deferred.** The
raw material already exists in the ingestion ledgers: `ucdp_candidate.max_date_start`,
`ucdp_annual.max_date_start`, `acled.max_date`, `shdi.year_range`. It is deferred because it changes
the value of a number three repositories already read, and doing that in the same change that first
makes the values visible would confound the two.

**Trigger:** before the next consumer builds logic on `last_valid_month_ids`, or when
views-postprocessing answers C-352 — whichever comes first.

### 4. Extrapolation: name it, bound it by disclosure, do not extend it

**The repository already extrapolates, and no ADR said so.** Both strategies in
`src/datafactory_viewpoint/temporal.py` hold the last epoch's value indefinitely past the end of
support (`interp_step` and `interp_linear`) and emit `0.0` before the first. So `linear` is
linear *inside* the support and constant-hold outside it, and the two edges behave differently for no
recorded reason.

That behaviour is **retained and now disclosed** rather than changed. `last_valid_month_ids` tells a
consumer where real observation stops, which makes held values identifiable and refusable — the
bound is on knowledge, not on the code path. Removing the carry-forward would change delivered values
for GHS-POP and GHS-BUILT-S in every month past their last epoch, and ADR-047 rejected NaN-fill
precisely because consumers assume float32 without NaN handling.

**No new extrapolation is introduced**, because criterion 7 below fails today: nobody is blocked by
missing values, and #476 asks for the opposite — the ability to *tell* that data is absent.

### 5. Criteria for any future extrapolation

All must hold. These are a gate, not a checklist to argue around.

1. **Stock, not flow.** A slowly-varying state — population, built-up area, an index. **Never an
   event count.** Extrapolating UCDP or ACLED fabricates deaths; this one is categorical.
2. **Constant-hold only. No trend extension.** The trend is precisely the quantity not measured, and
   extending it compounds an unmeasured rate. Counter-intuitively this makes `step` the *safer*
   strategy and `linear` the forbidden one, outside the support.
3. **Bounded horizon, expressed in the source's own sampling interval** — at most one interval past
   the last observation. SHDI's three-year gap on an annual series fails this; V-Dem's ~1-year lag
   does not.
4. **Back-tested error, published.** Hold out the last real epoch, extrapolate to it, measure the
   error, publish the number. **If the error cannot be measured, the value cannot ship.** This is the
   criterion that does the most work, and the one ADR-042's rejected B1 would have failed.
5. **Distinguishable per cell-month, not per config.** ADR-014 §5 condition 2, extended: recording
   that a strategy was configured is not the same as marking which values it manufactured.
6. **Refusable.** One consumer-side filter must drop every extrapolated month.
7. **NaN must be demonstrably worse**, with a named consumer who says so. Absent that, NaN plus
   coverage metadata wins — it is strictly more honest, and ADR-042 established that a filled value
   without an error bar narrows downstream confidence intervals *"even with provenance flags"*.

### 6. Provider projections are declared where they are produced

`docs/sources/ghspop.md` and `docs/sources/ghsbuilts.md` state that the **2025 and 2030 epochs
are projections** — UN WPP-based for GHS-POP, classification projections for GHS-BUILT-S. They are
delivered in the grid identically to observed epochs, so a population value for 2026 is somebody
else's forecast wearing the provenance of a measurement.

`PROVIDER_PROJECTED_EPOCHS` is now declared in both builders and recorded in each viewpoint ledger.

**Known limitation, stated rather than implied:** this is not surfaced in the served store. Doing so
would require assembly to read viewpoint ledgers — new coupling for a static, documented fact that no
consumer has asked to filter on programmatically. **Trigger: when a consumer needs to select on
projected epochs.** Recorded explicitly because the defect this ADR exists to fix was metadata that
was computed and then hidden, and repeating that pattern silently would be worse than not computing
it at all.

## Consequences

- **Positive.** #476 and #420 are answerable with data rather than prose. A consumer on either path
  can bound every source's real observation window. The change is a filter and a dict; no schema
  version, no new artifact, no dependency.
- **Negative.** The published bounds are only as good as an inference this ADR admits is wrong at
  both ends. A consumer trusting `last_valid_month_ids` inherits the partial-month flaw until §3's
  trigger fires. Said plainly here so it is not discovered downstream.
- **Neutral.** `last_valid_month_id` remains UCDP-scoped and ambiguously named until C-352 is
  answered elsewhere.

## Inconsistency noted, not resolved

ADR-042 states *"All other viewpoints (UCDP, ACLED, V-Dem, GHS-POP, GHS-BUILT-S) preserve NaN."*
GHS-POP and GHS-BUILT-S carry their last epoch forward past the end of support, which is not NaN
preservation. The two are most likely talking about different axes — ADR-042 about *spatial* absence,
this about the *temporal* tail — but the sentence as written is broader than that reading. Flagged
for whoever next amends ADR-042; not amended here, because guessing which of two readings its author
meant is how a correction becomes a second error.

## References

- ADR-014 §5 (interpolation policy — the precedent), §6 (the responsibility boundary)
- ADR-042 (forward-fill evaluated and rejected; Harrell 2015, Gelman et al. 2013)
- ADR-047 line 68 (the deferral this discharges)
- `scripts/assemble_grid.py` (where both bounds are computed)
- `scripts/export_zarr.py::_coverage_attrs_from_provenance` (where they are now published)
- `scripts/generate_consumer_data.py` (the manifest)
- `src/datafactory_viewpoint/temporal.py` (the carry-forward this ADR names)
- GitHub: #476, #420; views-postprocessing#292; register C-352, C-130
