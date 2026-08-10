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

## C-343 — the deploy that wasn't (2026-08-08)

Registered Tier 2 — the first Tier 2 added since C-337, and the only entry in the fails-green
cluster found by **looking at production** rather than by reading the repository.

**How it surfaced.** While sizing the blast radius of a Story 2 (#423) change, the question came up
of when an edit to `refresh_pipeline.sh` actually reaches the server. Reasoning about it produced a
hypothesis; a throwaway git repository tested it; the test said bash buffers the script and never
re-reads it, so shell changes lag one run. That prediction implied the deploy procedure might be
ambiguous, so the operator was asked to run one command on the host. It came back `v1.11.0` — the
tag file. The next command came back `v1.10.0` — the working tree. The third came back
`views_frames-1.0.0.dist-info`.

**The release cut specifically to fix C-337 had been inert on the server for five days,** and the
floor it raised was still the frozen 1.0.0 that C-337 is about. The tag file read correctly. The
pipeline was green. Nothing anywhere had a failure mode that said otherwise.

**A retraction inside the same hour.** On seeing views-frames 1.0.0 the first framing was *"the
first fails-green instance with production consequences."* That was wrong, and checking the diff
before believing it showed why: `git diff v1.10.0..v1.11.0` touches no `src/` file and no pipeline
script — only `pyproject.toml`, `uv.lock`, and three GitHub workflows that never run on the host.
Production imports four non-estimator symbols from views_frames. No number was ever wrong, and PyPI
consumers were never exposed, because the published wheel carried the correct floor throughout. The
damage was to what could be *claimed*, not to what was produced. The corrected framing is in the
entry.

**Remediated the same session**, with the operator at the keyboard: the three documented steps ran,
`uv sync` moved views-frames 1.0.0 → 1.10.2 and views-datafactory 1.10.0 → 1.11.0, and
`FeatureFrame` was imported on the host afterwards — because a ten-minor-version jump that nobody
has watched import is a belief, not an observation. The entry stays **open**: nothing prevents
recurrence.

**One method note.** The `uv sync` command was first given as `sudo -u views-deploy sh -c …`, which
does not source `~/.profile`, so `uv` was not on the PATH and it failed. That mistake is already a
recorded lesson in this project. It failed loudly and cost thirty seconds — which is the whole
difference between it and everything else in this cluster.

---

## C-342 — the lockfile nobody can catch being stale (2026-08-08)

`/register-risk` after `/code-review medium` on **#430**, the first story of epic #421.

**One entry registered.** C-342, Tier 3: `uv sync` rewrites `uv.lock` in place whenever
`pyproject.toml` has moved, and `.github/workflows/ci.yml` runs it before every job — so a pull
request whose committed lock disagrees with its committed `pyproject.toml` passes CI, because CI
repairs the lock in its own checkout, tests the repaired version, and discards it. The stale lock
stays in git. Verified by doing it: `uv lock --check` says *"The lockfile at `uv.lock` needs to be
updated"* where `uv sync` silently fixes and proceeds. Added to the **mechanisms that fail green**
cluster, which is now nine.

**Where it came from is the point.** It was not found by looking for it. It surfaced while
drilling the guard for C-337 — the cluster's own rule (*drill every guard by breaking it*) turning
up a defect adjacent to the one being guarded, for the second time in a week.

**It also weakens the guard that found it,** and the entry says so: `test_dependency_floors.py`
reads the committed lock, and only the way the suite happens to be invoked (`uv run` / `uv sync`
refresh first) makes that a real resolution rather than a stale one.

**Deliberately not fixed in #430.** The instrument is `uv lock --check` in CI, and a pytest cannot
substitute — by the time pytest runs, the lock has already been repaired. Proposed for **#424**
(Story 3, gates that run somewhere other than one laptop). Fixing it inside a story scoped to one
test file would have been the scope creep the epic's own conventions forbid.

**C-342 was wrong when first written, and `/review-diff` caught it the same hour.** The entry said
*"CI runs `uv sync` before every job … passes all four jobs."* `ci.yml` has **five** jobs. `docs` runs
bash only and needs no `uv`; `import-enforcement` is gated to `main`. A pull request to
`development` runs `uv sync` in **three**. The claim was not observed — it was inferred from four
`grep` hits, which is the exact move C-336 is about, committed inside an entry describing a
different flavour of the same thing. Corrected, and the `ci.yml:24,42,60,99` citation replaced with
the job names, since C-336's own lesson is that line citations rot. Recorded here rather than
buried, because an entry that was wrong on the day it was written says more about how this project
reasons than a clean one does.

**Six findings from the same review were not registered.** Two were fixed in place in #430 as
defects in its own docstring — a claim that `packaging` is guaranteed by matplotlib, which
`pyproject.toml` itself marks for removal (C-334); and `test_allow_list_has_not_rotted` passing
unconditionally once its allow-list empties, which is the "test that cannot fail" standard the same
file invokes to justify deleting two other guards. Two were documentation-rot observations below
the register's bar after the 2026-08-04 curation cut it from 45 open to 39. Two were refuted on
inspection: a dict-collision path that this project's single `requires-python` and marker-free
dependencies cannot reach, and a `SpecifierSet` ordering claim that is simply wrong — `packaging`
canonicalises to a sorted tuple.

---

## `/review-rr strategic` — curation (2026-08-04)

**C-324 resolved as stale.** It described a live credential in a server log; the token was revoked
2026-08-01 (GDL allows one per account, so issuing the replacement forced it), the leaking harvester
was superseded when the server moved to v1.11.0, and the log itself no longer exists — destroyed by
C-339. Every remediation the entry prescribed had happened. **The register had gone stale in exactly
the way it keeps warning about**, and a reader would have acted on exposure that ended three days
earlier.

**The "fails green" cluster named** — eight open entries (C-317, C-331, C-336, C-337, C-338, C-339,
C-340, C-341) that are symptoms of one root cause: mechanisms that report success while not doing
the thing. Individually small; together they say this project's characteristic failure is *silence,
not error*. The cluster carries a design rule rather than eight separate fixes: absence of an error
is not evidence of success, so any new mechanism needs an answer to "how would I know if this
silently did nothing?" before it ships.

**Five triggers rewritten** — C-332 (was perpetual, "any change to these files"; now names the act
that creates the exposure), C-70, C-72, C-333, and C-339 (which had stated a *rule* where a trigger
belongs).

**Five demoted to tech-debt backlog** following the C-136 precedent: C-46, C-116, C-117, C-147,
C-155 — mechanical, single-file, never fired, and loud rather than silent if they ever do. C-70 and
C-72 were on the demotion list and were kept, because their triggers had just been made concrete;
demoting an entry immediately after making it actionable is incoherent.

**Not registered, per skill rules** — blind spots go in the report, not the register: bus factor (one
person holds every credential, all server access, and the operational knowledge; unnamed across 341
entries), upstream source discontinuation, and whether a past release's grid can still be rebuilt.

Counts: 45 → 39 open, Tier 3 12→11, Tier 4 25→20, struck-through 110→115.

**Method note.** The cluster table first used `| C-317 |` as its leading column, which collides with
the summary-row format, and the repair used `replace(..., 1)` — which hit the *first* match and
silently bolded eight real summary rows. Two edits, both plausible, both wrong, neither raising an
error. The guards caught it. The cluster demonstrated itself during its own authoring.

## C-340 and C-341 registered (2026-08-04)

Two findings from the v1.11.0 close-out that had been acted on but never tracked. Both share the
property that made this whole week's work necessary: **they fail green.**

**C-340 — auto-merge fails silently, two ways.** `gh pr merge --auto --<method>` refuses to change
the method on an already-armed PR and reports nothing; during v1.10.0 that left `squash` armed on a
`development` → `main` promotion, which would have rewritten the release SHAs permanently. Caught
only by reading `auto_merge.merge_method` back. Separately, pushing a follow-up commit to a branch
whose PR has already auto-merged orphans the work — #416 merged the instant CI went green, and two
files were simply not on `development`, with `git push` reporting success. The only signal was
`commits=1` contradicting a remembered second push. Tier 3: recoverable, but live on every PR here.

**C-341 — deploy gates run only where someone types pytest.** The unexamined residual of C-320's own
fix: gates that could not answer in CI were made to skip with a reason, which was right, and the
consequence was that they now assure only whoever runs the suite at the right moment. After v1.10.0
the branch divergence went undetected for four hours and had been silently true after every prior
release. Partially mitigated by `release-topology.yml`; the rest remain local-only. Tier 4.

Skipped as duplicates or out of scope: the unchecked `numpy`/`pyarrow`/`zarr` floors (already inside
C-337 as its open residual), the views-faoapi monitor observations (different repo), and the
four-year-old `gh` (resolved; the residual is the operator's machine). Counts: 339→341 IDs, 43→45
open, Tier 3: 11→12, Tier 4: 24→25.

## C-330 resolved, C-339 registered (2026-08-03)

**C-330 was right, then corrected into being wrong, then confirmed right.** Observed on the server:
the logrotate config rotated `/root/views-datafactory/logs/refresh.log`, a path the pipeline left when
it moved to the service account, and `missingok` made it exit successfully every night for four
months. The file mode was `644` — world-readable, exactly as originally claimed and later downgraded
to "inferred, not observed". The 2026-07-31 retraction found an archived plan saying rotation was
configured, which was true, and concluded the alarm was false. **Existence was never the question;
efficacy was.** Fixed: correct path, `monthly`, `create 0640`, `su views-deploy`, and `missingok`
removed so a wrong path is loud. Verified by dry run.

**C-339 — I destroyed the log while fixing its rotation.** I handed the operator a multi-line
`sudo tee ... <<'EOF'` heredoc to paste; their terminal joined the first two lines, so `tee` took the
log path as a second output file and, running as root, overwrote it. 528 KB → 150 bytes,
unrecoverable — there was no rotated copy, because the rotation being fixed had never run. Lost:
four months of run output. Not lost: provenance ledgers, status page, ping history, git. Tier 3 for
the *mechanism*, not the damage: a root-privileged command whose failure mode is writing to an
unintended path, handed over to be pasted blind. Standing rule adopted — commands given to a human
are one line; multi-line content goes in an editor. Counts: 338→339 IDs, 43 open unchanged,
Tier 3: 10→11, Tier 4: 25→24.

## C-335 resolved, C-338 registered (2026-08-03)

The serving-path monitor is live: Better Stack on the public `status.html`, 3-minute interval,
verified **Up** at ~27 ms with a test alert delivered and read. The unbounded case C-335 was about —
Caddy stops, pipeline keeps succeeding and pinging, nothing ever notices — is closed.

Two qualifications kept in the closure rather than smoothed away: detection is by e-mail, not phone;
and the **freshness half is not in the vendor at all**, because Better Stack gates keyword matching
behind a paid plan. That half became `.github/workflows/serving-freshness.yml` — daily, on GitHub, so
genuinely external. Registered as C-338 (Tier 4: late notice of stale data, not wrong data).

**ADR-051's specification of the content check was itself wrong, and paying would not have fixed it.**
It said to alert when the body "does not contain the healthy marker". The page carries a legend —
`● OK ● Stale ● Missing` — so those words appear on *every healthy page*; the first implementation
reported one of each against a perfectly healthy server and would have opened an issue every day
until someone muted it. Caught by drilling the check against the live page before shipping. The
workflow parses per-cell `title="<status>"` attributes instead. Counts: 337→338 IDs, 43 open
unchanged (one closed, one opened), Tier 2: 3→2, Tier 4: 24→25.

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
