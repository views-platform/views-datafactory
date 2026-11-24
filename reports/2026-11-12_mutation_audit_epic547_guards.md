# Mutation Audit: every guard added by epic #547

**Date of the audits:** 2026-11-12 · **This file compiled:** 2026-11-21
**Author:** Simon Polichinel von der Maase, Claude Code
**Scope:** every test guard added or altered by stories #550, #551, #552 and #554 of epic
#547 (the spatial allocator wrote its decision to `priogrid_gid` and the event compiler
re-derived the cell from coordinates, so every allocated row returned to the cell it came
from), plus the three fixes in `fdef68d` and the re-audit of those fixes
**Issue:** #555 — *Story 8: independent mutation audit of every new guard — the auditor must
not be the author*
**Method:** `/falsify guard` mode, run by clean-context subagents in isolated git worktrees
**Related:** `reports/post_mortems/2026-11-11_release_v1180.md` (the release this epic fixed)
· `reports/post_mortems/2026-10-30_release_v1160.md:254-269` (the stale-bytecode flaw this
audit was designed around) · `reports/test_skip_catalogue.md`

---

## The thing to read if you read nothing else

**Guards written against one magnitude error pin that error's scale rather than the property.**

That sentence is the auditor's, from the re-audit, and it is the whole finding. The epic's
defect conserved every total, preserved every cell set, and got only the per-cell magnitudes
wrong. The guard written to catch that class of error used a fixture — 60/30/10 of 100 — whose
every share is exactly representable at two decimal places. Replacing `deaths / total` with
`round(deaths / total, 2)` therefore passed the entire suite: **2547 passed, exit 0**. The
guard pinned the magnitude of the one error it had seen, not the property it claimed.

The fix was four numbers. Changing the fixture shares to primes — 7/11/13/29 — moved the
boundary from *between 1 and 2 decimal places* to *between 6 and 7*, where it meets
`pytest.approx`'s own relative default. One fixture line, and the guard now holds against the
class rather than the instance.

---

## How this file was made, and what it therefore cannot show

This report is compiled from the three comments on issue #555, dated 2026-11-12, which are
themselves the author's summaries of two subagent reports. **The subagents' full per-mutation
tables — each mutation's predicted outcome beside pytest's own quoted summary line — were
returned into a conversation and were not written to a file. They are not recoverable.**

So #555's acceptance list is met here in substance and not in form. What is below is faithful
to the comments and adds nothing to them. What is missing, and is missing permanently:

- the **mutation plan committed before execution**, with a predicted caught/survives per row;
- the **per-mutation evidence line** for each of the 48 mutations;
- the mapping from every mutation ID to its M1–M7 category.

The mutation IDs (`M-01` … `M-23`) and the category codes (`M3`, `M4`, `M5`, `M6`) below are
quoted from the comments, where they appear without a key. `M3` is *assert on source text*,
`M4` is *a guard that cannot fail*, `M5` is *the author's enumeration bounds the audit*, and
`M6` is *correct and never runs* — read from `references/guard_mutations.md` in the `falsify`
skill, not from this repository.

**The lesson for next time is procedural: a subagent's audit report must be written to a file
in the worktree before the subagent returns.** That is the only reason this file is a
reconstruction rather than the original.

---

## 1 · Independence

Stated first because every other line depends on it.

**First audit — independent, with two self-disclosed contaminations.** Run by a clean-context
subagent in an isolated git worktree. It confirmed it had read none of the plan, the register,
the changelog, `reports/test_skip_catalogue.md`, the investigation reports, any ADR, any PR
body or any issue. It then disclosed two things against itself, unprompted:

1. The worktree was checked out at `main`, where none of the files in scope exist. Locating the
   changeset meant `git log --oneline --all`, which printed about fifteen **commit subject
   lines**, including #550's and #554's. No bodies. Its own judgement was that the
   contamination is negligible, because the same information is restated in the docstrings it
   was required to read. Recorded rather than glossed.
2. It left its worktree on a detached HEAD at `19bd737`. Nothing was lost.

**Re-audit — partially compromised, and the fault was in the brief.** The brief told the
auditor to run `git show --stat fdef68d`. That command prints the **full commit message body**
before the file list, so the auditor read the author's own model of failure in its second tool
call. It disclosed this as the first line of its report and could not un-read it.

The consequence is asymmetric and is the reason this is recorded rather than smoothed:

- its **catches are measurements and stand on their own**;
- its **failure to find further survivors is worth less**, because its enumeration was primed
  by the author's.

The three findings it did return were outside the author's enumeration, which is some evidence
the priming did not fully determine it — but not proof.

**The brief's instruction to skip the commit prose named the command that prints it.** Next
brief says `git show fdef68d --format=""`.

---

## 2 · Guard count, and how it was derived

The in-scope guards are those added or altered by #550, #551, #552 and #554, located from the
changeset rather than from any issue text:

| file | role in the epic |
|---|---|
| `tests/test_falsification_spatial_allocation_delivery.py` | the delivered-layer falsifiers for the declared-cell seam (#551) |
| `tests/test_synthetic_spatial_fixtures.py` | synthetic UCDP events and GAUL crosswalks standing in for the gitignored real store (#550) |
| `tests/test_adr053_production_profile.py::TestAdr053ComposedOnSyntheticGeographyGreen` | the composed golden criterion on synthetic geography (#550, #552) |
| `tests/test_skip_inventory.py` | the skip-count ratchet (#554) |
| `tests/conftest.py` — `pytest_terminal_summary`, `pytest_deselected` | the visibility half of #554: the banner announcing withheld coverage |
| six skip-site annotation comments | the human-readable half of the skip catalogue (#554) |

**48 mutations in total across the two audits: 28 in the first, 20 in the re-audit. 48 run, 0
`UNRUN`** — with one exception recorded in §7, a guard that cannot be run at all.

`__pycache__` was cleared before every apply and after every revert. This is not hygiene; it is
the specific defect that invalidated five earlier drills, recorded in
`reports/post_mortems/2026-10-30_release_v1160.md:254-269`: a `cp` restore within the same
whole second as pytest's compile leaves the mutant's `.pyc` in use, so the drill reports on
bytecode no longer on disk. Every verdict below comes from pytest's own last summary line. No
verdict was taken from a piped exit status, and no run was killed or timed out.

---

## 3 · First audit — 28 mutations, 18 caught, 10 survived

### What holds

**Seven independent mutations to the declared-cell seam were caught every time, by the right
guard, with messages that point the right way:** ignore `pgid_field` entirely (the shipped
defect, restored), clamp instead of fall back, off-by-one on the range check, off-by-one on the
index, swap the two counters in the report, re-impose the old majority threshold, and break the
coordinate fallback it depends on.

The `strict=True` xfail on the temporal seam is load-bearing: making `date_field` default to
`date_month` forced it red, exactly as its stated reason says it would.

`test_falsification_spatial_allocation_delivery.py` does the job it was written for.

### Survivor 1 — proportionality, within the epic's own guards

**M-21** replaced `_compute_weights`'s `deaths / total` with a flat `1.0 / n`, making every
allocation uniform over the weighted cells. **All 57 in-scope tests passed.**

The guards assert *which* cells receive mass and *how much in total*. Not one asserted how much
per cell. Four guards across two files were credited with checking a proportional allocation
and checked only its support and its sum.

This is an **absence, not a weakening**, and it is the property ADR-049 exists for. It is also
the thing the epic's own history should have predicted: the uniform fallback inside
`proportional` is the branch that makes a proportional allocation look like it worked while
distributing nothing proportionally. #550 had to read the code to find it, and built the
fixture with deliberately unequal fatalities so the two *could* be told apart — and then no
assertion ever did the telling.

**This finding was over-stated when first reported and is corrected in §5.** The mutation is
caught in CI, by a June test outside the epic's scope. The absence is real one layer lower.

### Survivor 2 — the synthetic fixture collapsed three fields into one

`_synthetic_event` set `best == low == high`, so
`test_composition_conserves_every_extensive_field_exactly`'s loop over
`("best", "low", "high")` was one assertion written three times. **M-06** — a plain
`low = _distribute_value(best, …)` copy-paste — was caught only by the **pre-existing**
`tests/test_spatial_distribution.py`, never by anything the epic added. The new synthetic
guards were weaker on conservation than the real-data guards they were written to stand in for.

### Survivor 3 — the skip ratchet stops a careless new skip and none of four careful ones

Four of its five guards were WEAK, by three unrelated mechanisms.

| | mutation | what happened |
|---|---|---|
| **M4** | **M-13**: add `skipif(True)` to an inventoried file **and bump its `_INVENTORY` entry 1→2** | `30 passed, 2 skipped`. A green test now skips forever and the ratchet is satisfied. Adding to the declaration is the module's own stated remedy — but nothing asserts the reason exists or that it is environmental, and with only per-file equalities and a floor of 40 there is **no ceiling on the total**, so file-by-file bumps are unbounded. |
| **M3** | **M-14**: flip an existing inventoried `skipif` condition to `True or …` | `26 passed`. Site count unchanged, suite green, coverage gone. The module's "what this does not catch" list names a runner losing `data/`, and a skip swapped for another in the same file. It does not name this one. |
| **M5** | **M-15**: `from pytest import mark` + `@mark.skipif(True)` in an unlisted file · **M-16**: `pytest.importorskip("no_such_module_xyz")` inside a test in an unlisted file | `117 passed, 1 skipped` both times. **A test genuinely skipped and the ratchet did not see it.** The walker matches only names *ending* `pytest.mark.skipif` / `pytest.mark.skip`, and the exact call `pytest.skip`. |

The auditor's own framing is the part worth keeping: *the author enumerated three forms, I
found two more in ten minutes, and the code's structure implies at least three further* —
`import pytest as pt`, a module-level marker alias, a class-body `pytestmark`. It tried the
walker against 5 of at least 8 identifiable spellings.

A live measurement it took while there: of the 61 declared sites, **49 are `pytest.skip(...)`
calls, 12 are decorators, and 0 are module-level `pytestmark`** — so that third branch has no
live exerciser. M-17 proves the branch works only because the auditor supplied the case.

**M-18** found the premise guard tolerant: `assert total >= 40` against 61 live sites, so
deleting the walker's decorator branch — 12 sites lost, 49 remaining — passed. A 20% walker
failure is invisible.

### Survivor 4 — the visibility half of #554 has no guard whatsoever

**M-19** deleted both `pytest_terminal_summary` and the `config.hook.pytest_deselected(...)`
call. `66 passed`, and the `coverage withheld by marker` banner was simply absent from the
output. Nothing in `tests/` or `.github/workflows/` references either hook.

That matters more than it looks, because the thing the banner exists to announce **is still
true**: 82 tests are deselected in CI — 59 `falsification`, 23 `consumer` — and no workflow
passes either flag. The only mechanism telling a reader about it is itself unprotected.

### The remaining survivors, named individually

"Fourteen of fifteen caught" is not a result; the one survivor is the whole result.

- **M-01 (partial):** `test_compilation_config_can_name_a_precomputed_cell_field` is
  **DECORATIVE** — textbook M4. `pgid_field` left on the dataclass, `_place_events` made to
  ignore it, the shipped defect restored, and this guard stayed green. Its siblings caught it,
  so the file is safe; the guard contributes nothing and reads as if it did.
- **M-10 (partial):** `test_schema_matches_the_real_crosswalks` is **WEAK**. Production
  switched to reading `pgid`/`code` and this guard still asserted the *fixture* is
  `["gid", "value"]`, and passed. It compares a declaration to a hardcoded literal, never to a
  real crosswalk — while its docstring claims it keeps the fixture aligned with
  `_load_gaul_crosswalk`.
- **M-07:** `test_all_four_precision_classes_are_present` is **WEAK**. It asserts
  `{1,4,5,6} <= precisions`, but `where_prec == 4` allocation is exercised by no guard: raising
  `_SPATIAL_THRESHOLD` to 5, so `where_prec == 4` events pass through undistributed, left all
  31 tests green. It declares a coverage class the suite does not cover.
- **M-20:** the six skip-site annotation comments are **DECORATIVE** — removing the identifying
  line from each turned nothing red. No assertion anywhere mentions
  `reports/test_skip_catalogue.md`.
- **M-23:** `test_both_stages_marked_the_rows_they_touched` is **WEAK**. It used
  `all(_temporal_distributed)` but only `any(_spatial_distributed)` — marking **1 of 8**
  allocated rows passed.

---

## 4 · Verdicts per guard set

| guard set | verdict |
|---|---|
| `test_falsification_spatial_allocation_delivery.py` | **HOLDS**, except one DECORATIVE guard |
| `test_synthetic_spatial_fixtures.py` | **WEAK** — 9 HOLDS, 5 WEAK. The fixture itself is sound; what it is used to assert is thinner than the docstrings claim |
| `test_adr053_production_profile.py::TestAdr053ComposedOnSyntheticGeographyGreen` | **WEAK** — all four survived at least one mutation |
| `test_skip_inventory.py` | **WEAK** — 1 HOLDS, 3 WEAK, 1 **UNVERIFIED** (`test_the_inventory_names_no_file_that_no_longer_exists`, not attacked) |
| `tests/conftest.py` hooks · the six annotation comments | **DECORATIVE** — no guard exists |

---

## 5 · The correction: proportionality is guarded in CI, and the absence is one layer lower

The first report of this audit said the proportionality guarantee is **"unguarded in CI"**.
That is wrong. It is recorded here because the wrong version was reported to the operator
before it was caught.

The mutation — `_compute_weights`'s `deaths / total` replaced by a flat `1.0 / n` — **is**
caught in CI, by `tests/test_spatial_distribution.py::TestWeightMapBeige::test_multiple_events_same_cell`.
That test asserts `0.6` and `0.4` on a two-cell polygon and has been in the suite since
`75ba82d` (2026-06-28), the original ADR-049 implementation.

The audit was correct within its stated scope — *guards added by this epic* — and none of those
caught it. The author generalised that to the whole suite without re-running the mutation
against the whole suite. **The error is the author's, not the auditor's.**

**The absence was real, one seam lower.** Equalising the weights *inside* `proportional` — same
cell set, equal magnitudes — was caught by nothing that runs in CI:

- every test in `TestProportionalGreen` asserted the allocated **total** and the **cell set**,
  and both are invariant to the weights. 100 deaths over 50/30/20 weights arrives as 34/33/33 —
  three cells, total 100 — and all nine passed;
- the only test in the whole suite that caught it was
  `tests/test_adr049_profile_contract.py::TestAdr049GoldenCriterion::test_allocation_is_proportional_to_the_weight_map`,
  which is `skipif`'d on the real consolidated store and the GAUL crosswalk parquets that
  `.gitignore` guarantees CI never has.

Correct, and never runs — **M6**, the same mechanism that hid the original defect this epic
exists to fix. That is the more useful finding than the one first reported, and it was only
reachable by **moving the mutation rather than reasoning about it**.

---

## 6 · The three fixes, and their drills

Closed by PR #575.

| survivor | fix |
|---|---|
| **M-21** | Two guards, one per seam. `TestWeightMapGreen::test_each_weight_is_its_cell_share_of_polygon_deaths` asserts exact shares at both polygon levels over four cells whose shares are pairwise distinct and none equal to `1/n` of either polygon. `TestProportionalGreen::test_each_cell_receives_its_weighted_share_not_an_equal_one` asserts per-cell magnitudes of `best`, `low` and `high`. |
| **M-06** | The synthetic fixtures set `low == high == best`, making the `_EXTENSIVE` conservation loops one assertion run three times. Now `best // 3` and `best * 2 + 1` — UCDP's own `low <= best <= high`, with different apportionment remainders per field. Applied in all three fixture builders. |
| **M-23** | Two marker assertions used `any()` over the allocated rows, which passes when a single row is marked. `proportional` marks every row it emits and the temporal stage carries the field through with `**event`, so `all()` is the correct claim. |

Drill results, `__pycache__` cleared around each mutation and `src/` confirmed clean after:

| mutation | caught by |
|---|---|
| `_compute_weights`: `deaths / total` → `1.0 / n` | the new weight-map test **and** the June Beige test |
| `proportional`: equalise the weights over the same cells | **only** the new proportional test, in CI scope |

Whole suite: **2584 passed, 16 skipped, 18 xfailed, 0 failures.**

---

## 7 · Re-audit of `fdef68d` — 20 mutations, three survivors, all in the fix

More useful than the first audit, because the survivors it found were in the fix rather than in
the original work.

### Survivor 1 — the new guard pinned the magnitude of one error, not the property

`round(deaths / total, 2)` in `_compute_weights` **passed the entire suite**: `2547 passed`,
exit 0, no `FAILED` or `ERROR` lines.

The fixture was 60/30/10 of 100 and 60/30/10/400 of 500. Every one of those shares is exactly
representable at two decimal places, so quantising every weight was invisible to the test
written to catch exactly this class of error.

**This is not a contrived mutation.** In a real GAUL polygon with many cells, 2dp quantisation
rounds the small ones to **zero weight** — they receive nothing — and a polygon whose every
cell rounds to zero makes `apportion` raise.

Fixed by changing four fixture numbers to primes — 7/11/13/29. Measured boundary afterwards:

| mutation | result |
|---|---|
| `round(share, 2)` | caught, **by the new guard alone** |
| `round(share, 6)` | caught |
| `round(share, 7)` | survives — `pytest.approx`'s 1e-6 relative default |

### Survivors 2 and 3 — two of the three M-06 fixture edits protected nothing

Worse than inert: each carried a **comment claiming a protection it did not provide**. Both
were verified by the author before being accepted.

- `test_falsification_spatial_allocation_delivery.py` — `_compile`'s `keep` tuple does not
  carry `low` or `high` into the parquet at all, and no assertion in the file reads either.
  Setting both to `None` left every test green. The comment claimed it strengthened *"a
  per-field conservation check"* in a file that has none.
- `test_adr053_production_profile.py` — the local `_synthetic_event` feeds only
  `TestAdr053ProvenanceCounters`, which has ledger counters and no conservation loop. The
  comment named *"the `_EXTENSIVE` conservation loop above"*, which takes its event from the
  generator fixture or the real store, never from that helper.

**Both reverted**, with comments stating why they are equal and that distinctness was measured
to protect nothing. The generator fixture edit is kept — the auditor isolated it by reverting
it alone, which made a wrong-field read invisible again, so it is the whole effect.

Three identical edits from one diagnosis; one load-bearing. *The diagnosis named one cause;
measurement finds one of three sites load-bearing.*

### What holds, with its blind spots now in its own docstring

`TestProportionalGreen::test_each_cell_receives_its_weighted_share_not_an_equal_one` **HOLDS**
against 7 mutations and is the **sole catcher out of 174 tests** for two of them:

- the allocator ignoring its weight map entirely;
- `low` apportioned on different weights than `best`, while every total conserves exactly and
  the cell set is right — a defect differing only in per-cell magnitude.

Two blind spots are now stated in its docstring rather than left implicit. It exercises **no
remainder**: all three fields divide exactly into 50/30/20, so it cannot distinguish
independent per-field apportionment from three copies of a lucky division
(`test_apportionment.py` covers that). And it **cannot tell admin-1 from country weights**,
because `_simple_weight_map` declares both identically (`test_provenance_annotations` covers
that, via `_spatial_polygon_code`).

### An `UNRUN` inside the fix itself

One of the two `any` → `all` changes sits in `TestAdr053ComposedGoldenCriterion`, which is
`skipif`'d on the real store and the GAUL crosswalks. **It has never executed, here or in CI.**
Correct but unverified; recorded `UNRUN`, which is not a passing grade. The sibling change in
`TestAdr053ComposedOnSyntheticGeographyGreen` does run, and the re-audit confirmed it goes red
when only the first row is marked.

### A systemic finding, recorded and not fixed

The wide selection stayed at `174 passed` for six separate weight-map mutations — including
reading an **entirely wrong column**. Nothing outside `tests/test_spatial_distribution.py`
checks weight-map magnitudes at all. **That one file is a single point of failure for the whole
property.**

---

## 8 · Two measured numbers worth keeping

**Exactly 37 tests run for a developer holding the gitignored data and skip in CI.** The
auditor's full suite was `2547 passed, 53 skipped`; the author's was `2584 passed, 16 skipped`.
Both total 2600. `TestAdr049GoldenCriterion::test_allocation_is_proportional_to_the_weight_map`
is among the 37. **That is the gap the original defect lived in, now a number rather than an
impression.**

**89 of 92 test citations across `docs/` are actually checked.** Found while relying on a guard
during the write-up: `tests/test_docs_citations.py::test_referenced_test_files_exist` verifies
that a cited **test file path** exists, but not the class or function name, so a document may
cite a test that does not exist and the guard stays green. Its regex allows one `::Symbol`
segment, so a two-level node ID — `path::Class::test_name` — does not match at all and is
invisible to the guard *including its file path*. All 3 unchecked citations point to files that
do exist, so nothing is currently broken. Low severity, recorded rather than fixed.

---

## 9 · What still survives

Unfixed, deliberately left until after the 2026-11-21 cron rather than opened as work during
the epic:

**The five skip-ratchet bypasses** — **M-13** (declaration bump), **M-14** (condition flip),
**M-15** (`from pytest import mark`), **M-16** (`pytest.importorskip`), **M-18** (the
20%-tolerant premise guard). **M-19** (the `conftest.py` hooks are unguarded). **M-20** (the
six annotation comments are decorative). And the three partials: **M-01**
(`test_compilation_config_can_name_a_precomputed_cell_field` DECORATIVE), **M-10**
(`test_schema_matches_the_real_crosswalks` WEAK), **M-07** (`_SPATIAL_THRESHOLD` 4→5 survived).

**The honest position on the five skip-ratchet bypasses is that the module asserts on source
text (M3) and is therefore bounded by whatever spellings its author enumerated (M5). Widening
the walker buys spellings, not a different kind of guarantee.** That is an argument for
replacing the instrument, not for extending it, and it is why these were not fixed in passing.

---

## 10 · The pattern, which is the transferable part

The ten survivors of the first audit are not one bad guard. They cluster in two habits.

1. **Asserting the support of a distribution instead of the distribution.** M-06, M-21, M-23 —
   and the asymmetric `any`/`all` is the same instinct in miniature.
2. **Asserting source text where the subject is behaviour.** M-13, M-14, M-15, M-16, M-18,
   M-20 — the whole skip-ratchet file plus the annotations.

The re-audit adds a third, and it is the sharpest because it applies to guards written *in
response to* an audit:

3. **A guard written against one magnitude error pins that error's scale rather than the
   property.** The fixture that makes the known defect visible can be the fixture that makes
   the next one invisible.

Both of the first two habits are visible in the guards' **own docstrings**, which are unusually
candid about what they do not cover. The audit's finding is largely that **the candour
understates it**.

---

## 11 · Tree state

Every mutation was reverted. After each: `git status --short`, `git diff` and
`git diff --cached` all empty, `src/` confirmed clean, and the pre-mutation baseline reproduced
exactly — `57 passed, 6 skipped, 1 xfailed` for the first audit's selection.

Final state after the fixes: whole suite **2584 passed, 16 skipped, 18 xfailed, 0 failures**,
pytest's own exit code 0 captured directly and not through a pipe. `uv run ruff check .` and
`uv run mypy src/` clean.

---

## 12 · The honest claim

**This is a count of 48 mutations tried, not a proof of sufficiency.**

`HOLDS` above means *withstood these mutations, chosen by these auditors*. M5 — the author's
enumeration bounds the audit — applies to the auditor too, and both auditors said so. The first
one demonstrated it on itself: it enumerated five skip spellings against the author's three and
then named three further ones it had not tried.

---

## 13 · What to do differently

1. **A subagent's audit report is written to a file in its worktree before the subagent
   returns.** This file is a reconstruction for exactly one reason: it was not. The
   per-mutation evidence from 48 mutations is gone.
2. **A brief that forbids reading the author's prose must not name a command that prints it.**
   `git show --stat <sha>` prints the commit body. Use `git show <sha> --format=""`.
3. **Do not generalise a scoped audit's finding past its scope without re-running it there.**
   "None of the epic's guards caught it" became "unguarded in CI", which was false, and was
   reported to the operator before being caught.
4. **When a mutation is caught, move it one seam deeper before believing the property is
   guarded.** The real absence was found by relocating the mutation, not by reasoning about it.
5. **Build the fixture so that no share is exactly representable at a convenient precision.**
   Primes, not round numbers. One line, and it moved the detection boundary by five decimal
   places.
