# ADR-050: Consumer Contract Export — Vocabulary, Executable Layout Spec, and Ownership

**Status:** Accepted
**Date:** 2026-07-21
**Deciders:** Operator (maintainer of views-datafactory and views-frames)
**Consulted:** Multi-expert design review 2026-07-21 (#116, epic #342); pipeline-core epic #265 context comment
**Informed:** pipeline-core (#162), views-baseline (FeatureFrame-native since their PR #60)

---

## Context

datafactory owns the data-format contract that downstream repos depend on, but
expresses it as internals:

- The valid `output_format` values live in `_VALID_FORMATS`, an
  underscore-private tuple in `src/datafactory_query/dataset.py`. pipeline-core
  re-declares the strings by hand (their `dataloaders.py`, risk C-62 on their
  side). A rename here is a silent string mismatch there.
- The FeatureFrame on-disk layout has no authoritative specification anywhere.
  The cost is already demonstrated: issue #116's own Evidence section
  (2026-06-04) documents a layout (`y_features.npy` + `feature_names.json` +
  `metadata.json`) that ceased to exist when the implementation moved to
  views-frames v1.0.0 (#220) — the real `save()` writes `header.json` +
  `identifiers.npz` + `values.npy`. The prose spec drifted within three weeks
  of being written.
- Consumers are now live, not hypothetical: pipeline-core epic #265 has the
  contract import as its first story, and views-baseline runs FeatureFrame-
  native models in production with float32 as an accepted platform property.
- Two fresh institutional lessons bind this decision: C-311 (checks must be
  validated against real data before becoming authoritative) and C-315 (test
  fixtures that do not mirror real artifact shapes validate readers against
  themselves — that bug disabled pre-coverage warnings on real data for two
  sprints while every test passed).
- Dependency reality: the views-datafactory wheel requires matplotlib,
  shapely, tifffile, imagecodecs, xarray, zarr. Requiring consumers to
  `pip install views-datafactory` for three strings is not acceptable
  (Common Reuse Principle violation).

## Decision

1. **datafactory exports the query vocabulary as a public contract.**
   A single-concept module `datafactory_query/output_format.py` provides
   `OutputFormat` (a `StrEnum` with members `FEATURE_FRAME = "feature_frame"`,
   `DATAFRAME = "dataframe"`, `COUNTRY_MONTH = "country_month"`),
   `CONTRACT_VERSION`, and `is_valid_output_format()`. These are exported via
   `datafactory_query.__all__`. `_VALID_FORMATS` remains as an internal alias
   derived from the enum.

2. **The contract's canonical form is data, not code.** A language-neutral
   `contract.json` (formats, contract version, identifier semantics, dtype,
   tensor shape, fixture digest) is committed beside a conformance fixture.
   The Python enum is a typed projection of it; a test asserts the enum,
   the JSON, and `_VALID_FORMATS` agree (three-way agreement). Consumers who
   cannot afford the wheel read the JSON; consumers who install us import
   the enum. Both are first-class adoption paths.

3. **The layout specification is executable.** A conformance fixture — a
   small FeatureFrame directory produced by the real
   `views_frames.FeatureFrame.save()` — is committed at
   `tests/fixtures/feature_frame_contract/` with a pinned digest.
   Fixture policy (the C-315 generalization):
   - The fixture is NEVER hand-authored and NEVER generated inside test
     setup. It is committed output of the real writer.
   - Regeneration is a deliberate act: run the documented generation script,
     review the diff, bump `CONTRACT_VERSION`, record the new digest.
   - A regeneration-identity test re-runs the generator into a temp dir and
     asserts byte-identity with the committed fixture. A views-frames
     version bump that changes the layout fails this test immediately —
     that failure is the intended drift alarm, not a nuisance.

4. **Ownership split** (approved by the operator, who maintains both repos):
   - **views-frames owns the byte-level layout.** Its `save()`/`load()`
     write and read the bytes; the layout specification lives in
     views-frames documentation, in the blast radius of the PRs that can
     change it (Common Closure Principle). datafactory documentation LINKS
     to it and never restates byte-level detail.
   - **datafactory owns the query vocabulary** (`OutputFormat`,
     `CONTRACT_VERSION`) and the semantics of what `load_dataset` returns
     per format: `unit` identifiers are `priogrid_id` / `country_id`
     (views-frames ADR-015; datafactory #316), `values` are float32
     contractually, index is (`time`, `unit`).
   - **datafactory hosts the conformance fixture** (it is the producer of
     real frames); views-frames and consumer repos may adopt the same
     fixture in their CI.

5. **Stability promise.**
   - The meaning of the three existing members never changes.
   - Removing or renaming a member is a MAJOR version event for the wheel
     and a MAJOR bump of `CONTRACT_VERSION`.
   - Adding a member is a MINOR event for both.
   - `CONTRACT_VERSION` is independent of the package version and changes
     ONLY for contract-affecting changes (vocabulary, layout, semantics).
   - The conformance test pins `CONTRACT_VERSION` to the fixture digest, so
     the two cannot drift apart silently.

**Out of scope:** a format-dispatch registry inside `load_dataset` (deferred
until a fourth format exists — same WET-before-DRY discipline as D-38); any
new top-level package or separate release unit (one wheel, REP); moving
`OutputFormat` into views-frames (rejected below); exporting `RemoteConfig`,
regions, or partitions (no consumer has asked; CRP guard).

## Rationale

- **Executable spec over prose.** #116's internal drift and C-315 are two
  demonstrations in one month that documentation which is not executed is
  documentation that lies. A committed artifact + digest + round-trip test
  cannot drift silently.
- **Data as the canonical form.** The contract must be honorable without
  installing our heavy wheel. JSON + fixture achieves that; the enum adds
  typed breaks for Python consumers who do install us.
- **Dependency direction (SDP/SAP).** views-frames is the platform's stable
  shared leaf; it must not accrete one producer's API vocabulary. Conversely,
  the byte layout must live where the bytes are written, or every layout PR
  in views-frames silently invalidates a spec it cannot see.
- **Export from a stable module.** `dataset.py` is the least stable file in
  the package (611 lines, five responsibilities, C-315's hiding place).
  Consumers depend on `output_format.py`, a module with one reason to change.

## Considered Alternatives

### Alternative A: Export `OutputFormat` from `dataset.py` (in-place)
- **Pros:** smallest diff.
- **Cons:** makes the least stable module the most depended-upon (SDP
  inversion); entrenches the dumping ground.
- **Reason for rejection:** consumers must depend toward stability.

### Alternative B: Vocabulary and layout both owned by views-frames
- **Pros:** one contract home; views-frames is dependency-light, so imports
  are cheap for every consumer.
- **Cons:** couples the platform's stable leaf to datafactory's API
  vocabulary (`country_month` is a `load_dataset` return shape, not a frame
  concept); every vocabulary change becomes a views-frames release.
- **Reason for rejection:** wrong dependency direction. Revisit only if
  `OutputFormat` provably becomes platform-wide vocabulary used by producers
  other than datafactory. Recorded as a disagreement in the risk register.

### Alternative C: Separate dependency-light `datafactory-contract` package
- **Pros:** cheap imports without the wheel.
- **Cons:** a new release unit for three strings and a validator (REP
  violation); `contract.json` achieves the same consumer affordance with no
  packaging cost.
- **Reason for rejection:** `contract.json` is the no-install path. Revisit
  if a consumer concretely rejects both the wheel and the JSON.

## Consequences

### Positive
- pipeline-core deletes its hand-copied strings (their C-62) and chooses
  import or JSON; a datafactory rename becomes a typed/CI break, not a
  silent mismatch.
- Layout drift between views-frames versions is caught by our CI at the
  version-bump PR, not by a consumer in production.
- The C-315 bug class (synthetic-shape fixtures) is structurally prevented
  for this contract.

### Negative
- Consumers couple to our release cadence to the extent they import the
  enum (mitigated by the JSON path and the stability promise).
- The committed fixture adds a maintenance ritual: deliberate regeneration
  on views-frames layout changes. This cost is the feature.
- Until Story 4 lands the views-frames layout doc, the byte-level spec's
  only authoritative form is the fixture itself (accepted for the interim).

## Implementation Notes

Implemented by epic #342: fixture + `contract.json` (#344), module + export
(#345), `dataset.py` split so the exporting package screams its
responsibilities (#346), documentation + cross-repo adoption (#347).
Cross-references: #116, C-311, C-315, C-62 (pipeline-core), views-frames
ADR-015, ADR-046 (schema evolution precedent), D-38 (WET discipline).
