# Pre-Analysis Plan: ACLED cursor pagination returns the same data as offset pagination

**Registered:** 2026-10-10
**Status:** Pre-registered (hypotheses stated before implementation code)
**Investigators:** Simon Polichinel von der Maase, Claude Code

---

## 1. Claim Under Investigation

> For any query slice, walking the ACLED API with `&cursor=X` and terminating on
> `next_cursor is null` returns exactly the same events as walking it with `&page=N` and
> terminating on a short or empty page.

This is falsifiable in one comparison: harvest one slice both ways, and the claim dies if the two
event sets differ in any member or in any field of any member.

It is also falsifiable **only until 27 October 2026**. After that date ACLED removes offset
pagination and the comparison can never be made again. That deadline, not the size of the code
change, is why this is pre-registered rather than simply implemented.

## 2. Background

ACLED's notice:

> "We've rolled out a new cursor-based pagination method and will deprecate the current offset
> method on 27 October 2026."

`fetch_paginated()` in `src/datafactory_harvester/sources/acled.py:377-465` sends `"page": page`
and terminates on three conditions: an empty `data` array (`:436-437`), a page shorter than
`config.page_size` (`:448-449`), or the optional `max_pages` cap (`:450-455`). The migration
replaces the request parameter and **deletes the first two terminators**, leaving
`next_cursor is None` as the only authoritative one.

### Why pre-registration matters here

A termination bug in a harvester does not announce itself. It returns fewer events, and
`_fetch_single_year()` records them with `outcome: "success"` and a new content digest. Nothing in
this repository reads `n_events` back to compare it against the previous harvest of the same year
(#488), so a short harvest becomes the cached truth on the following run.

ADR-027 exists because this already happened on UCDP — `page_size=50000` returned 335,918 of
384,918 events and the harvest reported success, because it validated schema and provenance but
never counted (`reports/post_mortems/2026-04-25_stale_zarr_store.md`). The residue is still a
manual check: `docs/guides/server_operations.md:238-239` asks an operator to read the expected
ACLED count off stdout and compare it by eye.

So a passing test suite is weak evidence here. The suite's ACLED tests patch
`datafactory_http.retry.requests.request` with ordered `side_effect` lists and none inspects the
request parameters to decide what to return — so **every one of them would pass against a mock that
simply hands back whatever the loop asks for next**, regardless of whether the loop walks correctly.
The parity measurement is the only check that compares our walk against the real API's notion of
completeness.

Registering first also forces the awkward branch to be planned: what we do if the two walks
*disagree*. That branch is §4, and committing to it before the measurement is what makes "stop" a
plan rather than a rationalisation.

## 3. Hypotheses

### H1: The two walks return identical data

**Prediction:** For one slice harvested both ways, the `event_id_cnty` sets are identical, the
symmetric difference is empty, every shared record is field-for-field equal, and the
`content_digest` computed by `validate_events()` is byte-identical.

**Falsification criterion:** Any difference in any of the four. Not "fewer than N differences" — any.

**Rationale:** `content_digest` is the right oracle because it is order-insensitive (it sorts before
hashing, `src/datafactory_harvester/event_validation.py:197-202`) so a different page ordering
cannot produce a false mismatch, and because it is the exact value the ingestion ledger records and
`_year_is_cached()` compares against. Parity in this number is parity in the terms the pipeline
already trusts.

**Risk:** The digest covers only `("event_id_cnty", "fatalities")`, so it alone would miss a
divergence in `latitude`. Full-record equality is asserted alongside it for that reason.

### H2: `next_cursor` is a top-level key in the JSON response body

**Prediction:** Every response in a `_format=json` cursor walk carries `next_cursor` at the top
level of the body.

**Falsification criterion:** The key is absent, or nested inside another object.

**Rationale:** ACLED's notice says so, but we have it second-hand — neither source is ACLED's own
page, and a third-party PR (kwyjad/Pythia#949) explicitly flags that the field's name and placement
rest on the notice rather than on an observed response. The notice also says that under
`_format=csv` the value moves to an `X-Next-Cursor` header, which is evidence that its placement is
format-dependent and therefore worth confirming rather than assuming.

**Risk:** This is a structural prerequisite, not a finding. If it fails the rest of the plan is
void, which is why it is tested first and separately.

### H3: `next_cursor` is null exactly once, on the final page

**Prediction:** Every non-terminal response carries a non-null `next_cursor`; the terminal response
carries null; and the walk does not continue past it.

**Falsification criterion:** A null `next_cursor` on a response that is not the last, or a walk that
never produces a null.

**Rationale:** This is the entire termination contract. If null can appear mid-walk the new
terminator truncates; if it never appears the walk does not end.

### H4: A cursor walk returns a short page while the cursor is still live

**Prediction: unknown, and deliberately so.** This is the one hypothesis with no prior.

**Falsification criterion:** n/a — this is a measurement, not a prediction. The result is recorded
either way.

**Rationale and why it is worth measuring:** the migration deletes
`if len(results) < config.page_size: break`. If ACLED's cursor walk *does* hand back a short page
mid-series, that deletion is **empirically load-bearing** — keeping the heuristic would have
truncated real harvests. If it never does, the deletion is defensive and its necessity is unproven,
which is a weaker but honest thing to record. Either answer is useful; neither changes the decision
to delete it, because `next_cursor` is authoritative regardless.

**Note on relevance:** this also settles whether the *old* code was ever at risk. Under offset
pagination a short page genuinely did mean the end of the series, so the old heuristic was correct
for the old API. The question is only whether it survives the change of mechanism.

### H5: `count` and `total_count` remain null under cursor pagination

**Prediction:** Both stay null, as in the committed fixture `tests/fixtures/acled_sample.json`.

**Falsification criterion:** Either carries a number.

**Rationale:** Those two nulls are the entire basis of **C-153** ("ACLED API has no TotalCount —
silent truncation undetectable") and of ACLED's exemption from ADR-027, whose rule is
`len(fetched) >= TotalCount * (1 - tolerance)` with violations raising and halting the pipeline. If
the new API populates either field, C-153 can be **closed** rather than amended, ADR-027 becomes
applicable to ACLED, and #488 gets a much better answer than a previous-vs-current count comparison.

**Risk:** Falsifying this would be good news, which is exactly the kind of prediction worth
committing to in advance. It is predicted null because nothing in ACLED's notice mentions these
fields, and a pagination change is no reason to start computing a total.

### H6: An empty page with a live cursor never occurs

**Prediction:** Not observed in any walk.

**Falsification criterion:** One occurrence.

**Rationale:** The new implementation *raises* on this condition. The alternatives were worse —
continuing risks an unbounded loop against a rate-limited API, and breaking is the silent
truncation this whole change exists to prevent. But a raise is a new production failure mode
introduced on a deadline, and the honest basis for it is that we have observed ACLED's cursor
behaviour once. This hypothesis is what turns that assumption into a measurement.

**Risk:** A walk of a few hundred events cannot prove the condition never occurs on a walk of
400,000. This measurement bounds the claim; it does not establish it. Stated here so the limit is
recorded rather than discovered later.

## 4. Decision Criteria

These are pre-committed. We will not revise them after seeing results.

| Outcome | Decision |
|---|---|
| **The detection drill fails** — the script cannot distinguish two deliberately different walks | **Discard the result entirely.** No parity claim is made, nothing ships, and the script is fixed before the measurement is re-run. A null result from an instrument that cannot detect the effect is not evidence. |
| H2 falsified — `next_cursor` is not a top-level body key | **Stop and re-plan.** The implementation design is void. Record the real envelope shape in `findings.md` and re-register. |
| H1 holds, H2 and H3 hold | **Proceed.** Commit the recorded envelopes as fixtures, ship the migration, release before 21 October. |
| **H1 falsified** — the walks disagree | **Stop. Do not ship.** Determine *which* walk is wrong before anything else; a cursor walk that returns more events than offset is as alarming as one that returns fewer. Write it up in `findings.md`, raise it with ACLED (Katayoun, per `docs/sources/acled.md`), and re-register with the discrepancy as the subject. Shipping either mechanism while they disagree is shipping a known-unknown into FAO-facing data. |
| H3 falsified — null mid-walk, or never null | **Stop and re-design the terminator.** The plan's central assumption is wrong. |
| H4 positive — short pages mid-walk observed | Record it as the empirical justification for deleting the short-page break. Proceed. |
| H4 negative — no short pages observed | Record that the deletion is defensive and its necessity unproven on this slice. Proceed anyway: `next_cursor` is authoritative whether or not the heuristic would have failed. |
| **H5 falsified** — `count` or `total_count` populated | Proceed with the migration unchanged, and open a follow-up to apply ADR-027's tolerance rule to ACLED and close C-153. **Do not do it in this branch** — it is a second change to harvest failure behaviour and belongs with #488. |
| H6 falsified — empty page with a live cursor observed | **Change the implementation before shipping**: the raise becomes a bounded retry with a warning, and the bound is stated. Log it in §7 as a deviation. |
| Parity holds but the fixtures cannot be recorded | **Blocking.** The fixtures are the only artefact that keeps the claim checkable after 27 October. Without them the measurement is a one-off assertion in a chat log, which is the failure mode this repository keeps paying for. |

## 5. Null Outcomes

Recording a null result is the point of pre-registering it. All of the following are acceptable
outcomes, publishable as-is, and none is a reason to go looking for something more interesting:

- **H1 holds and nothing is learned about ACLED.** The expected outcome. The deliverable is then the
  fixtures and the parity test, not a discovery.
- **H4 negative.** The short-page break is deleted without ever having been dangerous. The deletion
  is still correct; it is simply not vindicated.
- **H5 holds.** C-153 stays open and is amended rather than closed. No new capability.
- **H6 holds on a small slice and remains unproven at scale.** Explicitly a bounded result.
- **The migration turns out to be a twelve-line diff.** Proportionate is not the same as trivial;
  the measurement is what makes a twelve-line diff safe to ship into a monthly cron that nobody
  watches.

## 6. Method

### Step 1: Confirm the envelope before writing implementation code

One authenticated request, `&cursor=0`, narrow slice. Record and commit the raw top-level keys.
Settles H2 and H5. If H2 fails, stop here.

### Step 2: Write the parity script with both walks in it

`scripts/verify_acled_pagination_parity.py`, holding the cursor walk and the offset walk as sibling
functions. The offset walk is a **deliberate local copy** of the production loop, not an import —
the same construction and for the same stated reason as
`scripts/verify_area_majority_projection.py`: this script's whole job is to compare against what
production does today, and importing it would mean a later change there silently moves the baseline
this measurement was taken against.

### Step 3: Prove the measurement can detect a difference (precondition for Step 4's result)

`--self-test`, run as a hard precondition inside `main()` before any live request is made.

Construct two walks over synthetic responses that are *known to differ* — one event dropped from the
middle of one walk — and assert the comparison reports a mismatch on all four oracles (set
difference, record equality, digest, count). Then construct two walks known to be identical and
assert it reports parity.

Without this, "the digests match" is indistinguishable from a script that hashes the same list
twice. The existing suite cannot substitute: its mocks return responses from an ordered list
without inspecting the request, so they cannot tell a correct walk from one that asks for the wrong
page and is handed the right answer anyway.

### Step 4: Run the comparison live, once, before 27 October

One-month `event_date` window, `limit=500`, so a complete walk is a handful of pages each way —
enough to exercise multi-page termination, which a `max_pages`-capped walk would not. Well below the
courtesy threshold in `docs/guides/hetzner_deployment_guide.md:199-205` (a full re-fetch is ~480
pages; a normal monthly run ~80; this is single digits), so no advance note to ACLED is owed.

Settles H1, H3, H4, H6.

### Step 5: Emit the result and the fixtures

`reports/investigation_acled_cursor/parity.json` — slice, UTC timestamp, git sha, per-walk request
counts, both digests, the four comparison results, and a `"method"` string. Raw envelopes from both
walks to `tests/fixtures/acled_cursor/`.

**This is the only irreversible step in the plan.** After 27 October the offset envelopes cannot be
recorded again by anyone.

### Step 6: Make the claim survive the deadline

A fixture-replay parity test in `tests/`, so the comparison is re-run by CI indefinitely rather than
asserted once by hand.

### Step 7: Mutate the terminator and confirm the tests catch it

Six hand-applied mutants on the loop exit (restore either deleted break; invert the null check;
re-add `page` to the params; drop the missing-field guard; reset the cursor to 0 instead of
advancing). Each must turn the suite red. A surviving mutant on the termination condition means the
tests do not actually constrain the thing this change is about.

## 7. Deviations Log

*Intentionally empty at registration time.*

| Date | Deviation | Rationale |
|---|---|---|
