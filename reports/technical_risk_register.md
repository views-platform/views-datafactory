# Technical Risk Register

**Date:** 2026-03-17 (updated 2026-07-05)
**Last update:** Consumer contract verification (2026-07-05) — C-313 registered and resolved (hardcoded end-year defaults in 9 scripts made dynamic; ACLED 2026 was silently clipped at compile). Header counts: 312→313 IDs, 281→282 resolved. Prior: v1.6.1 deploy incident (2026-07-02) — C-311/C-312 registered and resolved (DGP ordering check downgraded to warn-only after contradicting real UCDP data; ACLED store 2x-duplicate corruption rebuilt + uniqueness guard added). C-257 updated with lesson: DGP checks must be verified against real source data before being made blocking. Header counts: 310→312 IDs, 279→281 resolved. Prior: Deploy v1.6.0 readiness (2026-06-29) — C-309/C-310 registered and resolved (merge topology fixed, deploy guide updated). Header counts: 308→310 IDs, 277→279 resolved. Prior: PR #307 review findings (2026-06-28) — C-306/C-307/C-308 registered and resolved (xfail removed, gh CLI error guard added, plan path globbed). Header counts: 274→277 resolved, 305→308 IDs. Prior: ADR-049 pre-merge fixes (2026-06-28) — C-303, C-304, C-305 resolved (provenance counters added, ADR §2 table corrected, config paths aligned). Header counts: 271→274 resolved, 31→28 open, Tier 4: 20→17. Prior: ADR-049 epic (#300, 2026-06-28) — C-303/C-304/C-305 registered via falsification; ADR-003 epic (#290, 2026-06-28) — C-299 resolved, C-300/C-301/C-302 registered; infrastructure test coverage (#280, 2026-06-26) — C-271/C-280/C-276/C-189 resolved; scaling headroom (#274, 2026-06-26) — C-144/C-145 resolved; temporal alignment (#266, 2026-06-26) — C-286/C-156 resolved; count conservation (#258, 2026-06-24) — C-131/C-291/C-249/C-241 resolved; WDI readiness (2026-06-24) — C-223/C-298 resolved; test hardening (#234, 2026-06-24) — C-290/C-294/C-295/C-296/C-297 resolved. Earlier history in git log
**Source:** Multi-expert engineering review, repo assimilation, falsification audits, expert code review (Martin, GoF, Feathers, Nygard, Kleppmann, Ousterhout, Hickey, Beck), magic-values compliance audit, stale-zarr incident 2026-04-24, pipeline verification audit 2026-04-30, ACLED integration test review 2026-05-02, ACLED test review 2026-05-03, ACLED compilation test review 2026-05-05, base documentation review 2026-05-07, ACLED harvester test review 2026-05-07, GHS-POP harvester test review 2026-05-18, GHS-POP viewpoint test review 2026-05-19, PR #53 review 2026-05-20, GHS-POP memory falsification + expert code review 2026-05-20, repo-assimilation 2026-05-20, ADR-031 compliance review 2026-05-21, harvest caching expert code review 2026-05-21, PR #59 falsification audit round 2 2026-05-21, provenance/shapefile expert code review 2026-05-21, GHS-BUILT-S review-rr triage 2026-05-22, GHS-BUILT-S coverage parity falsification 2026-05-22, GHS-BUILT-S visual audit falsification 2026-05-22, GHS-BUILT-S visual audit run 2026-05-22, C-190 resolution 2026-05-23, GHS-BUILT-S merge-readiness falsification 2026-05-23, pre-merge sprint (C-191/C-192/C-168/C-174) 2026-05-23, GHS-BUILT-S merge-readiness falsification round 2 2026-05-23, repo-assimilation v1.2.20 2026-05-24, tech-debt-cleanup investigation 2026-05-24, review-rr strategic + prioritize 2026-05-24, review-base-docs 2026-05-25, V-Dem test coverage parity falsification 2026-05-26, V-Dem ADR/guide compliance falsification 2026-05-26, V-Dem SOLID/package/file-org falsification 2026-05-26, review-rr strategic curation 2026-05-26, review-base-docs 2026-05-26, V-Dem visual audit falsification 2026-05-26, V-Dem visual audit documentation falsification 2026-05-26, sprint S4 standalone fixes (C-175/C-129/C-149) 2026-05-27, merge-readiness falsification (C-222) 2026-05-27, review-rr strategic curation 2026-05-28, SHDI review-diff 2026-05-29, expert code review C-164 2026-05-30, digest verification expert code review + 3 falsification audits 2026-06-02, preflight netrc falsification 2026-06-02, status page understanding falsification 2026-06-04, status page fix plan falsification 2026-06-04, ADR-040 scoping 2026-06-05, test-review area-majority effort 2026-06-05, review-base-docs area-majority effort 2026-06-05, review-rr strategic curation 2026-06-06, pre-deployment audit 2026-06-07, derived-artifact drift expert-code-review 2026-06-08, data soundness expert-method-review 2026-06-08, content-addressed skip investigation 2026-06-09, pipeline gap audit 2026-06-10, tech-debt-cleanup pre-deploy 2026-06-10, test-review deep coverage audit 2026-06-10, review-rr strategic curation 2026-06-10, repo-assimilation v1.3.0 2026-06-16, expert-code-review register-risk 2026-06-18, test-review v1.4.0 2026-06-24
**Status:** 313 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60, C-183 merged into C-44, C-44 merged into C-164, C-03 merged into C-176): 282 resolved, 28 open concerns (0 Tier 1, 1 Tier 2, 4 Tier 3, 17 Tier 4, 6 deferred by design; 2 with fired trigger), 8 open disagreements. 167 resolved concerns as full entries + 19 early-archive reference rows + 98 struck-through in active register (282 unique after dedup — 5 appear in both archive and active) + 32 resolved disagreements in archive. 40 disagreement IDs total: 32 resolved, 8 open.
**Archive:** Resolved concerns and disagreements are in `archive/technical_risk_register_resolved.md`.

**Ranking criteria:** Impact if wrong x likelihood x detectability. Items marked **[DEFER]** are accepted risks or wait for a specific trigger condition. See ADR-020 for governance rationale.

---

## Open Items Summary

| ID | Tier | Title | Trigger | Package |
|----|------|-------|---------|---------|
| ~~C-253~~ | ~~1~~ | ~~Export scripts have no source-digest verification — stale data served silently~~ | Resolved 2026-06-09 (commit 975b401: source-digest gates in export_zarr.py + generate_consumer_data.py) | Artifact consistency |
| ~~C-259~~ | ~~1~~ | ~~Assembly skip logic does not digest static/admin inputs — false skip serves stale grid~~ | Resolved 2026-06-09 (ADR-041: composite static/admin digests in provenance + check_assembly_skip) | Artifact consistency |
| ~~C-262~~ | ~~1~~ | ~~Skip path serves corrupt output — no output integrity verification on skip~~ | Resolved 2026-06-09 (ADR-041: check_assembly_skip verifies output_digest on skip path) | Artifact consistency |
| C-88 | 2 | SSH not restricted to PRIO/Uppsala IPs | Before granting additional SSH users | Server hardening |
| ~~C-121~~ | ~~4~~ | ~~Phase 6.4 documented but unexecuted (lessons from C-87)~~ | Demoted to tech-debt backlog 2026-06-10 (blocked on external — PRIO IT CIDRs) | — |
| ~~C-36~~ | ~~4~~ | ~~UCDP API contract has no schema versioning~~ | Resolved 2026-06-19 (ADR-046 documents schema defense strategy, #209) | UCDP schema |
| ~~C-37~~ | ~~4~~ | ~~`date_prec=5` semantics hardcoded~~ | Resolved 2026-06-19 (DGP validation fail-loud on unknown date_prec, #212) | UCDP schema |
| ~~C-45~~ | ~~4~~ | ~~No Parquet schema evolution strategy~~ | Resolved 2026-06-19 (ADR-046 documents promote_options + fingerprint approach, #209) | UCDP schema |
| C-46 | 4 | No ledger write idempotency | Before monitoring dashboard or external audit tool reads provenance JSONL directly | — |
| C-32 | — | Source registry returns `Any` | Accepted by design | — |
| C-29 | 4 | No end-to-end integration test — trigger fired, accepted at v1.0 | Before WDI integration (10th source) or multi-target deployment | Test infra |
| C-70 | 4 | No circuit breaker for UCDP API | Multi-operator deployment | UCDP resilience |
| C-72 | 4 | HTTP 429 not distinguished from 500 | UCDP returns 429s | UCDP resilience |
| ~~C-74~~ | ~~4~~ | ~~CompilationConfig leaks strategy vocabulary~~ | Demoted to tech-debt backlog 2026-06-06 | — |
| ~~C-78~~ | ~~4~~ | ~~`_place_events` hard to test in isolation~~ | Demoted to tech-debt backlog 2026-06-06 | — |
| ~~C-79~~ | ~~4~~ | ~~Compilation/consolidation require real Parquet I/O~~ | Demoted to tech-debt backlog 2026-06-14 (trigger permanently fired — suite at 6m38s, functioning normally) | — |
| C-97 | 4 | Basic auth + Caddy scalability ceiling at ~30-50 users | Before consumer count exceeds 30 | — |
| C-116 | 4 | No retry on remote zarr network failures | Consumer reports transient failures | Query resilience |
| C-117 | 4 | Remote zarr downloads all spatial cells before region filter | Consumer queries single country over slow connection | Query performance |
| ~~C-131~~ | ~~2~~ | ~~No external monitoring for cron job failure on Hetzner~~ | Resolved 2026-06-24 (heartbeat in refresh_pipeline.sh:260-263 + ADR-018 bounded staleness SLO) | Operational monitoring |
| ~~C-136~~ | ~~4~~ | ~~`read_last_entries()` crashes on non-UTF8 ledger files~~ | Demoted to tech-debt backlog 2026-06-16 (mechanical fix, single-file, perpetual trigger, loud failure) | — |
| C-126 | 3 | No transform layer — 14 viewser transforms not replaceable | Model migration requires derived features | Migration scope |
| ~~C-177~~ | ~~4~~ | ~~`_aggregate_to_prio_grid` holds source + copy simultaneously (ADR-031 P3)~~ | Demoted to tech-debt backlog 2026-06-14 (function not actively used; dead code concern) | — |
| ~~C-179~~ | ~~4~~ | ~~Consolidation dedup uses `.to_pylist()` + Python set (ADR-031 P1)~~ | Demoted to tech-debt backlog 2026-06-24 (mechanical fix, single-file, perpetual, data volume 60x below threshold) | — |
| C-180 | 4 | No falsification tests for non-GHS-POP compilation/viewpoint paths | Memory regression introduced in UCDP or ACLED path | Test coverage |
| ~~C-181~~ | ~~4~~ | ~~UCDP candidate/dot9 discovery probes API even when all versions cached~~ | Demoted to tech-debt backlog 2026-06-24 (optimization, single-file, no correctness impact, UCDP has not rate-limited) | — |
| ~~C-185~~ | ~~4~~ | ~~GHS-POP caching has no digest comparison (no change detection)~~ | Demoted to tech-debt backlog 2026-06-24 (hypothetical risk, JRC releases immutable by convention) | — |
| ~~C-186~~ | ~~3~~ | ~~Shapefile harvester lacks outcome vocabulary~~ | Resolved 2026-05-31 (outcome vocabulary added, ADR-032 updated) | Harvest correctness |
| ~~C-189~~ | ~~4~~ | ~~GHS-BUILT-S test coverage parity gap — 19% of combined other sources~~ | Resolved 2026-06-26 (#284): 74 new tests across harvester/viewpoint/compilation; parity ≥70% on all 3 metrics (functions 74%, assertions 70%, Red classes 100%); xfail markers replaced with 70% thresholds | Test coverage |
| ~~C-261~~ | ~~3~~ | ~~No provenance ledger entry for skip events — audit trail has temporal gaps~~ | Resolved 2026-06-09 (ADR-041: ledger entries for both skip and success, --force flag added) | Artifact consistency |
| ~~C-256~~ | ~~3~~ | ~~No definition of "data soundness" as a testable property~~ | Resolved 2026-06-18 (ADR-045 data soundness invariants, #200) | Data soundness |
| ~~C-223~~ | ~~3~~ | ~~Compilation pipeline allocates full grid in RAM (bounded-memory R&D)~~ | Resolved 2026-06-24 (memmap implemented in pregridded_compilation.py:191 + grid_compilation.py:257, ADR-037) | Scaling headroom |
| C-224 | 4 | No server backup or disaster recovery plan | Disk failure or accidental data deletion on Hetzner server | Server hardening |
| ~~C-293~~ | ~~2~~ | ~~Three-way feature name sync only partially tested~~ | Resolved 2026-06-19 (5 guard tests in test_assemble.py, #208) | Source registry |
| ~~C-294~~ | ~~4~~ | ~~Digest computation after lock release in event store~~ | Resolved 2026-06-24 (digest moved inside file_lock in event_store.py, #238) | Consolidation correctness |
| ~~C-295~~ | ~~4~~ | ~~No timeout on LOCK_EX in file_lock()~~ | Resolved 2026-06-24 (LOCK_NB + retry loop with 60s timeout, #238) | Provenance locking |
| D-23 | — | ADR-031 P1 strict columnar purity vs pragmatic materialization | Open | ADR-031 compliance |
| D-26 | — | Discovery probing cost vs cache staleness (UCDP candidate/dot9) | Open | Harvest caching |
| ~~D-29~~ | ~~—~~ | ~~Shapefile harvester retrofit depth — full outcome compliance vs organic~~ | Resolved 2026-06-24 (organic retrofit achieved — C-186 added outcome vocabulary 2026-05-31) | Harvest correctness |
| ~~D-30~~ | ~~—~~ | ~~Config validator extraction depth — utility functions vs declarative specs~~ | Resolved 2026-06-14 (utility functions first; declarative deferred to 12+ sources) | WET-before-DRY |
| ~~D-31~~ | ~~—~~ | ~~Harvest script consolidation — single unified script vs thin delegates~~ | Resolved 2026-06-14 (middle path: shared HarvestRunner + thin delegates. Deferred to WDI sprint.) | WET-before-DRY |
| ~~D-32~~ | ~~—~~ | ~~`assembled` flag vs removing features from partially-integrated sources~~ | Resolved #105 (features and phantom entries removed) | Source registry |
| ~~C-230~~ | ~~4~~ | ~~Script layer (harvest + pipeline) has zero unit tests~~ | Resolved 2026-06-18 (harvest + pipeline CLI tests, #201/#202) | Test coverage |
| ~~C-231~~ | ~~4~~ | ~~No compilation idempotence guard — silent recompilation with stale inputs~~ | Demoted to tech-debt backlog 2026-06-24 (single-operator, ordered pipeline, post-hoc audit exists) | — |
| ~~C-235~~ | ~~3~~ | ~~Source registry declares nonexistent SHDI downstream entries~~ | Resolved: #105 removed SHDI features and phantom entries | Source registry |
| ~~C-236~~ | ~~4~~ | ~~Status page artifact mapping requires manual update per source~~ | Resolved 2026-06-18 (3 alignment tests, #203) | Status page |
| ~~C-237~~ | ~~3~~ | ~~Status page generation + delivery verification gap~~ | Resolved 2026-06-18 (4 delivery tests, #204) | Operational monitoring |
| ~~C-238~~ | ~~3~~ | ~~Issue #104 stale Caddy claims + orphaned daily cron requirement~~ | Resolved 2026-06-06 (#104 closed, superseded by #123) | Operational monitoring |
| ~~C-239~~ | ~~2~~ | ~~Issue #104 paths produce silent wrong status page~~ | Resolved 2026-06-06 (#104 closed, superseded by #123) | Operational monitoring |
| ~~C-240~~ | ~~4~~ | ~~generate_status.py docstring specifies nonexistent /www/ path~~ | Resolved 2026-06-06 (commit dd69544, docstring updated) | Status page |
| ~~C-241~~ | ~~4~~ | ~~No invariant for intensive feature conservation across resolution or aggregation~~ | Resolved 2026-06-24 (UserWarning in grid_to_country_month.py for intensive features, #258) | Aggregation correctness |
| ~~C-246~~ | ~~2~~ | ~~`_compute_cell_polygon_map` is production code path with zero direct tests~~ | Resolved 2026-06-07 (#136: 15 tests — Green/Beige/Red/Equivalence) | GAUL data integrity |
| ~~C-247~~ | ~~3~~ | ~~Dual source of truth for GAUL name files~~ | Resolved 2026-06-19 (pipeline ordering guard test + docstrings, #211) | GAUL data integrity |
| ~~C-248~~ | ~~4~~ | ~~`area_majority_join` string tiebreaker crashes on mixed types~~ | Resolved 2026-06-07 (#136: type-safe tiebreaker + regression test) | GAUL data integrity |
| ~~C-249~~ | ~~4~~ | ~~Float64 CM conservation fix has no regression guard~~ | Resolved 2026-06-24 (regression test at 500K cells proves float32 divergence, #258) | Count conservation |
| ~~C-250~~ | ~~4~~ | ~~Hierarchical reconciliation not wired into any production code path~~ | Resolved 2026-06-19 (check_nesting() wired into generate_area_majority_gaul.py, #211) | GAUL data integrity |
| ~~C-251~~ | ~~1~~ | ~~ACLED consolidator cross-file event duplication (2× overcounting)~~ | Resolved 2026-06-07 (#138: dedup on event_id_cnty alone + overlap detection + 6 tests) | ACLED consolidation |
| ~~C-252~~ | ~~2~~ | ~~ACLED cross-run dedup drops updated events (first-seen wins, not latest)~~ | Resolved 2026-06-19 (latest-wins dedup with replacement tracking, #210) | ACLED consolidation |
| ~~C-254~~ | ~~2~~ | ~~Consumer parquet has zero provenance — no audit trail for training data~~ | Resolved 2026-06-18 (5 provenance tests, #199) | Artifact consistency |
| ~~C-255~~ | ~~2~~ | ~~Health check reports "SLO MET" for content-stale artifacts (time-fresh, content-wrong)~~ | Resolved 2026-06-09 (commit 975b401: check_export_freshness compares source_digest) | Artifact consistency |
| ~~C-260~~ | ~~2~~ | ~~Assembly skip logic ignores source removal — `all()` checks only current keys~~ | Resolved 2026-06-09 (ADR-041: check_assembly_skip uses key-set equality, not subset) | Artifact consistency |
| ~~C-257~~ | ~~2~~ | ~~No input data validation at system boundary — DGP assumptions untested~~ | Resolved 2026-06-19 (validate_dgp_assumptions() + ACLED/UCDP checks, #212) | Data soundness |
| ~~C-258~~ | ~~2~~ | ~~Count conservation not enforced at consolidation or viewpoint boundaries~~ | Resolved 2026-06-15 (conservation assertions at 4 boundaries + 14 tests in test_boundary_conservation.py) | Data soundness |
| ~~C-242~~ | ~~2~~ | ~~ADR-040 count conservation invariants accepted but zero test enforcement~~ | Resolved 2026-06-06 (PR #135: 10 tests + runtime assertions) | Count conservation |
| ~~C-243~~ | ~~3~~ | ~~ADR-040 hierarchical reconciliation untested (gaul0/1/2 sum equality)~~ | Resolved 2026-06-06 (PR #135: 6 tests + check_nesting + assert_hierarchical_reconciliation) | Count conservation |
| ~~C-244~~ | ~~4~~ | ~~4 CICs + ADR-025 not updated after ADR-040 acceptance~~ | Resolved 2026-06-06 (PR #135: 4 CICs + ADR-025 updated) | Count conservation |
| ~~C-245~~ | ~~3~~ | ~~Name file gap — 9,481 recovered cells have codes but no country names~~ | Resolved 2026-06-06 (PR #135: area-majority script generates name Parquet files) | Data completeness |
| D-33 | — | Pipeline-path information: registry field vs standalone mapping vs convention | Open | Source registry |
| ~~D-34~~ | ~~—~~ | ~~Provenance enforcement location: library gate vs pipeline gate vs both~~ | Resolved 2026-06-10 (both approaches implemented: library gates in ADR-041 skip.py, pipeline gates in EXIT trap + health check) | Artifact consistency |
| D-35 | — | Test scope: exhaustive verification vs minimum viable testing | Open | Data soundness |
| ~~D-36~~ | ~~—~~ | ~~Skip decision location: inline in script vs. provenance package function~~ | Resolved 2026-06-09 (ADR-041: extracted to provenance/skip.py) | Artifact consistency |
| D-37 | — | Code identity in skip decisions: include git hash or not | Open | Artifact consistency |
| D-38 | — | Script extraction timing — when does WET in scripts/ cross the extraction threshold | Deferred by design — WDI sprint provides 3rd pipeline script instance to validate abstraction | WET-before-DRY |
| D-39 | — | Viewpoint builder abstraction — Protocol extraction vs explicit repetition | Open | Viewpoint architecture |
| D-40 | — | DGP check module placement — source-agnostic `event_validation.py` vs per-source definitions | Open | Data soundness |
| ~~C-144~~ | ~~3~~ | ~~Compilation `to_pydict()` materializes millions of Python objects~~ | Resolved 2026-06-26 (columnar `.to_numpy()` extraction + row-index bins, #275) | Scaling headroom |
| ~~C-145~~ | ~~3~~ | ~~Viewpoint builder loads full consolidated store into memory~~ | Resolved 2026-06-26 (column-selective `pq.read_table()` in UCDP + ACLED builders, #276) | Scaling headroom |
| C-146 | 4 | Assembly logic lives in script, not importable package | Assembly orchestration refactored or new assembly path added | Testability |
| C-147 | 4 | No pipeline orchestrator in repository | Operator runs scripts out of order or skips a step | Operations |
| ~~C-148~~ | ~~4~~ | ~~Hardcoded Hetzner server IP in `defaults.py`~~ | Demoted to tech-debt backlog 2026-06-16 (mechanical fix, single-file, perpetual, Tier 4) | — |
| C-153 | 3 | ACLED API has no TotalCount — silent truncation undetectable | ACLED enforces server-side result caps within a page | ACLED data integrity |
| C-154 | 4 | ACLED_FEATURES config duplicated between script and tests | Feature filter values changed in script but not tests | ACLED test quality |
| C-155 | 4 | No shared visual audit framework — per-source scripts are idiosyncratic | Before 6th pipeline source (WDI) requires a verify script | Visual audit |
| ~~C-195~~ | ~~4~~ | ~~37 falsification test files accumulated without curation (3,129 lines)~~ | Demoted to tech-debt backlog 2026-06-19 (no correctness risk, single-developer scope) | — |
| C-173 | 4 | Hetzner server memory headroom (CPX42 + swap) | CPX42 RSS usage during full pipeline run exceeds 80% of available RAM (observed during WDI pilot) | Server hardening |
| C-164 | 3 | Cross-layer WET debt: 6 sources replicate patterns across all 4 layers — **trigger fired** | Before WDI integration or next data source | WET-before-DRY |
| ~~C-156~~ | ~~4~~ | ~~ACLED temporal range mismatch — zero-fill before 2020 in assembled grid~~ | Resolved 2026-06-26 (#266): `first_valid_acled_month_id` in provenance + `load_dataset()` pre-coverage UserWarning (ADR-047) | Assembly temporal alignment |
| ~~C-265~~ | ~~2~~ | ~~SHDI harvest missing from `refresh_pipeline.sh` — status page RED, data never collected~~ | Resolved 2026-06-10 (commit cd23624: harvest_shdi.py added to refresh_pipeline.sh line 173) | Pipeline completeness |
| ~~C-264~~ | ~~3~~ | ~~Factory/models partition boundary drift — 4 alignment tests failing~~ | Resolved 2026-06-14 (commit cd23624: partition boundaries updated in defaults.py lines 92-94) | Cross-repo alignment |
| ~~C-266~~ | 4 | ~~Flaky `test_latest_harvest_wins` — filesystem timestamp resolution~~ | ~~Full suite run where both test Parquet files created in same second~~ | ~~Test reliability~~ |
| ~~C-267~~ | ~~2~~ | ~~event_store.py crash-safety and concurrency untested — system of record at risk~~ | Resolved 2026-06-18 (6 characterization tests, #195) | Data soundness |
| ~~C-268~~ | ~~3~~ | ~~gaul_admin.py has zero test coverage — 7-feature spatial join untested~~ | Resolved 2026-06-19 (4 spatial join characterization tests, #211) | GAUL data integrity |
| ~~C-269~~ | ~~3~~ | ~~event_validation.py validate_events() and compare_snapshots() — zero direct tests~~ | Resolved 2026-06-18 (8 characterization tests, #196) | Data soundness |
| ~~C-270~~ | ~~3~~ | ~~_rotate_ledger() has zero tests — provenance rotation bug could destroy audit history~~ | Resolved 2026-06-18 (5 characterization tests, #197) | Provenance |
| ~~C-271~~ | ~~4~~ | ~~compute_file_digest() has zero direct tests~~ | Resolved 2026-06-26 (#281): 8 direct tests (Green/Beige/Red) covering determinism, hex length, content equivalence, empty file, multi-chunk, missing file, directory, binary content | Provenance |
| ~~C-272~~ | ~~4~~ | ~~TemporalConfig CIC Section 6 failure modes untested~~ | Demoted to tech-debt backlog 2026-06-10 (standard __post_init__ pattern, loud failure) | — |
| ~~C-273~~ | ~~4~~ | ~~snapshot_storage.py has no dedicated tests~~ | Demoted to tech-debt backlog 2026-06-24 (exercised indirectly, single-file, mechanical) | — |
| ~~C-274~~ | ~~4~~ | ~~tagging.py has only 1 test — no edge cases~~ | Demoted to tech-debt backlog 2026-06-12 (no correctness impact on data pipeline; thin metadata annotation layer) | — |
| ~~C-275~~ | ~~4~~ | ~~raster_io.py has only 1 test — no error path coverage~~ | Demoted to tech-debt backlog 2026-06-12 (exercised end-to-end by GHS-POP/GHS-BUILT-S tests; loud failures) | — |
| ~~C-276~~ | ~~4~~ | ~~UCDP candidate/dot9 per-version fetch failure modes untested~~ | Resolved 2026-06-26 (#283): 10 per-version tests (5 candidate + 5 dot9) covering not_served, all_cached, mixed outcomes, validation failure isolation, network errors | UCDP resilience |
| ~~C-277~~ | ~~4~~ | ~~check_disk_space() RuntimeError path untested~~ | Demoted to tech-debt backlog 2026-06-10 (simple utility, loud failure, zero data risk) | — |
| ~~C-278~~ | ~~4~~ | ~~ConsolidationResult / ViewpointResult no frozen-mutation tests~~ | Demoted to tech-debt backlog 2026-06-10 (testing Python machinery, zero correctness risk) | — |
| ~~C-279~~ | ~~4~~ | ~~land_mask.py has zero red tests~~ | Demoted to tech-debt backlog 2026-06-12 (downloaded once, cached permanently; loud HTTP failures; minimal surface) | — |
| ~~C-280~~ | ~~4~~ | ~~skip.py corrupted provenance.json / .zattrs untested~~ | Resolved 2026-06-26 (#282): 8 corrupted-input tests (assembly + export) covering empty provenance, malformed JSON, missing keys, null digests, malformed .zattrs | Artifact consistency |
| ~~C-281~~ | ~~4~~ | ~~No SHDI CIC — only source without governance document~~ | Resolved 2026-06-11 (ShdiViewpointConfig.md written) | Documentation |
| ~~C-282~~ | ~~3~~ | ~~V-Dem and SHDI bypass shared temporal module — ADR-014 P5 claim false for 2 of 4 builders~~ | Resolved 2026-06-14 (PR #169 commit 85601ec: V-Dem and SHDI migrated to shared temporal.py) | Doc/code consistency |
| ~~C-283~~ | ~~3~~ | ~~V-Dem viewpoint reads GAUL admin crosswalk — cross-source dependency violates ADR-014 P6~~ | Resolved 2026-06-14 (PR #169 commit 85601ec: ADR-014 P6 rewritten to allow reference source deps) | Doc/code consistency |
| ~~C-284~~ | ~~4~~ | ~~ACLED event_type_filter implemented but absent from ADR-028~~ | Resolved 2026-06-14 (PR #169: ADR-028 line 56 clarified event_type_filter) | Doc/code consistency |
| ~~C-285~~ | ~~3~~ | ~~No process lock prevents concurrent pipeline runs — data file overwrites possible~~ | Resolved 2026-06-14 (commit 428e479: flock in refresh_pipeline.sh lines 136-142) | Pipeline safety |
| ~~C-286~~ | ~~3~~ | ~~UCDP as implicit temporal anchor — source data silently dropped if UCDP contracts~~ | Resolved 2026-06-26 (#266): ADR-047 declares UCDP temporal anchor + `first_valid_*_month_id` provenance fields + consumer warning | Assembly temporal alignment |
| C-287 | 4 | Assembly channel order is positional — hardcoded offsets fragile if feature counts change | Source adds/removes a feature, assembly channel offsets shift silently | Assembly maintainability |
| ~~C-288~~ | ~~2~~ | ~~No cross-layer schema contract tests — viewpoint column rename silently breaks compilation~~ | Resolved 2026-06-15 (tests/test_cross_layer_contracts.py: 24 tests covering all 6 sources) | Cross-layer verification |
| ~~C-289~~ | ~~3~~ | ~~cell_generator.py has zero characterization tests — spatial backbone unpinned~~ | Resolved 2026-06-18 (6 characterization tests, #198) | Test coverage |
| ~~C-290~~ | ~~3~~ | ~~datafactory_query has 25% module coverage — consumer API mostly untested~~ | Resolved 2026-06-24 (RemoteConfig, PARTITIONS, country_month tests, #237) | Test coverage |
| ~~C-296~~ | ~~3~~ | ~~grid_from_feature_frame has zero tests — 89-line consumer-facing adapter untested~~ | Resolved 2026-06-24 (8 standalone Green/Beige/Red tests, #236) | Test coverage |
| ~~C-297~~ | ~~3~~ | ~~Assembly has zero Red team tests — partial-flag footgun unguarded~~ | Resolved 2026-06-24 (8 Red/Beige tests in test_assemble.py, #235) | Test coverage |
| ~~C-291~~ | ~~3~~ | ~~Conservation assertions use np.nansum() — NaN exclusion weakens partition invariant~~ | Resolved 2026-06-24 (assert_no_unexpected_nan pre-check in _conservation.py, #258) | Count conservation |
| ~~C-292~~ | ~~3~~ | ~~Fuvahmulah-signature cells unverified — distance discriminator proven unreliable~~ | Resolved 2026-06-19 (3 pgids verified in classification JSON, #211) | GAUL data integrity |
| ~~C-263~~ | ~~3~~ | ~~Assembly finally block `mkdir` outside `contextlib.suppress` — can mask original exception~~ | Resolved 2026-06-10 (removed redundant mkdir — append_ledger_entry handles directory creation internally) | Ledger reliability |
| ~~C-299~~ | ~~4~~ | ~~ADR-048 §5 claims `_SOURCE_DISPLAY_NAMES` deleted but it still exists~~ | Resolved 2026-06-28 (commit c45b919: ADR-048 §5 corrected to say `_SOURCE_DISPLAY_NAMES` retained) | ADR-003 compliance |
| C-300 | 4 | Zarr path returns empty `source_features` — pre-coverage warnings silently skipped | Consumer loads data via zarr backend and misinterprets zero-padding as observed | Query layer resilience |
| C-301 | 3 | Conservation no-op for direct callers without `feature_agg_types` — ADR-040 regression | New consumer calls `grid_to_country_month()` directly without `feature_agg_types` | Aggregation correctness |
| C-302 | 4 | Inline prefix check in excluded-cell warning — 4th ADR-003 pattern survived epic | New extensive source added; excluded-cell warning misses its features | ADR-003 compliance |
| ~~C-309~~ | ~~4~~ | ~~Main/development divergence blocks ff-only merge~~ | Resolved 2026-06-29 (merged main into development, topology restored) | Deploy procedure |
| ~~C-310~~ | ~~4~~ | ~~Deployment guide omits merge-main-into-development step~~ | Resolved 2026-06-29 (added step 1 to deployment procedure) | Deploy procedure |
| ~~C-311~~ | ~~2~~ | ~~DGP ordering check contradicts observed UCDP data — blocked v26.1 harvest~~ | Resolved 2026-07-02 (ordering check moved to warn-only, verified on real v25.1 data) | Data soundness |
| ~~C-312~~ | ~~2~~ | ~~ACLED store carried 2x duplicates — cryptic conservation crash~~ | Resolved 2026-07-02 (store rebuilt + uniqueness guard with remediation message) | Data soundness |
| ~~C-313~~ | ~~2~~ | ~~Hardcoded end-year defaults in 9 pipeline scripts — ACLED 2026 silently clipped~~ | Resolved 2026-07-05 (dynamic current-year defaults + regression test banning hardcoded --end-year) | Data soundness |
| ~~C-303~~ | ~~4~~ | ~~ADR-049 §Validation mandates 3 provenance counters; builder logs only 1~~ | Resolved 2026-06-28 (added `n_excluded_where_prec` and `n_passthrough_where_prec` to builder ledger entry) | ADR-049 provenance |
| ~~C-304~~ | ~~4~~ | ~~ADR-049 §2 table says `adm_1` field lookup for where_prec 4/5; code uses pgid→gaul1 crosswalk~~ | Resolved 2026-06-28 (ADR-049 §2 table updated to document crosswalk approach) | ADR-049 documentation |
| ~~C-305~~ | ~~4~~ | ~~ViewpointConfig default crosswalk paths point to `gaul_admin_area_majority/`; pipeline writes to `gaul_admin/`~~ | Resolved 2026-06-28 (config defaults changed to `gaul_admin/`) | ADR-049 pipeline alignment |
| ~~C-306~~ | ~~4~~ | ~~xfail neutralizes F1 hard falsification — test never blocks deployment~~ | Resolved 2026-06-28 (xfail removed, test fails loud pre-deploy) | Test quality |
| ~~C-307~~ | ~~4~~ | ~~gh CLI failure silently treated as "all issues closed" in F6~~ | Resolved 2026-06-28 (returncode guard + fail-loud on gh unavailable) | Test quality |
| ~~C-308~~ | ~~4~~ | ~~Hardcoded plan path in F7 silently skips when plan renamed~~ | Resolved 2026-06-28 (glob pattern finds highest-numbered plan) | Test quality |
| ~~C-159~~ | ~~4~~ | ~~ACLED snapshot archiving and revision comparison paths untested~~ | Demoted to tech-debt backlog 2026-06-06 | — |
| C-10 | — | Ontology vocabulary overhead | Accepted | — |
| C-38 | — | Version string year offset assumes 21st century | Never (2099) | — |
| C-41 | — | Digest truncation collision risk | Records exceed 100M | — |
| C-06 | — | Provenance composability | Deferred by design | — |
| C-07 | — | Frozen dataclass pattern repeated | Deferred by design | — |

## Work Packages

Items that should be resolved together:

| Package | Items | Trigger |
|---------|-------|---------|
| **Server hardening** | C-88, C-97, ~~C-148~~, C-173, C-224 (C-84, C-85, C-86, C-87 resolved; C-173 recalibrated 3→4; C-121 demoted 2026-06-10; C-97, C-148 added 2026-06-12; C-148 demoted 2026-06-16) | Before production deployment or server migration |
| **UCDP API resilience** | C-70, C-72, ~~C-181~~ (C-181 added 2026-06-12; C-181 demoted 2026-06-24) | Multi-operator deployment or UCDP rate-limiting observed |
| ~~**UCDP schema defense**~~ | ~~C-36~~, ~~C-37~~, ~~C-45~~, ~~C-175~~ | Resolved 2026-06-19 (ADR-046 + DGP validation, #209/#212) |
| **Test infrastructure** | C-29, ~~C-79~~, C-146, ~~C-267~~, ~~C-270~~ (C-60, C-169 resolved; C-78 demoted; C-79 demoted 2026-06-14; C-146 recalibrated 3→4; C-267, C-270 resolved 2026-06-18) | Test suite growth |
| **Operational monitoring** | ~~C-131~~, ~~C-136~~, C-147, ~~C-237~~ (C-132, C-191 resolved; C-238, C-239 resolved 2026-06-06; C-265 resolved 2026-06-10; C-136 demoted 2026-06-16; C-237 resolved 2026-06-18; C-131 resolved 2026-06-24 #258) | Before relying on Hetzner pipeline without manual checks |
| **Source registry integrity** | ~~C-236~~, ~~C-293~~, D-33 (C-235, D-32 resolved #105; C-293 resolved 2026-06-19 #208) | Before next data source integration (WDI) |
| ~~**Scaling headroom**~~ | ~~C-144~~, ~~C-145~~, ~~C-179~~, ~~C-223~~ (C-179 demoted 2026-06-24; C-223 resolved 2026-06-24 — memmap, ADR-037; C-144 resolved 2026-06-26 — columnar extraction #275; C-145 resolved 2026-06-26 — column-selective reads #276) | Resolved 2026-06-26 (all items resolved) |
| ~~**Harvest correctness**~~ | ~~C-185~~ (C-182, C-184, C-186, C-188 resolved; C-185 demoted 2026-06-24) | All items resolved or demoted |
| ~~**Count conservation**~~ | ~~C-241~~, ~~C-249~~, ~~C-291~~, C-301 (C-242, C-243, C-244 resolved PR #135; C-291 resolved #260, C-249 resolved #261, C-241 resolved #262 — sprint #258; C-301 added 2026-06-28 — ADR-048 regression, conservation no-op for direct callers) | C-301: new consumer calls `grid_to_country_month()` directly without `feature_agg_types` |
| ~~**GAUL data integrity**~~ | ~~C-247~~, ~~C-250~~, ~~C-268~~ (C-246, C-248 resolved #136) | Resolved 2026-06-19 (#211) |
| **WET-before-DRY refactor** | C-07, C-154, C-155, C-164, ~~C-195~~, ~~C-230~~, C-287, D-38, D-39 (C-44 merged into C-164; C-230 resolved 2026-06-18; C-154 added 2026-06-12; C-287 added 2026-06-14; C-195 demoted 2026-06-19; D-38, D-39 added 2026-06-19) | Before WDI or next refactor sprint |
| ~~**V-Dem test & doc gaps**~~ | ~~C-203~~, ~~C-204~~, ~~C-205~~, ~~C-206~~, ~~C-207~~, ~~C-208~~, ~~C-209~~, ~~C-210~~, ~~C-211~~, ~~C-212~~, ~~C-213~~, ~~C-214~~, ~~C-215~~, ~~C-216~~ | Resolved 2026-05-26: all items resolved in V-Dem sprint |
| **Artifact consistency** | ~~C-253~~, ~~C-254~~, ~~C-255~~, ~~C-259~~, ~~C-260~~, ~~C-261~~, ~~C-262~~, ~~C-231~~, ~~C-280~~, ~~D-34~~, ~~D-36~~, D-37 (C-231 demoted 2026-06-24; C-280 resolved 2026-06-26 #282) | Before expanding consumer bridge beyond UCDP-only features |
| **Data soundness** | ~~C-256~~, ~~C-257~~, ~~C-258~~, ~~C-269~~, D-35 | Before next data source integration (WDI) or next consolidation/viewpoint change |
| ~~**Infrastructure test coverage**~~ | ~~C-189~~, ~~C-271~~, ~~C-273~~, ~~C-276~~, ~~C-280~~, ~~C-296~~, ~~C-297~~, ~~C-289~~ (C-272, C-277, C-278 demoted 2026-06-10; C-274, C-275, C-279 demoted 2026-06-12; C-281 resolved 2026-06-11; C-189 added 2026-06-12; C-289 added 2026-06-14; C-289 resolved 2026-06-18; C-296, C-297 added 2026-06-24; C-273 demoted 2026-06-24; C-296, C-297 resolved 2026-06-24 #235, #236; C-189, C-271, C-276, C-280 resolved 2026-06-26 #281-#284) | Resolved 2026-06-26 (all items resolved or demoted) |
| **Provenance resilience** | C-46, ~~C-136~~, ~~C-270~~, ~~C-271~~ (C-270 resolved 2026-06-18; C-271 resolved 2026-06-26 #281) | Before production ledger exceeds 10MB or next provenance refactor |
| **Query layer resilience** | C-116, C-117, C-300, ~~C-290~~ (C-290 added 2026-06-14; C-290 resolved 2026-06-24 #237; C-300 added 2026-06-28) | Consumer reports transient failures or slow remote queries |
| ~~**Cross-layer verification**~~ | ~~C-288~~ | Resolved 2026-06-15 (tests/test_cross_layer_contracts.py: 24 tests covering all 6 sources) |
| ~~**Cross-repo alignment**~~ | ~~C-264~~ | Resolved 2026-06-14 (partition boundaries updated in defaults.py) |
| ~~**Doc/code consistency**~~ | ~~C-282~~, ~~C-283~~, ~~C-284~~ | Resolved 2026-06-14 (PR #169: temporal routing, ADR-014 P6, ADR-028 event_type_filter) |
| ~~**Pipeline safety**~~ | ~~C-285~~ | Resolved 2026-06-14 (commit 428e479: flock in refresh_pipeline.sh) |
| ~~**Assembly temporal alignment**~~ | ~~C-156~~, ~~C-286~~ | Resolved 2026-06-26 (#266): ADR-047, `first_valid_*_month_id` provenance, `load_dataset()` pre-coverage warning |
| ~~**Provenance locking**~~ | ~~C-294~~, ~~C-295~~ | Resolved 2026-06-24 (#238): digest inside lock + timeout with non-blocking poll |
| **Migration scope** | C-126 (C-125 resolved) | Before claiming full viewser replacement for the fleet |

---

## Tier 1 — Fix Immediately

### ~~C-251: ACLED consolidator cross-file event duplication (2× overcounting)~~ — RESOLVED

The ACLED consolidator deduplicated on `(event_id_cnty, _harvest_digest)`, where `_harvest_digest` is a per-file content digest. When the same event appeared in two source files (`acled_2020_2025.parquet` and `acled_2025_2025.parquet`), each file had a different digest, so both copies survived dedup. All 411,089 ACLED events for 2025 were double-counted in the assembled grid (822,178 instead of 411,089). Silent data corruption with no error signal.

Root cause: the UCDP vintage pattern (ADR-017) was incorrectly applied to ACLED, which has a single source type with no vintage semantics. The dedup key should have been `event_id_cnty` alone from the start.

| Field | Value |
|-------|-------|
| ID | C-251 |
| Tier | 1 — silent data corruption, no error signal |
| Source | Visual audit investigation + manual data inspection, 2026-06-07 |
| Trigger | Multiple ACLED harvest files covering overlapping year ranges |
| Location | `src/datafactory_consolidation/consolidators/acled.py:252-270` |

**Resolution (2026-06-07):** Changed dedup key to `event_id_cnty` alone. Added cross-file dedup within new data (keeps latest harvest per event). Added `_check_year_overlap()` warning for overlapping source files. Added 6 red-team tests. Updated ADR-028. See #138.

---

### ~~C-253~~: Export scripts have no source-digest verification — stale data served silently — RESOLVED

Resolved 2026-06-09 (commit 975b401, branch `chore/pre-deploy-drift-detection`). Source-digest gates added to both export scripts:

- `export_zarr.py` (lines 172-194): calls `compute_file_digest(grid_path)` and compares against `provenance.json["output_digest"]`. ABORTs with exit code 1 on mismatch, preventing stale data export.
- `generate_consumer_data.py` (lines 206-234): same digest gate pattern. ABORTs if grid.npy doesn't match its provenance.
- `health.py:check_export_freshness()` (lines 208-310): now compares `zarr/.zattrs["source_digest"]` against assembly `provenance.json["output_digest"]` — content-based staleness detection (C-255).

The ACLED dedup incident vector (stale zarr after grid correction) is now structurally blocked. Both automated runs and manual out-of-band re-assembly are covered.

**Note:** The original concern is resolved, but the content-addressed skip feature on `feat/content-addressed-skip` introduces a new Tier 1 concern (C-259) — the skip logic does not digest static/admin inputs, creating a different vector for stale data.

See also C-259 (new: skip logic completeness gap), C-147 (no pipeline orchestrator), C-231 (compilation idempotence guard). Part of causal cluster: **Artifact consistency**.


### ~~C-259: Assembly skip logic does not digest static/admin inputs — false skip serves stale grid~~

**Resolved 2026-06-09:** ADR-041 implementation adds composite static/admin digests (sorted `*.parquet` file digests hashed together) to both the provenance write and the skip comparison. `check_assembly_skip` in `datafactory_provenance/skip.py` includes `static_digest` and `admin_digest` in key-set comparison. Integration tests `test_static_change_triggers_rebuild` and `test_admin_change_triggers_rebuild` verify the fix.

| Field | Value |
|-------|-------|
| ID | C-259 |
| Tier | ~~1~~ → Resolved |
| Source | content-addressed skip investigation (2026-06-09) |
| Trigger | Static or admin Parquet files updated (e.g., new GAUL release, updated landarea/mountainous values) and operator runs assembly with `--skip-if-unchanged` |
| Location | `scripts/assemble_grid.py` (skip logic), `src/datafactory_provenance/skip.py` (check_assembly_skip) |

The content-addressed skip logic in `assemble_grid.py` computes SHA256 digests of 5 compiled grid.npy files and compares them against the previous run's `provenance.json`. If all 5 match, it skips assembly. However, the assembly also reads static Parquet files (landarea, mountainous, etc. from `--static-dir`) and admin boundary Parquet files (gaul0_code, gaul1_code, etc. from `--admin-dir`). These inputs are NOT included in the digest set. If someone updates a static or admin file, the skip logic would incorrectly report "all input digests match" and exit early, serving a grid built from stale Parquet data.

The provenance-writing section (lines 784-853) records `static_dir` and `admin_dir` as path strings in the provenance but does NOT compute or store their digests — there is nothing to compare against even if the skip logic tried to check them.

This is the same class of bug as C-253 (stale data served silently) but introduced by the skip feature rather than by missing digest gates.

See also ~~C-253~~ (resolved — same bug class at export boundary), C-260 (source removal false skip — same skip logic), C-261 (no provenance for skips), C-262 (corrupt output passes skip). Part of causal cluster: **Artifact consistency**.


### ~~C-262: Skip path serves corrupt output — no output integrity verification on skip~~

**Resolved 2026-06-09:** ADR-041 implementation adds output integrity verification to the skip path. `check_assembly_skip` computes `compute_file_digest(output_path)` and compares against `provenance["output_digest"]`. If they don't match, `should_skip=False` with `output_valid=False` — assembly rebuilds. Integration test `test_corrupt_output_triggers_rebuild` verifies the fix. `--force` flag added per ADR-032 precedent.

| Field | Value |
|-------|-------|
| ID | C-262 |
| Tier | ~~1~~ → Resolved |
| Source | expert-code-review (2026-06-09), Nygard perspective |
| Trigger | Disk-full condition or `kill -9` during grid.npy write, followed by `--skip-if-unchanged` on the next pipeline run |
| Location | `src/datafactory_provenance/skip.py` (check_assembly_skip output integrity check) |

The skip path at `assemble_grid.py:314` checks `prov_path.exists() and (config.output_dir / "grid.npy").exists()` — both conditions can be true even if `grid.npy` is truncated (partial write from a disk-full condition or process kill). It then compares source digests at lines 341-343 — all match because the source digests describe *inputs*, not the *output*. Assembly skips, and the truncated `grid.npy` is served to consumers.

This failure mode is **self-reinforcing**: every subsequent run with `--skip-if-unchanged` also skips because inputs haven't changed. The corrupt output persists indefinitely. There is no `--force` flag to bypass the skip cache (ADR-032 mandates this as a safety valve), and no health check verifies `grid.npy` integrity between assembly and export.

The fix is to add output integrity verification to the skip path: after determining all input digests match, call `compute_file_digest(output_dir / "grid.npy")` and compare against `provenance.json["output_digest"]`. If they don't match, the output is corrupt — fall through to rebuild.

This is distinct from C-259 (which is about missing *input* digests for static/admin). C-262 is about missing *output* verification on the skip path itself.

See also C-259 (missing input digests), C-261 (no `--force` flag), ADR-032 (harvest idempotence — mandates `--force`). Part of causal cluster: **Artifact consistency**.

---

## Tier 2 — Fix Before Sharing Server Access

### C-88: SSH not restricted to PRIO/Uppsala IPs — [DEFER]
SSH is open to all source IPs. IT head advised whitelisting PRIO and Uppsala VPN IPs via fail2ban or Hetzner firewall, requiring VPN for SSH access. **Trigger: before granting additional SSH users, or when PRIO IT provides VPN CIDR ranges for firewall rules (trigger rewritten during review-rr 2026-05-24).** Procedure documented in `hetzner_deployment_guide.md` Phase 6.4. Requires PRIO/Uppsala VPN CIDR ranges from IT.
**Source:** PRIO IT security guidance, server setup 2026-03-28


### ~~C-131: No external monitoring for cron job failure on Hetzner~~ — RESOLVED

**Resolved 2026-06-24:** Heartbeat ping implemented in `refresh_pipeline.sh:260-263` — on successful pipeline completion, pings `$HEARTBEAT_URL` (env var) via `curl -fsS --max-time 10`. healthchecks.io service configured and operational since v1.2.29. ADR-018 documents bounded staleness SLO with operator monitoring mandate. Deployment guide (`docs/guides/hetzner_deployment_guide.md`) documents healthchecks.io setup procedure.

The monthly pipeline runs via a single cron job (`0 0 21 * *`) under the `views-deploy` user. If the cron daemon crashes, the server reboots without re-enabling cron, or the `views-deploy` user is deleted during maintenance, the pipeline silently stops running. No external monitoring (cronitor, uptime check, systemd watchdog) exists to detect this. ADR-018 explicitly defers monitoring to operators (line 76: "Operators must monitor and intervene during outages") but no operator-side monitoring has been configured. The `ALERT_EMAIL` variable in `refresh_pipeline.sh:68` is a documented TODO (deployment log line 332) and is not set on the server.

**Fix applied (2026-04-22):** Added optional heartbeat ping to `refresh_pipeline.sh` — on successful pipeline completion, pings `$HEARTBEAT_URL` (env var) if set. Operator must configure a healthchecks.io/cronitor service and set the URL on the server. Architectural review confirmed this is a deployment concern (not a new module) per ADR-018.

**Trigger:** ~~Before 2nd month of production cron without `HEARTBEAT_URL` configured on server, or Hetzner server reboots and cron daemon fails to restart.~~ Resolved.
**Location:** Server crontab (`views-deploy` user), `scripts/refresh_pipeline.sh:260-263` (heartbeat ping), `docs/ADRs/018_operational_resilience.md:76,90`.
**Source:** Falsification audit P1/P2 (2026-04-22).


### ~~C-252: ACLED cross-run dedup drops updated events (first-seen wins, not latest)~~ — Resolved 2026-06-19 (#210)

The ACLED consolidator's cross-run dedup path (existing-store merge at lines 309-321) drops new rows when `event_id_cnty` already exists in the store. This contradicts the within-run dedup (`_dedup_by_event_id`) which keeps the latest harvest. If ACLED revises a past event (corrected fatalities, reclassified event_type, updated coordinates), the corrected version is silently dropped in favor of the stale version. ADR-028 states "the version from the most recent harvest is kept" — the cross-run path violates this.

Mitigating factor: current operational pattern deletes and rebuilds the store from all raw files, so cross-file dedup (stage 1) handles most cases. The risk materializes only when the store already exists from a prior run and new data arrives with a corrected event.

| Field | Value |
|-------|-------|
| ID | C-252 |
| Tier | 2 — silent data staleness when ACLED revises events, no error signal |
| Source | review-diff, 2026-06-07 |
| Trigger | ACLED revises a past event (corrected fatalities, reclassified type) and operator re-consolidates incrementally against existing store |
| Location | `src/datafactory_consolidation/consolidators/acled.py:309-321` |

Cross-ref: C-251 (resolved — same-run cross-file duplication, different path).

**Update (2026-06-19, expert-code-review of sprint issues):** Implementation hazard identified — `_harvest_timestamp` may be stored as ISO string in legacy store entries and as Unix epoch in newer entries. String comparison of heterogeneous formats yields wrong ordering. The fix (#210) must normalize timestamps to a comparable format before comparison, and fall back to first-seen-wins with a warning if `_harvest_timestamp` is missing from either side.


### ~~C-254: Consumer parquet has zero provenance — no audit trail for training data~~ — [RESOLVED]

| Field | Value |
|-------|-------|
| ID | C-254 |
| Tier | 2 — structural fragility; becomes Tier 1 when consumer bridge expands beyond UCDP-only features |
| Source | expert-review (2026-06-08), derived-artifact drift audit; content-addressed skip investigation (2026-06-09) |
| Trigger | Consumer bridge expanded to include ACLED or other features (`FEATURE_RENAME` dict in `generate_consumer_data.py:45-50`), or model trains on stale parquet after a mid-cycle grid correction |
| Location | `scripts/generate_consumer_data.py` (no ledger entry, no manifest — only digest gate), `scripts/export_dataframe.py` (zero provenance infrastructure — no digest, no gate, no ledger) |

`generate_consumer_data.py` calls `load_dataset()` at line 120, transforms the result, and writes parquet at line 237. It records nothing about what data version it read, when, or from what source. There is no way to determine what grid version a consumer parquet was generated from — no sidecar manifest, no parquet metadata, no provenance ledger entry. Currently low-risk because the consumer bridge only exports UCDP features (`ged_sb_best`, `ged_ns_best`, `ged_os_best`, `gaul0_code`) renamed to VIEWSER convention. But the R&D roadmap plans to expand this bridge. When ACLED or other features are added, the same stale-export vector that caused C-253 applies to training data with no forensic capability. A model suspected of training on stale data has no audit trail.

**Partially resolved (2026-06-09, commit 975b401):** `generate_consumer_data.py` now has a source-digest gate (lines 206-234) that ABORTs if `grid.npy` doesn't match its provenance. This prevents serving stale data but does NOT create an audit trail — no ledger entry, no manifest, no record of what was exported when. The "stale data served" vector is closed; the "no forensics" vector remains open.

**Additional location (2026-06-09, content-addressed skip investigation):** `scripts/export_dataframe.py` has zero provenance infrastructure — no `compute_file_digest()`, no digest gate, no ledger entry, no skip logic. It reads assembled data and writes DataFrame output with no provenance awareness at all.

See also ~~C-253~~ (resolved — digest gates added), C-06 (provenance composability — deferred by design). Part of causal cluster: **Artifact consistency**.

**Resolved 2026-06-18:** 5 characterization tests added in `tests/test_consumer_provenance.py` (#199). Pins provenance.json creation, schema keys, source digest match, output file digests, and abort on digest mismatch.


### ~~C-255~~: Health check reports "SLO MET" for content-stale artifacts (time-fresh, content-wrong) — RESOLVED

Resolved 2026-06-09 (commit 975b401, branch `chore/pre-deploy-drift-detection`). `check_export_freshness()` (lines 208-310 in `health.py`) now compares `zarr/.zattrs["source_digest"]` against `provenance.json["output_digest"]` — content-based staleness detection. The function reports `content_fresh: bool` separately from `time_fresh: bool`, decomplecting the two concerns as Hickey recommended. The `verify_source_digest()` function (lines 163-205) provides the reusable building block.

The ACLED dedup incident vector is now detectable: a zarr with a stale `source_digest` would be flagged even if the `export_timestamp` is within SLO.

See also ~~C-253~~ (resolved — root cause), D-34 (enforcement location disagreement, still open). Part of causal cluster: **Artifact consistency**.


### ~~C-260: Assembly skip logic ignores source removal — `all()` checks only current keys~~

**Resolved 2026-06-09:** ADR-041 implementation replaces the inline `all()` with `check_assembly_skip`, which compares the full key set in both directions (current vs prev). If `current_keys != prev_digest_keys`, the function returns `should_skip=False` with `missing_keys` or `changed_keys` populated. Unit test `test_no_skip_when_source_removed` and `test_no_skip_when_source_added` verify both directions.

| Field | Value |
|-------|-------|
| ID | C-260 |
| Tier | ~~2~~ → Resolved |
| Source | content-addressed skip investigation (2026-06-09) |
| Trigger | A source is removed from the assembly CLI args (e.g., `--acled-grid` removed) while `--skip-if-unchanged` is active |
| Location | `src/datafactory_provenance/skip.py` (check_assembly_skip key-set equality) |

The skip logic's `all()` check iterates only over `current_digests.items()` — the keys present in the current run. It does NOT check whether `prev_src` (from `provenance.json`) contains keys that are absent from `current_digests`. If a source was part of the previous assembly but is removed from the current invocation (e.g., operator drops `--acled-grid`), the old digest key persists in `prev_src` but is never compared. The `all()` check succeeds for all *current* keys, and the skip proceeds, serving a grid that still contains the removed source's data from the previous run.

This is a realistic scenario during source integration/removal and during debugging when operators selectively disable sources.

See also C-259 (static/admin not digested — same skip logic), C-261 (no provenance for skips). Part of causal cluster: **Artifact consistency**.


### ~~C-257: No input data validation at system boundary — DGP assumptions untested~~ — Resolved 2026-06-19 (#212)

| Field | Value |
|-------|-------|
| ID | C-257 |
| Tier | 2 — structural fragility; silent corruption if any source changes its data model |
| Source | expert-method-review (2026-06-08), McElreath perspective |
| Trigger | ACLED or UCDP changes their data model (e.g., ACLED introduces multi-day events, UCDP adds a new `date_prec` value, GHS-POP switches from float to int encoding) |
| Location | `src/datafactory_harvester/sources/` (all source modules — acled.py, ucdp_annual.py, ghspop.py, ghsbuilts.py, vdem.py) |

The harvest layer trusts that external sources send data matching the pipeline's DGP assumptions. No test verifies incoming ACLED events have single dates (not ranges, per ADR-028), UCDP coordinates are non-null and within valid spatial bounds, UCDP `date_prec` values fall within the expected set `{1,2,3,4,5}`, or GHS-POP raster values are non-negative. These are assumptions about the data-generating process, not the pipeline code. If a source silently changes its data model — ACLED introducing multi-day events, UCDP adding a new precision category, GHS-POP switching encoding — the pipeline would process invalid data without detection, producing silent corruption downstream. Breck et al. 2019 ("Data Validation for ML") calls these "data unit tests" and identifies them as the highest-priority data testing investment. Currently mitigated only by manual inspection during visual audits, which is neither systematic nor automated. The ACLED harvester does validate `event_id_cnty` presence (for dedup), but does not validate event content against DGP assumptions.

See also C-36 (UCDP API contract has no schema versioning — related but narrower), C-45 (no Parquet schema evolution strategy), C-153 (ACLED API has no TotalCount). Part of causal cluster: **Data soundness**.

**Update (2026-06-19, expert-code-review of sprint issues):** Failure mode unspecified — original DoD had "or documented" escape clause allowing checks to exist without being wired in. Expert review correction: `validate_dgp_assumptions()` raises `ValueError` on any violation (fail-loud per ADR-011). No silent skip, no "log and continue." Check definitions live in per-source modules, not in `event_validation.py`. See also D-40 (DGP check module placement).

**Update (2026-07-02, v1.6.1 deploy incident):** The `best/high/low` ordering check contradicted the observed UCDP DGP — published data violates the ordering in ~1.3% of events (all versions, all years). It blocked the first fresh fetch (v26.1) and was downgraded to warn-only (C-311). The "fail-loud on any violation" stance holds for genuine invariants only; checks encoding assumptions the source never promised must be verified against real data before being made blocking.


### ~~C-258: Count conservation not enforced at consolidation or viewpoint boundaries~~ RESOLVED

Resolved 2026-06-15. Conservation assertions now enforced at 4 boundaries: (1) ACLED consolidation — `_dedup_by_event_id` returns `(table, n_removed)`, fail-loud assertion `n_concat == n_new_raw + n_dedup_removed`, store merge assertion `n_total == n_before + n_new`, ledger records `n_records_concat`/`n_dedup_removed`/`n_records_dedup_filtered`. (2) UCDP consolidation — ledger records `n_records_raw`/`n_records_dedup_filtered` (already had assertions). (3) ACLED viewpoint — fail-loud assertion `n_input == n_output + n_filtered`. (4) UCDP viewpoint — fail-loud assertion `n_read == n_input + n_stale`, ledger records `n_events_read`/`n_stale_filtered`/`n_groups`/`n_survivorship_discarded`. 14 tests in `tests/test_boundary_conservation.py`.

**Source:** expert-method-review (2026-06-08), Betancourt perspective. Cross-ref: C-242 (resolved — conservation at compilation/CM boundaries), C-251 (resolved — the incident that demonstrates this gap).


### ~~C-239: Issue #104 paths produce silent wrong status page~~ RESOLVED

Resolved 2026-06-06 (review-rr strategic curation). Issue #104 closed with comment pointing to #123 as the superseding issue. The wrong `--data-dir` and `--provenance-dir` paths can no longer mislead developers because the issue is closed. The docstring path was also fixed (C-240, commit dd69544).

**Source:** falsification audit (2026-06-04, G4). Cross-ref: C-238 (resolved same session), C-237 (delivery gap, still open), C-240 (resolved, docstring fixed).


### ~~C-242: ADR-040 count conservation invariants accepted but zero test enforcement~~ RESOLVED

Resolved 2026-06-06 (PR #135). Runtime assertions added at both layer boundaries: `assert_placement_conservation()` in `grid_compilation.py` (exact integer equality) and `assert_cm_conservation()` in `grid_to_country_month.py` (`np.allclose` for float32 sums). Uses `if/raise RuntimeError` — not `assert`. 10 tests in `tests/test_count_conservation.py` (Green/Beige/Red tiers).

Cross-ref: C-241 (intensive feature gap — different invariant, still open), C-243 (resolved same PR), ADR-040.


### ~~C-246: `_compute_cell_polygon_map` is production code path with zero direct tests~~ — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-246 |
| Tier | 2 |
| Source | Pre-deployment test coverage audit (2026-06-07) |
| Resolution | 2026-06-07 (#136): 15 direct tests across 4 classes — TestCellPolygonMapGreen (6), TestCellPolygonMapBeige (4), TestCellPolygonMapRed (2), TestCellPolygonMapEquivalence (3). Equivalence tests cross-check against `area_majority_join` results. |
| Location | `scripts/generate_area_majority_gaul.py:122-166` (`_compute_cell_polygon_map`) |

Cross-ref: C-230 (script layer has zero unit tests), ADR-039 (area-majority spatial join).

---

### ~~C-265: SHDI harvest missing from `refresh_pipeline.sh` — status page RED, data never collected~~ — RESOLVED

Resolved 2026-06-10 (commit cd23624: `uv run python scripts/harvest_shdi.py` added to `refresh_pipeline.sh` line 173).

| Field | Value |
|-------|-------|
| Trigger | ~~Pipeline runs on server; SHDI remains permanently unharvested~~ — resolved |
| ID | C-265 |
| Tier | ~~2~~ |
| Source | Pipeline gap audit (2026-06-10) |
| Location | `scripts/refresh_pipeline.sh:173` (SHDI harvest now wired in) |

Cross-ref: C-236 (status page artifact mapping requires manual update per source), C-164 (cross-layer WET debt — SHDI is the 6th source copied without wiring).

---

### ~~C-267: event_store.py crash-safety and concurrency paths untested — system of record at risk~~

`event_store.py` implements the atomic write path for the consolidated store (the system of record per DDIA Ch.1 pp.10-11): temp file + `os.rename()` for crash-safe writes, `file_lock` for concurrent access via `fcntl.flock()` with a 5-minute stale threshold. None of these paths have direct tests. The atomic write pattern is correct (temp+rename is the standard POSIX idiom), but a regression during refactoring — e.g., writing directly without temp file, or removing the lock — would silently compromise the authoritative store with no test to catch it. The stale lock cleanup (5-minute threshold, `os.stat().st_mtime` comparison) has zero tests for: lock file older than threshold, lock file younger than threshold, missing lock file, or clock skew.

**Lock file race window (added 2026-06-16, repo-assimilation):** The stale-lock cleanup in `file_lock()` (`_STALE_LOCK_SECONDS = 300` at `digests_and_ledgers.py:145`) has a race window: if process A crashes while holding the lock and a monitoring system restarts it within the 5-minute window, process B may detect the stale lock (age > 300s), remove it, and acquire a new lock — but the restarted process A may still reference the old lock. Additionally, some legitimate operations (consolidation of large stores) can exceed 5 minutes, causing a live lock to be incorrectly classified as stale. Currently mitigated by: (1) pipeline-level flock in `refresh_pipeline.sh` (C-285, resolved) prevents concurrent runs, (2) single-operator deployment reduces collision risk.

| Field | Value |
|-------|-------|
| Trigger | Refactoring `event_store.py` write path (e.g., adding compression, changing serialization format) without characterization tests to catch behavioral change; or consolidation run exceeds 5 minutes on constrained hardware |
| ID | C-267 |
| Tier | 2 |
| Source | test-review (2026-06-10), repo-assimilation (2026-06-16) |
| Location | `src/datafactory_consolidation/event_store.py` (atomic write, file_lock), `src/datafactory_provenance/digests_and_ledgers.py:120-160` (stale lock cleanup) |

Cross-ref: C-258 (count conservation at consolidation boundary — same code path), C-257 (no input validation — same layer).

**Resolved 2026-06-18:** 6 characterization tests added in `tests/test_consolidation.py::TestStoreCharacterization` (#195). Pins write-read roundtrip, atomic temp file usage, None on missing path, content digest, concurrent reads, and overwrite behavior.

---

### ~~C-293: Three-way feature name sync only partially tested~~ — Resolved 2026-06-19 (#208)

| Field | Value |
|-------|-------|
| ID | C-293 |
| Tier | 2 — silent feature mismatch produces wrong grid channel if name lists diverge; promoted from 3 during review-rr strategic 2026-06-19 |
| Source | expert-code-review (2026-06-18), Martin/Kleppmann |
| Trigger | Adding a new data source — developer updates `source_registry.py` feature names but forgets to update `assemble_grid.py`'s stacking order or vice versa |
| Location | `src/datafactory_provenance/source_registry.py` (feature names), `scripts/assemble_grid.py` (stacking order), `scripts/generate_status.py` (SOURCE_STAGES), `tests/test_generate_status.py` (TestSourceRegistryAlignment — only tests registry↔status pair) |

Feature names appear in three places that must stay synchronized: (1) `source_registry.py` declares canonical feature names per source, (2) `assemble_grid.py` stacks compiled npy files into the grid using a hardcoded source order that determines channel offsets, (3) `generate_status.py` maps sources to display stages. `TestSourceRegistryAlignment` (C-236, #203) verifies the registry↔status pair, but no test verifies the registry↔assembly pair. If a developer adds features to the registry but doesn't update assembly's stacking order, the assembled grid silently maps features to wrong channels — a Tier 1 failure mode that currently depends on manual discipline, not automated enforcement.

**To resolve:** Add a test in `tests/test_grid.py` or a new test file that loads `assemble_grid.py`'s source ordering and compares it against `source_registry.py`'s `get_all_features()` — verifying that every registry feature appears in assembly and the channel count matches.

Cross-ref: ~~C-236~~ (resolved — registry↔status pair tested), C-146 (assembly logic in script not importable package). Part of work package: **Source registry**.

---

## Tier 3 — Improve Quality

### ~~C-261: No provenance ledger entry for skip events — audit trail has temporal gaps~~

**Resolved 2026-06-09:** ADR-041 implementation adds ledger entries for both skip (`outcome: "unchanged"`) and success (`outcome: "success"`) in both assembly and export. `--force` flag added to both scripts, bypassing skip entirely per ADR-032 precedent. Integration tests `test_skip_records_ledger_entry` and `test_export_skip_records_ledger_entry` verify ledger writes. `test_force_flag_bypasses_skip` and `test_export_force_bypasses_skip` verify the override.

| Field | Value |
|-------|-------|
| ID | C-261 |
| Tier | ~~3~~ → Resolved |
| Source | content-addressed skip investigation (2026-06-09) |
| Trigger | Operator investigates a data freshness question and cannot determine from the ledger whether the pipeline ran and found no changes, or simply didn't run |
| Location | `scripts/assemble_grid.py`, `scripts/export_zarr.py`, `src/datafactory_provenance/skip.py` |

When the content-addressed skip logic determines that inputs haven't changed, both `assemble_grid.py` and `export_zarr.py` print "SKIP: ..." and return 0. Neither script appends a ledger entry recording the skip event. The provenance trail has temporal gaps — there is no way to distinguish "pipeline ran at 21:00, nothing changed" from "pipeline didn't run at 21:00."

The established pattern from ADR-032 (harvest idempotence and caching) records `"outcome": "unchanged"` in ledger entries when a harvest finds no new data. The skip logic should follow this vocabulary: `success` (work done), `unchanged` (inputs matched, work skipped), `cached` (output reused), `failed` (error).

Additionally, the skip logic has no `--force` flag to bypass caching, which ADR-032 mandates as a safety valve ("all cache layers must be bypassable with `--force`"). A corrupted `provenance.json` with matching digests would permanently prevent rebuild with no override mechanism.

See also C-259 (skip completeness gap), C-260 (source removal), ADR-032 (harvest idempotence — the model pattern). Part of causal cluster: **Artifact consistency**.


### ~~C-256: No definition of "data soundness" as a testable property~~

| Field | Value |
|-------|-------|
| ID | C-256 |
| Tier | 3 — organizational/maintainability gap affecting multiple operators and the deploy decision |
| Source | expert-method-review (2026-06-08), synthesis of Betancourt/Gelman/Gneiting/Hyndman perspectives |
| Trigger | Before next deploy that follows a mid-cycle data correction or new source integration — operator must manually integrate pytest, visual audits, `check_health.py`, and manual inspection with no composite decision |
| Location | No artifact exists; concept is implicit across `tests/test_falsification_deploy_readiness.py`, `scripts/check_health.py`, `src/datafactory_provenance/health.py`, and operator knowledge |

"Data soundness" is used informally across ADRs, test names, and operational procedures but has no formal definition as a testable property. Without a definition, testing is reactive (add a test per incident) rather than systematic (test against a specification). The expert-method-review proposes a four-part definition: data is sound if (a) all count conservation invariants hold at every boundary, (b) all derived artifact digests match their sources, (c) no feature-month parity exceeds float32 tolerance, (d) no temporal coherence anomaly is flagged. This should be codified in an ADR and implemented as a single `check_deploy_readiness.py` script returning PASS/FAIL. Currently, the operator must mentally integrate 4+ signal sources with no composite score.

See also C-253 (digest gates — component b), C-258 (conservation at all boundaries — component a), C-255 (health check false assurance — symptom of missing definition). Part of causal cluster: **Data soundness**.

**Resolved 2026-06-18:** ADR-045 (`docs/ADRs/045_data_soundness_invariants.md`) defines soundness as layer-boundary invariant preservation (#200). Includes invariant chain table, extensive vs intensive distinction, and gap table of tested vs untested invariants.

---

### C-126: No transform layer — models using viewser transforms cannot migrate — [DEFER]
14 distinct viewser transforms are in active use across the fleet: `replace_na`, `fill`, `tlag` (832 uses), `countrylag` (486), `gte` (316), `decay` (288), `time_since` (285), `ln` (233), `moving_sum`, `spatial.lag`, `sptime_dist`, `treelag`, `delta`, `moving_average`. The factory provides raw values + `fillna(0)` only. Models using any transform beyond fillna cannot migrate without reimplementing those transforms outside viewser. The transform layer will likely be a separate repo or integrated into model classes (hydranet, r2darts2, stepshifter) — too early to decide architecture. **Trigger: model migration plan requires features derived from viewser transforms.**
**Source:** Falsification audit 2026-04-20 (F7). Cross-ref: S2 in `test_falsification_viewser_replacement.py`.

### ~~C-144~~: ~~Compilation `to_pydict()` materializes millions of Python objects~~ — Resolved #275

| Field | Value |
|-------|-------|
| ID | ~~C-144~~ |
| Tier | ~~3~~ |
| Source | repo-assimilation (2026-04-30) |
| Trigger | ~~When the consolidated store exceeds ~5M events (currently ~2.3M), compilation memory usage on the CPX32 server (32GB) may exceed available RAM~~ |
| Location | `src/datafactory_compilation/grid_compilation.py` (`_place_events`) |

**Resolved 2026-06-26 (#275).** Replaced `table.to_pydict()` with columnar `.to_numpy(zero_copy_only=False)` extraction per column, producing `dict[str, np.ndarray]`. Bin assignment now stores integer row indices (`dict[tuple[int,int], np.ndarray]`) instead of full event dicts. Aggregation constructs ephemeral 1-key dicts on-the-fly, bounded by bin size (~100 events) not total events (~2M). Strategy function interface `(list[dict], str) -> float` preserved unchanged. Tests in `TestColumnarExtractionGreen` and `TestColumnarExtractionBeige` verify row-index arrays, column-array values, filtered aggregation, and empty-input edge case.

### ~~C-145~~: ~~Viewpoint builder loads full consolidated store into memory~~ — Resolved #276

| Field | Value |
|-------|-------|
| ID | ~~C-145~~ |
| Tier | ~~3~~ |
| Source | repo-assimilation (2026-04-30) |
| Trigger | ~~When the consolidated store exceeds ~5M rows on a memory-constrained machine, or when building viewpoints on developer laptops with <16GB RAM~~ |
| Location | `src/datafactory_viewpoint/builders/ucdp_v1.py`, `src/datafactory_viewpoint/builders/acled_v1.py` |

**Resolved 2026-06-26 (#276).** Both UCDP and ACLED viewpoint builders now use column-selective Parquet reads. UCDP: `pq.read_schema()` first, then `pq.read_table(columns=...)` skipping `_ingested_at`, `_harvest_digest`, `_harvest_timestamp` (pure metadata) while keeping `_source_type` and `_source_version` (needed for survivorship). ACLED: same schema-first pattern, validates `REQUIRED_CONSOLIDATED_FIELDS` against schema before reading, then skips all `STRIPPED_FIELDS`. Tests in `TestColumnSelectionGreen` verify metadata exclusion and survivorship correctness with column selection.

### ~~C-235~~: Source registry declares nonexistent SHDI downstream entries — Resolved #105

| Field | Value |
|-------|-------|
| ID | C-235 |
| Tier | 3 |
| Source | expert-code-review (2026-06-03), pipeline status page initiative |
| Trigger | SHDI viewpoint implemented without removing or updating phantom downstream entries; or new developer reads registry and assumes SHDI is fully integrated |
| Location | `src/datafactory_provenance/source_registry.py:273-278` (SHDI Viewpoint), `src/datafactory_provenance/source_registry.py:315-320` (SHDI Compilation) |

`PIPELINE_SOURCES` contains `SourceEntry` declarations for "SHDI Viewpoint" (with `viewpoint/shdi_v1_ledger.jsonl`) and "SHDI Compilation" (with `compilation/shdi_ledger.jsonl`). No corresponding code exists: no `builders/shdi_v1.py`, no `compile_shdi.py`, no assembly integration. These entries create false expectation of integration completeness. The SHDI harvest entry (line 192-205) declares 4 features (`shdi_shdi`, `shdi_healthindex`, `shdi_edindex`, `shdi_incindex`) that `get_all_features()` returns, causing `verify_remote.py` to expect 79 features when the grid contains 75.

The root cause is that the source registry conflates "this source will eventually produce these features" (planning document) with "these features are in the grid" (deployment document). Six experts in the 8-expert review flagged this as the core issue. See D-32 for the disagreement on the fix approach.

Cross-ref: C-164 (WET debt — SHDI copied patterns), D-32 (assembled flag vs feature removal). GitHub: #101, #103.

### ~~C-237: Status page generation + delivery verification gap~~ — RESOLVED 2026-06-18

| Field | Value |
|-------|-------|
| ID | C-237 |
| Tier | 3 |
| Source | expert-code-review (2026-06-03), Nygard perspective; falsification audit (2026-06-04, F5) |
| Trigger | Before next production deploy — verify #126 implementation closes delivery gap; or EXIT trap runs but output doesn't land at Caddy path |
| Location | `scripts/refresh_pipeline.sh:47` (`set -euo pipefail`), `scripts/refresh_pipeline.sh:92-98` (EXIT trap), `scripts/generate_status.py:410` (output path default) |

Two gaps in the status page generation chain:

**Gap 1 — Generation reliability:** The original `set -e` concern was mitigated by moving generation into a `trap EXIT` handler (lines 92-98). The EXIT trap fires on normal exit, ERR, SIGTERM, SIGHUP, SIGINT — but NOT on SIGKILL. The `|| echo` pattern inside the trap suppresses `generate_status.py` failures silently.

**Gap 2 — Delivery verification (from falsification audit F5):** Even when the EXIT trap runs and `generate_status.py` succeeds, nothing verifies the output file exists at the path Caddy actually serves (`/srv/views-data/status.html`). The script writes to `data/status.html` (relative to repo). No post-generation check confirms reachability. The v1.2.27 diagnosis was built on HTTP status codes (401/404) without ever verifying whether the file was generated on the server — symptom-based diagnosis, not root-cause verification.

**Mitigation:** #126 proposes adding a verify check to `verify_remote.py` and a file-existence check to the EXIT trap. When implemented, this resolves Gap 2 for deployments but not for the daily cron (C-238, now resolved — daily cron covered by #123).

Cross-ref: C-131 (no external monitoring for cron), ~~C-238~~ (resolved 2026-06-06). GitHub: #101, #104, #123, #126.

**Resolution (2026-06-18):** 4 characterization tests in `tests/test_generate_status.py::TestDeliveryContract` pin: HTML output written, all sources present, generation timestamp, feature count 79. Sprint epic #205, issue #204.

### ~~C-238: Issue #104 stale Caddy claims + orphaned daily cron requirement~~ RESOLVED

Resolved 2026-06-06 (review-rr strategic curation). Issue #104 closed with comment pointing to #123 as the superseding issue. The stale Caddy claims, wrong paths, and orphaned daily cron requirement in #104 can no longer mislead developers because the issue is closed. #123 and #125 were updated with concrete fix instructions and acknowledgment of manual post-pipeline server steps.

**Source:** falsification audit (2026-06-04, F2+F4). Cross-ref: C-237 (delivery gap, still open), C-239 (resolved same session).

### ~~C-243: ADR-040 hierarchical reconciliation untested (gaul0/1/2 sum equality)~~ RESOLVED

Resolved 2026-06-06 (PR #135). `check_nesting()` and `assert_hierarchical_reconciliation()` added in `src/datafactory_adapters/_reconciliation.py`. 6 tests in `tests/test_hierarchical_reconciliation.py` (Green/Beige/Red tiers + real-data skipif test). Tests verify nesting (every L2→L1 and L1→L0 mapping is unique) and sum reconciliation (grouping by any level produces identical totals).

Cross-ref: C-242 (resolved same PR), C-241 (intensive feature gap, still open), ADR-040.

### ~~C-156: ACLED temporal range mismatch — zero-fill before 2020 in assembled grid~~ — RESOLVED 2026-06-26

| Field | Value |
|-------|-------|
| ID | C-156 |
| Tier | 4 (demoted from 3 during review-rr strategic curation 2026-06-24 — documented, consumer-responsibility, single-developer, trigger requires consumer unawareness) |
| Source | ACLED grid verification (2026-05-06) |
| Trigger | Model uses ACLED features for pre-2020 months without awareness that values are zero-fill, not observed zeros |
| Location | `scripts/assemble_grid.py`, `src/datafactory_query/dataset.py` |

**Resolved:** Assembly temporal alignment hardening sprint (#266, 2026-06-26). All three resolution options (a) and (b) implemented: (a) `first_valid_acled_month_id` recorded in `provenance.json` alongside existing `last_valid_acled_month_id`; (b) `load_dataset()` emits `UserWarning` when consumer requests ACLED features for months before `first_valid_acled_month_id`. Same pattern applied to all 5 non-UCDP sources (ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI). Option (c) NaN-fill deferred — would break models expecting float32 without NaN handling. ADR-047 documents the temporal anchor architecture.

See also C-130 (zero-filled future months), C-133 (zero-padding warning bypass), C-286 (temporal anchor).

### C-153: ACLED API has no TotalCount — silent truncation undetectable — [OPEN]

| Field | Value |
|-------|-------|
| ID | C-153 |
| Tier | 3 |
| Source | ACLED test review (2026-05-03) |
| Trigger | ACLED API starts enforcing server-side result caps or query complexity limits that return partial data within a single page |
| Location | `src/datafactory_harvester/sources/acled.py:fetch_paginated()`, `docs/ADRs/027_harvest_count_verification.md` |

The ACLED API response envelope has `"count": null, "total_count": null` — there is no server-reported total to verify pagination completeness. The harvester terminates on empty/short pages (correct behavior for complete pagination) but cannot detect if the API silently caps results within a page. Unlike UCDP (which provides `TotalCount`), there is no way to verify "did I get everything?" without an independent count source. ADR-027 documents this as an accepted limitation with the short-page heuristic as the only available detection signal. Not Tier 1/2 because: (a) short-page heuristic catches most truncation, (b) documented in ADR-027, (c) no evidence truncation occurs in practice. Medium because: if it does occur, downstream models train on incomplete data with no error signal.

See also C-72 (HTTP 429 not distinguished), C-45 (no schema evolution strategy).

### C-164: Cross-layer WET debt — 6 sources replicate patterns across all 4 layers — [TRIGGER FIRED]

| Field | Value |
|-------|-------|
| ID | C-164 |
| Tier | 3 |
| Source | WET-before-DRY audit (2026-05-19), GHS-POP Phase 4 completion, expert code review (2026-05-30) |
| Trigger | **Fired 2026-05-22 (GHS-BUILT-S), 2026-05-26 (V-Dem), 2026-05-29 (SHDI):** 6th pipeline source copied cross-layer patterns without extraction. Acknowledged 2026-06-12 (review-rr strategic): accepted at Tier 3 — WET-before-DRY strategy is intentional, patterns are clear, extraction is safe when WDI arrives. **Rewritten trigger:** Before WDI integration (10th source). |
| Location | All `src/datafactory_*` packages — see inventory below |

With 4 sources implemented (UCDP, ACLED, GHS-POP, GHS-BUILT-S), the codebase has accumulated intentional WET patterns across all four layers. The WET-before-DRY strategy (ADR: write 3 times before abstracting) has succeeded — concrete patterns are now clear. The 4th source (GHS-BUILT-S, v1.2.20) copied all patterns again, confirming the abstraction boundaries.

**Inventory of cross-layer WET patterns:**

1. **Harvester config validation** (5 files): `timeout >= 1`, `page_size >= 1`, `max_retries >= 1`, year range validation — all follow identical `if val < 1: raise ValueError` patterns. Files: `ucdp_annual.py`, `ucdp_candidate.py`, `ucdp_dot9.py`, `acled.py`, `ghspop.py`. Abstraction: trivial (shared validators or base config).

2. **Consolidation helpers** (2 files): `_build_harvest_index()`, `_get_harvest_metadata()`, and `_tag_table()` are line-by-line identical between `consolidators/ucdp.py` and `consolidators/acled.py`. Only dedup key construction differs. Abstraction: trivial-moderate (extract shared functions, parameterize dedup key).

3. **Viewpoint builder scaffolding** (3 files): Config-or-shortcut pattern, file existence check, provenance recording, ViewpointResult construction — structurally identical across `acled_v1.py`, `ghspop_v1.py`, and `ucdp_v1.py` (via `builders/ucdp_v1.py`). Core logic differs (event filtering vs. spatial aggregation). Abstraction: moderate (base builder class with template method).

4. **Compilation output writing** (2 files): `grid.npy`, `pgids.npy`, `time_steps.npy`, `feature_names.json`, `provenance.json` — identical output generation code in `grid_compilation.py` and `pregridded_compilation.py`. Input logic is fundamentally different (lat/lon events vs. pgid/month_id rows). Abstraction: moderate (extract `_write_grid_output()` helper).

5. **`_VIEWS_EPOCH_YEAR = 1980`** (2 files): Duplicated in `ghspop_v1.py` and `pregridded_compilation.py`. Already defined as `_VIEWS_EPOCH` in `temporal_generator.py`. Abstraction: trivial (import from single source).

6. **Provenance recording** (~48 call sites): `append_ledger_entry()` called with structurally similar dicts across all layers. Common fields: dataset, outcome, ledger_version, digest_algorithm. Source-specific fields vary. Abstraction: trivial-moderate (builder pattern for ledger dicts). See also C-06.

7. **Pipeline runner scripts** (3 files): `run_ucdp_pipeline.py`, `run_ghspop_pipeline.py`, `run_ghsbuilts_pipeline.py` replicate the same orchestration pattern (~846 lines combined): argparse setup, `--skip-to` logic, sequential step execution with log headers. Core logic varies (which steps to run, source-specific paths). Abstraction: moderate (shared runner with pluggable step definitions).

8. **Harvest script wrappers** (7 files): `harvest_ucdp.py`, `harvest_acled.py`, `harvest_ghspop.py`, `harvest_ghsbuilts.py`, `harvest_priogrid.py`, `harvest_gaul.py`, `harvest_candidates.py` are thin ~150-line wrappers (~1,035 lines combined) that parse args and call the harvester function. Structurally identical. Abstraction: trivial (shared `harvest_main()` wrapper with source config).

**Recommended abstraction order** (by ROI when 5th source arrives):
1. `_VIEWS_EPOCH_YEAR` constant dedup (trivial, 5 min)
2. Compilation output writer extraction (moderate, prevents most duplication)
3. Harvest script wrappers (trivial, 7 near-identical files)
4. Harvester config validators (trivial, prevents 5→6+ duplication)
5. Pipeline runner shared infrastructure (moderate, 3 files with shared arg/step pattern)
6. Consolidation shared helpers (moderate, 3 near-identical functions)
7. Viewpoint builder base class (moderate, highest design risk)

Cross-ref: C-44 (harvest pipeline template), C-07 (frozen dataclass pattern), C-155 (visual audit framework), C-06 (provenance composability), C-219 (PrecomputedData CIC).

**Note (2026-05-26, visual audit docs falsification):** Beyond code duplication, the verification scripts also lack governance: no ADR, CIC, or standard defines what a verification script must check, how plots are selected, or what "PASS" means. ADR-005 covers unit/integration tests. ADR-019 covers aesthetics. Neither covers visual audit methodology. When extraction happens, a verification standard should accompany it.

**Note (2026-05-22):** Trigger fired — GHS-BUILT-S (8th source, 4th raster) copied all 6 patterns. `ghsbuilts_v1.py` duplicates `_read_geotiff`, `_aggregate_with_alignment`, `_interpolate_temporal` from `ghspop_v1.py`. `_VIEWS_EPOCH_YEAR` now duplicated in 3 files. Accepted for v1.2.20; extract shared raster utilities before 5th source (V-Dem or WDI).

**Note (2026-05-24, tech-debt-cleanup investigation):** Quantified each pattern for extraction planning:

| # | Pattern | Identical lines | Files | Extraction risk | Notes |
|---|---------|----------------|-------|----------------|-------|
| 1 | Harvester config validators | 36 (12×3 UCDP) | 5 | Safe | `page_size`, `max_retries`, `timeout` checks |
| 2 | `_tag_table()` | 34 | 2 | Safe | 100% copy-paste; zero domain variance |
| 3 | Viewpoint scaffolding | 35 | 4 | Moderate | Config-or-shortcut + provenance; tightly coupled to config classes |
| 4 | Compilation output writer | 30 | 2 | Safe | Only diff: pregridded adds 3 diagnostic fields to ledger dict |
| 5 | `_VIEWS_EPOCH_YEAR` | 2 | 3 (ghspop_v1, ghsbuilts_v1, pregridded imports correctly) | Safe | Trivial: replace private copies with import |
| 6 | Provenance recording | ~48 call sites | all layers | Moderate | Deferred — C-06 tracks this |
| 7 | Pipeline runners `--skip-to` | 80-120 | 3 | Moderate | Step index handling, timing, fallback validation |
| 8 | Harvest script wrappers | 200-250 | 7 | Moderate | argparse + timing + banner boilerplate |

Raster-specific functions confirmed identical copy-paste between `ghspop_v1.py` and `ghsbuilts_v1.py`:
- `_read_geotiff()`: 39 lines identical (pure I/O, no domain coupling)
- `_interpolate_temporal()` + `_interp_step()` + `_interp_linear()`: 103 lines identical (pure data transformation)
- `_aggregate_with_alignment()`: 74 lines each, **NOT identical** — ghspop has nodata masking (float32, `strip[(strip == nodata) | (strip < 0.0)] = 0.0`), ghsbuilts has no masking (uint32, no nodata sentinel). Domain-justified divergence — **do not extract**.

**Total confirmed-safe extraction candidates: ~340 lines across patterns 1-5 + raster functions. Total deferred: ~530 lines across patterns 3, 6-8 (moderate risk or larger refactor scope).**

**v1.2.21 extractions completed (2026-05-25):**
- Pattern #2 resolved: `_tag_table()` extracted to `datafactory_consolidation/tagging.py` (Task 6)
- Pattern #4 resolved: compilation output writer extracted to `datafactory_compilation/output.py` (Task 7)
- Pattern #5 resolved: `VIEWS_EPOCH_YEAR` moved to `datafactory_provenance/constants.py` (Task 3)
- Raster I/O resolved: `_read_geotiff()` extracted to `datafactory_viewpoint/raster_io.py` (Task 4)
- Temporal interpolation resolved: `_interpolate_temporal()`, `_interp_step()`, `_interp_linear()`, `VALID_TEMPORAL_INTERPOLATIONS` extracted to `datafactory_viewpoint/temporal.py` (Task 5)
- Remaining: patterns 1 (harvester config validators), 3 (viewpoint scaffolding), 6 (provenance recording), 7 (pipeline runners), 8 (harvest wrappers) deferred to next cycle.

**Note (2026-05-26, review-rr strategic):** V-Dem (9th source, 5th pipeline source) added — replicated harvest, viewpoint, compilation, pipeline runner, and harvest wrapper patterns. V-Dem viewpoint uses ISO3→pgid crosswalk (new pattern, not raster-based), so raster-specific extractions (patterns already done in v1.2.21) don't apply. Remaining unextracted patterns (1, 3, 7, 8) were each copied one more time. Total: 5 pipeline sources replicating 5 remaining patterns = 25 pattern copies.

**Note (2026-05-28, review-rr strategic curation):** C-44 merged into this entry. C-44 (harvest pipeline template) was a subset covering only the harvest layer; its 9 accumulated notes tracked each source addition. The harvest template gap is covered here as patterns #1 (harvester config validators) and #8 (harvest script wrappers). C-183 was previously merged into C-44, and now transitively merges here.

**Note (2026-05-30, expert code review C-164):** SHDI (10th source, 6th pipeline source) added — replicated all remaining unextracted patterns. Deep audit quantified actual pattern scope:
- Pattern #1: 10 config classes (not 5) with `__post_init__` validation: `ucdp_annual.py`, `ucdp_candidate.py`, `ucdp_dot9.py`, `acled.py`, `ghspop.py`, `ghsbuilts.py`, `priogrid_static.py`, `gaul_admin.py`, `vdem.py`, `shdi.py`. `timeout < 1` check appears in all 10.
- Pattern #3: 5 viewpoint builders (not 3-4): `ucdp_v1.py`, `acled_v1.py`, `ghspop_v1.py`, `ghsbuilts_v1.py`, `vdem_v1.py`. All share config-or-shortcut entry point + `append_ledger_entry` with `LEDGER_VERSION`/`DIGEST_SCHEME`.
- Pattern #7: 4 pipeline runners (not 3): `run_acled_pipeline.py`, `run_ghspop_pipeline.py`, `run_ghsbuilts_pipeline.py`, `run_vdem_pipeline.py`. All use `STEPS.index(args.skip_to)` + `if skip_idx < N` pattern. Total 1,093 lines.
- Pattern #8: 9 harvest scripts (not 7): `harvest_ucdp.py`, `harvest_acled.py`, `harvest_ghspop.py`, `harvest_ghsbuilts.py`, `harvest_priogrid.py`, `harvest_gaul.py`, `harvest_shapefile.py`, `harvest_vdem.py`, `harvest_shdi.py`. Total 1,185 lines of argparse + banner + timing boilerplate.
- Pattern #6: 87 provenance call sites in `/src` (47 `append_ledger_entry`, 16 `last_digest_for_version`, 10 `compute_content_digest`, 9 `compute_file_digest`, 5 other).

Total: 6 sources × 5 remaining patterns = 30 pattern copies, 8,537 lines in pattern-affected files.

Extraction risks identified (failure mode analysis):
- FM-1 (Pattern #1): Extracted validator could produce wrong field name in error message → mitigated by TDD (test error message includes field name).
- FM-2 (Pattern #8): Shared HarvestRunner could change exit codes → mitigated by characterization tests before extraction.
- FM-3 (Pattern #7): Shared PipelineRunner could change `--skip-to` precondition checking → mitigated by source-specific preconditions declared per pipeline.
- FM-4 (Pattern #3): Config-or-shortcut resolution varies (V-Dem accepts 2 shortcuts, others accept 1) → mitigated by per-config `@classmethod from_shortcuts()`.

Recommended extraction order (TDD): #1 (config validators, trivial, low risk) → #8 (harvest wrappers, moderate, characterize first) → #7 (pipeline runners, moderate) → #3 (viewpoint scaffolding, low risk but low payoff) → #6 (provenance, HIGH risk, DEFER to C-06).

**Note (2026-06-09, content-addressed skip investigation):** A 9th WET pattern identified: digest comparison logic ("compare current digest against recorded digest, decide whether to skip/gate/detect"). This pattern appears in 5 locations: (a) `assemble_grid.py:312-357` (assembly skip), (b) `export_zarr.py:96-119` (export skip), (c) `export_zarr.py:172-194` (export digest gate), (d) `generate_consumer_data.py:206-234` (consumer digest gate), (e) `health.py:208-310` (`check_export_freshness` drift detection). Each implements the same "load provenance JSON, extract digest key, compare against computed/stored digest" logic independently. When the skip feature ships, this should be factored into `datafactory_provenance` as a reusable function (e.g., `should_skip()` or `compare_digests()`) — aligns with C-261 (no skip provenance) and the broader pattern extraction plan.

**Source:** WET-before-DRY inventory audit after GHS-POP Phase 4 completion (2026-05-19), updated GHS-BUILT-S (2026-05-22), tech-debt-cleanup investigation (2026-05-24), v1.2.21 maintenance sprint (2026-05-25), expert code review C-164 (2026-05-30).

### ~~C-186: Shapefile harvester lacks outcome vocabulary~~ RESOLVED

Resolved 2026-05-31. Outcome vocabulary (`"outcome": "success"/"unchanged"/"failed"`) and failure recording added to shapefile harvester. ADR-032 updated to reflect resolution. Tests cover all three paths. See archive.

Cross-ref: C-164 (cross-layer WET debt), ADR-032.

### ~~C-223: Compilation pipeline allocates full grid in RAM~~ RESOLVED

Resolved 2026-06-24. Both `compile_pregridded()` (`pregridded_compilation.py:191`) and `compile_grid()` (`grid_compilation.py:257`) now use `np.lib.format.open_memmap()` instead of `np.full()`. Peak RSS stays ~200 MB regardless of feature count. ADR-037 documents the bounded-memory decision. WDI readiness falsification audit confirmed memmap is in place — the R&D plan (`rd_plan_bounded_memory_compilation.md`) has been executed. See archive.

Cross-ref: C-144 (compilation to_pydict), C-145 (viewpoint full store load), C-173 (server memory headroom), D-24 (hardware vs software — resolved: both).

### ~~C-247: Dual source of truth for GAUL name files~~ — Resolved 2026-06-19 (#211)

| Field | Value |
|-------|-------|
| ID | C-247 |
| Tier | 3 |
| Source | Pre-deployment behavioral change audit (2026-06-07) |
| Trigger | `harvest_gaul.py` and `generate_area_majority_gaul.py` both run in Step 1 of `refresh_pipeline.sh`, writing `gaul0_name.parquet`, `gaul1_name.parquet`, `gaul2_name.parquet`, `iso3_code.parquet` to the same directory with different spatial join methods |
| Location | `scripts/harvest_gaul.py` (centroid-in-polygon), `scripts/generate_area_majority_gaul.py` (area-majority), `scripts/refresh_pipeline.sh` Step 1 |

Both scripts write name Parquet files to `data/raw/gaul_admin/`. `harvest_gaul.py` uses centroid-in-polygon assignment; `generate_area_majority_gaul.py` uses area-majority (ADR-039). They disagree for ~9,481 coastal cells whose centroids fall in water. In `refresh_pipeline.sh`, `harvest_gaul.py` runs before `generate_area_majority_gaul.py`, so area-majority wins — but this ordering is fragile and undocumented. Whichever runs last wins. A developer running only `harvest_gaul.py` would silently revert the name files to centroid-based assignments.

Cross-ref: C-245 (resolved — name file gap), C-246 (untested production code path), ADR-039.

---

### ~~C-245: Name file gap — 9,481 recovered cells have codes but no country names~~ RESOLVED

Resolved 2026-06-06 (PR #135). `generate_area_majority_gaul.py` extended to produce 4 name Parquet files (`gaul0_name`, `gaul1_name`, `gaul2_name`, `iso3_code`) using OCP `dtype=pa.utf8()` parameter. `GAUL_VARIABLES` split into `GAUL_CODE_VARIABLES` + `GAUL_NAME_VARIABLES` (CRP). Name files regenerated on both server (via `refresh_pipeline.sh`) and dev machine (2026-06-11). The xfail on `test_name_file_row_count_matches_code_file` has been removed — test now passes.

Cross-ref: C-149 (resolved — the root cause this gap is a residual of), ADR-039.

---

### ~~C-282: V-Dem and SHDI bypass shared temporal module — ADR-014 Principle 5 claim false for 2 of 4 builders~~

ADR-014 Principle 5 states "The shared implementation lives in `datafactory_viewpoint.temporal`" and describes two strategies (`linear`, `step`). GHS-POP and GHS-BUILT-S route through this module. However, V-Dem (`vdem_v1.py:257-258`) and SHDI (`shdi_v1.py:225-226`) implement step-function temporal expansion inline via `np.repeat()`/`np.tile()` without importing from `temporal.py`. The shared module is used by only 2 of 4 builders that perform temporal expansion — ADR-014's characterization of it as THE shared implementation is misleading.

The inline implementations produce correct results. The risk is that a future contributor reads ADR-014, assumes all temporal logic flows through `temporal.py`, modifies that module (e.g., adding provenance metadata to interpolated values), and misses the two inline implementations. The fix is either: (a) refactor V-Dem/SHDI to use `temporal.py`'s `step` strategy, or (b) narrow ADR-014's claim to accurately describe which builders use the shared module.

| Field | Value |
|-------|-------|
| ID | C-282 |
| Tier | 3 — maintainability; ADR makes a false architectural claim affecting 2 of 6 viewpoint builders |
| Source | falsify (2026-06-13), probe P-1 |
| Trigger | New builder author reads ADR-014 P5, modifies only temporal.py, misses inline implementations in vdem_v1.py and shdi_v1.py |
| Location | `src/datafactory_viewpoint/builders/vdem_v1.py:257-258`, `src/datafactory_viewpoint/builders/shdi_v1.py:225-226`, `docs/ADRs/014_viewpoints_as_derived_views.md` (Principle 5, line 86) |

Cross-ref: C-164 (WET debt — temporal.py extraction completed v1.2.21 but V-Dem/SHDI predate it), C-283 (V-Dem cross-source dep — same builder, different issue).

---

### ~~C-283: V-Dem viewpoint reads GAUL admin crosswalk — cross-source dependency violates ADR-014 Principle 6~~

ADR-014 Principle 6 states "A viewpoint builder must be a pure function of its own source data plus configuration. It must not read from other sources' consolidated stores, viewpoints, or compiled outputs." The V-Dem builder's `VdemViewpointConfig` has a default `crosswalk_path = "data/raw/gaul_admin/iso3_code.parquet"` (line 82) — a file produced by the GAUL admin harvester, stored in GAUL admin's data directory. This is a cross-source dependency: V-Dem's viewpoint reads another source's raw data.

The dependency is architecturally necessary — V-Dem publishes country-year data, so mapping to PRIO-GRID cells requires an ISO3→pgid crosswalk. By contrast, SHDI's builder uses `data/raw/shdi/gdl_to_pgid.parquet`, a crosswalk produced by its own harvester. The V-Dem builder could be fixed by: (a) having the V-Dem harvester produce its own ISO3→pgid crosswalk, or (b) moving the crosswalk to `datafactory_priogrid` as a shared spatial utility (not owned by any source), or (c) acknowledging the dependency in ADR-014 as an accepted exception. Option (c) is the simplest but weakens the principle.

| Field | Value |
|-------|-------|
| ID | C-283 |
| Tier | 3 — structural coupling; violates a newly-formalized constitutional principle |
| Source | falsify (2026-06-13), probe P-6 |
| Trigger | GAUL admin data regenerated (e.g., area-majority update changes iso3_code.parquet) without triggering V-Dem viewpoint rebuild |
| Location | `src/datafactory_viewpoint/builders/vdem_v1.py:82` (crosswalk_path default), `docs/ADRs/014_viewpoints_as_derived_views.md` (Principle 6, lines 88-94) |

Cross-ref: C-282 (V-Dem temporal bypass — same builder, different issue), C-247 (dual GAUL source of truth — same data directory).

---

### ~~C-264: Factory/models partition boundary drift — 4 alignment tests failing~~

`datafactory_query.defaults.PARTITIONS` defined calibration/validation boundaries that no longer match the partition configs in `views-models`. Factory had `calibration: train=(121,444), test=(445,492), validation: train=(121,492), test=(493,540)`. Models updated to `calibration: train=(121,456), test=(457,504), validation: train=(121,504), test=(505,552)`. All 5 integrated models (`bright_starship`, `heavy_freighter`, `heavy_strider`, `light_strider`, `shining_codex`) agreed on the new boundaries, but the factory wasn't updated. Four `TestPartitionAlignment` tests failed as a result.

| Field | Value |
|-------|-------|
| Trigger | Factory partitions updated without coordinating with views-models, or model training uses mismatched partitions |
| ID | C-264 |
| Tier | 3 |
| Source | Deploy-readiness falsification (2026-06-10) |
| Location | `src/datafactory_query/defaults.py:92-94` (`_partitions_raw`), `tests/test_structural_invariants.py:121-205` (`TestPartitionAlignment`) |

**Update (2026-06-10):** Test review found `PARTITIONS` boundaries in `defaults.py` have no unit tests for correctness or immutability. No test verifies `start < end` for all partition ranges, no test guards against silent mutation. Location: `src/datafactory_query/defaults.py:92-94`.

Cross-ref: C-29 (no end-to-end integration test).

---

### ~~C-268: gaul_admin.py has zero test coverage — 7-feature spatial join untested~~ — Resolved 2026-06-19 (#211)

`gaul_admin.py` produces 7 features (`gaul0_code`, `gaul1_code`, `gaul2_code`, `gaul0_name`, `gaul1_name`, `gaul2_name`, `iso3_code`) via area-majority spatial join with L1/L2 fallback logic. No dedicated test file exists. The CIC `gaul_admin.md` states "not yet written" in its test alignment section. The `_compute_cell_polygon_map()` function has 15 tests (C-246 resolved), but the higher-level pipeline functions — GAUL data loading, admin hierarchy parsing, fallback when L2 is unavailable — have zero tests.

| Field | Value |
|-------|-------|
| Trigger | Modification to GAUL admin hierarchy parsing, or new GAUL data release with different field names |
| ID | C-268 |
| Tier | 3 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_harvester/sources/gaul_admin.py` (entire module), missing test file |

Cross-ref: C-246 (resolved — `_compute_cell_polygon_map` tested), C-247 (dual source of truth for GAUL name files), C-164 (WET debt — GAUL is pattern instance).

---

### ~~C-269: event_validation.py validate_events() and compare_snapshots() — zero direct tests~~

`event_validation.py` exports `validate_events()` (field presence, type checks, dedup) and `compare_snapshots()` (revision detection across harvests). Neither function has direct tests. `compare_snapshots()` is the only mechanism to detect upstream data mutations between harvest runs — if it silently fails to detect a revision, the consolidated store misses an update. `validate_events()` is called in the consolidation path but never tested for boundary conditions: empty events, missing required fields, duplicate event IDs. C-159 was demoted with the claim "both compare_snapshots and archive_snapshot are tested in their own modules" — the test review contradicts this for `compare_snapshots()`.

| Field | Value |
|-------|-------|
| Trigger | UCDP or ACLED revises a past event and `compare_snapshots()` fails to detect it, or a new field is added that `validate_events()` should reject |
| ID | C-269 |
| Tier | 3 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_consolidation/event_validation.py` (`validate_events`, `compare_snapshots`), no dedicated test file |

Cross-ref: C-159 (demoted — demotion rationale partially contradicted), C-257 (no input validation at system boundary).

**Resolved 2026-06-18:** 8 characterization tests added in `tests/test_event_validation.py` (#196). Covers validate_events (valid input, missing field, null column, empty list) and compare_snapshots (identical, added, removed, revised).

---

### ~~C-270: _rotate_ledger() has zero tests — provenance rotation bug could destroy audit history~~

`_rotate_ledger()` in `ledger_ops.py` rotates the provenance JSONL ledger when it exceeds 10MB. The function creates a timestamped backup and starts a new ledger file. Zero tests exist for this function. A bug in rotation (e.g., truncating before backup completes, wrong backup path, race with concurrent append) could silently destroy the audit trail — the append-only property of the provenance ledger (DDIA Ch.1 p.10, Ch.11 p.457) would be violated. The function is only triggered at scale (production ledgers approaching 10MB), so any bug would first manifest in production.

| Field | Value |
|-------|-------|
| Trigger | Production ledger exceeds 10MB and rotation fires for the first time |
| ID | C-270 |
| Tier | 3 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_provenance/ledger_ops.py` (`_rotate_ledger`), no test coverage |

Cross-ref: C-46 (no ledger write idempotency), C-136 (non-UTF8 ledger crash).

**Resolved 2026-06-18:** 5 characterization tests added in `tests/test_provenance.py::TestRotateLedgerCharacterization` (#197). Pins .1 creation, backup shifting, .10 cap, below-threshold no-op, and original file absence after rotation.

---

### ~~C-286: UCDP as implicit temporal anchor — source data silently dropped if UCDP contracts~~ — RESOLVED 2026-06-26

Assembly (`assemble_grid.py`) aligns all sources to UCDP's `time_steps.npy`. Each source's temporal offset is computed as the position where its start date matches in the UCDP timeline. If UCDP's temporal range contracts (e.g., early years removed in a future UCDP release), data from other sources that extends beyond UCDP's range is silently dropped — the offset computation produces an out-of-bounds index and the assertion `source_end <= assembled_length` fails. Conversely, if UCDP extends, other sources are zero-filled. The dependency on UCDP as the temporal anchor is implicit in the assembly script's control flow, not declared in any ADR or config.

| Field | Value |
|-------|-------|
| ID | C-286 |
| Tier | 3 — architectural coupling; UCDP temporal range contraction would break assembly for all sources with no recovery path except reverting UCDP |
| Source | repo-assimilation (2026-06-14), Phase 3 |
| Trigger | UCDP temporal range shortened (early years removed) or a new source with a start date before UCDP's start (1989) |
| Location | `scripts/assemble_grid.py`, `docs/ADRs/047_assembly_temporal_anchor.md` |

**Resolved:** Assembly temporal alignment hardening sprint (#266, 2026-06-26). ADR-047 explicitly declares UCDP as the temporal anchor. The dependency is now documented with rules for future sources: all sources must fit within UCDP's timeline; temporal backbone extension is a manual operator decision requiring an ADR amendment. `first_valid_*_month_id` provenance fields record each source's leading edge; `load_dataset()` warns consumers about pre-coverage zero-fill.

Cross-ref: C-156 (ACLED zero-fill before 2020 — also resolved in this sprint).

---

### ~~C-290: datafactory_query has 25% module coverage — consumer API mostly untested~~ — RESOLVED 2026-06-24

The `datafactory_query` package is the primary consumer-facing interface (`load_dataset()`), yet only 1 of 4 modules (`temporal.py`) has a dedicated test file. The untested modules: `dataset.py` (the `load_dataset()` entry point and `_load_grid_from_zarr` backend), `defaults.py` (`DEFAULT_REMOTE`, `get_last_valid_month_id`), `regions.py` (`list_regions`, `load_region_pgids`). While `test_query.py` (18 tests) exercises some `dataset.py` paths via integration, it only covers the npy backend — the remote zarr code path has zero happy-path tests (see C-116 note). Consumer-facing edge cases are untested: zero-grid response, stale grid without warning, empty feature list, unknown region name. This is the layer that downstream forecasting models directly depend on.

| Field | Value |
|-------|-------|
| ID | C-290 |
| Tier | 3 — consumer-facing API; failures affect model training; currently works but unguarded against regression |
| Source | test-review (2026-06-14), Leveson perspective |
| Trigger | Developer changes `load_dataset()`, region subsetting, or zarr backend without regression tests |
| Location | `src/datafactory_query/dataset.py`, `src/datafactory_query/defaults.py`, `src/datafactory_query/regions.py` |
| Resolution | Resolved 2026-06-24 (#237). 12 tests added: RemoteConfig (4 Green, 2 Beige), PARTITIONS (4 Green), country_month (2 Green). RemoteConfig frozen enforcement, URL construction, and PARTITIONS immutability now covered. |

Cross-ref: C-116 (remote zarr no retry + zero test coverage note), C-117 (remote zarr downloads all cells).

**Update (2026-06-24, test-review v1.4.0):** RemoteConfig (`defaults.py:25`) is a CIC-governed frozen dataclass with 6 guarantees (frozen, valid scheme, valid host, non-negative port, zarr_url computation, timeout > 0) and zero test coverage. The CIC Section 10 references `tests/test_defaults.py` which does not exist. This is the most specific untested class in the query module — any change to its defaults or validation will be undetected.

---

### ~~C-291: Conservation assertions use np.nansum() — NaN exclusion weakens partition invariant~~ — RESOLVED

**Resolved 2026-06-24:** `assert_no_unexpected_nan()` added to `_conservation.py` — raises `RuntimeError` before nansum if any extensive feature column contains NaN. Called for all three partitions (all, land, excluded) inside `assert_cm_conservation()`. NaN in intensive features (SHDI, V-Dem) is still allowed. 5 tests: `test_nan_in_extensive_feature_raises`, `test_nan_in_non_extensive_feature_does_not_raise`, `test_nan_detected_in_all_partition`, `test_clean_data_passes`, `test_empty_array_passes`. Sprint epic #258, issue #260.

| Field | Value |
|-------|-------|
| ID | C-291 |
| Tier | ~~3~~ → Resolved |
| Source | repo-assimilation (2026-06-16) |
| Trigger | ~~NaN-type corruption introduced during grid-to-country-month aggregation~~ Resolved. |
| Location | `src/datafactory_adapters/_conservation.py` (`assert_no_unexpected_nan`, `assert_cm_conservation`) |

`assert_cm_conservation()` verifies the partition invariant `grid_total ≈ land_total + excluded_total` using `np.nansum()` and `np.allclose()`. The `np.nansum()` call silently excludes NaN values from all three sums. If a bug during aggregation converts valid counts to NaN (e.g., division by zero in area-weighted aggregation), the conservation check still passes because NaN is excluded from both sides of the comparison. The check verifies that the partition holds for non-NaN values, but does not verify that the NaN pattern is consistent across the partition or that NaN count hasn't increased relative to the input grid. The placement conservation at the compilation boundary (`assert_placement_conservation`) uses exact integer equality and would catch most corruption — this gap is specifically in the downstream aggregation path. Currently mitigated by: (1) compilation-level conservation catches most corruption vectors, (2) NaN is expected in the grid (SHDI 10.1% of land cells, V-Dem 9 dropped countries), so `np.nansum()` is the correct function choice. The gap is that NaN-producing bugs in the aggregation code itself would pass this check.

See also ~~C-241~~ (resolved — intensive feature warning), ~~C-249~~ (resolved — float64 regression guard). Part of causal cluster: **Count conservation**.

---

### ~~C-292: Fuvahmulah-signature cells unverified — distance discriminator proven unreliable~~ — Resolved 2026-06-19 (#211)

| Field | Value |
|-------|-------|
| ID | C-292 |
| Tier | 3 — verification gap; 3 cells classified by a discriminator proven wrong at the same distance band |
| Source | falsification audit round 3 (test_falsification_round3.py) |
| Trigger | Next GAUL release or excluded-cell reclassification exercise relies on distance discriminator output without knowing it was never revalidated after Fuvahmulah |
| Location | `reports/investigation_gaul_excluded_cells/excluded_cell_classification.json`, `tests/test_falsification_round3.py:56-85` |

Three PRIO-GRID cells (pgids 118753, 129574, 132525) are classified as `coastal_resolution_gap` based on a distance-to-nearest-polygon discriminator. Round 2 of the falsification audit proved this discriminator unreliable: Fuvahmulah (Maldives) sat at 0.33° from its nearest polygon — inside the same distance band as all 66 coastal_resolution_gap cells — yet was a genuine source defect (the correct GAUL unit was absent). The fix corrected Fuvahmulah by hand but never revalidated the other cells with a reliable method. The 3 flagged cells share Fuvahmulah's signature (island-nation or "Administrative Unit Not Available" nearest admin2) and carry no recorded per-cell verification that their correct GAUL unit actually exists in the dataset. Their classification rationale is asserted, not established.

**To resolve:** For each of pgids 118753, 129574, 132525, verify by polygon presence (not distance proxy) that the correct GAUL admin unit exists. Record the result as `unit_verified: true` or `verification_note` in the classification JSON. The failing test (`test_fuvahmulah_signature_cells_carry_recorded_unit_verification`) passes once all 3 entries carry verification.

Cross-ref: ~~C-246~~ (resolved — cell polygon map tests), ~~C-248~~ (resolved — tiebreaker bug). Part of causal cluster: **GAUL data integrity**.

---

### ~~C-296: grid_from_feature_frame has zero tests — 89-line consumer-facing adapter untested~~ — RESOLVED 2026-06-24

`grid_from_feature_frame.py` exports `feature_frame_to_grid()`, the inverse of `grid_to_feature_frame()`. It reconstructs a [T, H, W, F] grid from a FeatureFrame using pgids lookup. The module has 89 lines, a single public function, and zero test coverage — no test file references it. A regression here silently produces wrong grid reconstructions for any consumer using the round-trip path. The forward path (`grid_to_feature_frame`) has 4 Green tests + 6 Beige tests + 2 Red tests in `test_adapters.py`, but the inverse has none.

| Field | Value |
|-------|-------|
| ID | C-296 |
| Tier | 3 — consumer-facing adapter; shape mismatch would likely raise (not silent), but value-mapping errors would silently corrupt |
| Source | test-review v1.4.0 (2026-06-24), Feathers perspective |
| Trigger | Developer modifies inverse adapter or consumer calls `feature_frame_to_grid()` without regression coverage |
| Location | `src/datafactory_adapters/grid_from_feature_frame.py` |
| Resolution | Resolved 2026-06-24 (#236). 8 standalone tests added: 3 Green (reconstruction, dtype, shape), 3 Beige (unmapped pgids, skipped unit_ids, single row), 2 Red (NaN propagation, duplicate pgid last-write-wins). |

Cross-ref: C-290 (query module coverage gap — same consumer-facing theme).

---

### ~~C-297: Assembly has zero Red team tests — partial-flag footgun unguarded~~ — RESOLVED 2026-06-24

`test_assemble.py` has 33 tests across 9 classes but zero Red team tests (0% ADR-005 compliance). Assembly is the most critical integration point — it combines all sources into the final grid. The most dangerous untested scenario: running `assemble_grid.py` with a subset of source flags (e.g., omitting `--vdem-grid`) silently produces a grid with fewer features (42 instead of 79) that passes all shape checks. This footgun is documented in `docs/guides/server_operations.md:142-145` but no test catches it. Other untested adversarial scenarios: misaligned temporal ranges from different sources, corrupted provenance.json during skip-if-unchanged, and concurrent assembly + export.

| Field | Value |
|-------|-------|
| ID | C-297 |
| Tier | 3 — operator error produces silently incomplete grid; documented but unguarded; downstream feature-count check would catch for aware consumers |
| Source | test-review v1.4.0 (2026-06-24), Nygard + Leveson perspectives |
| Trigger | Operator runs `assemble_grid.py` with subset of source flags, producing a grid with fewer features than expected |
| Location | `scripts/assemble_grid.py`, `tests/test_assemble.py` |
| Resolution | Resolved 2026-06-24 (#235). 8 Red/Beige tests added: partial-sources fewer features, NaN propagation, feature-names length, correct offset, corrupted provenance (Red); missing files, start outside timeline, extends beyond timeline (Beige). |

Cross-ref: C-146 (assembly in script — testability), C-287 (channel order positional — assembly fragility), C-280 (skip.py corrupted provenance.json untested).

### ~~C-298: Integration guide missing tabular non-event source path~~ — RESOLVED 2026-06-24

| Field | Value |
|-------|-------|
| ID | C-298 |
| Tier | 4 — documentation drift, single-developer scope, no correctness impact |
| Source | WDI readiness falsification audit (2026-06-24) |
| Trigger | Developer follows the integration guide for a tabular non-event source (WDI) and cannot find the correct layer path pattern |
| Location | `docs/guides/data_source_integration_guide.md` lines 20–25 (layer path table) |
| Resolution | Resolved 2026-06-24. Layer path table updated with 4th path type (Tabular, non-event: V-Dem, SHDI, WDI). Intro updated to reflect 8 source integrations. Dimension naming corrected from `[T, H, W, F]` to `[T, H, W, C]`. |

Layer path table lists 3 path types (Event data, Raster data, Static data) but V-Dem and SHDI added a 4th type: tabular, non-event sources that skip consolidation and go Harvest → Viewpoint → Compilation → Assembly. A WDI developer following the guide would not find their pattern type in the table.

Cross-ref: C-164 (cross-layer WET debt).

---

### C-301: Conservation no-op for direct callers without `feature_agg_types` — ADR-040 regression

Before epic #290 (ADR-048), `_EXTENSIVE_PREFIXES = ("ged_", "acled_")` provided a built-in default for `_extensive_indices()`, so conservation checking always ran — even for callers that didn't explicitly opt in. After the epic deleted `_EXTENSIVE_PREFIXES` and replaced it with declared `feature_agg_types`, calling `_extensive_indices(feature_names, None)` returns `[]`, making `assert_cm_conservation()` a complete no-op. The production path through `load_dataset()` passes `feature_agg_types` from provenance, so the invariant holds there. But any direct caller of `grid_to_country_month()` without `feature_agg_types` silently loses all conservation checking — NaN corruption and aggregation bugs would go undetected.

| Field | Value |
|-------|-------|
| ID | C-301 |
| Tier | 3 — structural regression in safety invariant (ADR-040); direct callers silently lose conservation; currently no direct callers outside `load_dataset()`, but the API accepts `None` without warning |
| Source | Falsification audit, epic #290 (2026-06-28), probe P6 |
| Trigger | New consumer calls `grid_to_country_month()` directly without passing `feature_agg_types` — conservation checking silently disabled, NaN or aggregation bugs go undetected |
| Location | `src/datafactory_adapters/_conservation.py:_extensive_indices` (returns `[]` when `feature_agg_types=None`), `src/datafactory_adapters/grid_to_country_month.py` (passes `None` through to conservation) |

Cross-ref: ~~C-241~~ (resolved — intensive feature gap, same function, different invariant), ~~C-291~~ (resolved — NaN pre-check in conservation), ADR-040, ADR-048.

---

## Tier 4 — Accept or Defer

### C-146: Assembly logic lives in script, not importable package — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-146 |
| Tier | 4 (recalibrated from 3 during strategic curation 2026-05-28) |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When assembly orchestration needs refactoring, or a second assembly path is needed (e.g., different feature sets for different consumers) |
| Location | `scripts/assemble_grid.py` (~350 LOC procedural, not in any `src/datafactory_*` package) |

Every other layer exposes its core logic as an importable function: `consolidate_ucdp()`, `build_ucdp_v1()`, `compile_grid()`, `load_dataset()`. Assembly is the exception — its spatial join, static feature broadcast, and admin boundary merge logic lives entirely in `assemble_grid.py`'s `main()`. `test_assemble.py` tests sub-components (spatial join helper, GID lookup) but cannot import and test the orchestration function directly. Extracting an `assemble_grid()` function into `datafactory_compilation` or a new `datafactory_assembly` package would make the logic importable and directly testable.

**Note (2026-05-24, repo-assimilation v1.2.20):** At 4 sources / 831 lines, the script grows linearly per source (~100-150 lines per source for loading, slicing, and stacking). At source #8-10, `assemble_grid.py` will exceed 1,200 lines of procedural code with no importable interface. The linear growth compounds the testability concern: each new source adds code paths that cannot be unit-tested in isolation.

**Note (2026-05-24, tech-debt-cleanup investigation):** The linear growth mechanism is now identified: lines 240-441 contain 3 source load-validate-align blocks (ACLED 59 lines, GHS-POP 66 lines, GHS-BUILT-S 77 lines = 202 lines total) that are **structurally identical** with only variable-name substitution. Each block: load grid.npy + feature_names.json + time_steps.npy → assert existence → assert_grid_shape → find temporal offset → validate bounds → print diagnostics. A parameterized `_load_source_grid(name, grid_dir, time_steps)` function (~40 lines) would replace all 3 blocks and handle the 5th source without new code. Extraction is safe (no memory or behavioral change — same np.load with mmap_mode="r"), but the function must remain in the script until C-146's testability concern is also addressed (extraction to importable package).

See also C-29 (no end-to-end integration test), C-164 (cross-layer WET debt).

### ~~C-121: Phase 6.4 (SSH IP restriction) is documented but unexecuted~~ — DEMOTED
Phase 6.4 of `hetzner_deployment_guide.md` documents SSH IP restriction via Hetzner Cloud Firewall or ufw, but has never been executed end-to-end. C-87 surfaced the same pattern: Phase 6.3 was documented in March but only executed today (2026-04-10), revealing a missing `passwd` step that locked the new user out of `sudo`. The fix took 30 minutes; the bug was in the documentation since v1.0. **Lesson: untested documentation is broken documentation.** Phase 6.4 should be audited and ideally dry-run before the first real execution. **Trigger: before executing Phase 6.4 (which itself is blocked on PRIO IT CIDRs).** Resolution: walk through Phase 6.4 line-by-line, verify each command, add missing edge cases, then execute on the server.
**Source:** Lessons from C-87 incident, 2026-04-10

### ~~C-37: `date_prec=5` semantics hardcoded~~ — Resolved 2026-06-19 (#212, DGP validation fail-loud on unknown date_prec)
`temporal_distribution.py:22` defines `_SUMMARY_DATE_PREC = 5`. If UCDP changes `date_prec` semantics, temporal distribution silently produces wrong results. No UCDP documentation exists for `date_prec` values. **Trigger: UCDP publishes a codebook or changes observed empirically.**
**Source:** Repo assimilation

### ~~C-36: UCDP API contract has no schema versioning~~ — Resolved 2026-06-19 (#209, ADR-046 documents fail-loud + fingerprint defense)
API envelope format and 13 `REQUIRED_FIELDS` are hardcoded in `ucdp_annual.py:43-72,176-190`. No schema version negotiation. Fail-loud catches field removals; field additions are harmless (silently preserved). Kleppmann (Ch.4 pp.131-136) notes that service providers often cannot control client upgrades, making forward compatibility essential — our fail-loud on missing fields is the correct strategy, but we have no mechanism to detect silent semantic changes in existing fields. **Trigger: UCDP announces API v2 or breaking change.**
**Source:** Repo assimilation. DDIA Ch.4 pp.112, 131-136.

### ~~C-45: No Parquet schema evolution strategy~~ — Resolved 2026-06-19 (#209, ADR-046 documents promote_options + fingerprint approach)
`pa.concat_tables(promote_options="default")` in `ucdp.py:439-441` silently adds columns when UCDP adds fields. Removed fields leave nulls in new records. No schema registry. Kleppmann (Ch.4 pp.112-127) treats schema evolution as essential for long-lived data: backward compatibility (new code reads old data) and forward compatibility (old code reads new data) must both be maintained. Our `promote_options="default"` handles column additions (backward compat) but not removals or renames. Ch.4 p.125 recommends a schema versioning database; Ch.4 p.131 notes archival storage should re-encode using the latest schema. **Trigger: UCDP removes a field or renames a column.**
**Source:** Kleppmann (expert review 6). DDIA Ch.4 pp.112-127, 131.
**Update (2026-06-10):** Test review found UCDP consolidation has no schema drift test and no corrupted Parquet test — ACLED has both (`test_acled_consolidation.py::TestSchemaEvolution`, `TestCorruptedParquet`). This is a specific instance of C-45: when UCDP does change schema, no test detects the regression. Location: `src/datafactory_consolidation/ucdp.py`, missing test in `tests/test_consolidation.py`.

### C-46: No ledger write idempotency — [DEFER]
`append_ledger_entry()` has no dedup key. Process crash after append but before caller return causes duplicate on retry. Ledger readers tolerate duplicates. Kleppmann (Ch.12 pp.516-518) argues exactly-once semantics require idempotence via operation identifiers — each write carries a unique ID; consumers deduplicate on read. Ch.7 p.231 warns that retrying a successful-but-unacknowledged write without dedup causes silent duplication. Recommended approach: add an `operation_id` field (e.g., content digest of the entry) to each ledger record. **Trigger: Before monitoring dashboard or external audit tool reads provenance JSONL directly (trigger rewritten during review-rr 2026-06-19).**
**Source:** Kleppmann (expert review 6). DDIA Ch.7 p.231, Ch.12 pp.516-518.

### C-29: No end-to-end integration test — [DEFER]
Partially addressed by `test_integration.py` (100 events, realistic pipeline). Full-scale end-to-end with all 9 sources untested. **Trigger: Before WDI integration (10th source) or multi-target deployment (trigger rewritten during review-rr 2026-06-19).**
**Note (2026-04-04):** Trigger condition met — server in production at 204.168.219.108. Accepted at v1.0 scope: integration test covers the critical harvest→compile path, `verify_remote.py` validates the deployed output (10/10 checks). Reassess before V-Dem.
**Update (2026-04-26):** Test review identified specific gap: no harvest→consolidation integration test. `test_integration.py` tests the full pipeline but with synthetic events. No test verifies that actual UCDP Parquet output (column names, types, date format) is consumed correctly by `consolidate_ucdp()`. The stale-zarr incident showed that harvester changes (page_size, assertion thresholds) can produce subtly different output that breaks downstream.
**Update (2026-05-05):** ACLED compilation test review identified same gap for ACLED pipeline: no integration test connecting harvest→consolidate→viewpoint→compile. No test verifies viewpoint→compilation Parquet schema compatibility (that viewpoint output columns match what `compile_grid` expects via `date_field`, `lat_field`, `lon_field`, and filter fields). ACLED pipeline has the same structural risk as UCDP.
**Update (2026-06-10):** Test review found pipeline consistency tests (`test_pipeline_consistency.py`) are all green-only and consumer-gated. No beige/red tests verify boundary conditions at layer transitions (e.g., empty viewpoint output → compiler, malformed viewpoint Parquet → compiler). These gaps compound the existing e2e gap.
**Source:** Repo assimilation, Feathers, Test review 2026-04-26, ACLED compilation test review 2026-05-05, test-review 2026-06-10

### C-70: No circuit breaker for UCDP API — [DEFER]
After `max_retries` exhaustion, harvest fails immediately. If UCDP API is down for hours, every harvest attempt exhausts retries. No "open circuit" to fail fast on known-dead endpoints. Kleppmann (Ch.7 p.231) warns that retrying overload "will make the problem worse, not better" and recommends exponential backoff with distinct handling for overload vs transient errors. Ch.8 pp.281-283 discusses timeout-based fault detection and network congestion amplification. **Trigger: implement before multi-operator or automated deployment.**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 pp.281-283.

### C-72: HTTP 429 not distinguished from 500 — [DEFER]
Rate-limit responses get the same retry treatment as server errors. No `Retry-After` header parsing. `request_with_retry` fails fast on all 4xx (no retry), meaning a 429 rate-limit terminates the harvest immediately. Kleppmann (Ch.7 p.231) explicitly argues "it is only worth retrying after transient errors (e.g., deadlock, network interruption); after a permanent error, a retry would be pointless" and that overload errors need distinct handling. Ch.8 p.281 notes short timeouts risk declaring healthy services dead during load spikes. **Trigger: if UCDP or ACLED starts returning 429s during multi-page harvest (not observed to date). Impact is higher for ACLED because multi-page pagination can be long-running and all in-memory events are lost on failure.**
**Source:** Nygard (expert review #4). DDIA Ch.7 p.231, Ch.8 p.281. Updated: ACLED test review 2026-05-03.
**Location:** `src/datafactory_http/retry.py` (4xx fail-fast logic), `src/datafactory_harvester/sources/acled.py:fetch_paginated()`.

### ~~C-74: CompilationConfig leaks strategy vocabulary~~ DEMOTED
Demoted to tech-debt backlog 2026-06-06 (review-rr strategic curation). Naming/API ergonomics concern with no correctness impact. Single-developer project. Re-register if onboarding new developers.
**Source:** Ousterhout (expert review #4)

### ~~C-78: `_place_events` hard to test in isolation~~ DEMOTED
Demoted to tech-debt backlog 2026-06-06 (review-rr strategic curation). Test ergonomics concern; compilation tests run well under 5s. No correctness impact. Re-register if compilation tests exceed 5s.
**Source:** Feathers (expert review #4), ADR-031 compliance review (2026-05-21). Cross-ref: C-144.

### ~~C-79: Compilation/consolidation require real Parquet I/O in tests — [DEFER]~~
`compile_grid()` and `consolidate_ucdp()` always read from disk. No seam to inject mock reader. Tests create actual Parquet files. **Trigger: add `read_table_fn` parameter when test suite exceeds 30 seconds.**
**Source:** Feathers (expert review #4)

### ~~C-115: Summary detection threshold (>= vs >) is architectural~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Threshold is documented in ADR-023 and matches VIEWSER. No evidence of UCDP or VIEWSER changing this. Re-register if threshold changes.
**Source:** Parity investigation 2026-04-08, notebook archaeology (GED_loader{0,1,2}.ipynb).

### C-116: No retry on remote zarr network failures — [DEFER]
`_load_grid_from_zarr` in `dataset.py` opens a remote zarr store via xarray/fsspec/aiohttp. Transient network errors (DNS timeout, TCP reset, server restart) fail immediately — no retry, no backoff. `datafactory_http.retry.request_with_retry()` exists but is designed for `requests`-based harvester calls, not the xarray/fsspec path. For consumers, a transient failure at 2am during automated training means a full pipeline retry. **Trigger: consumer reports intermittent failures loading remote data.** Cross-ref: C-70 (circuit breaker, harvester path).
**Source:** Expert review #5 (M12 investigation), Nygard perspective, 2026-04-08.
**Update (2026-06-14, repo-assimilation):** The entire remote zarr code path has zero test coverage — `test_query.py` (18 tests) exercises only the npy backend. Not just edge cases; the happy path through `_load_grid_from_zarr` is also untested.

### C-117: Remote zarr downloads all spatial cells before region filter — [DEFER]
`_load_grid_from_zarr` applies temporal and feature subsetting lazily (xarray isel/variable selection), but spatial subsetting (region → pgid set) happens AFTER full grid materialization in `load_dataset`. For remote stores, this means downloading all 259,200 cells even when only ~13,000 are needed (e.g., Africa). The spatial dimension is 360x720 per time step per feature — less impactful than temporal (which IS subsetted), but still ~20x more data than needed for typical region queries. xarray does not support efficient irregular spatial selection on chunked stores without rechunking. **Trigger: consumer queries a single country over a slow connection and complains about latency.**
**Source:** Expert review #5 (M12 investigation), Kleppmann perspective, 2026-04-08.

### C-97: Basic auth + Caddy scalability ceiling at ~30-50 users — [DEFER]
Caddy's `basic_auth` stores username/bcrypt-hash pairs in a flat Caddyfile. No audit trail (who accessed what, when), no per-user rate limiting, no credential rotation, no MFA. Acceptable for a small research team (5-20 users). Breaks down at 30-50 users when credential management, audit requirements, and revocation coordination become operational burdens. Migration path: Caddy `forward-auth` directive + oauth2-proxy with institutional SSO (PRIO/Uppsala). **Trigger: before consumer count exceeds 30, or before institutional audit/compliance requirements emerge.**
**Source:** Falsification audit 2026-04-01 (F2)

### ~~C-135: No runtime type validation for zarr `.zattrs` values~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Only risk vector is manual server-side editing of `.zattrs`, which is unlikely. Our code writes correct types. Re-register if external consumers can write attrs.
**Source:** Tech-debt-cleanup audit (2026-04-22). Cross-ref: C-130 (zero-padding metadata).

### ~~C-136: `read_last_entries()` crashes on non-UTF8 ledger files~~ DEMOTED
Demoted to tech-debt backlog 2026-06-16 (review-rr strategic curation). Mechanical fix (add encoding guard), single-file scope, perpetual trigger, loud failure (crash, not silent corruption). Re-register if ledger files are exposed to external writers.
**Source:** Test review gap implementation (2026-04-22). Cross-ref: C-131, C-132 (operational monitoring).

### C-147: No pipeline orchestrator in repository — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-147 |
| Tier | 4 |
| Source | repo-assimilation (2026-04-30) |
| Trigger | When a new operator runs the pipeline for the first time without reading documentation, or when a 2nd deployment target is set up |
| Location | `scripts/` directory (19 scripts, no ordering definition) |

The pipeline is executed via individual scripts called in sequence: `harvest_ucdp.py` → `consolidate_ucdp.py` → `build_viewpoint.py` → `compile_grid.py` → `assemble_grid.py` → `export_zarr.py`. No Makefile, DAG definition, or workflow file in the repository defines or enforces this order. Correct sequencing depends on operator knowledge or reading CLAUDE.md. Each script validates its inputs exist (raises `FileNotFoundError`), so running out of order produces a clear error rather than silent corruption. `check_health.py` detects staleness after the fact. The server deployment uses cron under `views-deploy` (single `refresh_pipeline.sh` script). Currently mitigated by fail-loud input validation and single-operator deployment.

See also C-131 (no cron monitoring), C-29 (no e2e integration test).

### ~~C-148: Hardcoded Hetzner server IP in `defaults.py`~~ DEMOTED
Demoted to tech-debt backlog 2026-06-16 (review-rr strategic curation). Mechanical fix (extract to env var), single-file scope, perpetual, Tier 4. Single constant, trivial to update on server migration. Re-register if multi-server deployment is planned.
**Source:** repo-assimilation (2026-04-30).

### C-154: ACLED_FEATURES config duplicated between script and tests — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-154 |
| Tier | 4 |
| Source | ACLED compilation test review (2026-05-05) |
| Trigger | Developer changes an event_type filter value in `scripts/compile_acled.py` but not in the test fixture `ACLED_FEATURES` |
| Location | `scripts/compile_acled.py` (lines 97-125), `tests/test_acled_compilation.py` (lines 29-59) |

The `ACLED_FEATURES` tuple in `tests/test_acled_compilation.py` is a copy-paste of the feature configuration in `scripts/compile_acled.py`. They are not shared — the script is not importable as a module (it uses `if __name__ == "__main__"` with `sys.exit(main())`). If a developer updates a filter value (e.g., renames `"Battles"` to `"Armed clashes"` to track an ACLED codebook change) in the script but not the test, the per-type column would silently produce zeros in production while the test still passes against its own stale fixture. Tier 4 because: (a) single-developer project, (b) filter values come from ACLED's codebook which rarely changes, (c) the `test_feature_names_match_adr028` test would catch name changes but not filter value changes.

See also C-29 (no integration test), C-74 (strategy vocabulary).

### C-155: No shared visual audit framework — per-source scripts are idiosyncratic — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-155 |
| Tier | 4 |
| Source | ACLED grid verification (2026-05-06), GHS-BUILT-S visual audit falsification (2026-05-22) |
| Trigger | Before WDI verify script is needed, or next visual audit sprint (trigger rewritten during review-rr 2026-06-19). Previous trigger (5th source, V-Dem) resolved 2026-05-26. |
| Location | `scripts/visualize_audit.py` (UCDP), `scripts/verify_acled_grid.py` (ACLED), `scripts/verify_ghspop_grid.py` (GHS-POP), `scripts/verify_ghsbuilts_grid.py` (GHS-BUILT-S), `scripts/viz_style.py` (shared aesthetics only) |

Each data source has its own plotting/audit script with duplicated structural patterns: `PrecomputedData` dataclass, single-pass `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, and statistical pass/fail checks. The scripts share `viz_style.py` for aesthetic constants and helpers (`spatial_imshow`, `style_ax`, `save_plot`) but nothing for plot structure, check logic, or report generation.

**Note (2026-05-20):** Trigger condition met — GHS-POP is the third visual audit script. The three scripts share structural patterns but differ in domain-specific checks (population density vs. fatality rates vs. event counts). Accepted for now: three scripts is enough to see the abstraction clearly, but the abstraction is moderate complexity (pluggable feature specs, check definitions, report generation). Consider extraction when 4th source arrives. Cross-ref: C-164 (WET inventory).
**Note (2026-05-22):** GHS-BUILT-S added as 4th data source. Falsification audit proved total absence of visual audit capability — 5/5 probes hard-falsified. Escalated from Tier 4 DEFER to Tier 2.
**Note (2026-05-22):** C-155 remediated — `verify_ghsbuilts_grid.py` created (10 plots, 6 statistical checks), `--verify` flag added to pipeline, falsification stubs F1-F3 flipped. Full pipeline run successful with all checks PASS. Demoted back to Tier 4 DEFER — the original idiosyncrasy concern (4 bespoke scripts) remains but is not acute. Reassess at 5th source.

**Note (2026-05-24, repo-assimilation v1.2.20):** Quantified: 4 verification scripts total 2,804 lines (UCDP 1,015, GHS-POP 811, GHS-BUILT-S 978, ACLED not counted separately). ~60% structural overlap across scripts (`PrecomputedData` dataclass, `precompute()`, `cell_to_label()`, `REGION_BOUNDS`, per-plot functions, statistical pass/fail checks). At source #5, the extraction cost (~2 days) will be less than the duplication cost (~1 day per copy + ongoing maintenance).

**Note (2026-05-26, review-rr strategic):** V-Dem (5th pipeline source) added without verify script — trigger fired. V-Dem data is country-level democracy indicators (not spatial raster), so the existing raster-oriented verify framework doesn't directly apply. A V-Dem verify script would need different checks (ISO3 coverage, NaN rates, annual→monthly step-function verification). Cross-ref: C-204 (V-Dem has zero falsification files).

**Note (2026-05-26, review-rr strategic curation):** V-Dem verify script created (`scripts/verify_vdem_grid.py`, 15 plots), resolving the "5th source, no verify script" trigger. Underlying concern remains: 5 bespoke verify scripts (UCDP 1,015 lines, GHS-POP 811 lines, GHS-BUILT-S 978 lines, ACLED ~600 lines, V-Dem ~1,770 lines = ~5,174 lines total) with ~60% structural overlap. Trigger updated to 6th source (WDI).

See also C-44 (harvest pipeline template — same WET-before-DRY decision), C-154 (ACLED feature config duplication), C-164 (cross-layer WET inventory), C-195 (falsification test accumulation).

### ~~C-181: UCDP candidate/dot9 discovery probes API even when all versions cached~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-24 (review-rr strategic curation). Optimization, single-file scope, no correctness impact, UCDP has not rate-limited. Re-register if UCDP rate-limits or blocks IP.

| Field | Value |
|-------|-------|
| ID | C-181 |
| Tier | 4 |
| Source | Expert code review of harvest caching (2026-05-21) |
| Trigger | UCDP rate-limits or blocks IP after repeated full-range discovery probes on every pipeline run |
| Location | `src/datafactory_harvester/sources/ucdp_candidate.py:146-200` (`discover_versions`), `src/datafactory_harvester/sources/ucdp_dot9.py:132-182` (`discover_dot9_versions`) |

Both candidate and dot9 harvesters probe the UCDP API month-by-month from `start_year`/`start_month` until a version returns no data. With data from Jan 2018 onward, this is 98+ API calls per harvest run — even when every version is already cached locally. The probes are small (pagesize=1) but still hit the API on every run. The caching check happens _after_ discovery: `_fetch_version` skips download for cached versions, but `discover_versions` always probes the full range. A discovery cache (persist known versions to disk, only probe beyond the last known month) would reduce 98+ calls to 1-3. Tier 4 because: (a) UCDP has not rate-limited us, (b) each probe is tiny, (c) the cost is latency (~2 min) not correctness.

Cross-ref: D-26 (discovery probing cost vs cache staleness), C-44 (harvest pipeline template).

### ~~C-185: GHS-POP epoch caching has no digest comparison~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-24 (review-rr strategic curation). Hypothetical risk — JRC releases are immutable by convention. Re-downloading 450 MB ZIP for comparison is impractical. Re-register if JRC changes release practice.

| Field | Value |
|-------|-------|
| ID | C-185 |
| Tier | 4 |
| Source | Expert code review of harvest caching (2026-05-21) |
| Trigger | JRC silently updates a GeoTIFF epoch at the same URL without changing the filename |
| Location | `src/datafactory_harvester/sources/ghspop.py:140-164` (`_fetch_epoch` cache check) |

GHS-POP uses single-tier caching: file exists + ledger has digest → skip. Unlike UCDP candidate/dot9, there is no post-fetch digest comparison that would detect if the remote file changed. This is architecturally appropriate for GHS-POP because JRC releases are immutable (a new epoch gets a new URL, not a replacement file). However, if JRC ever silently replaces a file, the harvester would not detect it. Tier 4 because: (a) JRC releases are versioned and immutable by convention, (b) the risk is hypothetical, (c) a digest comparison would require re-downloading a 450 MB ZIP to compare.

Cross-ref: C-184 (ACLED same weakness), D-27 (two-tier vs single-tier cache), C-44 (harvest pipeline template).

### ~~C-109: Advisory file locks (fcntl) don't work across NFS~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). NFS migration is hypothetical; server uses local NVMe SSD. Re-register if multi-server deployment is planned.
**Source:** Repo assimilation 2026-04-04 (Phase 5, invariant 10). DDIA Ch.7 pp.234-236, Ch.8 pp.301-303.

### ~~C-159: ACLED snapshot archiving and revision comparison paths untested~~ DEMOTED
Demoted to tech-debt backlog 2026-06-06 (review-rr strategic curation). Integration wiring gap only — both `compare_snapshots` and `archive_snapshot` are tested in their own modules. Re-register if archiving logic is implicated in a data integrity incident.
**Source:** ACLED test review (2026-05-07). Cross-ref: C-164 (harvest pipeline template).

### ~~C-160: ACLED `fetch_paginated` string-data corruption has no guard~~ DEMOTED
Demoted to tech-debt backlog 2026-05-28 (review-rr strategic curation). Downstream `validate_events` catches this; type guard at fetch layer is defense-in-depth, not load-bearing. Re-register if validation layer is refactored.
**Source:** ACLED test review (2026-05-07). Cross-ref: C-153.

### C-173: Hetzner server memory headroom — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-173 |
| Tier | 4 (recalibrated from 3 during strategic curation 2026-05-28) |
| Source | Falsification audit + 8-expert code review (2026-05-20) |
| Trigger | When WDI or next source is added and pipeline peak RSS on CPX42+swap exceeds 28 GB during full pipeline run (trigger rewritten during review-rr 2026-06-24) |
| Location | Hetzner CPX32 server configuration, `docs/guides/hetzner_deployment_guide.md` (troubleshooting section) |

**Update 2026-05-28 (review-rr strategic curation):** Server rescaled to CPX42 (16 GB RAM) + 16 GB swap = 32 GB total (confirmed during v1.2.22 deployment). V-Dem compilation (9.7 GB), assembly (35.5 GB on mmap), and zarr export all completed successfully. Tier recalibrated 3→4: the immediate risk (OOM on 8 GB) is resolved; remaining concern is architectural (R&D plan for bounded-memory compilation at `reports/rd_plan_bounded_memory_compilation.md`).

The Hetzner CPX32 (8 GB RAM) has no swap partition or swapfile. Without swap, the Linux OOM killer is the only backstop — any process that exceeds available RAM is killed immediately (exit code 137) with no chance to degrade gracefully. The GHS-POP viewpoint loads a 6.88 GiB GeoTIFF array, leaving ~600 MB headroom for Python, tifffile buffers, and OS services. A 2 GB swapfile would convert hard kills into degraded performance. Swap setup documented in deployment guide troubleshooting section (v1.2.18). Cross-ref: C-165 (original OOM), C-170 (list accumulation OOM), C-88 (server hardening).

### ~~C-184~~ — Resolved 2026-06-02. See archive.

### ~~C-189: GHS-BUILT-S test coverage parity gap — 19% of combined other sources~~ RESOLVED

Resolved 2026-06-26 (#284). 74 new tests added across all three GHS-BUILT-S test files. Parity metrics now meet ≥70% threshold on all 3 dimensions: functions 177 vs 239 (74%), assertions 287 vs 410 (70%), Red classes 10 vs 10 (100%). `xfail strict=True` markers replaced with `assert ours >= int(theirs * 0.7)` thresholds in `test_falsification_ghsbuilts_coverage_parity.py`. F4 (falsification file count) and F5 (viewpoint line parity) also pass.

| Field | Value |
|-------|-------|
| ID | C-189 |
| Tier | 4 (recalibrated from 3 during strategic curation 2026-05-28) |
| Source | Falsification audit — coverage parity (2026-05-22) |
| Trigger | Before GHS-BUILT-S viewpoint or compilation refactor, or next red-test sprint (trigger rewritten during review-rr 2026-06-19) |
| Location | `tests/test_ghsbuilts_harvester.py`, `tests/test_ghsbuilts_viewpoint.py`, `tests/test_ghsbuilts_compilation.py`; parity stubs in `tests/test_falsification_ghsbuilts_coverage_parity.py` |

Cross-ref: C-164 (WET-before-DRY raster code duplication), C-180 (no falsification tests for non-GHS-POP compilation/viewpoint paths).

### ~~C-177: `_aggregate_to_prio_grid` holds source + copy simultaneously (ADR-031 P3) — [DEFER]~~

| Field | Value |
|-------|-------|
| ID | C-177 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | When `_aggregate_to_prio_grid` is re-activated for a new data source or the function is called outside the builder's strip-based path |
| Location | `src/datafactory_viewpoint/builders/ghspop_v1.py:263` (`clean = data.copy()`) |

`_aggregate_to_prio_grid` creates a full copy of the input array (`clean = data.copy()`) to replace nodata with 0.0. For a 43200x86400 float32 array (~14 GiB), this doubles peak memory — a direct ADR-031 P3 violation ("never hold source and copy simultaneously at scale"). The function is no longer called from `build_ghspop_v1` (v1.2.18 switched to unconditional `_aggregate_with_alignment`), but it is retained because 7 tests exercise it directly. A docstring warning has been added (v1.2.18). If the function is ever re-activated, it must be rewritten to use in-place nodata replacement.

Tier recalibrated from 3 to 4 during review-rr (2026-05-24). Dead function, single developer, docstring warning. D-25 tracks the design question.

Cross-ref: C-170 (GHS-POP list accumulation OOM, resolved), C-173 (no swap on Hetzner).

### ~~C-179: Consolidation dedup uses `.to_pylist()` + Python set (ADR-031 P1)~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-24 (review-rr strategic curation). Mechanical fix (PyArrow `pc.is_in()`), single-file scope, perpetual trigger, data volume 60x below threshold. Re-register if any consolidation path exceeds 5M rows.

| Field | Value |
|-------|-------|
| ID | C-179 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | When consolidated store exceeds ~5M rows on an 8 GB machine |
| Location | `src/datafactory_consolidation/consolidators/ucdp.py:451-458`, `src/datafactory_consolidation/consolidators/acled.py:283-291` |

Both UCDP and ACLED consolidators extract 4 columns via `.to_pylist()` and build Python sets for deduplication. At ~2.3M UCDP rows this is ~260 MB (manageable). The pattern is a P1 violation (columnar Arrow → row-oriented Python objects). PyArrow's `pc.is_in()` + `pc.filter()` would accomplish dedup without materialization. Deferred: current data volume fits comfortably, and consolidation runs infrequently.

Cross-ref: C-145 (viewpoint full store load), C-144 (compilation to_pydict).

### C-180: No falsification tests for non-GHS-POP compilation/viewpoint paths — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-180 |
| Tier | 4 |
| Source | ADR-031 compliance review (2026-05-21) |
| Trigger | Before refactoring UCDP or ACLED compilation/viewpoint code without path-specific falsification coverage (trigger rewritten during review-rr 2026-06-19) |
| Location | `tests/test_falsification_ghspop_memory.py` (GHS-POP only; no equivalent for UCDP/ACLED) |

The GHS-POP memory falsification tests (`test_falsification_ghspop_memory.py`) use AST analysis to verify structural memory safety properties (e.g., `del` targets, no `.to_pylist()`, maxworkers=1). No equivalent tests exist for UCDP viewpoint (`ucdp_v1.py`), ACLED viewpoint (`acled_v1.py`), or grid compilation (`grid_compilation.py`). Memory regressions in those paths would not be caught by the falsification framework. Deferred: the GHS-POP path is the only one that currently operates near the memory ceiling.

Cross-ref: C-144 (grid_compilation to_pydict), C-145 (viewpoint full store load), C-178 (compute_content_digest).

### D-23: ADR-031 P1 — strict columnar purity vs pragmatic materialization

Martin/Hickey favor strict P1 compliance: every `.to_pylist()` and dict-of-lists accumulation is a violation regardless of data volume. Beck/Feathers counter that fixing low-volume paths (UCDP at ~2.3M rows, ACLED at ~800K) adds complexity without preventing any real failure — the 8 GB constraint only binds on GHS-POP (~60M cells). **Resolution: fix GHS-POP and compilation paths (where it matters), defer UCDP/ACLED (where data volume is 60x smaller). Re-evaluate when any non-GHS-POP path exceeds 5M rows.**

**Source:** ADR-031 compliance review (2026-05-21). Cross-ref: C-144, C-145, C-179.


### D-26: Discovery probing cost vs cache staleness (UCDP candidate/dot9)

Nygard argues the 98+ discovery probes per run are a reliability risk: if UCDP starts rate-limiting, the pipeline fails before any useful work. A discovery cache (persist known versions, probe only the frontier) reduces API calls from 98+ to 1-3. Kleppmann counters that a discovery cache introduces a staleness window: if UCDP retracts a version or changes the available set, the cache would serve stale metadata. Beck notes the current approach "works fine" and the optimization should wait for evidence of rate-limiting. **No resolution yet — monitor for rate-limiting before investing in a discovery cache.**

**Source:** Expert code review of harvest caching (2026-05-21). Cross-ref: C-181 (discovery probing).

### ~~D-29: Shapefile harvester retrofit depth — full outcome compliance vs organic~~ — RESOLVED

Nygard and Martin argue for full outcome-vocabulary compliance now (add try/except, record `"failed"` entries, use `"outcome": "success"/"unchanged"`). Feathers and Beck argue the current code works correctly via backward compat and the retrofit should happen organically when the shapefile harvester is next touched. Hickey notes `"changed": True/False` is accidental complexity but not dangerous. **Trigger: when shapefile harvester is next touched for a bug fix, or when a future source requires shapefile-like ingestion.**

**Resolution (2026-06-24, review-rr strategic curation):** Resolved organically. C-186 added outcome vocabulary to the shapefile harvester (2026-05-31) — `"outcome": "success"/"unchanged"/"failed"` and ADR-032 updated. The Feathers/Beck position (organic retrofit on next touch) was vindicated. Full compliance achieved without a dedicated retrofit sprint.

**Source:** Expert code review of provenance/shapefile (2026-05-21). Cross-ref: ~~C-186~~ (resolved — shapefile outcome vocabulary added), C-44 (harvest pipeline template).

### ~~C-195: 37 falsification test files accumulated without curation (3,129 lines)~~ DEMOTED

| Field | Value |
|-------|-------|
| ID | C-195 |
| Tier | 4 |
| Source | repo-assimilation v1.2.20 (2026-05-24) |
| Trigger | Next audit round adds files, or total exceeds 45 — consolidation then reduces navigation cost (trigger rewritten during review-rr 2026-05-26) |
| Location | `tests/test_falsification_*.py` (37 files, 3,129 lines, 129 test functions) |

Falsification audits produce `test_falsification_*.py` files containing failing test stubs that flip green after fixes. Over 10+ audit rounds (GHS-POP memory, coverage parity, visual audit, merge-readiness ×2, deployment ×2, plus earlier UCDP/ACLED audits), 37 files have accumulated. Many test stubs target concerns that are now resolved (C-190, C-191, C-193, C-194) — their stubs pass but serve no ongoing purpose beyond documentation that the fix exists. The test files are not consolidated by concern or source: `test_falsification_ghsbuilts_coverage_parity.py`, `test_falsification_ghsbuilts_merge_ready.py`, `test_falsification_ghsbuilts_deploy_v2.py` all test overlapping aspects of GHS-BUILT-S readiness. Curation options: (a) archive resolved stubs into a `tests/archive/` directory, (b) consolidate per-source stubs into one file per source, (c) tag resolved stubs with `@pytest.mark.resolved` and skip in CI. Tier 4 because: (a) all tests pass, (b) no correctness impact, (c) single-developer scope, (d) the accumulation is a navigation and maintenance burden, not a risk.

**Note (2026-05-26, review-rr strategic):** V-Dem added 0 falsification files (opposite extreme from GHS-BUILT-S at 12 files). The prediction "5th source adds 5-8 files" was wrong — C-204 tracks the V-Dem gap separately. File count remains at 37.

Cross-ref: C-189 (GHS-BUILT-S coverage parity gap), C-180 (no falsification for non-GHS-POP paths), C-164 (WET-before-DRY broader inventory), C-204 (V-Dem zero falsification files).

**Demoted to tech-debt backlog 2026-06-19** (review-rr strategic curation). No correctness impact, single-developer scope, navigation burden only. Re-register if test count exceeds 50 or onboarding new developers.

### ~~C-225~~, ~~C-226~~, ~~C-227~~, ~~C-228~~, ~~C-229~~ — Resolved 2026-05-29. See archive.

### C-224: No server backup or disaster recovery plan — [DEFER]

| Field | Value |
|-------|-------|
| ID | C-224 |
| Tier | 4 |
| Source | review-rr strategic blind spot (2026-05-28) |
| Trigger | Disk failure, accidental `rm -rf`, or Hetzner datacenter incident causes data loss |
| Location | Hetzner server `/home/views-deploy/views-datafactory/data/` (raw, consolidated, compiled, assembled) |

The Hetzner server stores all pipeline data (raw harvests, consolidated stores, compiled grids, assembled output) on a single NVMe disk with no backup, snapshot, or disaster recovery plan. All data is rebuildable from source APIs (UCDP, ACLED, JRC, V-Dem), but a full rebuild from scratch takes ~8-12 hours and requires all API credentials. Hetzner Cloud offers automated snapshots (~€0.01/GB/month) and Volumes for incremental backups. The `data/raw/` directory is the highest-value target — everything downstream is derived.

Cross-ref: C-88 (SSH access control), C-131 (no external monitoring).

### ~~C-230: Script layer (harvest + pipeline) has zero unit tests~~ — RESOLVED 2026-06-18

| Field | Value |
|-------|-------|
| ID | C-230 |
| Tier | 4 |
| Source | Expert code review of C-164 (2026-05-30), Feathers and Beck perspectives |
| Trigger | Harvest script or pipeline runner refactoring (Pattern #7/#8 extraction) changes exit codes, banner format, or `--skip-to` behavior with no test to catch the regression |
| Location | `scripts/harvest_*.py` (9 files, 1,185 lines), `scripts/run_*_pipeline.py` (4 files, 1,093 lines) |

The 9 harvest scripts and 4 pipeline runners have zero unit tests. The scripts are tested only via integration (running the full pipeline on a live server). There are no tests for: correct argument forwarding (`--force` → `force_refresh=True`), exit code semantics (0 on success, 1 on failure), `--skip-to` precondition checking (file existence before skipping), or banner output correctness. This is the largest untested surface in the codebase (2,278 lines, 13 files). When Pattern #8 and #7 extraction begins, characterization tests must be written FIRST to capture current behavior before refactoring. Tier 4 because: (a) scripts are thin wrappers with most logic in the tested source modules, (b) single-developer project, (c) no correctness risk from script bugs beyond operational inconvenience.

**Update (2026-06-10):** Test review confirmed assembly (`assemble_grid.py`) and export (`export_zarr.py`, `generate_consumer_data.py`) are only tested via synthetic test path (`test_content_addressed_skip.py`, `test_skip_module.py`). No unit tests exercise individual script functions (argument parsing, provenance computation, error paths). Assembly/export scripts combined are ~1,200 lines with zero function-level testing.

Cross-ref: C-164 (WET-before-DRY — patterns #7 and #8), C-180 (no falsification tests for non-GHS-POP paths), C-189 (test coverage parity gap), C-146 (assembly in script not package).

**Resolution (2026-06-18):** Harvest: 2 parametrized tests + 1 completeness test in `tests/test_harvest_scripts.py` (9 scripts, #201). Pipeline: 2 parametrized tests + 2 step tests + 1 completeness test in `tests/test_pipeline_scripts.py` (5 scripts, #202). Sprint epic #205.

### ~~C-236: Status page artifact mapping requires manual update per source~~ — RESOLVED 2026-06-18

| Field | Value |
|-------|-------|
| ID | C-236 |
| Tier | 4 |
| Source | expert-code-review (2026-06-03), Feathers + Ousterhout perspectives |
| Trigger | Next source integration (e.g., WDI) adds source to registry and pipeline but omits artifact mapping in `generate_status.py` |
| Location | `scripts/generate_status.py` (proposed — artifact path mapping dict) |

The status page will contain a hardcoded mapping from source names to artifact paths per pipeline stage. This mapping must be manually updated whenever a new source is integrated. The same pipeline-path information also exists in `docs/guides/data_source_integration_guide.md:22-25`, `refresh_pipeline.sh` (implicit in step ordering), and `test_operational_integration.py:22-28` (exclusion list). Four locations for the same information is an information leakage risk. Tier 4 because: (a) single-developer project, (b) impact is "wrong status page" not "wrong data," (c) the status page itself can derive some answers from filesystem state.

Long-term mitigation: standardize artifact output paths by convention (e.g., `data/compiled/{source_id}/grid.npy`) so the status page derives paths instead of hardcoding them. Short-term: add a test that all sources with features in the registry have an entry in the artifact mapping.

**Resolution (2026-06-18):** 3 alignment tests in `tests/test_generate_status.py::TestSourceRegistryAlignment` pin: all PIPELINE_SOURCES in status, no orphan status sources, feature counts match. Sprint epic #205, issue #203.

Cross-ref: C-164 (cross-layer WET debt), C-155 (no shared verify framework), D-33 (pipeline-path location). GitHub: #101, #102.

### ~~C-240: generate_status.py docstring specifies nonexistent /www/ path~~ RESOLVED

Resolved 2026-06-06 (commit dd69544). Docstring updated to show `--output data/status.html` matching actual deployment usage. The `/www/` path no longer appears anywhere in the codebase.

**Source:** falsification audit (2026-06-04, G1). Cross-ref: C-239 (resolved), C-238 (resolved).

### ~~C-241: No invariant for intensive feature conservation across resolution or aggregation~~ — RESOLVED

**Resolved 2026-06-24:** `UserWarning` added to `grid_to_country_month.py`. **Re-resolved 2026-06-28 (ADR-048, epic #290):** Root-cause fix — prefix inference (`_INTENSIVE_PREFIXES`) deleted and replaced with declared `feature_agg_types` from the source registry. Intensive features now raise `ValueError` (fail-loud, ADR-011) instead of emitting a suppressible warning. Static features excluded from aggregation output. All three prefix-based ADR-003 violations (`_INTENSIVE_PREFIXES`, `_EXTENSIVE_PREFIXES`, `_SOURCE_PREFIXES`) deleted. 4 tests: `test_intensive_feature_raises_when_types_declared`, `test_extensive_only_succeeds_with_types`, `test_static_features_excluded_from_output`, `test_no_types_falls_through_without_error`.

| Field | Value |
|-------|-------|
| ID | C-241 |
| Tier | ~~4~~ → Resolved |
| Source | ADR-040 scoping discussion (2026-06-05) |
| Trigger | ~~First consumer aggregates intensive features~~ Resolved. |
| Location | `src/datafactory_adapters/grid_to_country_month.py` (`_INTENSIVE_PREFIXES`, warning block) |

ADR-040 establishes count conservation (Invariant 1) and hierarchical reconciliation (Invariant 2) for extensive quantities — fatalities, event counts, population counts — where sums must balance across layers and aggregation levels. Intensive features (V-Dem democracy scores, SHDI human development index, GHS-BUILT-S built-up surface fraction) are explicitly out of scope because sums are not meaningful for these quantities. There is no ADR and no defined invariant for how intensive features should behave under aggregation (area-weighted average? population-weighted average?) or when grid resolution changes (does a 0.25° cell inherit its parent 0.5° cell's value? does it interpolate?).

Currently this is not acute: `grid_to_country_month.py` sums all features including intensive ones (line 115), which is mathematically wrong for HDI and democracy scores but harmless because no downstream consumer currently uses country-month intensive feature totals. The problem becomes acute when: (a) a model or consumer aggregates V-Dem or SHDI to country-month and interprets the sum as meaningful, or (b) grid resolution changes and intensive features must be resampled. Both scenarios require defining what "conservation" means for non-additive quantities — likely area-weighted or population-weighted averaging, which is a research decision, not an engineering one.

Cross-ref: ADR-040 (scope boundary table, "Intensive feature conservation"), ADR-024 (Invariant 6: country-level broadcast for V-Dem), ADR-035 (GHS-BUILT-S integration).

### ~~C-244: 4 CICs + ADR-025 not updated after ADR-040 acceptance~~ RESOLVED

Resolved 2026-06-06 (PR #135). All 5 documents updated: ADR-040 added to Related ADRs, conservation guarantees in Section 3, test alignment in Section 10 for grid_to_country_month.md, CompilationConfig.md, AssemblyConfig.md, GaulAdminConfig.md, and ADR-025 back-reference added.

Cross-ref: C-242 (resolved same PR), C-243 (resolved same PR), ADR-040.

### ~~C-266: Flaky `test_latest_harvest_wins` — filesystem timestamp resolution~~ — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-266 |
| Tier | 4 |
| Source | tech-debt-cleanup pre-deploy (2026-06-10) |
| Trigger | Full suite run where both test Parquet files are created within the same filesystem timestamp granularity (same second) |
| Location | `tests/test_acled_consolidation.py:406` (`test_latest_harvest_wins`), `src/datafactory_consolidation/consolidators/acled.py:117` (`st_mtime` fallback) |

`test_latest_harvest_wins` creates two Parquet files sequentially and expects the second file's data to win cross-file dedup. `_get_harvest_metadata()` falls back to `stat().st_mtime` when no ledger entry exists. When both files are created within the same filesystem timestamp tick, they get identical timestamps. The dedup uses `ts > timestamps[seen[eid]]` (strict greater-than), so ties keep first-seen — the test expects the second file's `fatalities=99` but gets the first file's `fatalities=0`. Observed as intermittent failure in full suite runs (passes in isolation, passes most full runs, fails occasionally).

**Resolution (2026-06-10):** Added explicit `os.utime()` calls in the test to set distinct mtimes on the two Parquet files (1000000 and 2000000), guaranteeing the second file always has a later mtime regardless of filesystem timestamp resolution. Verified with 5 consecutive full-file test runs (100/100 pass).

Cross-ref: C-252 (ACLED cross-run dedup — same dedup code, different concern).

### ~~C-231: No compilation idempotence guard — silent recompilation with stale inputs~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-24 (review-rr strategic curation). Single-operator deployment, pipeline runs steps in order, provenance provides post-hoc audit. Re-register if multi-operator deployment or automated recompilation is planned.

| Field | Value |
|-------|-------|
| ID | C-231 |
| Tier | 4 |
| Source | Expert code review of C-164 (2026-05-30), Kleppmann perspective |
| Trigger | Operator re-runs compilation after viewpoint is re-built with different parameters, producing a grid from mixed-vintage inputs without warning |
| Location | `src/datafactory_compilation/grid_compilation.py` (`compile_grid`), `src/datafactory_compilation/pregridded_compilation.py` (`compile_pregridded`), `src/datafactory_compilation/output.py` (`write_compilation_output`) |

`compile_grid()` and `compile_pregridded()` always overwrite the output directory. If run twice with different inputs (e.g., viewpoint was re-built between runs with different parameters), there is no warning that the input context changed. The provenance ledger records what happened, but nothing reads the ledger to check input consistency before writing. A pre-compilation digest check — compute digests of all input files, compare against the previous compilation's input digests in the ledger — would be cheap and would catch accidental recompilation with stale or mixed inputs. Tier 4 because: (a) single-operator deployment, (b) the pipeline script runs steps in order so mixed inputs are unlikely, (c) provenance provides post-hoc audit capability.

Cross-ref: C-223 (compilation memory — same functions, different concern), C-46 (no ledger write idempotency), C-253 (same pattern at export layer — no digest verification). Part of causal cluster: **Artifact consistency**.

### ~~C-232~~ — Resolved 2026-06-02 (PR #98, v1.2.25). See archive.

### ~~C-248: `area_majority_join` string tiebreaker crashes on mixed types~~ — RESOLVED

| Field | Value |
|-------|-------|
| ID | C-248 |
| Tier | 4 |
| Source | Pre-deployment test coverage audit (2026-06-07) |
| Resolution | 2026-06-07 (#136): type-safe tiebreaker with `isinstance` guard + `default` fallback. Regression test `test_string_field_tiebreaker_no_crash` added to `TestGenerationScriptRed`. |
| Location | `scripts/generate_area_majority_gaul.py:112-115` |

Cross-ref: C-246 (resolved — production code path tested), C-247 (dual source of truth).

### ~~C-249: Float64 CM conservation fix has no regression guard~~ — RESOLVED

**Resolved 2026-06-24:** Two regression tests added in `TestRedFloat64Regression`: (1) `test_float32_has_nonzero_partition_error` — at 500K cells with values in [10, 100], proves float32 accumulation introduces 0.6875 gap (>0.01) while float64 has zero gap. (2) `test_production_code_passes_at_scale` — verifies `assert_cm_conservation()` passes at 500K-cell production scale. The float64 path is demonstrated as providing exact partition-sum equality vs measurable float32 error. Sprint epic #258, issue #261.

| Field | Value |
|-------|-------|
| ID | C-249 |
| Tier | ~~4~~ → Resolved |
| Source | Pre-deployment test coverage audit (2026-06-07) |
| Trigger | ~~When `_conservation.py` is refactored~~ Resolved. |
| Location | `tests/test_count_conservation.py::TestRedFloat64Regression` (2 tests) |

The `dtype=np.float64` fix prevents float32 summation order divergence between `nansum(all)` and `nansum(land) + nansum(excluded)`. But the test uses 10,000 cells with values in [0,1), producing sums around 5,000 — well within float32's exact range. The `allclose(rtol=1e-6, atol=1e-4)` tolerance passes with or without the fix at this scale. Removing `dtype=np.float64` causes zero test failures. The same gap applies to the `assert_cm_conservation` wiring in `grid_to_country_month.py:99-104` — deleting the call also causes no test failure.

Cross-ref: ~~C-242~~ (resolved — the assertion this fix belongs to), ~~C-241~~ (resolved — intensive feature warning), ADR-040.

### ~~C-250: Hierarchical reconciliation not wired into any production code path~~ — Resolved 2026-06-19 (#211)

| Field | Value |
|-------|-------|
| ID | C-250 |
| Tier | 4 |
| Source | Pre-deployment behavioral change audit (2026-06-07) |
| Trigger | New GAUL release introduces hierarchy corruption (L2 unit maps to two different L1 units) and `generate_area_majority_gaul.py` processes it without checking nesting |
| Location | `src/datafactory_adapters/_reconciliation.py` (`check_nesting`, `assert_hierarchical_reconciliation`), `scripts/generate_area_majority_gaul.py` (no import of reconciliation) |

`check_nesting()` and `assert_hierarchical_reconciliation()` are tested (6 tests in `test_hierarchical_reconciliation.py`) but not called from any production script or pipeline step. The GAUL area-majority script produces L0/L1/L2 code files but never verifies that the hierarchy nests correctly. A corrupted GAUL release with inconsistent nesting would produce silently wrong CM aggregations (L0 sums != L1 sums != L2 sums). Tier 4 because: (a) GAUL releases are manually curated and stable, (b) the real-data test (`TestRealDataHierarchy`) catches this when run locally, (c) wiring is a small change when needed.

Cross-ref: C-243 (resolved — test existence), C-246 (untested production code path), ADR-040.

### ~~C-271: compute_file_digest() has zero direct tests~~ RESOLVED

Resolved 2026-06-26 (#281). 8 direct tests added to `tests/test_provenance.py`: Green (deterministic output, 16-hex length, equivalence with content digest), Beige (empty file, multi-chunk streaming via 200KB file), Red (missing file raises, directory raises, binary content determinism).

| Field | Value |
|-------|-------|
| ID | C-271 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Trigger | Changing digest algorithm or chunk size without a regression test |
| Location | `src/datafactory_provenance/digest.py` (`compute_file_digest`) |

Cross-ref: C-267 (event_store crash-safety — same provenance layer).

### ~~C-272: TemporalConfig CIC Section 6 failure modes untested~~ — DEMOTED

`TemporalConfig` CIC documents failure modes for `month=0`, `month=13`, `start_month > end_month`. No test exercises these boundary conditions. The `__post_init__` validation in `TemporalConfig` rejects these values, but the rejection behavior is untested. Tier 4 because: (a) frozen dataclass `__post_init__` is a standard pattern unlikely to regress, (b) single-developer project, (c) the CIC itself serves as documentation.

| Field | Value |
|-------|-------|
| Trigger | Modifying TemporalConfig validation logic or adding new temporal boundary checks |
| ID | C-272 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | CIC `docs/CICs/temporal_config.md` (Section 6), `src/datafactory_priogrid/temporal.py` |

### ~~C-273: snapshot_storage.py has no dedicated tests~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-24 (review-rr strategic curation). Exercised indirectly through consolidation integration tests, single-file scope, mechanical gap. Re-register if snapshot storage logic is refactored.

`snapshot_storage.py` in `datafactory_consolidation` handles snapshot file operations: empty event handling, field merging across snapshots, and archive management. No dedicated test file exists. These functions are exercised indirectly through consolidation integration tests, but edge cases — empty snapshots, field schema mismatch between snapshots, corrupt archive files — are untested.

| Field | Value |
|-------|-------|
| Trigger | When snapshot_storage.py is modified: write characterization tests before making changes (trigger rewritten during review-rr 2026-06-24) |
| ID | C-273 |
| Tier | ~~4~~ |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_consolidation/snapshot_storage.py` |

### ~~C-274: tagging.py has only 1 test — no edge cases or adversarial~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-12 (review-rr strategic). No correctness impact on data pipeline; thin metadata annotation layer. Same class as already-demoted C-272/C-277/C-278. Re-register if tag-based filtering or tag-driven pipeline logic is added.

| Field | Value |
|-------|-------|
| ID | C-274 |
| Tier | ~~4~~ |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_harvester/tagging.py` |

### ~~C-275: raster_io.py has only 1 test — no error path coverage~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-12 (review-rr strategic). Exercised end-to-end by GHS-POP/GHS-BUILT-S compilation tests; error paths produce loud failures (FileNotFoundError, rasterio exceptions). Re-register if a new raster source uses raster_io with different format characteristics.

| Field | Value |
|-------|-------|
| ID | C-275 |
| Tier | ~~4~~ |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_compilation/raster_io.py` |

### ~~C-276: UCDP candidate/dot9 per-version fetch failure modes untested~~ RESOLVED

Resolved 2026-06-26 (#283). 10 per-version tests added (5 candidate in `tests/test_ucdp_candidate.py`, 5 dot9 in `tests/test_ucdp_dot9.py`): Beige (not_served version returns not_served, all versions cached), Red (mixed batch outcomes with partial success/failure, validation failure does not corrupt prior success, network error on fetch_version).

| Field | Value |
|-------|-------|
| Trigger | UCDP changes version numbering scheme or per-version API endpoint format |
| ID | C-276 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_harvester/sources/ucdp_candidate.py`, `src/datafactory_harvester/sources/ucdp_dot9.py` |

Cross-ref: C-181 (discovery probes even when cached), C-70 (no circuit breaker).

### ~~C-277: check_disk_space() RuntimeError path untested~~ — DEMOTED

`check_disk_space()` in `preflight.py` raises `RuntimeError` when available disk is below the threshold. No test exercises this path. Tier 4 because: (a) preflight runs before any data processing, (b) the RuntimeError produces a loud failure, (c) the check is a simple `shutil.disk_usage` comparison.

| Field | Value |
|-------|-------|
| Trigger | Modifying disk space thresholds or adding per-step space checks |
| ID | C-277 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | `scripts/preflight.py` (`check_disk_space`) |

### ~~C-278: ConsolidationResult / ViewpointResult have no frozen-mutation tests~~ — DEMOTED

`ConsolidationResult` and `ViewpointResult` are frozen dataclasses that carry pipeline stage outputs. No test verifies their immutability — i.e., that attempting to assign to a field raises `FrozenInstanceError`. Tier 4 because: (a) `@dataclass(frozen=True)` is enforced by Python's dataclass machinery, (b) a regression would require removing the `frozen=True` flag, which would be visible in code review.

| Field | Value |
|-------|-------|
| Trigger | Refactoring result containers to use a different data class pattern (e.g., attrs, Pydantic) |
| ID | C-278 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_consolidation/` (ConsolidationResult), `src/datafactory_viewpoint/` (ViewpointResult) |

### ~~C-279: land_mask.py has zero red (adversarial) tests~~ — DEMOTED

Demoted to tech-debt backlog 2026-06-12 (review-rr strategic). Downloaded once and cached permanently; download failures produce loud HTTP errors; minimal surface area. Re-register if Natural Earth API changes endpoint URL or response format.

| Field | Value |
|-------|-------|
| ID | C-279 |
| Tier | ~~4~~ |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_priogrid/land_mask.py` |

### ~~C-284: ACLED event_type_filter implemented but absent from ADR-028 — [DEFER]~~

`acled_v1.py` implements an `event_type_filter` capability (lines 138-151) using PyArrow `pc.is_in()` to conditionally filter events by type. The `AcledViewpointConfig` CIC lists the field (`event_type_filter: Optional[tuple[str, ...]]`), but ADR-028 does not mention filtering at all. ADR-028 characterizes the ACLED viewpoint as "no survivorship, no temporal distribution, no spatial transformation, no aggregation" — accurate, but the filtering capability is an undocumented behavior. A developer reading ADR-028 to understand what the ACLED viewpoint does would miss this capability entirely.

| Field | Value |
|-------|-------|
| ID | C-284 |
| Tier | 4 — documentation gap; no correctness risk, single-developer scope |
| Source | falsify (2026-06-13), probe P-8 |
| Trigger | Developer reads ADR-028 to understand ACLED viewpoint behavior and misses the event_type_filter capability, or adds a similar filter to another viewpoint without knowing the ACLED precedent |
| Location | `src/datafactory_viewpoint/builders/acled_v1.py:138-151`, `docs/ADRs/028_acled_consolidation_and_viewpoint.md` |

Cross-ref: C-154 (ACLED feature config duplication — same builder, different concern).

---

### ~~C-285: No process lock prevents concurrent pipeline runs — data file overwrites possible~~

`refresh_pipeline.sh` and individual `run_*_pipeline.py` scripts write grid.npy, assembled grid, and zarr stores using an atomic `.tmp` + rename pattern. Ledger writes are protected by `fcntl.flock`, but data file writes have no process-level lock. If two pipeline runs overlap (e.g., cron schedule fires while a previous run is still assembling), the atomic rename prevents file corruption but the slower run's output silently replaces the faster one's — potentially reverting a more recent assembly to an older state. The risk increases if cron intervals are shorter than pipeline duration (~7 min for full refresh).

| Field | Value |
|-------|-------|
| ID | C-285 |
| Tier | 3 — operational risk; not silent corruption (atomic writes are correct), but potential data staleness from race condition |
| Source | repo-assimilation (2026-06-14), Phase 5 |
| Trigger | Operator starts second pipeline run (cron overlap or manual re-trigger) while first is still writing grid.npy or assembled output |
| Location | `scripts/refresh_pipeline.sh`, `scripts/assemble_grid.py` (atomic rename pattern), `scripts/export_zarr.py` |

Cross-ref: C-267 (event_store.py crash-safety — same concern class, different data files), C-147 (no pipeline orchestrator).

---

### C-287: Assembly channel order is positional — hardcoded offsets fragile if feature counts change — [DEFER]

`assemble_grid.py` concatenates features from all sources using cumulative positional offsets: UCDP occupies channels `[0:n_ucdp]`, ACLED occupies `[n_ucdp:n_ucdp+n_acled]`, and so on. If a source adds or removes a feature (e.g., ACLED adds a 9th event type), all subsequent channel offsets shift. The `feature_names.json` sidecar correctly records the actual feature order, so consumers using named feature access are safe. The risk is to the assembly script maintainer: a mismatch between the hardcoded assignment order and the feature names list would produce silent misalignment. The repetitive load-validate-align blocks (C-164 pattern #7) compound this — each source block independently computes its offset range.

| Field | Value |
|-------|-------|
| ID | C-287 |
| Tier | 4 — maintainability; consumers are protected by feature_names.json; risk is assembly-time misalignment |
| Source | repo-assimilation (2026-06-14), Phase 3 |
| Trigger | Source adds/removes a feature without updating channel offset logic in assemble_grid.py |
| Location | `scripts/assemble_grid.py` (channel assignment block — positional offsets: `n_ucdp`, `n_ucdp + n_acled`, etc.) |

**Test gap note (test-review 2026-06-14):** No test verifies that planted data values appear at the correct channel index. The synthetic pipeline test (`test_synthetic_pipeline.py`) checks that planted values exist somewhere in the grid but does not verify they are in the right feature channel. If two source arrays were swapped during assembly (e.g., GHS-POP data placed in V-Dem channels), all current tests would pass. A channel-data-name consistency test is needed.

Cross-ref: C-146 (assembly logic in script — same file, testability concern), C-164 (WET debt — repetitive load-validate-align blocks), C-288 (cross-layer schema verification gap).

---

### ~~C-299: ADR-048 §5 claims `_SOURCE_DISPLAY_NAMES` deleted but it still exists~~ — Resolved 2026-06-28

ADR-048 §5 line 62 states: "Delete `_SOURCE_DISPLAY_NAMES` — source-to-feature ownership now read from provenance `*_features` keys." However, `_SOURCE_DISPLAY_NAMES` still exists at `dataset.py:343-349`. The dict maps source keys (`"acled"`, `"ucdp"`, etc.) to human-readable names for the pre-coverage warning message. It is not a prefix-inference mechanism (it doesn't infer aggregation type from names), so its continued existence doesn't violate ADR-003. But the ADR makes a false statement about the codebase.

| Field | Value |
|-------|-------|
| ID | C-299 |
| Tier | 4 — documentation accuracy; the dict serves a display purpose, not inference; no correctness impact |
| Source | Falsification audit, epic #290 (2026-06-28), probe P2 |
| Trigger | Developer reads ADR-048 §5 and assumes `_SOURCE_DISPLAY_NAMES` was removed, then writes code that duplicates the display-name mapping |
| Location | `docs/ADRs/048_declared_feature_aggregation_types.md:62` (false claim), `src/datafactory_query/dataset.py:343-349` (`_SOURCE_DISPLAY_NAMES` still present) |

Cross-ref: ADR-048, ~~C-241~~ (resolved — intensive feature gap, same codebase area).

---

### C-300: Zarr path returns empty `source_features` — pre-coverage warnings silently skipped — [DEFER]

`_load_grid_from_zarr()` returns `source_features={}` (line 223), while `_load_grid_from_npy()` reads the actual source-feature mapping from provenance `*_features` keys. When `source_features` is empty, `_warn_pre_coverage()` has no sources to check and returns immediately — zarr consumers get no warning about pre-coverage zero-padding. The npy path correctly warns. This is a pre-existing parity gap widened by the epic: before, `_SOURCE_PREFIXES` provided a fallback for both paths; now the npy path reads from provenance but the zarr path has no equivalent metadata.

| Field | Value |
|-------|-------|
| ID | C-300 |
| Tier | 4 — informational warning gap; data is correct, consumers may misinterpret zero-padding; zarr is a secondary path |
| Source | Falsification audit, epic #290 (2026-06-28), probe P4 |
| Trigger | Consumer loads data via zarr backend and misinterprets zero-padding in pre-coverage months as observed data |
| Location | `src/datafactory_query/dataset.py:223` (`_load_grid_from_zarr` returns `source_features={}`) |

Cross-ref: C-116 (remote zarr no retry), C-117 (remote zarr downloads all cells). Part of work package: **Query layer resilience**.

---

### C-302: Inline prefix check in excluded-cell warning — 4th ADR-003 pattern survived epic — [DEFER]

`grid_to_country_month.py:90-93` uses `f.startswith(("ged_", "acled_"))` to identify event features for the excluded-cell diagnostic warning. This is functionally the same class as the deleted `_EXTENSIVE_PREFIXES` — inferring feature type from name prefix instead of reading declared `feature_agg_types`. The epic deleted three named prefix constants but this inline check survived because it wasn't a named constant (the `grep` for prefix lists missed it). CIC §5 line 60 documents this prefix behavior. The warning would miss GHS-POP (also extensive) in excluded cells, though GHS-POP values are zero in ocean cells by construction.

| Field | Value |
|-------|-------|
| ID | C-302 |
| Tier | 4 — diagnostic warning path, not correctness; single inline instance; GHS-POP is zero in ocean cells so the gap is theoretical |
| Source | Falsification audit round 2 (2026-06-28), probe Q2 |
| Trigger | New extensive source (e.g., WDI count feature) added; excluded cells with nonzero values for the new source not included in diagnostic warning |
| Location | `src/datafactory_adapters/grid_to_country_month.py:90-93` (inline `startswith`), `docs/CICs/grid_to_country_month.md:60` (documents prefix behavior) |

Cross-ref: ~~C-241~~ (resolved — intensive feature gap, same function), C-301 (conservation no-op — same function, different gap), C-299 (ADR-048 doc accuracy — same epic). Part of work package: **ADR-003 compliance**.

---

### ~~C-303: ADR-049 §Validation mandates 3 provenance counters; builder logs only 1~~

ADR-049 §Validation & Monitoring (line 136) requires three provenance counters: `n_spatially_distributed`, `n_excluded_where_prec`, and `n_passthrough_where_prec`. The builder (`ucdp_v1.py:372-396`) logs `n_spatially_distributed` and `n_spatial_cells_created` but never computes or logs `n_excluded_where_prec` or `n_passthrough_where_prec`. The existing `n_filtered` counter conflates all filter types (priogrid_gid, type_of_violence, where_prec). An auditor checking the ledger for the ADR-specified counters would find them absent. Fix: either add the two missing counters to the builder, or amend ADR-049 §Validation to match what is actually logged.

| Field | Value |
|-------|-------|
| ID | C-303 |
| Tier | 4 — audit metadata, not data-path values; no correctness or reliability impact |
| Source | Falsification audit (2026-06-28), probe F3 |
| Trigger | Auditor checks provenance ledger for `n_excluded_where_prec` or `n_passthrough_where_prec` after reading ADR-049 |
| Location | `src/datafactory_viewpoint/builders/ucdp_v1.py:372-396` (ledger entry), `docs/ADRs/049_spatial_distribution_of_imprecise_ucdp_events.md:136` (§Validation) |

Cross-ref: C-304 (ADR-049 §2 method divergence — same ADR, different section).

---

### ~~C-304: ADR-049 §2 table says `adm_1` field lookup for where_prec 4/5; code uses pgid→gaul1 crosswalk~~

ADR-049 §2 table (lines 43-48) specifies three distinct polygon-determination methods: `adm_1` field matching for where_prec=4, `adm_1` matching for where_prec=5-with-adm_1, and centroid spatial join for where_prec=5-without-adm_1. The implementation (`spatial_distribution.py:118-129`) uses a single uniform method for all where_prec 4/5 cases: `weight_map.pgid_to_gaul1.get(pgid_int)` — a pgid→gaul1_code crosswalk lookup. The `adm_1` field is never read anywhere in the codebase. The implementation plan explicitly stated "no name matching" — the crosswalk approach is arguably more robust (no transliteration/abbreviation fragility), but the ADR was drafted after implementation and describes a different method. Fix: update ADR-049 §2 table to document the crosswalk approach actually used.

| Field | Value |
|-------|-------|
| ID | C-304 |
| Tier | 4 — documentation inaccuracy, not a code bug; the crosswalk approach is correct behavior |
| Source | Falsification audit (2026-06-28), probe F4 |
| Trigger | Developer reads ADR-049 §2 and implements `adm_1`-based GAUL name matching, creating divergent or fragile behavior |
| Location | `src/datafactory_viewpoint/spatial_distribution.py:118-129` (code), `docs/ADRs/049_spatial_distribution_of_imprecise_ucdp_events.md:43-50` (ADR §2 table) |

Cross-ref: C-303 (ADR-049 §Validation counter gap — same ADR, different section), C-305 (crosswalk path mismatch — same epic, different gap).

---

### ~~C-305: ViewpointConfig default crosswalk paths point to `gaul_admin_area_majority/`; pipeline writes to `gaul_admin/`~~

`ViewpointConfig` (`viewpoint_config.py:47-51`) defaults `gaul1_crosswalk_path` and `gaul0_crosswalk_path` to `data/raw/gaul_admin_area_majority/gaul{0,1}_code.parquet`. The pipeline (`refresh_pipeline.sh:168`) runs `generate_area_majority_gaul.py --data-dir data/raw/gaul_admin`, writing crosswalks to `data/raw/gaul_admin/`. The `gaul_admin_area_majority/` directory exists on the development machine as a leftover from the area-majority development era — it is not the pipeline's output target. On a fresh server with `spatial_distribution_strategy="proportional"` (the default), `build_spatial_weight_map()` reads the config default paths and raises `FileNotFoundError`. Currently masked in production because `build_viewpoint.py` defaults to `production_parity` profile (passthrough — crosswalks never read). Fix: change ViewpointConfig defaults to `data/raw/gaul_admin/`.

| Field | Value |
|-------|-------|
| ID | C-305 |
| Tier | 4 — fail-loud (FileNotFoundError), not silent corruption; only affects non-production-parity configs on fresh servers |
| Source | Falsification audit round 2 (2026-06-28), probe G5 |
| Trigger | Fresh server (or data wipe) runs viewpoint with proportional strategy using default config paths |
| Location | `src/datafactory_viewpoint/viewpoint_config.py:47-51` (config defaults), `scripts/refresh_pipeline.sh:168` (pipeline `--data-dir`) |

Cross-ref: C-303 (ADR-049 provenance counters), C-304 (ADR-049 §2 method divergence).

---

### ~~C-306: xfail neutralizes F1 hard falsification — test never blocks deployment~~

`test_falsification_deploy_v160.py:42-45` wraps the version-tag check with `@pytest.mark.xfail(condition=_tag_exists(...))`. When the tag already exists (the exact condition the test should flag), the assertion failure is caught as XFAIL and CI stays green. The "hard falsification" F1 can never turn the suite red, defeating its purpose as a deploy gate.

| Field | Value |
|-------|-------|
| ID | C-306 |
| Tier | 4 — test quality, no production data impact |
| Source | PR #307 review (2026-06-28), Angle A |
| Trigger | Developer relies on F1 to block deployment when version is not bumped |
| Location | `tests/test_falsification_deploy_v160.py:42-45` |

Cross-ref: C-307 (same file, different test quality gap).

---

### ~~C-307: gh CLI failure silently treated as "all issues closed" in F6~~

`test_falsification_deploy_v160.py:88-98` loops over 10 issue numbers calling `gh issue view`. If `gh` is missing, unauthenticated, or the API fails, `result.stdout` is empty (not `"OPEN"`), so every issue silently passes as closed. The test gives a false green when it has no data.

| Field | Value |
|-------|-------|
| ID | C-307 |
| Tier | 4 — test quality, no production data impact |
| Source | PR #307 review (2026-06-28), Angle A |
| Trigger | CI runs without `gh` installed or authenticated |
| Location | `tests/test_falsification_deploy_v160.py:88-98` |

Cross-ref: C-306 (same file, different gap), C-308 (same file, different gap).

---

### ~~C-308: Hardcoded plan path in F7 silently skips when plan renamed~~

`test_falsification_deploy_v160.py:113` hardcodes `product_development_plan11.md`. When the plan is renamed to v12+, the path doesn't exist, `pytest.skip` fires, and the staleness check is permanently disabled. A falsification test that skips when its input is absent is self-defeating.

| Field | Value |
|-------|-------|
| ID | C-308 |
| Tier | 4 — test quality, no production data impact |
| Source | PR #307 review (2026-06-28), Altitude angle |
| Trigger | Product plan renamed from v11 to v12+ |
| Location | `tests/test_falsification_deploy_v160.py:113` |

Cross-ref: C-306 (same file), C-307 (same file).

---

### ~~C-309: Main/development divergence blocks ff-only merge — GitHub merge commits create non-ancestor topology~~

GitHub PR squash-merges create merge commits on `main` that do not exist on `development`. After enough PRs, `main` is no longer an ancestor of `development`, causing `git merge development --ff-only` on main to fail. Fixed by merging main into development before the ff-only merge.

| Field | Value |
|-------|-------|
| ID | C-309 |
| Tier | 4 — operational procedure, single-developer scope, no correctness impact; merge is conflict-free |
| Source | Falsification audit round 2 (2026-06-29), probe DF-1 |
| Trigger | Operator runs `git merge development --ff-only` on main after GitHub PR merges created divergent topology |
| Location | Git topology (main vs development branches), `docs/guides/hetzner_deployment_guide.md` |

Cross-ref: C-310 (deploy guide omits the prerequisite step).

---

### ~~C-310: Deployment guide omits merge-main-into-development prerequisite step~~

The Hetzner deployment guide says `git merge development --ff-only` without documenting that this requires main to be an ancestor of development. When GitHub PR merges create commits on main, the ff-only merge fails. Fixed by adding a prerequisite step to the guide: merge main into development first.

| Field | Value |
|-------|-------|
| ID | C-310 |
| Tier | 4 — documentation gap, single-developer scope, no correctness impact |
| Source | Falsification audit round 2 (2026-06-29), probe DF-2 |
| Trigger | Operator follows deployment guide verbatim; ff-only merge fails with no guidance on resolution |
| Location | `docs/guides/hetzner_deployment_guide.md` (ff-only merge step without prerequisite) |

Cross-ref: C-309 (the topology divergence this guide gap fails to prevent).

---

### ~~C-311: DGP ordering check contradicts observed UCDP data — blocked v26.1 harvest~~

`_check_best_high_low_ordering` (added with C-257, #212) asserted `low <= best <= high` as a hard invariant. Published UCDP data violates this ordering in ~1.3% of events (v25.1: 3,594 best>high + 1,415 low>best across 1989-2024). The check never fired in production because v25.1 was harvested before the check existed and cache-hit ever since; the first v26.1 fetch (2026-07-02, triggered by v1.6.1 version discovery) crashed the harvest and killed the whole pipeline (`set -e`). Fixed by moving the ordering check to `UCDP_DGP_WARN_CHECKS` (warn-not-block) with `warn_only=True` support in `validate_dgp_assumptions()`. The four remaining hard checks verified clean on all 384,918 real v25.1 events.

| Field | Value |
|-------|-------|
| ID | C-311 |
| Tier | 2 — pipeline-blocking failure on real published data; a validation check encoding an assumption the source never promised |
| Source | v1.6.1 deploy incident (2026-07-02), server refresh_pipeline failure |
| Trigger | Any fresh UCDP Annual fetch (new version discovery or cache miss) |
| Location | `src/datafactory_harvester/sources/ucdp_annual.py` (UCDP_DGP_CHECKS/UCDP_DGP_WARN_CHECKS), `src/datafactory_harvester/event_validation.py` (warn_only) |

Resolved 2026-07-02 (warn-not-fail split; empirically verified against real v25.1 snapshot). Lesson: DGP checks must be validated against real source data before being made blocking — the check shipped in v1.4.0 but was only ever exercised by synthetic test events. Cross-ref: C-257 (the sprint that introduced the check), D-40 (check module placement).

---

### ~~C-312: ACLED consolidated store carried 2x duplicate events — cryptic conservation crash on replacement~~

The server's ACLED store (4,095,646 rows, only 2,049,899 unique event_ids) predated cross-file dedup and carried ~2x duplicates. The C-252 cross-run replacement filter removes ALL rows matching a replaced event_id, so the merge lost ~2M more rows than the conservation formula expected, crashing with a numerically confusing error (`expected 4310703, got 2265408`). Store was rebuilt clean from raw snapshots (2,262,881 records). Guard added: `consolidate_acled()` now fails loud with a diagnostic error (row count vs unique count + remediation: delete store, re-run) when the existing store contains duplicate event_ids.

| Field | Value |
|-------|-------|
| ID | C-312 |
| Tier | 2 — silent store corruption persisted across runs until a replacement event exposed it; conservation check caught it only accidentally with a misleading message |
| Source | v1.6.1 deploy incident (2026-07-02), server refresh_pipeline failure at ACLED consolidation |
| Trigger | Consolidation merge into a store containing duplicate event_ids (historical corruption or future dedup regression) |
| Location | `src/datafactory_consolidation/consolidators/acled.py` (uniqueness guard after existing_lookup) |

Resolved 2026-07-02 (store rebuilt on server; uniqueness guard + 2 regression tests in `tests/test_acled_consolidation.py::TestCorruptedStoreGuard`). Cross-ref: C-252 (the replacement logic that exposed the corruption), C-258 (conservation assertions — the accidental guard).

---

### ~~C-313: Hardcoded end-year defaults in 9 pipeline scripts — ACLED 2026 silently clipped at compile~~

Third instance of the year-rot pattern (after `AcledConfig.end_year` and `UcdpAnnualConfig.version`, both fixed in v1.6.1). `run_acled_pipeline.py` defaulted `--end-year` to 2025, so the compile step's `TemporalConfig` clipped 210,954 harvested 2026 ACLED events ("outside temporal range") — the consumer FeatureFrame served zeros for all 2026 ACLED months while UCDP showed data, verified end-to-end from the server zarr on 2026-07-05. Eight more scripts defaulted to 2026 and would rot identically on 2027-01-01. All nine now compute the default from the current UTC year; a parametrized regression test bans hardcoded `--end-year` defaults in these scripts (help text must read "default: current year"). Start years remain hardcoded by design (fixed historical anchors).

| Field | Value |
|-------|-------|
| ID | C-313 |
| Tier | 2 — silent data truncation at a layer boundary; consumer saw zeros with no error signal |
| Source | Consumer contract verification (2026-07-05), FeatureFrame pull from server zarr |
| Trigger | Calendar year advances past a script's hardcoded --end-year default (annual, automatic) |
| Location | `scripts/run_acled_pipeline.py`, `scripts/compile_acled.py`, `scripts/compile_grid.py`, `scripts/compile_vdem.py`, `scripts/compile_shdi.py`, `scripts/run_{ghspop,ghsbuilts,vdem,shdi}_pipeline.py` |

Resolved 2026-07-05 (dynamic defaults + `tests/test_pipeline_scripts.py::TestDynamicEndYearDefaults`). Cross-ref: C-311 (same incident family — v1.6.1/v1.6.2 staleness sprint), viewpoint builder end_years (shdi=2023, ghspop/ghsbuilts=2030, vdem=2025) are declared source coverage per ADR-003, NOT instances of this pattern.

---

### ~~C-288: No cross-layer schema contract tests — viewpoint column rename silently breaks compilation~~

No test verifies that a viewpoint builder's output Parquet schema matches the compilation layer's input expectations. The viewpoint produces columns like `date_month`, `latitude`, `longitude`, `best`, etc., and compilation reads those exact column names via `CompilationConfig.lat_field`, `lon_field`, `date_field`, and feature names. If a viewpoint builder renames an output column (e.g., `date_month` → `month_id`), compilation would raise `KeyError` at runtime — but no test catches this at the contract boundary. The SHDI and V-Dem paths use `PregriddedCompilationConfig` with `pgid_field`/`month_id_field`, adding a second contract surface. The gap is structural: each layer tests its own inputs and outputs, but no test validates that one layer's outputs are the other layer's valid inputs.

| Field | Value |
|-------|-------|
| ID | C-288 |
| Tier | 2 — silent pipeline breakage; no error until runtime compilation; affects every source path |
| Source | test-review (2026-06-14), Kleppmann perspective |
| Trigger | Developer renames a viewpoint output column without updating compilation input expectations, or vice versa |
| Location | viewpoint builders (`src/datafactory_viewpoint/builders/*.py` output schemas) → compilation configs (`src/datafactory_compilation/compilation_config.py`, `pregridded_compilation.py` input field names) |

Cross-ref: C-287 (assembly channel order — same class of positional/naming fragility at a different boundary), C-258 (conservation not enforced at boundaries — same inter-layer gap theme).

---

### ~~C-289: cell_generator.py has zero characterization tests — spatial backbone unpinned~~

`cell_generator.py` in `datafactory_priogrid` implements `pgid_to_latlon()`, `latlon_to_pgid()`, and `generate_grid()` — the spatial backbone for the entire PRIO-GRID system. These functions determine which geographic coordinates map to which grid cell ID. Despite being foundational, no test pins exact (lat, lon) → pgid mappings. The functions are tested only indirectly through `test_grid.py`'s higher-level tests (cell count, resolution, boundary checks). A change in rounding mode, boundary convention (cell-center vs cell-edge), or floating-point comparison would silently shift every grid placement, corrupting all downstream data. This is a characterization test gap, not a code bug — the functions work correctly today, but their exact behavior is not pinned.

| Field | Value |
|-------|-------|
| ID | C-289 |
| Tier | 3 — no current bug; risk is undetected regression from future modification |
| Source | test-review (2026-06-14), Feathers perspective |
| Trigger | Developer modifies pgid calculation, cell boundary logic, or rounding mode in `cell_generator.py` |
| Location | `src/datafactory_priogrid/cell_generator.py` (`pgid_to_latlon`, `latlon_to_pgid`, `generate_grid`) |

Cross-ref: C-268 (gaul_admin.py zero coverage — same "foundational module with zero characterization tests" pattern).

**Resolved 2026-06-18:** 6 characterization tests added in `tests/test_grid.py::TestGridCharacterization` (#198). Pins cell count, known pgid↔latlon for 5 cities, roundtrip identity for 10 pgids, bbox dimensions, and global coverage bounds.

---

### ~~C-294: Digest computation after lock release in event store~~ — RESOLVED 2026-06-24

| Field | Value |
|-------|-------|
| ID | C-294 |
| Tier | 4 — narrow race window; requires concurrent writes to same store file within milliseconds |
| Source | expert-code-review (2026-06-18), Nygard |
| Trigger | Concurrent pipeline runs on the same source write overlapping consolidated stores — digest returned by `write_store()` may not match the file on disk if another writer intervenes |
| Location | `src/datafactory_consolidation/event_store.py:59-60` (digest computed after `file_lock` context exits) |
| Resolution | Resolved 2026-06-24 (#238). Moved `compute_file_digest(path)` inside the `file_lock` block in `write_store()`. 2 Red tests verify digest matches file contents and changes on rewrite. |

In `write_store()`, the `file_lock` context manager (line 58) releases the lock when its block exits, then `compute_file_digest()` (line 60) reads the file to compute the digest. If a concurrent process acquires the lock and overwrites the file between these two operations, the returned digest describes the new writer's content, not the caller's. The provenance ledger entry would then record a digest that doesn't match what this process wrote. In practice this is unlikely — the lock release and digest computation are microseconds apart, and concurrent single-source runs are operationally rare — but it violates the provenance contract (the digest should describe exactly what was written).

**To resolve:** Move `compute_file_digest(path)` inside the `file_lock` block, or compute the digest from the bytes before writing (avoiding a second read).

Cross-ref: ~~C-267~~ (resolved — event store crash safety characterization tests), ~~C-285~~ (resolved — concurrent pipeline run safety). Part of work package: **Provenance locking**.

### ~~C-295: No timeout on LOCK_EX in file_lock()~~ — RESOLVED 2026-06-24

| Field | Value |
|-------|-------|
| ID | C-295 |
| Tier | 4 — operational annoyance, not data correctness; pipeline hangs visibly |
| Source | expert-code-review (2026-06-18), Nygard |
| Trigger | Pipeline process hangs indefinitely waiting for a lock held by a dead or stuck process whose PID was recycled (stale lock cleanup matched wrong process) |
| Location | `src/datafactory_provenance/digests_and_ledgers.py:156` (`fcntl.flock(fd, fcntl.LOCK_EX)`) |
| Resolution | Resolved 2026-06-24 (#238). Replaced blocking `flock(fd, LOCK_EX)` with non-blocking retry loop (`LOCK_EX | LOCK_NB`), 0.1s poll interval, warning after 5s, `TimeoutError` after 60s (configurable). 3 Red tests verify timeout raises, acquisition after release, and error message content. |

`file_lock()` uses `fcntl.flock(fd, LOCK_EX)` which blocks indefinitely until the lock is acquired. The function includes a 5-minute stale-lock cleanup heuristic (checks lock file age, removes if older than threshold), but `flock()` itself has no timeout — if the stale cleanup doesn't trigger (e.g., lock was recently created by a process that then hung), the pipeline blocks forever with no diagnostic output. Adding `LOCK_NB` with a retry loop and a configurable timeout (e.g., 60 seconds) would convert an indefinite hang into a fail-loud error, consistent with ADR-011.

**To resolve:** Replace the blocking `flock(fd, LOCK_EX)` with a retry loop using `flock(fd, LOCK_EX | LOCK_NB)` + sleep + timeout. Log a warning after N seconds of waiting. Raise `TimeoutError` after the limit.

Cross-ref: C-46 (ledger write idempotency). Part of work package: ~~**Provenance locking**~~ (fully resolved).

---

### ~~C-280: skip.py does not test corrupted provenance.json or .zattrs~~ RESOLVED

Resolved 2026-06-26 (#282). 8 corrupted-input tests added to `tests/test_skip_module.py`: Assembly Beige (empty provenance file raises JSONDecodeError, missing source_digest key returns should_skip=False, null digest values return should_skip=True), Assembly Red (malformed JSON raises JSONDecodeError), Export Beige (empty provenance file raises JSONDecodeError, missing output_digest key returns should_skip=False), Export Red (malformed provenance JSON raises JSONDecodeError, malformed .zattrs raises JSONDecodeError).

| Field | Value |
|-------|-------|
| Trigger | When skip.py is extended to new script types or provenance.json schema changes (trigger rewritten during review-rr 2026-06-24) |
| ID | C-280 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | `src/datafactory_provenance/skip.py` (`check_assembly_skip`, `check_export_skip`) |

Cross-ref: C-262 (resolved — skip output integrity), ADR-041.

### ~~C-281: No SHDI CIC — only source without governance document~~ RESOLVED

Resolved 2026-06-11. `docs/CICs/ShdiViewpointConfig.md` written with all 10 CIC sections: purpose, non-goals, responsibilities (value range [0,1], step function, NaN for unmapped), inputs/outputs, failure modes (FileNotFoundError, unmapped GDL codes warn+skip), boundaries (ADR-036 skip consolidation, ADR-040 intensive quantity), correct/incorrect usage, and test alignment (green/beige/red).

| Field | Value |
|-------|-------|
| Trigger | Before SHDI pipeline path is extended beyond harvest (consolidation, viewpoint, compilation) |
| ID | C-281 |
| Tier | 4 |
| Source | test-review (2026-06-10) |
| Location | `docs/CICs/ShdiViewpointConfig.md` |

Cross-ref: C-265 (SHDI harvest not wired), C-164 (WET debt — SHDI is pattern instance).

### ~~D-30~~: Config validator extraction depth — utility functions vs declarative specs — Resolved

Martin/Beck advocate extracting simple utility functions (`validate_positive_int(value, name)`) that configs call in their `__post_init__`. Each config retains its `__post_init__` method but delegates to shared validators. This preserves the existing seam, is easy to TDD, and follows the proven extraction precedent (`raster_io.py`, `temporal.py`). Hickey advocates a declarative validation spec where configs declare constraints as data and a single generic validator applies them, eliminating `__post_init__` entirely for standard constraints. The declarative approach is more elegant but harder to reverse: once configs drop their `__post_init__`, re-adding them requires touching every config class. **Recommendation: start with utility functions (lower risk, reversible), promote to declarative specs only if utility approach still feels repetitive at 12+ sources.**

**Source:** Expert code review of C-164 (2026-05-30). Cross-ref: C-07 (frozen dataclass pattern), C-164 (pattern #1).

**Resolution (2026-06-14):** Recommendation accepted: utility functions first. Declarative validation specs deferred until 12+ sources make utility approach feel repetitive. Implementation deferred to WDI sprint.

### ~~D-31~~: Harvest script consolidation — single unified script vs thin delegates — Resolved

Ousterhout argues the 9 harvest scripts should be merged into one deep `harvest.py` with `--source acled|vdem|shdi|...` dispatch via the existing Registry. The scripts are shallow modules (pure boilerplate) and 9 copies of a shallow module is worse than 1. Nygard counters that a single script creates a single failure domain — a bug in shared argparse handling blocks all 9 sources. Feathers proposes a middle path: extract a shared `HarvestRunner` function, but keep source-specific scripts as 5-10 line thin delegates that call it. This satisfies both deep-module design (Ousterhout) and blast-radius isolation (Nygard). **No resolution yet — the middle path (shared runner + thin delegates) appears to be the pragmatic choice, but extraction hasn't started.**

**Source:** Expert code review of C-164 (2026-05-30). Cross-ref: C-164 (pattern #8), C-230 (script layer zero tests).

**Resolution (2026-06-14):** Middle path accepted: shared HarvestRunner function with source-specific scripts as thin delegates. Satisfies both deep-module design (Ousterhout) and blast-radius isolation (Nygard). Implementation deferred to WDI sprint.

### ~~D-32~~: `assembled` flag vs removing features from partially-integrated sources — Resolved #105

**Positions:**

- **Add `assembled: bool` to `SourceEntry`** (#103 proposal): SHDI keeps its features in the registry but gets `assembled=False`. `get_all_features()` filters by default. Pro: registry remains a planning document; features are declared even before code exists. Con: adds a second source of truth (flag vs filesystem); flag can drift from reality; every `get_all_features()` caller must understand the default.

- **Remove SHDI features and phantom downstream entries** (Martin, Hickey, Kleppmann): Delete SHDI's `features` tuple and the SHDI Viewpoint / SHDI Compilation entries from `PIPELINE_SOURCES`. Re-add when code exists. Pro: zero code changes to `get_all_features()`; registry stops lying; simpler. Con: registry loses its planning role; source exists in registry with no features (confusing?).

- **Create separate function `get_assembled_features()`** (Kleppmann): Leave `get_all_features()` unchanged (returns all 79). Add a new function for consumers that need only assembled features. Pro: no breaking change, explicit semantics. Con: two functions for overlapping concepts.

**Key tension:** Is the source registry a planning document or a deployment document? The `assembled` flag says both; removing features says deployment-only. The answer determines whether future sources should be declared before or after their code is written.

**Source:** expert-code-review (2026-06-03). Cross-ref: C-235, D-30 (config validator depth).

### D-33: Pipeline-path information — registry field vs standalone mapping vs convention

**Positions:**

- **Add `pipeline_path` field to `SourceEntry`** (Ousterhout, GoF): An enum or literal `"event" | "raster" | "static"` on the harvest-level entry. One source of truth. `generate_status.py`, `test_operational_integration.py`, and future tools derive behavior from it. Pro: eliminates information leakage across 4 files. Con: registry grows; pipeline path is a reporting/operational concern, not a data-model concern.

- **Keep as standalone mapping in `generate_status.py`** (plan proposal, WET-before-DRY): The status page script owns its own mapping. Extract to registry only when a second consumer needs it. Pro: keeps registry simple; one consumer, one mapping. Con: mapping will drift; `test_operational_integration.py` already needs the same information and hardcodes its own version.

- **Derive from conventions** (Hickey): Standardize artifact paths (`data/compiled/{source_id}/grid.npy`). The status page probes predictable paths instead of maintaining a mapping. Pro: zero maintenance; self-healing. Con: requires all sources to follow the convention (they currently don't); retrofit cost.

**Source:** expert-code-review (2026-06-03). Cross-ref: C-236 (artifact mapping maintenance), C-164 (cross-layer WET).

### ~~D-34: Provenance enforcement location — library gate vs pipeline gate vs both~~ — RESOLVED

Resolved 2026-06-10 (review-rr strategic curation). Both approaches implemented: library-level digest gates in `datafactory_provenance/skip.py` (ADR-041: `check_assembly_skip`, `check_export_skip`, source-digest verification in `export_zarr.py` and `generate_consumer_data.py`), and pipeline-level gates via EXIT trap status page and health check step in `refresh_pipeline.sh`. The Hickey position ("both, separated") was adopted in practice. C-253 (the concrete concern) is resolved.

| Field | Value |
|-------|-------|
| ID | D-34 |
| Source | expert-review (2026-06-08), derived-artifact drift audit |
| Perspectives | Martin/Ousterhout (library gate), Nygard (pipeline gate), Hickey (both, separated) |
| Resolution | Resolved. Both approaches adopted: library gates (ADR-041, commit 975b401) + pipeline gates (EXIT trap, health check). |

Cross-ref: ~~C-253~~ (resolved — the concrete concern), C-147 (no pipeline orchestrator — related structural gap).

---

### D-35: Test scope — exhaustive verification vs minimum viable testing

| Field | Value |
|-------|-------|
| ID | D-35 |
| Source | expert-method-review (2026-06-08), data soundness audit |
| Perspectives | Betancourt/Gelman (exhaustive computational faithfulness — verify every intermediate representation against the DGP, posterior predictive checks at each boundary), Hyndman (minimum viable testing — count conservation at boundaries plus known-answer tests on synthetic data is sufficient; exhaustive checking costs more than the bugs it catches), McElreath (generative model — write a DGP simulator and test the pipeline against synthetic data with known answers; covers both camps) |
| Resolution | Unresolved. Recommendation from audit: start with minimum viable testing (count conservation at all layer boundaries, digest gates on derived artifacts), then add generative/synthetic tests for the highest-risk paths (ACLED dedup, UCDP survivorship). Exhaustive per-cell verification is infeasible at 259k cells × 456 months. |

Cross-ref: C-256 (no testable definition of data soundness), C-258 (count conservation gaps at consolidation/viewpoint). Part of work package: **Data soundness**.


### ~~D-36: Skip decision location — inline in script vs. provenance package function~~

| Field | Value |
|-------|-------|
| ID | D-36 |
| Source | expert-code-review (2026-06-09), Martin/Ousterhout vs Beck/Hickey |
| Perspectives | Martin/Ousterhout (extract to `datafactory_provenance` — the 5-location WET pattern crossed the abstraction threshold; the provenance.json schema is leaked to all consumers; a `should_skip()` function with a clean interface would concentrate the complexity), Beck/Hickey (premature — only 2 scripts use skip today; the user's WET-before-DRY preference says write 3 times before abstracting; extracting a broken pattern is worse than duplicating a broken pattern; fix C-259/C-260/C-262 first, then extract) |
| Resolution | **Resolved 2026-06-09.** Followed the Beck/Hickey recommendation: fixed correctness gaps (C-259, C-260, C-261, C-262) first, then extracted to `datafactory_provenance/skip.py` with `check_assembly_skip` and `check_export_skip`. Martin/Ousterhout were right about the threshold (5 locations); Beck/Hickey were right about the order (fix then extract). Both sides vindicated. See ADR-041. |

Cross-ref: C-164 (WET debt — digest comparison is pattern #9), C-259/C-260/C-262 (correctness gaps that should be fixed before extraction). Part of work package: **Artifact consistency**.


### D-37: Code identity in skip decisions — include git hash or not

| Field | Value |
|-------|-------|
| ID | D-37 |
| Source | expert-code-review (2026-06-09), Hickey vs Nygard |
| Perspectives | Hickey (the skip logic conflates data identity with code identity — a bug fix to assembly code would be masked by unchanged input digests; a `code_version` field in provenance.json decomplects the two concerns), Nygard (adding code version creates operational cost — every code deployment invalidates the skip cache, defeating the feature; documentation changes and unrelated fixes would trigger unnecessary rebuilds; the false-negative cost is already manageable) |
| Resolution | Unresolved. Pragmatic middle ground proposed: hash the specific script file (`sha256sum assemble_grid.py`) rather than the repo HEAD. This catches assembly code changes without invalidating on unrelated commits. Not blocking for initial ship — acceptable to defer. |

Cross-ref: C-259 (skip completeness — same skip logic), D-36 (skip decision location — same feature). Part of work package: **Artifact consistency**.

### D-38: Script extraction timing — when does WET in scripts/ cross the extraction threshold

| Field | Value |
|-------|-------|
| ID | D-38 |
| Source | expert-code-review (2026-06-18), Martin vs Feathers vs Beck |
| Perspectives | Martin (scripts/ has crossed the extraction threshold — 14 scripts averaging 200+ lines, with repeated argparse/logging/EXIT-trap patterns; extract now to prevent accidental behavioral drift between copies), Feathers (scripts are the seams that make the system testable — if extraction breaks the seam, the characterization tests lose their anchor; extract only when the next functional change touches 3+ scripts simultaneously), Beck (wait for the WDI sprint — that's the 3rd instance of the pipeline script pattern, which triggers the WET-before-DRY rule; extracting before the 3rd data source risks encoding an abstraction that doesn't generalize) |
| Resolution | Deferred by design (2026-06-24, #239). All three perspectives have merit. D-31 resolved the harvest-script subset (shared HarvestRunner + thin delegates). Pipeline scripts are the next candidate. WDI sprint provides the 3rd pipeline script instance to validate the abstraction — extraction before that risks encoding an abstraction that doesn't generalize. Revisit when WDI pipeline script is implemented. |

Cross-ref: D-31 (resolved — harvest script consolidation), C-164 (WET debt), C-230 (resolved — script layer tests). Part of work package: **WET-before-DRY**.

### D-39: Viewpoint builder abstraction — Protocol extraction vs explicit repetition

| Field | Value |
|-------|-------|
| ID | D-39 |
| Source | expert-code-review (2026-06-18), GoF vs Hickey |
| Perspectives | GoF (the 6 viewpoint builders — UCDP annual, UCDP candidate, ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI — share a common Template Method shape: read consolidated/raw, apply temporal alignment, write viewpoint Parquet. A `ViewpointBuilder` Protocol with `build(config) -> ViewpointResult` would enforce the contract and let composition tests verify new builders automatically), Hickey (the builders are simple-and-boring; a Protocol adds a layer of indirection that conflates the interface with the implementation. Each builder's build function already has a clear signature. Extract a Protocol only when the 7th builder arrives and proves the need — adding indirection to working code to satisfy an aesthetic principle is the wrong trade-off at this scale) |
| Resolution | Unresolved. With 7 builders now (6 existing + SHDI), the threshold for extraction is approaching. But each builder has genuinely different inputs (Parquet vs GeoTIFF vs CSV) and different temporal semantics, so a Protocol would need to be very thin. Defer until builder count reaches 8 or a consumer needs to iterate all builders programmatically. |

Cross-ref: D-30 (resolved — config validator extraction), C-07 (frozen dataclass pattern), C-164 (WET debt). Part of work package: **Viewpoint architecture**.


### D-40: DGP check module placement — source-agnostic `event_validation.py` vs per-source definitions

| Field | Value |
|-------|-------|
| ID | D-40 |
| Source | expert-code-review of sprint issues (2026-06-19), Martin vs GoF |
| Perspectives | Martin (`event_validation.py` docstring declares "No knowledge of specific data sources" — adding ACLED event-type enums and UCDP date_prec ranges violates this contract), GoF/Kleppmann (Strategy pattern: define DGP checks as callables per source module, inject into a source-agnostic `validate_dgp_assumptions()` framework in `event_validation.py` — framework stays source-agnostic, checks live in source modules), Hickey (the checks are pure data — a list of callables — and should be defined close to the source they describe, not in a shared module that becomes a magnet for source-specific knowledge) |
| Resolution | Unresolved. All perspectives converge on: framework function in `event_validation.py`, check definitions in per-source modules (e.g., `ucdp_annual.py`, `acled.py`). Sprint issue #212 should follow this pattern. |

Cross-ref: C-257 (no input data validation), D-35 (test scope). Part of work package: **Data soundness**.

---

## Deferred by Design

### C-10: Ontology vocabulary overhead
Terms like "Source Nodes," "Compilation Edges," "Explicit Non-Entities" are precise but add conceptual overhead. For a 7-package project, governance is heavy. **Accepted: governance has proven itself (ADR-008 caught bugs in 3 audits). Cost is documentation maintenance, not development velocity.**
**Source:** Ousterhout

### C-38: Version string year offset assumes 21st century
`_DOT9_YEAR_OFFSET = 2000` / `_CANDIDATE_YEAR_OFFSET = 2000` in `ucdp_dot9.py:50` and `ucdp_candidate.py:43`. Breaks silently for pre-2000 or post-2099 data. UCDP data starts 1989 (annual uses full version strings). **Trigger: never (2099 is 73 years away).**
**Source:** Repo assimilation

### C-41: Digest truncation collision risk
`DIGEST_TRUNCATE = 16` hex chars = 64-bit space. 50% collision at ~4B items. Fine at ~2M events. **Trigger: consider when total records exceed 100M or digests are used as unique keys.**
**Source:** Repo assimilation

### C-06: Provenance logic should be a composable utility
Every module independently calls `append_ledger_entry()` with its own format. A `@provenance` decorator or context manager would centralize ~50 lines of boilerplate across 4 modules. Kleppmann (Ch.12 pp.499-501) advocates Unix philosophy: composable tools with uniform interfaces. Our current approach (each module calls the same function with its own format) is composition via shared function, not shared abstraction — acceptable at this scale. **Accepted: explicit > implicit for now.**
**Source:** Hickey. DDIA Ch.12 pp.499-501.

### C-07: Frozen dataclass pattern repeated
14 config classes (10 harvester + 4 viewpoint) follow the same frozen-dataclass-with-`__post_init__` pattern. No shared Protocol or base. A declarative validation approach or `ValidatedConfig` Protocol would reduce duplication. Kleppmann (Ch.4 p.127) argues schemas serve as documentation that "cannot diverge from reality" — our frozen dataclasses with `__post_init__` validation are effectively runtime schemas. **Accepted: explicit repetition is simple and readable; each config is its own schema.** See D-30 for the utility-functions vs declarative-specs disagreement.
**Source:** Hickey. DDIA Ch.4 p.127. Updated: expert code review C-164 (2026-05-30).

### C-32: Source registry returns `Any`
`fetch_source` returns `Any` (widened from `Path` for candidate's `list[dict]`). Sources, consolidators, and builders are intentionally heterogeneous — each has a different signature. The three strategy registries (aggregation, survivorship, temporal_distribution) already use precise types. Kleppmann (Ch.4 p.126) notes dynamically generated schemas are an acceptable trade-off when sources have heterogeneous structures. **Accepted: heterogeneous signatures are by design.**
**Source:** GoF, Hickey (expert review 5). DDIA Ch.4 p.126. Reclassified 2026-04-06.
