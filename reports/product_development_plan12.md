# Product Development Plan v12 — current through v1.12, 11 registry sources, 79 Features, on PyPI

**Date:** 2026-06-29 (v1.10 addendum 2026-07-31)
**Supersedes:** product_development_plan11.md (2026-05-08)
**Status:** Active
**Goal:** A data factory that training scripts can depend on — robust subsetting, multiple output formats, verified parity, and data across conflict, population, built environment, democracy, and human development. Counted three ways, because one number was never right: **11** harvest entries in the source registry, **8** distinct upstream providers (UCDP is three entries, one provider), **6** sources wired into `assemble_grid.py`. Earlier revisions said "9 data sources", which matched none of these — see C-164's 2026-07-31 addendum.

---

## v1.12 Addendum (2026-08-13)

**v1.12.0 (Python floor; no change to shipped code).** `src/` is untouched again — the wheel is
byte-identical apart from metadata. Minor rather than patch because the *supported environment set
grew*: `requires-python` moved `>=3.12` → `>=3.11`.

*Why it was a problem worth a release.* This repository was the only one on the platform above 3.11.
Everything else declares `>=3.10` or `>=3.11`, and the views-models conda environments run 3.11.14 /
3.11.15 — so `pip install views-datafactory` failed in all four of them, and 28 requirements files
could not use the package at all. The floor was never chosen: ADR-030 set `>=3.12` in May because
*"tifffile's current releases require it"*, a fact about a vendor at a moment. 3.11 was never
considered — the string does not appear in that ADR. Nothing in our own code needs 3.12; verified by
running the suite, ruff, mypy and `compileall` at 3.11.13 before deciding.

*The cost, which is permanent and worth stating.* `uv.lock` now forks. Under 3.11 the raster stack
resolves `tifffile 2026.3.3` / `imagecodecs 2026.3.6`; under >=3.12 it stays `2026.5.15` /
`2026.5.10`. Both upstreams dropped 3.11 deliberately — tifffile adopted PEP 695 syntax, imagecodecs
ships `cp312-abi3` wheels only — so a 3.11 consumer is pinned to the March-2026 line for good. The
required CI check runs the floor and therefore exercises the *older* decoder than the server does
(**C-347**); a non-required `test-py313` job covers the production line until it can be made
required. ADR-030 amended rather than superseded — the tooling decision was never in question.

*What the change exposed rather than caused.* `imagecodecs` decodes every GHS-POP and GHS-BUILT-S
GeoTIFF — all of them LZW — is imported by **nothing** under `src/`, and until this release **no
test in this repository had ever written a compressed TIFF**. An import-graph audit would have
called the dependency removable, and removing it would have broken every production raster read
while leaving the suite green. Now covered. Also registered: **C-348** (nothing asserts which
interpreter the server runs, and the wider floor now lets that choice select a decoder) and
**C-349** (a config value restated in prose has nothing binding it back — the deployment guide said
"Install Python 3.10+" for the three months the floor was `>=3.12`).

---

## v1.11 Addendum (2026-08-03)

**v1.11.0 (governance repair; no change to shipped code).** `src/` is untouched — the wheel is
byte-identical to v1.10.0 apart from metadata. Minor rather than patch for exactly one reason: the
`views-frames` floor moved.

*The dependency floor, and why it is a release at all.* `views-frames>=1.0` was too loose, and worse,
`uv.lock` had **pinned 1.0.0 since June** — `uv lock` keeps an existing pin while it still satisfies
the constraint, so nothing ever pulled it forward. Six weeks of CI ran against pre-amendment MAP/HDI
semantics. views-frames changed how the summary statistics are computed three times (1.2.0 outside-in
HDI tower; 1.3.0 no magnitude-based zeroing; 1.9.0 tower-tip MAP `tip_mass` 0.5→0.25), all shipped
MINOR. Floor now `>=1.10.2`; the server's environment inherits it on redeploy. C-337, and
views-frames#237 filed upstream about `CONFORMANCE_FLOOR` reading as a safe dependency floor when it
is not.

*Release procedure.* Two guides described contradictory rituals and the more detailed one prescribed
commands branch protection forbids. Consolidated into `publishing_to_pypi.md` as the single home, with
the post-release back-merge that had been skipped after **every** release before v1.10.0.
`release-topology.yml` now detects the divergence daily instead of relying on someone running the
suite at the right moment (#402).

*Monitoring.* C-335 closed: a Better Stack monitor watches the serving path, verified live. The
freshness half moved to `serving-freshness.yml` because keyword matching is a paid feature — and the
drill found ADR-051's specification of that check was itself wrong, so buying it would not have
helped. Setup of record in `docs/guides/monitoring.md`.

*Documentation.* `validate_docs.sh` now runs in CI as a required check, having previously run nowhere.
Full base-docs audit of 54 ADRs and 34 CICs: ten line-number citations replaced with symbol names,
`lab_grid` references annotated (views-metric-lab deleted that package), and a CIC written for
`load_dataset` — the public contract, which had none while 32 config dataclasses did.

*Operational.* C-330 resolved on the server: logrotate had been pointing at a path the pipeline left
months earlier, exiting successfully every night. C-339 registered — I destroyed `refresh.log` while
fixing it, with a pasted multi-line command.

*Not in this release.* GDL token rotation (done 2026-08-01, operator) and the server deploy tag.

## v1.10 Addendum (2026-07-31)

**v1.10.0 (dependency hygiene + governance repair).** Minor, not patch: the
dependency set changed for consumers.

*Packaging.* `pandas` moved from a required dependency to a `[pandas]` extra
(#378) — with the honest caveat recorded in `pyproject.toml` that the extra
gates **nothing** today, because xarray requires pandas and no installable
configuration of this package lacks it. The declaration makes pandas *not
imported*, not *not installed*; #381 asks whether the remote zarr reader can
drop xarray, which is what would make it real. Verified per-package in a clean
venv (xarray is the sole carrier). Import purity is now enforced by subprocess
probes (`tests/test_import_purity.py`) — in-process assertions are worthless
once pytest has loaded the module. `matplotlib` was demoted and then
**restored**: views-hydranet imports it at module level without declaring it,
and four views-models environments receive it through us (C-334,
views-hydranet#215). Adapters split so legacy and frame-native outputs stop
sharing a file (#379).

*Consumer surface.* `load_dataset` gained a `storage_options` seam, so a new
API can bring its own auth instead of waiting on a netrc entry on our server
(P6). Local paths are unaffected — xarray rejects storage options for local
zarr, which a test caught before the code shipped.

*Governance.* Branch protection enabled on both long-lived branches with
`enforce_admins: true` (C-320) — it caught two real errors of mine within
hours. All GitHub Actions pinned to commit SHAs (C-329). ADR-026 gained a
credential ownership table with named roles and review dates (#392), and its
false "Public GitHub is safe" sentence was corrected (#391) — a working Caddy
password had been committed in post-mortem prose. C-330 was **retracted**: it
claimed no log rotation exists, but the archive records logrotate configured on
the server 2026-03-31; the entry inferred world state from repo contents. The
WET-before-DRY deferral was re-audited (C-164): half its inventory was already
done, and its "9 sources" unit counted nothing.

*Not in this release.* GDL token rotation (C-324) and the server tag bump are
operator actions. #381, #387, #341, #363, #368 remain deferred.

## v1.9 Addendum (2026-07-27)

**v1.9.0 (go-public + PyPI + onboarding):** repo public, first PyPI release
(`pip install views-datafactory`; Trusted Publishing/OIDC via
publish_package.yml, TestPyPI-rehearsed); first-time-user guide
(`docs/guides/model_consumer_quickstart.md`) + guides index; credential guide
gaps closed (GDL token); house install convention switched to PyPI floor pins
(`>=X.Y.Z`, never `@development`); docs use `DEFAULT_REMOTE`, never the bare
IP. Hardening: server SSH now key-only (C-88 addendum); C-318 cleartext-auth
trade-off recorded. Test-suite integrity restored: C-319 (lock contamination,
42 errors/run since v1.8.1) + C-320 (deploy gates red in CI) + C-321 (401 →
raw aiohttp error, found by the TestPyPI rehearsal) — CI green again.
Gates unchanged; next milestone remains WDI (after #341 Kosovo/GAUL).

## v1.8 Addendum (2026-07-21)

**v1.8.0 (epic #342 "Own the consumer contract"):** public `OutputFormat` +
`CONTRACT_VERSION` + `is_valid_output_format` (ADR-050); committed real-save()
conformance fixture + language-neutral `contract.json` (executable layout
spec with drift alarm); `datafactory_query` split by responsibility
(dataset.py 613→263: backends_zarr / backends_npy / coverage);
`docs/guides/consumer_contract.md`. Unblocks pipeline-core #162→#161
(FeatureFrame-native pipeline); views-frames#200 formalizes byte-layout
ownership. #116 closed. Gates unchanged; next milestone remains WDI.

## v1.7 Addendum (2026-07-19)

Between v1.6 and this addendum, three releases shipped without changing the
plan's gates or roadmap position:

- **v1.6.1–v1.6.3 (staleness sprint):** dynamic version/year defaults across
  harvest configs, DGP ordering check warn-only (C-311), ACLED store
  uniqueness guard (C-312), dynamic script end-years (C-313). UCDP v26.1
  (1989–2025) and ACLED through 2026 now serve with zero manual bumping.
- **v1.7.0 (epic #322 "Trust what we serve"):** consumer contract
  verification as the pipeline's final step (freshness FAILs, plausibility
  WARNs), dead-man heartbeat failure ping (verified live), zarr source
  metadata, canonical `priogrid_id`, atomic raw snapshots, ACLED Jan-2026
  spike adjudicated REAL (#320).

Next feature milestone remains **WDI (10th source)** — the WET-before-DRY
inflection (D-38): pipeline registry, assembly extraction, named channel
map (C-287).

---

## Current State

### What Works

| Layer | Component | Status | Tests |
|-------|-----------|--------|-------|
| 0 | Provenance (digests, ledgers, locking, rotation, schema fingerprint, health diagnostics) | Done | 47 |
| 0 | HTTP retry with backoff + jitter (`datafactory_http`) | Done | 7 |
| 1 | PRIO-GRID backbone (grid, temporal, parity, shapefile, land mask) | Done | 67 |
| 1 | Harvester — UCDP annual | Done | 15 |
| 1 | Harvester — UCDP candidate | Done | 16 |
| 1 | Harvester — UCDP .9 | Done | 14 |
| 1 | Harvester — PRIO-GRID static (34 variables) | Done | 13 |
| 1 | Harvester — GAUL admin boundaries (3 levels) | Done | 12 |
| 1 | Harvester — ACLED (OAuth2, paginated, year-by-year, courteous) | Done (server-proven) | 46 |
| 1 | Harvester — GHS-POP (raster, bounded memory) | Done (server-proven) | 21 |
| 1 | Harvester — GHS-BUILT-S (raster, bounded memory) | Done (server-proven) | 16 |
| 1 | Harvester — V-Dem (CSV, 485 indicators, subset extraction) | Done (server-proven) | 14 |
| 1 | Harvester — SHDI (CSV, 4 indices, GDL subnational regions) | Done (server-proven) | 8 |
| 2 | Consolidation — UCDP (3-source, vintage-aware, atomic writes) | Done | 35 |
| 2 | Consolidation — ACLED (single-source, metadata tagging) | Done (server-proven) | 13 |
| 3 | Viewpoint — UCDP (survivorship, spatial distribution ADR-049, filtering, profiles) | Done | 134 |
| 3 | Viewpoint — ACLED (event type filter, date_month, profiles) | Done (server-proven) | 20 |
| 3 | Viewpoint — GHS-POP (raster → cell-month, bounded memory) | Done (server-proven) | 18 |
| 3 | Viewpoint — GHS-BUILT-S (raster → cell-month, bounded memory) | Done (server-proven) | 15 |
| 3 | Viewpoint — V-Dem (country-year → cell-month, 8 selected indicators) | Done (server-proven) | 24 |
| 3 | Viewpoint — SHDI (GDL region → cell-month, NaN preservation ADR-042) | Done (server-proven) | 12 |
| 4 | Grid compilation — UCDP (columnar placement, feature disaggregation, configurable dtype/fill) | Done | 39 |
| 4 | Grid compilation — ACLED (8 features, column projection, OOM-safe) | Done (server-proven) | 11 |
| 4 | Grid compilation — GHS-POP, GHS-BUILT-S, V-Dem, SHDI (pregridded, skip-consolidation) | Done (server-proven) | 24 |
| — | Assembly (6 compiled sources + static + admin → 79 features, temporal anchor ADR-047, content-addressed skip ADR-041) | Done (server-proven) | 30 |
| — | Adapters (FeatureFrame via views-frames, grid-to-DataFrame, conservation ADR-040) | Done | 42 |
| — | Query (regions, temporal parsing, unified load_dataset, zarr support, pre-coverage warning) | Done | 38 |
| — | Consumer parity (DataFrame, FeatureFrame, zarr vs VIEWSER gold set) | Done | 3 (marker-gated) |
| — | DAG enforcement | Done | 1 |
| — | Cross-layer schema contract tests | Done | 12 |
| — | Falsification suites (deploy gates v1.3/v1.4/v1.5/v1.6, ADR compliance, SOLID) | Done | 155 |
| — | Structural invariants + script structure tests | Done | 38 |
| — | Health check tests | Done | 17 |
| — | HTTP serving (Caddy, basic auth, cron, healthchecks.io monitoring) | Done | 0 (operational) |
| — | Verification examples (`examples/run_examples.sh`) | Done | 15 scripts |
| — | Remote verification (10-check server probe) | Done | 0 (script) |

**Total: ~2,308 tests (pytest) + 15 verification examples + 10-check remote verification**

**Status key:**
- **Done** = code exists, tested, validated against real data
- **Done (server-proven)** = code exists, tested, and confirmed working end-to-end on the production Hetzner server

### Architecture

- **9 packages** under `src/datafactory_*`: provenance, http, priogrid, harvester, consolidation, viewpoint, compilation, adapters, query
- **8 upstream providers** (11 registry entries; UCDP is three): UCDP (annual + candidate + .9), ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI, PRIO-GRID static, GAUL admin — this list has always had 8 items, which is likely where the phantom "9" came from
- **79 assembled features** across conflict, population, built environment, democracy, human development, static geography, and admin codes
- **50 ADRs** (10 constitutional + 40 project-specific)
- **32 CICs** (class intent contracts)
- **Technical risk register** (ADR-020): 308 concern IDs tracked, 277 resolved, 28 open (0 Tier 1, 1 Tier 2, 4 Tier 3, 17 Tier 4, 6 deferred by design), 8 open disagreements
- **Deployed:** v1.5.0 on Hetzner, serving 79 features via zarr + parquet

### WET-before-DRY Status

Nine data source pipelines exist. They share structural patterns but have real differences:

- **Harvesters:** ACLED uses OAuth2; UCDP uses API token; GHS-POP/GHS-BUILT-S are raster downloads; V-Dem/SHDI are CSV.
- **Consolidators:** UCDP merges 3 sub-sources with vintage tracking (ADR-017); ACLED merges one source. GHS-POP, GHS-BUILT-S, V-Dem, and SHDI skip consolidation entirely (ADR-029, ADR-034, ADR-035, ADR-036).
- **Viewpoints:** UCDP has survivorship strategies, spatial distribution (ADR-049), and filtering. ACLED has event type filters. GHS-POP/GHS-BUILT-S use bounded-memory raster processing. V-Dem uses country-year broadcast. SHDI uses GDL region mapping with NaN preservation (ADR-042).
- **Compilers:** UCDP/ACLED use `FeatureSpec` (ADR-024); GHS-POP, GHS-BUILT-S, V-Dem, SHDI use `PregriddedCompilationConfig` (direct cell assignment).

**Rule (C-44/C-164):** WET-before-DRY. The unit is **pipeline sources wired into `assemble_grid.py`** — 6 today (UCDP, ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI), threshold 10. Abstract types (Protocol/ABC for provenance) and the assembly registry stay deferred until the 10th forces interface extraction. Provenance sub-packaging is **not** on this clock: its trigger is a consumer needing a strict subset of the 21 exports, and no source count produces that. Earlier text here said "9 sources", a number matching no artifact in the repo (C-164 addendum, 2026-07-31).

---

## Version History

### v1.0 — Single-user research deployment (2026-04-02) — COMPLETE
### v1.1 — Multi-user / external consumers — CODE COMPLETE (operator work blocked)
### v1.2 — Consumer API + ACLED (2026-05-08) — COMPLETE

29 patch releases (v1.2.0 through v1.2.29). ACLED end-to-end on server, consumer API with `load_dataset()`, VIEWSER parity, 51 features, 6 data sources, ~821 tests.

### v1.3 — Source expansion: GHS-POP, GHS-BUILT-S, SHDI, area-majority (2026-06-15) — COMPLETE

| Criterion | How verified | Status |
|-----------|-------------|--------|
| All v1.2 criteria | — | Done |
| GHS-POP harvester + viewpoint + compilation | End-to-end pipeline, 21+18 tests | Done |
| GHS-BUILT-S harvester + viewpoint + compilation | End-to-end pipeline, 16+15 tests | Done |
| SHDI harvester + viewpoint + compilation | End-to-end pipeline, 8+12 tests, NaN preservation (ADR-042) | Done |
| Area-majority GAUL assignment (ADR-039) | 259,200-cell generation, hypothesis tests H1-H5 | Done |
| Cross-layer schema contract tests | 12 tests (C-288) | Done |
| Count conservation at consolidation/viewpoint | Conservation module + hierarchical reconciliation (ADR-040) | Done |
| Grid grows from 51 to 79 features | Assembly verified, features.json updated | Done |
| Falsification deploy gate | `test_falsification_deploy_v130.py` survived | Done |

Key ADRs: ADR-029 (GHS-POP), ADR-034 (GHS-BUILT-S), ADR-036 (SHDI), ADR-039 (area-majority), ADR-040 (count conservation), ADR-041 (content-addressed skip), ADR-042 (SHDI NaN preservation), ADR-043 (GAUL Azores supplement).

### v1.4 — V-Dem, data soundness, test hardening (2026-06-24) — COMPLETE

| Criterion | How verified | Status |
|-----------|-------------|--------|
| All v1.3 criteria | — | Done |
| V-Dem harvester + viewpoint + compilation | End-to-end pipeline, 14+24 tests, 8 democracy indicators | Done |
| Data soundness invariants (ADR-045) | Cross-layer contract tests | Done |
| views-frames adoption | FeatureFrame via views-frames v1.0.0 | Done |
| Coastal gap cell validation | 946 cells verified, africa_me_gaul region | Done |
| Pre-WDI test hardening | 33 new tests: assembly, query, provenance locking | Done |
| Documentation drift cleanup | 15 governance files updated | Done |
| Falsification deploy gate | `test_falsification_deploy_v140.py` survived | Done |

Key ADRs: ADR-035 (V-Dem), ADR-044 (source taxonomy), ADR-045 (data soundness), ADR-046 (UCDP schema evolution).

### v1.5 — Conservation hardening, temporal alignment, scaling headroom (2026-06-27) — COMPLETE

| Criterion | How verified | Status |
|-----------|-------------|--------|
| All v1.4 criteria | — | Done |
| Count conservation hardening | NaN guard, float64 regression, intensive quantity warning (C-258) | Done |
| Consumer bridge cleanup | Removed `lr_*` rename, serve raw factory names | Done |
| Assembly temporal anchor (ADR-047) | `first_valid_*_month_id` in provenance, pre-coverage consumer warning | Done |
| Scaling headroom | Columnar extraction in compilation (C-144), column-selective viewpoint reads (C-145) | Done |
| Infrastructure test coverage | Aliased dict fix, ACLED column guard, placement column filter | Done |
| ADR-003 compliance — declared aggregation types | ADR-048, `feature_agg_types` in SourceEntry (C-299) | Done |
| ADR-049 — Spatial distribution of imprecise UCDP events | where_prec 4-6 distributed across admin-region cells | Done |
| Falsification deploy gate | `test_falsification_deploy_v160.py` in progress | In progress |

Key ADRs: ADR-047 (temporal anchor), ADR-048 (declared aggregation types), ADR-049 (spatial distribution).

### v1.6 — Deploy readiness (target: 2026-06-29) — IN PROGRESS

| Criterion | How verified | Status |
|-----------|-------------|--------|
| All v1.5 criteria | — | Done |
| Version bumped to 1.6.0 | `pyproject.toml` | Pending |
| Product plan current | This document (v12) | Done |
| Sprint issues closed | 50 of 68 closed, 18 remaining | Done |
| main/development mergeable (ff-only) | Merge main into development, then ff-only to main | Pending |
| Stale release branches deleted | `release/v1.5.0` | Pending |
| Falsification deploy gate passes | `test_falsification_deploy_v160.py` all green | Pending |

### v2.0 — Institutional / scaled deployment

| Criterion | How to verify |
|-----------|--------------|
| All v1.6 criteria | — |
| WDI integrated | WDI compiled + assembled + served. NB this is the **7th** pipeline source, not the 10th — the old "10th source" phrasing assumed the uncountable 9 (C-164 addendum). |
| WET-before-DRY abstractions extracted | Protocol/ABC for provenance, assembly registry — gated on **10 pipeline sources**, which WDI alone does not reach. This criterion and the WDI criterion are now independent; previously they were assumed to fall together. |
| OAuth2 / institutional SSO | Caddy `forward_auth` + oauth2-proxy |
| Per-user audit trail | Access logs with authenticated username |
| Circuit breaker on APIs | `datafactory_http` circuit breaker module |
| Pipeline duration tracked | Provenance ledger includes `duration_seconds` |

---

## Prioritized Action List

### Active (v1.6 deploy)

| # | Task | Effort | Status |
|---|------|--------|--------|
| 1 | Bump version 1.5.0 → 1.6.0 | Trivial | Pending |
| 2 | Merge main into development (resolve divergence) | 10 min | Pending |
| 3 | Delete stale `release/v1.5.0` branch | Trivial | Pending |
| 4 | Run v1.6.0 falsification tests | 5 min | Pending |
| 5 | Merge development → main (ff-only) | 5 min | Pending |
| 6 | Tag v1.6.0, deploy | 15 min | Pending |

### Blocked (v1.1 operator work)

| # | Task | Blocker |
|---|------|---------|
| 17 | Register domain + HTTPS | Domain not registered |
| 18 | Restrict SSH to institutional IPs | IT CIDRs not provided |
| 19 | Service account + deploy key | Requires SSH to server |

### Next (v2.0 source expansion)

| # | Task | Ref | Depends on |
|---|------|-----|------------|
| 30 | WDI harvester + full pipeline (27 indicators, 45 models) | `reports/rd_roadmap_wdi.md` | v1.6 deployed |
| 31 | Extract shared abstractions at 10th source | C-44/C-164 | WDI integration |

### Deferred (v2.0 infrastructure)

| # | Task | Ref | Target |
|---|------|-----|--------|
| 20 | OAuth2 (forward_auth + oauth2-proxy) | C-97 | v2.0 |
| 21 | Per-user audit trail | C-97 | v2.0 |
| 22 | Circuit breaker for APIs | C-70 | v2.0 |
| 23 | Pipeline duration tracking | C-91 | v2.0 |

---

## Architecture References

| ADR | Relevance |
|-----|-----------|
| ADR-003 | Authority of declarations over inference (constitutional) |
| ADR-011 | Fail-loud: crash-stop fault model (constitutional) |
| ADR-012 | 4-layer graph architecture |
| ADR-013 | Consolidation: lossless, append-only, bitemporal |
| ADR-014 | Viewpoints: disposable, rebuildable, versioned |
| ADR-015 | UCDP consolidation + viewpoint specifics |
| ADR-016 | Viewpoint profiles — constitutional, applies to all sources |
| ADR-017 | Vintage-aware consolidation (content-digest dedup) |
| ADR-018 | Operational resilience + timeout policy + freshness SLO |
| ADR-020 | Technical risk register |
| ADR-021 | Zarr export format |
| ADR-022 | Tag-based deployment gate |
| ADR-023 | Viewpoint builder invariants |
| ADR-024 | Compilation grid invariants |
| ADR-025 | Country identity via GAUL |
| ADR-026 | Credential management — UCDP token + ACLED OAuth2 |
| ADR-027 | Harvest count verification |
| ADR-028 | ACLED consolidation + viewpoint specifics |
| ADR-029 | GHS-POP as first population source |
| ADR-030 | Raster tooling |
| ADR-031 | Resource ownership and data representation |
| ADR-033 | Data source catalog |
| ADR-034 | GHS-BUILT-S as built-up surface source |
| ADR-035 | V-Dem as democracy source |
| ADR-036 | SHDI as subnational HDI source |
| ADR-037 | Bounded-memory compilation |
| ADR-039 | Area-majority GAUL assignment |
| ADR-040 | Count conservation and hierarchical reconciliation |
| ADR-041 | Content-addressed skip |
| ADR-042 | SHDI NaN preservation |
| ADR-045 | Data soundness invariants |
| ADR-046 | UCDP schema evolution |
| ADR-047 | Assembly temporal anchor |
| ADR-048 | Declared feature aggregation types |
| ADR-049 | Spatial distribution of imprecise UCDP events |
