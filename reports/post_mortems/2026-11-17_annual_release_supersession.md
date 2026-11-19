# Post-mortem: UCDP annual releases never superseded each other — 4,939 deaths we published and UCDP did not

**Date:** 2026-11-17 (written up 2026-11-18)
**Author:** Simon Polichinel von der Maase, Claude Code
**Severity:** High. Published fatality figures were above the source's own in every year, in the
served store, with no check red and no conservation invariant violated. Not critical: the error was
an overcount of roughly 0.03%–1.3% of global deaths per year, concentrated in a few country-years,
and the data was never structurally broken.
**Status:** Diagnosed, fixed, and proven against production data. The fix is in PR #596, **not yet
merged and not yet deployed**; the served store still carries the defect as of this writing. CI was
green on the first revision, after which `/code-review` found two defects in the fix itself — see
*Found by review* below — so the branch has been amended and CI re-runs.
**Scope:** #594 (diagnosis), #595 (fix), #596 (PR), #597 (the documentation pattern that hid it).
Neighbouring defects #592 and #593 are deliberately untouched.
**Discovered by:** Håvard Hegre, by reading a table we sent him and comparing it to UCDP's own
website. Not by any check of ours.

---

## The thing to read if you read nothing else

UCDP deletes events when it publishes a new annual release — merges duplicates, reclassifies,
drops reports that did not hold up. Our store keeps every version it ever downloaded, on purpose.
The step that decides which stored version to publish had a rule saying *a newer monthly file
replaces an older monthly file*, and no equivalent rule for annual releases. So when UCDP withdrew
an event, we kept publishing it.

**321 events, 4,939 deaths, across 24 years and 45 country-years.** Ukraine 2024 was the worst in
absolute terms: we published 100,601 where our own method applied to the current release gives
98,352.

The fix is one new rule: among annual releases, keep only the newest, except rows reaching past its
coverage. After it, our global totals for 2022, 2023 and 2024 equal UCDP release v26.1 **exactly**,
in all three violence types — nine cells, nine exact matches.

Nothing is deployed yet. The serving store is still wrong.

---

## 1. How the data reaches our published figures

UCDP publishes in two kinds of file.

Once a year there is an **annual release**: every event from 1989 to the end of the previous
calendar year, cleaned and checked. It is authoritative. The current one is **v26.1**, published
July 2026, covering 1989–2025.

Between annual releases there are **monthly files**, so the data stays current. These are
provisional.

Our pipeline downloads both and stores every file it has ever downloaded. Nothing is deleted from
storage — a deliberate choice (ADR-013, ADR-017) so that any figure we published on any past date
can be reconstructed.

A later **selection step** then decides which stored version of each event to use when building the
grid we publish. That step is where the defect was.

## 2. UCDP does not only correct events. It removes them.

This is the part that is easy to miss, and it is the root of the whole thing.

A new annual release revises events — a death toll moves from 40 to 45, a date sharpens, a location
gets pinned down. Our pipeline handles that correctly and always has.

But UCDP also **withdraws** events, in three ways:

- two reports it later recognises as the same incident are merged, so one record disappears;
- an event is reclassified out of the dataset, because it turns out not to have been organised
  violence;
- an event is dropped outright, because the underlying reporting did not hold up.

So an event present in **v25.1** can be **absent from v26.1** — not changed, gone, with no
replacement record and no note saying it was removed. The newer release is not a superset of the
older one. Part of the correction is subtraction.

Measured on our production store: **321 v25.1 events have no counterpart anywhere in v26.1.**

## 3. We hold two annual releases at once, and that is by design

Production currently holds both **v25.1** (in the store since March 2026 — read from the
2026-04-25 post-mortem, not re-checked) and **v26.1** (harvested 2026-07-02).

That is not a cleanup we forgot. The architecture splits the job in two:

- **Storage keeps everything.** Its only promise is that nothing is lost. Deleting v25.1 would
  destroy our ability to reproduce past published figures.
- **The selection step chooses.** Its job is to decide which stored version wins and to discard
  versions that have been superseded.

So the responsibility for ignoring v25.1 where v26.1 replaced it sat entirely with the selection
step. Storage was doing its job correctly throughout. ADR-013 is explicit that discarding
superseded records is the viewpoint's job, which is why the fix belongs where it went.

For the ten months before v26.1 arrived, only one annual release existed. There was nothing to
choose between, so the question never came up.

## 4. The defect: the selection step knew monthly files supersede each other, and not that annual
releases do

`filter_stale_versions`, inside the UCDP viewpoint builder, had three rules. In plain words:

1. **Annual coverage boundary** — work out how far forward the annual data reaches.
2. **Within annual period** — inside that window, drop any monthly row whose event id is not in the
   annual data.
3. **Latest .9 only** — among the monthly files, keep only the newest; drop all older monthly
   versions.

Read rule 3 next to rule 2. Rule 3 says, correctly, *a newer monthly file replaces an older monthly
file*. There is no equivalent sentence anywhere for annual releases. Rule 2 says the opposite: keep
every annual row.

What that did to a withdrawn event:

- its v25.1 row is annual, so **rule 2 kept it unconditionally**;
- **rule 3 never looked at it**, because rule 3 concerns monthly files only;
- the later survivorship step could not help either. Survivorship only acts when two rows compete
  for the same event id. A withdrawn event has no v26.1 row to lose to, so it was the only
  candidate and won a group of one.

Every rule behaved exactly as written. The event survived because no rule was watching that door.

**The asymmetry is the bug.** Monthly supersedes itself; annual did not.

### Why the document is part of the cause, not just the code

ADR-023 §Decision item 3 listed those three rules and presented them as the specification of the
stale filter. Anyone asking "does our pipeline handle one annual release superseding another?"
would have opened that ADR, read three rules, found no fourth, and reasonably concluded there was
nothing more to know.

The list was in fact a transcript of the cases that came up during the April 2026 parity
investigation — which the ADR's own Rationale section says, thirty lines below the list, where it
does not change how the list reads.

A second signal was on the page and went unread: rule 3 defines supersession for one release family
and rules 1–2 define none for the other. The asymmetry was visible. Nothing prompted anyone to ask
why.

This generalises. Numbered rule or invariant lists appear in 16 of 56 ADRs, and none of them say
whether the list is complete or merely what we had thought of. Filed as **#597** with the counts and
four options.

## 5. How we discovered it, honestly

Not by a check. By an external reader, and only because we had already sent him a confusing table.

| When | What |
|------|------|
| 2026-07-02 | v26.1 harvested. Both annual releases now in the store. The defect becomes live on the next grid rebuild. |
| 2026-11-10 | v1.18.0 deployed; production allocation profile switched to `kgi_kti_activity`. Grid rebuilt — carrying the defect. |
| shortly before 2026-11-17 | We mail Håvard a table of UCDP and ACLED fatality totals. The table is **global** and its heading does not say so. |
| 2026-11-17 | Håvard replies: UCDP's website gives **369,028** for Ukraine, 99% state-based; why are ours so much higher, and where did they come from? |
| 2026-11-17 | First finding: the table was global, not Ukraine. That alone explains most of the apparent gap, and it was our omission, not a data error. |
| 2026-11-17 | Verifying our global table against UCDP's API v26.1 to be sure: 2025 exact in all three violence types, 2022 **+0.03%**, 2023 **+0.2%**, 2024 **+1.3%**. Small, one-directional, and unexplained. |
| 2026-11-17 | Decomposing the Ukraine difference separates two causes: country definition (grid-cell owner versus source label — #592, #593) and something else of roughly 2,200 deaths in 2024. |
| 2026-11-17 | That residual is traced to events present in v25.1 and absent from v26.1. Orphan counts per year — 90 / 388 / 2,400 — account for the entire measured gap of +90 / +388 / +2,400. Filed as **#594**. |
| 2026-11-17 | Fix planned (#595), branch `fix/595-annual-release-supersedes`, implemented, tested, measured against production data, PR **#596** opened to `development`. |
| 2026-11-17 | All five CI checks green: docs 7s, lint 20s, typecheck 28s, test 9m19s, test-py313 15m23s. |
| 2026-11-18 | This post-mortem. #597 filed. Not merged, not deployed. |

Two things are worth saying plainly about this sequence.

**The one-directional sign was the tell, and we nearly missed it.** Our figures were above UCDP's in
every year and never below. A revision difference would scatter in both directions; only an
addition of events we should not have had produces that pattern. That observation is what turned a
vague "vintage lag" hand-wave into a specific hypothesis we could count.

**Our own unlabelled table is what started the investigation that found a real bug.** The
presentation error was ours and was not a data error. It was also the only reason anyone looked.

## 6. What we did, and why

### The fix

One new rule, added as step (a0) in the same block as the other three, under the same
`filter_stale_versions` flag:

> Among the annual releases, keep only the newest version — except rows whose `date_end` lies beyond
> the newest version's own coverage, which survive.

The first half does the work. v26.1 is newer than v25.1, so every v25.1 row is dropped, and a
withdrawn event has no v26.1 row to take its place. It is simply gone, which is what UCDP intended.

The second half selects nothing today: v26.1 spans 1989–2025, v25.1 spans 1989–2024, so no v25.1 row
reaches past v26.1's end. It exists for a future release covering a *shorter* span than its
predecessor — a corrected re-issue stopping at 2023, say. Without the clause, that release would
silently delete two years of history from our published figures. With it, the older release still
supplies the years the newer one does not reach. One extra `pc.or_` term, not machinery.

The step logs at INFO which versions were superseded, through what date, and how many rows went.

### Why the ordering is load-bearing

The new rule runs **first**, before the other three. This is the one subtle thing in the change, and
getting it wrong reintroduces the bug in a better disguise.

A withdrawn event often has more than one row: its v25.1 annual row, and a row from a provisional
monthly file from when the event was current.

**Running it first.** The v25.1 row is dropped immediately. Rule 1 then derives the coverage
boundary and the annual id set from v26.1 alone, so the withdrawn event is not in the annual id set,
and rule 2 drops its monthly row too. The event disappears from every source at once. Correct, with
no change to rules 1–3.

**Running it last.** Rules 1–3 would run with both releases present. Rule 1 would derive the annual
id set from the **union** of v25.1 and v26.1, so the withdrawn event would count as "in the annual
data" and its monthly row would be kept. The new rule would then drop the v25.1 annual row, leaving
the monthly row standing alone with no competitor. It would win survivorship, and the withdrawn
event would be republished — now sourced from a provisional file instead of a superseded annual one,
and correspondingly harder to notice.

### The tests

Four tests in `tests/test_viewpoint.py::TestBuildUcdpV1Beige` — the first fixtures in the suite with
two annual versions present:

| test | what it guards |
|---|---|
| `test_later_annual_release_wins_for_a_shared_event` | an event in both releases takes the newer release's value |
| `test_event_deleted_by_a_later_release_is_dropped` | the regression guard for #594: a withdrawn event is absent from the output entirely |
| `test_deleted_event_does_not_return_through_dot9` | the ordering above: a withdrawn event that also has a monthly row still does not come back |
| `test_older_release_survives_beyond_the_latest_coverage` | the span clause, against an over-aggressive "latest annual wins outright" fix |

The third is the one that distinguishes this fix from a careless one. A fix with the ordering wrong
passes the other three and fails that one.

Both regression tests were confirmed to fail with the source change reverted and pass with it —
the guards were sabotaged and seen to go red, not merely written.

### Why here and not in consolidation

ADR-013 places the discarding of superseded records in the viewpoint, not in storage. Fixing it in
consolidation would have deleted v25.1 rows from disk and destroyed reproducibility of past
published figures. Nothing in `data/raw/` was touched.

## 7. Is it fixed? The proof against real data

The test suite cannot answer this. Tests use small invented fixtures; the claim is about 2.7 million
real rows, and `data/` is gitignored with no fetch step in CI. So the proof is a measurement,
recorded in `reports/investigations/2026-11-17_annual_supersession/findings.md`.

Production's consolidated store was copied to a scratch path (not over the local one) and the
viewpoint built from it **twice** — once with the fix, once with the source change stashed — under
production's own profile, `kgi_kti_activity`. Same data, same settings, one difference. The
before-build is therefore a faithful reproduction of what production publishes today, and it
reproduces the figures in the served store and in the mail sent on 2026-11-17.

Global fatality totals, all three violence types:

| year | before (= published today) | after | UCDP v26.1 | after − UCDP |
|---|---:|---:|---:|---:|
| 2022 | 318,026 | **317,936** | 317,936 | **0** |
| 2023 | 170,820 | **170,432** | 170,432 | **0** |
| 2024 | 190,609 | **188,209** | 188,209 | **0** |

Broken out by violence type, all nine year × type cells also agree exactly:

| year | type | before | after | UCDP v26.1 |
|---|---|---:|---:|---:|
| 2022 | state-based | 285,348 | 285,324 | 285,324 |
| 2022 | non-state | 20,159 | 20,093 | 20,093 |
| 2022 | one-sided | 12,519 | 12,519 | 12,519 |
| 2023 | state-based | 139,528 | 139,149 | 139,149 |
| 2023 | non-state | 19,581 | 19,578 | 19,578 |
| 2023 | one-sided | 11,711 | 11,705 | 11,705 |
| 2024 | state-based | 157,628 | 155,255 | 155,255 |
| 2024 | non-state | 18,248 | 18,234 | 18,234 |
| 2024 | one-sided | 14,733 | 14,720 | 14,720 |

**Ukraine 2024: 100,601 → 98,352** — the acceptance criterion written into #595 before any of this
was built, to the digit.

Total movement: **321 events, 4,939 deaths, 24 years, 45 country-years.** 21 country-years move by
more than 1%, 8 by more than 5%, 7 by more than 10%. The nine country-years moving 50 deaths or more
are tabulated in the findings report.

Larger than the 2,878 quoted in #594, because that measurement covered only 2022–2024, the span for
which both releases were in hand at the time.

## 8. What this does not fix

The fix settles **which events** we count. It does nothing about **where** we put them.

The clearest illustration is in the movement table. The United States in 2010 falls from 2,205
deaths to 752 — down 66%, far larger in relative terms than Ukraine. That is correct, and it is two
defects meeting:

- The four events removed are Juárez–Sinaloa cartel killings of roughly 250–265 deaths each. UCDP's
  own country label on all four is **Mexico**. UCDP withdrew them in v26.1, so removing them is
  right — that part is this fix working.
- They sat under the **United States** because all four fall in PRIO-GRID cell 175108, which
  straddles the border, and our method assigns a cell to whichever country holds the larger share of
  its area. That cell goes to the USA, so Mexican deaths were reported as American ones.

The second part is untouched. It is:

- **#592** — our country totals are not the source's country totals, and nothing says so.
- **#593** — `where_prec == 5` means "spread over more than one first-level administrative unit" and
  we resolve it to a single one. Measured: **15.63%** of level-5 deaths land in the wrong country,
  against 1.60% at level 4 and 0.67% at level 6. This is where the Kursk-deaths-in-Sumy problem
  lives.
- Also noted on #593: the spatial weight map has no time dimension at all, which is why forcing
  Kursk onto Russia's country polygon would put 4,680 deaths in the Moscow region and 310 in
  "Waterbody". That measurement is what killed one of the candidate fixes.

So after this change our counts agree with UCDP and our geography does not, and we have not yet said
that anywhere a reader of our figures would see it. #592 exists to fix the second half.

## Found by review, before it merged

The measurement in section 7 was complete and the PR was green when `/code-review` ran on the
branch. It found two defects in the fix itself. Neither changes any figure in section 7, and
neither affects today's data — both are latent — but one is a data-loss path in a change about not
losing data, and it was mine.

**The span bound was one-sided (#598).** Section 6 explains the clause that keeps an older
release's rows when they fall outside the newest release's coverage, and says it stops a future
release from silently deleting history. It only stopped half of that. The clause tested whether a
row ends *after* the latest release's coverage, and never whether it begins *before* it. A release
covering 2000–2026 alongside one covering 1989–2024 deletes every pre-2000 event. Confirmed with an
independent probe. Worse, the test I wrote for the property —
`test_older_release_survives_beyond_the_latest_coverage` — asserted the general claim in its
docstring while exercising only the upper half.

The symmetric fix does not work, which is the interesting part. `max(date_end)` is a sound proxy
for where a release's coverage ends, because a release is dense up to its cutoff. `min(date_start)`
is not a proxy for where coverage begins — it is just the earliest event that happens to be
present. Adding it broke all three #595 regression tests, correctly: in a sparse store every older
row falls "before" the latest release's first event, and supersession stops happening at all. The
declared span *is* available — it is in the harvest filename, `ucdp_ged_v25.1_1989_2024.parquet` —
and `_ANNUAL_PATTERN` captures only the version group and discards both years, so the consolidated
store never sees it. Carrying it through is a consolidation schema change, which is out of scope
for a viewpoint bug fix. So the bound stays upper-only, the code comment and the ADR amendment now
say so, and #598 holds the rest.

**A malformed version string would have deleted the real release (fixed).** `_parse_version` maps a
non-numeric version to `(0,)`, which sorts below every real version. In the `.9` rule that only
loses a preference; here it decides deletion, so a new release arriving as `v26.` would lose to
v25.1 and have its own rows dropped as superseded. Supersession is now refused outright when any
annual version is non-numeric, and warns. My first test for this was decorative — the fixture put
the malformed release's event outside the older release's span, so it survived either way. The
fixture was tightened until removing the guard turns it red.

**A short harvest is now destructive (C-371, registered, not fixed).** The rule works by event id,
and an id in the old release and not the new one has two causes it cannot distinguish: UCDP
withdrew the event, or our harvest missed it. Before this change a short harvest of the newest
release was *masked* — the old rows stayed, the totals ran high, nothing was lost. After it, the
same shortfall is *amplified*: each missing event takes its predecessor's row with it. The harvest
guard raises only when a shortfall exceeds both 1% and 1,100 events, a band set in April 2026 for
small candidate versions; on a 416,968-row annual release 1% is about 4,169 events. And nothing
would go red, because the dropped rows count into `n_stale` and conservation still balances — the
same blindness that let #594 run for four and a half months.

All four guards in the change were then sabotaged one at a time and confirmed to go red.

**A second review round found three more things, two of them in my own tests.** One guard that
needed widening: two distinct annual version strings can parse to the same tuple — `26.1` and
`26.01` both give `(26, 1)` — so which release counts as latest depended on row order in the
store. Supersession now refuses unless the versions are totally ordered. One finding documented
rather than fixed: the span bound is derived from `max(date_end)` rather than from the release's
declared span, so one corrupt far-future date in the newest release makes it vacuous and
supersedes the older release wholesale. Same cause as #598 and recorded there; it moved the
recommendation on that issue from "hard-code the invariant" to "carry the declared span into the
store", because only a declared span is immune to a corrupt date on both sides of the comparison.

And one test of mine could not fail. `test_later_annual_release_wins_for_a_shared_event` asserted
only the output value, which survivorship alone already produces for an id with two annual rows —
it passed against `development` with the entire supersession block absent. It now asserts
`n_events_input == 1`, which is the thing that distinguishes supersession (the older row is removed
from the input) from survivorship (the older row is merely outvoted). Then the fixture for the new
ambiguous-version guard was decorative on its first attempt too, for the third time tonight: the
losing release's event fell outside the winner's span, so it survived either way. Both now go red
when the code they guard is disabled.

Three decorative guards in one evening, each caught by something other than me, is the number
worth remembering from this incident.

**A third round, a `/falsify` audit, found the worst defect of the three rounds — in the fix.** A
null `date_end` in the newest annual release made the supersession step delete **every** annual
row, its own release included. `n_read=2, n_input=0, n_output=0`, conservation balancing exactly,
nothing logged above INFO. On `development`, before supersession existed, the same input raises
`TypeError`.

So the fix for a silent-wrong-data bug had introduced a silent-total-data-loss path. The cause is
pyarrow's null semantics: `pc.max` skips nulls and returns null, `pc.greater` against a null
scalar yields null, and `filter` treats null as drop. Worse, because the new step runs first, it
changed the input to the *Annual coverage boundary* rule so that rule's own `TypeError` no longer
fired — the new code did not merely fail silently, it silenced an existing alarm.

The step now refuses to supersede when any annual `date_end` is null, which lets the pre-existing
loud failure fire. No new error path. Measured: zero nulls and zero empty strings in `date_start`
and `date_end` across all 384,918 rows of the annual snapshot, so this was never reachable with
real data — but ADR-023 §2 documents a missing `date_end` as possible, which makes it a
contract-relevant shape rather than a hypothetical.

That audit also corrected the test count stated in this document and in `findings.md`, which both
said 2,622 when the suite was 2,625. And it cleared one thing I expected to be a gap: ADR-040
already disclaims ownership of *which* events are selected, so no amendment to it was owed by
this change.

**The lesson is not "review caught it".** It is that I wrote a guarantee into a code comment and an
ADR, wrote a test whose docstring claimed the guarantee and whose body tested half of it, and did
not notice. That is the same failure as #597, one layer down: a correctness property asserted in
prose, with a guard that looked like it checked it.

## Honest negatives — what we got wrong on the way

Recorded because the register and the ADRs are the only places this stays true, and because three of
these were caught by the operator pushing back, not by self-checking.

1. **"This is release vintage lag."** Asserted before measuring, about a figure of roughly 2,200
   deaths, as part of an explanation sent to an external reader. When challenged with "I still don't
   get this sentence", the figure could not be reproduced and the explanation was withdrawn and
   replaced with an honest admission. It later turned out to be substantively right — these were
   withdrawn v25.1 events — but it was unproven at the time it was stated, and being lucky is not
   the same as being correct.
2. **"UCDP assigns an event to the country whose conflict it belongs to."** Wrong. UCDP's `country`
   field is where the event took place. This was in a paragraph written for an external reader, and
   it took two rounds of "I still don't get this sentence" before it was checked and found false.
3. **"The 8,569 Kursk deaths are piled in one cell and pass through unredistributed."** Wrong.
   Production runs `kgi_kti_activity`, whose spatial strategy is `proportional`, and those deaths
   are spread across all 13 Sumska cells. #593's body was corrected and a correcting comment posted.
4. **"Placeholder coordinates are the problem."** The operator pushed back that country-centroid
   handling was already solved, and asked for it to be measured. Measuring by `where_prec` proved
   him right and produced the real finding: the damage is at level 5, not at level 6. #593 was
   retitled and rewritten.
5. **A table was sent with no scope label.** The "summed over all grid cells" caveat existed in an
   earlier message; the corrected table that was actually re-sent carried no scope in its heading.
   That table went into a mail and generated the question that started all of this. Commitment made:
   scope goes in every table heading, every time.

The pattern across 1, 2, 3 and 4 is the same: an explanation was produced before the corresponding
measurement. In each case the measurement, once taken, contradicted it.

## Verification performed

- Full suite: **2,626 tests, 0 failures, 0 errors**, counted from JUnit XML rather than the exit
  status — this repo's conftest withholds the summary line, and C-345 warns that a piped status can
  hide a SIGKILL.
- `ruff check .`, `mypy src/` (91 files), `bash docs/validate_docs.sh` — all clean.
- Both regression tests confirmed red with the source change reverted, green with it.
- CI on #596: docs 7s, lint 20s, typecheck 28s, test 9m19s, test-py313 15m23s — all pass.
- Conservation held in both builds: `n_read == n_input + n_stale`.
- Before-fix scratch build reproduces the figures in the served store and in the 2026-11-17 mail.
- Scratch store: production's `ucdp_ged_v26.1_1989_2025.parquet` (416,968 rows, digest matching the
  production consolidation ledger) plus local raw — 2,713,398 rows across 164 sources, against
  production's 2,891,590 across 177. The difference is more recent candidate and monthly files,
  which cannot affect any year an annual release covers.

## Remaining weaknesses

1. **Nothing compares our totals to the source's totals.** This is the gap that let a 4.5-month
   error run. There is no precedent in the repo for asserting our figures against UCDP's — the
   nearest thing, ADR-027's harvest count check, lives in production code, not a test — and the
   suite cannot hold it anyway, because `data/` is gitignored and CI has no fetch step. An
   out-of-band check is the plausible shape. Not filed yet; it is the strongest candidate for the
   next issue out of this.
2. **No alarm when a second annual release lands.** The transition from one annual release to two is
   exactly the moment this class of defect becomes possible, and it passed unremarked on 2026-07-02.
3. **The span bound is upper-only (#598).** A release starting later than its predecessor would
   delete the earlier history. Open, with the reproduction in the issue.
4. **A short harvest of the newest annual release deletes the previous release's rows** (C-371,
   Tier 2). Registered, not fixed; the smallest candidate fix is a tighter shortfall tolerance for
   annual, where the UCDP `type_of_violence=4` offset is 0.26% rather than 40–100%.
5. **The same unlabelled-list shape is elsewhere.** 16 of 56 ADRs carry numbered rule lists;
   ADR-049 (22 closed-list phrasings) and ADR-053 (19) enumerate the handling of `where_prec` levels
   and have an open instance of the same problem in #593. Filed as #597.
6. **`fetch_ucdp_annual`'s local-first guard uses `last_digest`, not `last_digest_for_version`**, so
   a snapshot restored without its ledger line would be treated as cached. Latent, unrelated to this
   incident, not filed.
7. **`docs/` cannot cite the UCDP viewpoint builder by symbol**, because
   `src/datafactory_viewpoint/builders/` is missing from the citation guard's search roots. Found
   while writing the ADR-023 amendment; worked around by rewording rather than widening the guard.
   Not filed.
8. **`low`/`best`/`high` are apportioned independently**, so per-cell ordering between them is not
   enforced. Pre-existing, unrelated, not filed.

## Lessons

1. **An append-only store needs a supersession rule for every source family it holds, not for the
   ones where the problem has already bitten.** The monthly rule existed because a previous
   investigation hit it. The annual rule did not exist because nothing had hit it yet. Both families
   had the same property and only one had the rule.
2. **A source that corrects its data by subtraction breaks the assumption that newer means more.**
   Our handling was built around revision — same event, better numbers. Deletion is a different
   operation and nothing in the pipeline represented it. Worth asking of every source we ingest:
   can a record disappear?
3. **A one-directional error is a different diagnosis from a scattered one.** Our totals were above
   UCDP's in all three years and never below. That sign, not the magnitude, is what identified the
   cause. Always look at the sign of a discrepancy before explaining its size.
4. **Conservation invariants cannot see this class of error.** Every ADR-040 conservation check held
   throughout: deaths were neither created nor destroyed by the pipeline. The error entered at
   ingestion of a release that was later withdrawn, which is upstream of everything conservation
   watches. Conservation proves the pipeline did not corrupt the data; it says nothing about whether
   the data should have been there.
5. **An enumerated list in a governing document is read as exhaustive whether or not it is.** Three
   rules presented as a specification stopped further enquiry for months. If a list is open, it has
   to say so.
6. **Explain after measuring, not before.** Four wrong explanations in one evening, all produced
   before the corresponding measurement, three caught by the operator and not by self-checking. The
   cost was real: one of them went out in a mail to an external reader and had to be retracted.
7. **Put the scope in the heading of every table, not in the sentence above it.** A table travels;
   the sentence does not. This one travelled into a mail and cost a day.
8. **Being found by an external reader is a result about our checks, not about them.** Håvard had no
   access to our pipeline. He compared a number we published to a number on a website. That is the
   cheapest possible check and we were not running it.

## Open after this post-mortem

🛠️ In order, all requiring the operator:

1. **Merge #596.** Green, mergeable, targeting `development`.
2. **Rebuild and redeploy.** This republishes the figures. Confirmed at the moment of doing it.
3. **Verify the served store:** `scripts/verify_consumer_contract.py`, plus the three global totals
   read back through `load_dataset`.
4. **Notify views-hydranet, views-models and views-postprocessing.** A figure change, not a release
   note. The outstanding 26.49% → 35.94% state-based correction belongs in the same message.
5. **Then** the follow-up to Håvard, which was the operator's explicit condition: mapped, fixed and
   proven before anything goes out.

📌 Tracked and not blocking: #592, #593, #597.

❔📌 Not yet filed, listed in Remaining weaknesses above: the source-total comparison check (1), the
second-annual-release alarm (2), the `last_digest` guard (6), and the citation-guard search root (7).
