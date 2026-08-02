# Risk register — change log

Narrative history of how `technical_risk_register.md` evolved: what was registered, what
was corrected, and what was retracted. Newest first.

**Why this file exists.** The register header used to carry this narrative inline, where it
competed for space with the header's other job — being an index. The search-window guard
(`test_falsification_merge_readiness.py`, 8000 chars) then forced someone to delete history
whenever the two collided. On 2026-08-02 two entries were retired purely to reclaim 1200
characters, not because they had stopped being true. **Both are restored below.** Separating
the two jobs keeps the index findable and lets this record grow without anything being
deleted to make room (#404).

**The corrections are the valuable part.** An entry registered, then retracted, then partly
re-confirmed by observation (C-330) says more about how this project reasons than any clean
entry could.

---

## C-337 registered (2026-08-02)

A loose dependency floor **froze** an estimator version. `views-frames>=1.0` let `uv.lock` pin
**1.0.0**, and `uv lock` keeps an existing pin while it still satisfies the constraint — so every
CI run and local test since June executed against pre-amendment MAP/HDI semantics (`tip_mass` 0.5,
pre-1.2.0 HDI tower, pre-1.3.0 zeroing). views-frames changed the statistics three times in 1.2.0,
1.3.0 and 1.9.0, all shipped MINOR, so nothing looked breaking. **The audit that checked this floor
got it wrong**: it asked "what does this package import?" (four symbols, no estimators), verified
they work at 1.0.0, and stopped. A floor constrains the resolver, not the import list — and the
audit never opened `uv.lock`, which is where the damage was. Same failure class as C-336, committed
inside the audit written about it, one day later; caught by the operator, who knew the estimator
history. Floor raised to `>=1.10.2`, lock moved, guard added. Counts: 336→337 IDs, 42→43 open,
Tier 2: 2→3.

## C-336 registered (2026-08-02)

Full base-docs audit — all 54 ADRs and 34 CICs checked against the code as it exists. Three
drift mechanisms, all fixed: (1) ten `file.py:NNN` citations, three already pointing at blank
lines, all replaced by symbol names; (2) ADR-006/ADR-010 cite `lab_grid/`, a package
**views-metric-lab deleted** in their commit `6e1a34d` — ADR-010 even asserts it "remains as-is
for the lab's own use", a claim about another repo that stopped being true without anything here
failing; (3) a CIC cited a test file that has never existed, hedged with "(if present)" — a claim
qualified into unfalsifiability, which is why nobody ever corrected it. Also written:
`docs/CICs/load_dataset.md`, the public contract per ADR-050, absent while 32 config dataclasses
had contracts — the CICs had been written where writing was cheap, not where dependency was heavy.
**Near-miss recorded:** `audit_data_parity.py` was on the stale list until checked — it exists in
views-models. Deleting it would have been C-330's error committed inside the audit written to catch
it, so the new guard deliberately does not assert that every referenced path exists. Counts:
335→336 IDs, 41→42 open, Tier 4: 23→24.

## C-335 registered (2026-08-01)

**nothing watches the serving path.** The heartbeat answers "did the pipeline run?"; nothing answers "can a consumer read anything?" If Caddy stops serving while the host stays up, the pipeline still succeeds and still pings, so the check stays green while every consumer gets nothing — detected never. Host-death is bounded (~32d: 30d period + 48h grace); Caddy-death is not. Tier 2 because it reports healthy while broken, the shape of views-faoapi's C-50/C-170. ADR-051: keep the push heartbeat (Better Stack has **no `/start`** — verified — so migrating would discard C-317's OOM mitigation) and add an external poll. Counts: 334→335 IDs, 40→41 open, Tier 2: 1→2.

## C-330 corrected (2026-07-31, hours after registering it)

the falsification audit caught my own error: the sweep grepped the repo for logrotate config, found none, and concluded the log was unrotated and growing without bound. `reports/archive/product_development_plan03.md:97,136,177` says rotation was configured on the server on 2026-03-31. **Absence in the repo was read as absence in the world** — the third instance of that failure mode in this repo inside a week (with the "zero secrets in git" audit behind þing-02's Á-1, and ADR-026:97 behind #391). The entry is retitled and narrowed: what survives is that the rotation is documented *only* in an archived March product plan and nowhere in `docs/guides/`, which is why the sweep missed it and the next reader will too; and that the file-mode claim was inferred from the absence of `chmod`/`umask` in scripts, never observed. Counts unchanged.

## Five-angle security sweep (2026-07-31, #388)

seven entries, none urgent, all grounded in file:line. C-327: a Caddy basic-auth password was published in git history (3 commits, ancestors of main, public since 2026-07-27) — **tested live and dead (401)**; residual is a password *pattern*, and the process lesson that the pre-public audit searched code and config but not post-mortem *prose*. C-328: HEAD re-publishes the username the go-public redaction removed. C-329 (Tier 3, highest consequence): the PyPI-publishing job runs unpinned actions while holding OIDC rights — a poisoned wheel needs no secret to leak. C-330: `refresh.log` world-readable and unrotated (`logs/` gitignored same day, closing the accidental-commit path). C-331: HEARTBEAT_URL capability URL on the curl command line. C-332 (Tier 3): redaction incomplete — `_redact_url` ignores URL userinfo, `zarr_path` interpolated raw into 7 messages, netrc exceptions log contents, `BasicAuth`/`_TokenState` reprs. C-333: UCDP's custom auth header survives cross-host redirects. Verified clean: no `.env`/`.netrc`/key ever committed, harvest tokens never in git, heartbeat URL never committed, no CI authenticates to the data server, zero `${{ secrets.* }}`, OIDC-only publishing, no `pull_request_target`, ledgers and zarr attrs carry no URLs. Header counts: 326→333 IDs, 32→39 open, Tier 3: 7→9, Tier 4: 18→23.

## CI enforcement at the platform (2026-07-31)

C-320's recurrence note corrected: the first diagnosis (`;` vs `&&` in the merge chain) was falsified by PR #372, where `gh pr merge --auto --squash` merged with `test` still pending. Real cause: neither `development` nor `main` had branch protection (404 Branch not protected) and repo auto-merge was disabled, so every PR was mergeable on open and `--auto` degraded to a plain merge. Fixed same day: required checks `lint`/`typecheck`/`test` on development, plus `import-enforcement` on main, `enforce_admins: true` on both, PRs required (0 approvals), force-push/deletion off, auto-merge enabled; documented in `docs/guides/publishing_to_pypi.md`. Rule of record: a client-side gate is advisory; enforcement lives in required status checks.

## Epic #376

pandas becomes an output format, not a dependency (2026-07-31). pandas moved to `[project.optional-dependencies]` and matplotlib to the dev group (zero `src/` imports); imports made lazy so `from datafactory_query.defaults import DEFAULT_REMOTE` — a stdlib-only module and 29 of the 35 datafactory imports across views-models — no longer loads pandas; `tests/test_import_purity.py` guards it, and the guard was **observed red** before being trusted. C-325 registered (Tier 4: CI locks pandas 2.3.3 while fresh installs resolve 3.0.5 — mitigated by running the full suite under 3.0.5: 2301 passed, 0 failed, counts identical to the locked run). C-326 registered (Tier 4: the extra gates nothing today — xarray is the sole pandas carrier, verified per-package in a clean venv — so this makes pandas *not imported*, not *not installed*; the `ImportError` paths are unreachable until #381 resolves; REP/CRP condition recorded — one wheel, two audiences). D-42 registered-and-resolved (relocating the pandas adapters to views-pipeline-core: rejected — breaks the published ADR-050 contract, ADR-040/048 semantics belong beside the registry, no reduction in version votes; end state is deletion, not relocation, which #379's file split made cheap). Header counts: 324→326 IDs, 30→32 open, Tier 4: 16→18, disagreements 41→42.

---

## Where the findings came from

Every audit, review, and incident that contributed entries to the register, oldest first.
This list lived on the register's `**Source:**` header line and grew by one item per audit
— 71 entries and 2783 characters by 2026-08-02. The search-window guard's own docstring
named it as a growth vector (*"wide enough to find 'N open concerns' despite Source-line
growth"*), so the header was being defended against this list rather than relieved of it.
Moved here as part of #404; the header keeps a pointer.

- Multi-expert engineering review
- repo assimilation
- falsification audits
- expert code review (Martin
- GoF
- Feathers
- Nygard
- Kleppmann
- Ousterhout
- Hickey
- Beck)
- magic-values compliance audit
- stale-zarr incident 2026-04-24
- pipeline verification audit 2026-04-30
- ACLED integration test review 2026-05-02
- ACLED test review 2026-05-03
- ACLED compilation test review 2026-05-05
- base documentation review 2026-05-07
- ACLED harvester test review 2026-05-07
- GHS-POP harvester test review 2026-05-18
- GHS-POP viewpoint test review 2026-05-19
- PR #53 review 2026-05-20
- GHS-POP memory falsification + expert code review 2026-05-20
- repo-assimilation 2026-05-20
- ADR-031 compliance review 2026-05-21
- harvest caching expert code review 2026-05-21
- PR #59 falsification audit round 2 2026-05-21
- provenance/shapefile expert code review 2026-05-21
- GHS-BUILT-S review-rr triage 2026-05-22
- GHS-BUILT-S coverage parity falsification 2026-05-22
- GHS-BUILT-S visual audit falsification 2026-05-22
- GHS-BUILT-S visual audit run 2026-05-22
- C-190 resolution 2026-05-23
- GHS-BUILT-S merge-readiness falsification 2026-05-23
- pre-merge sprint (C-191/C-192/C-168/C-174) 2026-05-23
- GHS-BUILT-S merge-readiness falsification round 2 2026-05-23
- repo-assimilation v1.2.20 2026-05-24
- tech-debt-cleanup investigation 2026-05-24
- review-rr strategic + prioritize 2026-05-24
- review-base-docs 2026-05-25
- V-Dem test coverage parity falsification 2026-05-26
- V-Dem ADR/guide compliance falsification 2026-05-26
- V-Dem SOLID/package/file-org falsification 2026-05-26
- review-rr strategic curation 2026-05-26
- review-base-docs 2026-05-26
- V-Dem visual audit falsification 2026-05-26
- V-Dem visual audit documentation falsification 2026-05-26
- sprint S4 standalone fixes (C-175/C-129/C-149) 2026-05-27
- merge-readiness falsification (C-222) 2026-05-27
- review-rr strategic curation 2026-05-28
- SHDI review-diff 2026-05-29
- expert code review C-164 2026-05-30
- digest verification expert code review + 3 falsification audits 2026-06-02
- preflight netrc falsification 2026-06-02
- status page understanding falsification 2026-06-04
- status page fix plan falsification 2026-06-04
- ADR-040 scoping 2026-06-05
- test-review area-majority effort 2026-06-05
- review-base-docs area-majority effort 2026-06-05
- review-rr strategic curation 2026-06-06
- pre-deployment audit 2026-06-07
- derived-artifact drift expert-code-review 2026-06-08
- data soundness expert-method-review 2026-06-08
- content-addressed skip investigation 2026-06-09
- pipeline gap audit 2026-06-10
- tech-debt-cleanup pre-deploy 2026-06-10
- test-review deep coverage audit 2026-06-10
- review-rr strategic curation 2026-06-10
- repo-assimilation v1.3.0 2026-06-16
- expert-code-review register-risk 2026-06-18
- test-review v1.4.0 2026-06-24

---

Earlier history: `git log reports/technical_risk_register.md`.
