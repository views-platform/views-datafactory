# Where this suite declines to run, and why

**Measured 2026-11-12** by `tests/test_skip_inventory.py`'s own walker, which is the same
code the ratchet asserts with — so this document and the guard cannot drift on the numbers.

**61 skip sites across 22 test modules.** 12 are `@pytest.mark.skipif` decorators, 49 are
`pytest.skip(...)` calls inside a test or a fixture, and 0 are module-level `pytestmark`.

Issue #554 measured **62** before #550 landed. The one that went is exactly the module-level
`skipif` #550 deleted from the spatial delivery guards, which is a small independent
confirmation that it actually went rather than being weakened.

## Why this document exists

The delivery defect this epic exists to fix shipped because a correct test stopped running and
nothing said so. 47 spatial tests passed, one skipped, and in every report anyone read the skip
was indistinguishable from a pass. The remedy is not "convert all 61" — that is unbounded, and
most of them are right. The remedy is that **the number cannot rise without someone writing
down why**, which is what `tests/test_skip_inventory.py` enforces, and that each group has a
stated disposition, which is what this document is.

## Two whole markers were worse than skipped

`tests/conftest.py` removes every item marked `falsification` unless `--run-falsification` is
passed, and every `consumer` item unless `--run-consumer` is passed. **Neither flag appears
anywhere in `.github/workflows/`, `scripts/` or `docs/`.**

Until 2026-11-12 those items were dropped from the collection without telling pytest, so they
appeared in the run's counts not at all — not passed, not failed, not even skipped. Two markers
of coverage were withheld on every run and no line of output said so.

Fixed under #554: the hook now calls `pytest_deselected`, so they are reported as deselected,
and a terminal summary names the count and the flag that would include them. On this machine a
default run of a marked module prints:

```
------------------------- coverage withheld by marker --------------------------
18 falsification test(s) deselected -- pass --run-falsification to run them
```

Nothing asserts that number. Making it visible to a reader is the whole of the fix; a ratchet on
it would flutter for the same reason the skip *count* cannot be ratcheted — see below.

## Why the ratchet counts declared sites, not actual skips

The obvious design is to assert how many tests skipped in a run. It cannot work here, and the
reason is worth recording because it is the second-order trap in this story.

How many tests skip depends on the environment. This machine has `data/`; a CI runner does not.
`test_falsification_deploy_v160` skips or does not depending on whether `HEAD` sits on a `v*`
tag, which flips on every release commit. Both `development` and `main` require the `test` job
and set `enforce_admins: true`, with no override for the repository owner. **A guard that
flutters would wedge the branch closed for reasons unrelated to the code** — the
permanently-red-CI failure already on the register, which is worse than the gap it would close.

An inventory of *declared* sites is a property of the source. It is identical on every machine,
on every commit, in CI and at the keyboard.

## Dispositions by group

| Group | Depends on | Sites | Disposition |
|---|---|---:|---|
| **A** | real GAUL crosswalks or the L1 shapefile | 6 | **Accepted.** Reviewed under #550. |
| **A/B** | the consolidated store **and** real GAUL | 2 | **Accepted**, with CI-runnable siblings added. |
| **B** | the consolidated UCDP store alone | 3 | **Accepted.** |
| **C** | assembled grid or zarr store on disk | 19 | **Accepted.** |
| **D** | a built viewpoint or compiled grid on disk | 4 | **Accepted.** |
| **E** | a sibling repository checkout | 9 | **Accepted.** Environmental by construction. |
| **F** | git refs, deep checkout, or authenticated `gh` | 7 | **Accepted**, with one registered defect. |
| **G** | the live data server | 2 | **Accepted.** |
| **H** | a gold-set reference parquet, not committed | 2 | **Accepted.** |
| **I** | a file committed to this repository | 2 | **Wrong. Should not be able to skip.** |
| **J** | an uncommitted source fixture or report directory | 5 | **Accepted**, two of them weakly. |

### A — real geography (6 sites, plus 2 that also need the store)

`test_falsification_adr043.py` (3) · `test_falsification_round2.py` (1) ·
`test_falsification_shdi_ordering.py` (1) · `test_hierarchical_reconciliation.py` (1)

**Accepted, and this group is the one #550 examined in detail.** Each asserts a fact about the
*shipped GAUL 2024 release*: whether it contains a Gnaviyani polygon, whether the three real
crosswalks nest consistently, whether real land cells carry a `gaul2_code`, whether the harvest
produced the file at all. Synthetic crosswalks cannot stand in for any of them — a fixture
asserting that invented cells behave as invented is vacuous by construction, mutation category
M4. Converting them would have raised the CI-run count and lowered the evidence.

Each carries a comment at its skip site naming what it is a claim about.

**What #550 did instead**: the properties that belong to the *code* rather than the world now
run in CI on synthetic geography — `tests/test_synthetic_spatial_fixtures.py` and
`TestAdr053ComposedOnSyntheticGeographyGreen`.

### A/B and B — the consolidated store (5 sites)

`test_adr049_profile_contract.py` (2) · `test_adr053_production_profile.py` (3) ·
`test_pipeline_consistency.py` (1 of its 7)

**Accepted.** These are golden criteria about real events in real geography: that event 463131's
December cell-month comes down inside the real Tigray polygon, that a year across three named
Ethiopian regions reaches at least ten of their cells. Both ADRs' amendments of 2026-11-12 record
that their validation criteria belong against the served store.

Two of them additionally skip *within* the test when the Tigray event is absent from a given
store build — correct behaviour, and it reports its reason.

### C and D — pipeline artefacts on disk (23 sites)

`test_consumer_parity.py` (4) · `test_falsification_deploy_readiness.py` (2) ·
`test_falsification_executability.py` (3) · `test_falsification_staleness.py` (5) ·
`test_model_parity.py` (4) · `test_pipeline_consistency.py` (6) ·
`test_adr053_production_profile.py` (1)

**Accepted.** These read a 37 GB assembled grid, a zarr store, a built viewpoint or a compiled
grid. None can exist on a CI runner, and committing a fixture of that size is not an option.
They are deploy-gate and parity checks: they run at the keyboard and on the server, which is
where the artefacts are.

The honest risk in this group is not the skipping. It is that **a deploy gate which skips when
the artefact is missing cannot distinguish "no artefact" from "bad artefact"** on a runner that
has neither. That is why the deploy readbacks are performed by hand against the server rather
than inferred from a green CI run.

### E — a sibling repository (9 sites)

`test_structural_invariants.py` (5) · `test_falsification_shining_codex.py` (2) ·
`test_falsification_viewser_replacement.py` (2)

**Accepted. Environmental by construction.** These assert properties of `views-models` and its
model packages, which live in a different repository. A CI runner for *this* repository has no
checkout of them, and giving it one would couple the two repositories' CI — the opposite of what
the graph architecture separates. Cross-repository contracts are carried by issues and peer
messages, not by this suite.

### F — git refs, deep checkout, `gh` CLI (7 sites)

`test_falsification_deploy_v160.py` (5) · `test_falsification_deploy_v160_r2.py` (2)

**Accepted as environmental**, with one registered defect that is *not* environmental.

`.github/workflows/ci.yml`'s `actions/checkout` sets no `fetch-depth`, so a CI runner has one
branch and no `main`/`development` refs; these gates cannot answer there.
`.github/workflows/release-topology.yml` does set `fetch-depth: 0` and creates the local refs,
which is the pattern to copy if any of these is ever wanted in CI — and it is the reason the
topology guards are enforced at all.

**Registered separately, and genuinely wrong:** `test_falsification_deploy_v140.py` reads **live
GitHub state**, so it is flaky by construction, and `if result.returncode != 0: return` makes it
pass silently with no `gh`, no auth, or no network. It fails green. That is in the register as
part of the epic's deferred set.

### G — the live server (2 sites)

`test_falsification_staleness.py` (1) · `test_falsification_preflight_netrc.py` (1)

**Accepted.** One probes the remote zarr store, one needs live server access plus a `HOME`
override. Both state the manual command in the skip reason, which is the right form for a check
that cannot be automated here.

### H — a gold reference set (2 sites)

`test_model_parity.py` (1) · `test_consumer_parity.py` (1)

**Accepted.** `viewser_pgm_africa_me.parquet` is the externally produced reference these parity
tests compare against. It is not ours to commit.

### I — a committed repository file (2 sites) — **this group is wrong**

- `test_falsification_ghspop_deploy.py` skips when `.gitignore` is not found
- `test_falsification_ghspop_memory.py` skips when the deployment guide is not found

**Both files are committed to this repository.** A test that skips because a tracked file is
missing cannot ever legitimately skip: if the file is gone, that is the finding. These should
fail, not skip.

**Not changed here**, because changing them is a behaviour change to two unrelated guards and
this story is scoped to the ratchet. They are recorded here so the next person touching either
file knows the skip is wrong rather than cautious. Two sites, no data at stake — the smallest
item in this catalogue and the only one that is simply a mistake.

### J — uncommitted fixtures and report directories (5 sites)

`test_acled_harvester.py` (1) · `test_falsification_ghsbuilts_visual_audit.py` (2) ·
`test_pipeline_consistency.py` (1) · `test_structural_invariants.py` (1)

**Accepted, two of them weakly.** The ACLED sample fixture and the GHS-BUILT-S raw/compiled data
are legitimately absent in CI. The visual-audit test skipping when `reports/audit_ghsbuilts/` is
absent is weaker — that directory is gitignored output, so the test can only ever run right after
someone generates it by hand.

Two sites in this group skip on a *condition inside the data* rather than on a missing file
(`Unknown type_of_violence`, and a per-file parse failure). Those are closer to group I: a
surprise in the data is a finding, not a reason to decline. Recorded, not changed.

## How to change these numbers

1. Adding a skip: add the site to `_INVENTORY` in `tests/test_skip_inventory.py` and add a row
   here with its group and reason. The ratchet is red until you do, by design.
2. Removing a skip: lower the number in `_INVENTORY` and strike the row here. The per-file
   exactness check is red until you do — removing withheld coverage is good news and still has
   to be written down.
3. Changing a group's disposition: say what changed about the dependency, not about the
   convenience.

## What none of this catches

Stated here rather than discovered later, and repeated in the guard's own docstring:

- **An existing skip that begins firing where it did not before** — a runner losing `data/`, a
  fixture quietly disappearing. The number of declared sites is unchanged; only the number of
  actual skips moves. The withheld-coverage summary makes that visible to a reader; nothing
  asserts it, for the flutter reason above.
- **A skip swapped for a different skip in the same file.** The count is unchanged, so no
  count-based scheme can see it — including an exact one.
- **`@pytest.mark.xfail`.** An xfail declares an expectation of failure and is reported as such.
  It is not coverage withheld, and it is deliberately out of scope here.

## The ratchet was attacked, and one attack succeeded

Five mutation drills against `tests/test_skip_inventory.py`, each with `__pycache__` cleared
beforehand — the 2026-10-30 post-mortem records five earlier drills that reported `CAUGHT` while
measuring bytecode no longer on disk.

| Drill | Outcome |
|---|---|
| Add a skip site to a file **not** in the inventory | **Caught** — `test_no_undeclared_file_declines_to_run` |
| Add a skip site to a file **already** in the inventory | **Caught** — `test_each_declared_allowance_is_fully_used` |
| Inflate one inventory number by 1 | **Caught** — `test_each_declared_allowance_is_fully_used` |
| Name a module in the inventory that does not exist | **Caught** — three tests, including the stale-entry guard |
| **Delete `tests/test_skip_inventory.py` and run the whole suite** | **SURVIVED.** Exit 0. |

The fifth one is the finding, and it is reported rather than buried.

**Deleting this guard leaves the build green.** Nothing in this repository counts collected
tests, so removing a test module removes its coverage silently — which is the same failure
class this module exists to detect, one level up. Worse, the inventory *is* this file, so the
guard and the record of what it was guarding disappear together.

That is mutation category **M6 applied to the remedy for M6**. It is not a reason to distrust
the four drills that passed: within the file, the ratchet works, and a skip cannot be added or
an allowance inflated without it going red. It is a statement about the boundary of what a
single test file can defend.

**Deliberately not fixed here.** The obvious remedy is a floor on the number of collected
tests, which would catch any test module vanishing. It is a new guard in a shared place, on the
path of every later change, and it needs editing every time a test is legitimately removed —
and this story's scope is the skip ratchet. Recorded as a finding instead, where the next
person deciding whether to build that floor can see what it would buy.

### A sixth finding, from review rather than from a drill

The drills above were run against a version of this module that carried **two** assertions on
the number: a ceiling (`live <= declared`) and a per-file equality (`live == declared`). The
PR body claimed they were two halves of one mechanism.

They were not. Every state that violates a ceiling is also an inequality, so **the ceiling
could never fail without the equality test failing too** — a guard that could not fail alone,
inside the module written to catch exactly that. The D2 drill showed both going red together
and that was read as corroboration rather than as subsumption, which is the mistake worth
recording: *two guards failing together is evidence they overlap, not evidence both work.*

Review of #571 caught it; the ceiling is gone. What makes this module immune to the fluttering
that would have wedged a protected branch is not a choice between a bound and an equality — it
is that the number counts skip sites **declared in the source** rather than tests that actually
skipped. That property lives in the inventory, and the earlier docstring misattributed it.

The first run of this drill returned exit **124** — a timeout at 75%, because the whole suite
takes longer than the 900 s the drill script allowed. That was recorded as `UNRUN` and re-run
without a limit rather than reported as green. A timeout is not a pass, and exit 124 is as
misleading here as exit 137 is for an out-of-memory kill.
