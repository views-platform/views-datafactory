# Do ACLED's cursor and offset pagination return the same events?

**Issue:** #487 · **Pre-registered:** 2026-10-10 (`pre_analysis_plan.md`, commit `18029fe`)
**Measured:** 2026-10-10 · **Register:** C-153 (amended), C-359 (new)
**Status:** Complete. H1 holds — the migration is safe to ship. H4 came back negative and that is recorded as such.

---

## The question, and the short answer

ACLED removes offset (`&page=N`) pagination on **27 October 2026**. Our harvester used it. Before
replacing the mechanism we needed to know that the replacement returns the same data — and that
question could only be answered before the deadline, because after it one half of the comparison
ceases to exist.

**It returns the same data.** One slice harvested both ways returned **7,609 events in 8 requests
each way**, identical on all four oracles, content digest `ae4a6e815168e95f` both times.

This document follows the shape of `reports/investigation_zarr_restatement/findings.md`: what is
confirmed, what is inferred, and what is genuinely open. Every claim carries a citation. Where the
evidence runs out, that is said rather than smoothed over.

---

## 1. What we KNOW (empirically confirmed)

### 1.1 `next_cursor` is a top-level key in the JSON body, and it is an integer

H2 confirmed. The live envelope carries nine top-level keys:

```
status, success, count, total_count, messages, data, filename,
next_cursor, data_query_restrictions
```

Observed `next_cursor` values across the recorded walk, in order:

```
1156286 → 1185253 → 1331256 → 1595700 → 1874023 → 2130249 → 2427980 → null
```

Monotonically increasing integers, consistent with being row identifiers.

**This matters more than it looks.** The cursor is an `int`, the walk starts at `cursor=0`, and `0`
is falsy in Python. A termination test written as `if not next_cursor: break` would end a walk on a
legitimate cursor value. `fetch_paginated()` therefore tests `is None`, and
`test_zero_cursor_is_not_treated_as_terminal` in `tests/test_acled_harvester.py` pins it. Mutant M8
in the drill below is exactly this error, and it is caught.

ACLED's notice said the field was in the body; we had that second-hand, from two trackers rather
than from ACLED (kwyjad/Pythia#949 flagged that the name and placement rested on the notice).
It is now confirmed against a real response.

### 1.2 The two walks returned identical data

H1 confirmed. Four independent oracles, all agreeing:

| Oracle | Result |
|---|---|
| Event count | 7,609 = 7,609 |
| `event_id_cnty` set | identical, symmetric difference empty |
| Full-record equality over sorted lists | equal |
| `content_digest` | `ae4a6e815168e95f` = `ae4a6e815168e95f` |

Slice: all countries, `2024-03-01|2024-03-07`, `limit=1000`, no event-type filter. Recorded in
`parity.json` with the UTC timestamp and git sha.

The digest is the load-bearing oracle because it is the value the ingestion ledger records and
`_year_is_cached()` compares against, and because `validate_events()` sorts before hashing — so a
different page ordering between the walks could not have produced a false mismatch. Full-record
equality is asserted alongside it because the digest covers only `event_id_cnty` and `fatalities`
and would not have seen a divergence in, say, `latitude`.

### 1.3 The measurement can detect a difference

This is a precondition, not a formality. `scripts/verify_acled_pagination_parity.py` runs a
four-part detection drill before it makes a single request, and `main()` aborts if the drill fails.
The drill checks that identical input reports parity, that a dropped event trips **all four**
oracles, that a single changed field trips `records_equal` even where the counts and id sets agree,
and that the two walk implementations actually behave differently on input designed to separate
them.

The drill was itself verified by sabotage — two deliberate breaks, both caught, each returning
exit 1:

- forcing `"parity": True` → *"a dropped event was reported as parity"*, *"a changed field was
  reported as parity"*
- deleting the short-page break from the frozen offset walk → *"both walks returned the same count
  on input designed to separate them — the two walks are not actually different"*

Without this, "the digests match" would be indistinguishable from a script that hashes the same
list twice. The existing ACLED tests could not substitute: all 22 of them patch
`datafactory_http.retry.requests.request` with an ordered `side_effect` list and none inspects the
request parameters, so they cannot tell a correct walk from one that asks for the wrong page and is
handed the right answer anyway.

### 1.4 `next_cursor` is null exactly once, on the final page

H3 confirmed. Seven non-null integers, then one null, and the walk stopped there. Pinned against
the recording in `test_acled_cursor_parity_fixture.py`.

### 1.5 `count` and `total_count` are still null

H5 confirmed — the prediction was that they stay null, and they do, on every page of the walk.

**So C-153 stands and is amended rather than closed.** ACLED still reports no server-side total,
which is why it remains exempt from ADR-027's
`len(fetched) >= TotalCount * (1 - tolerance)` rule. Had either field carried a value, the better
fix for #488 would have been to apply ADR-027 to ACLED and close C-153 outright. It did not, so
#488 keeps the harder problem.

### 1.6 No empty page with a live cursor

H6 confirmed on this slice. The implementation raises on that condition, and it did not fire. See
§3.1 for what that does and does not establish.

### 1.7 All eight termination mutants are caught

The drill, run 2026-10-10, baseline green, every mutant reverted afterwards (`git diff` clean):

| Mutant | Verdict |
|---|---|
| M1 restore `if len(results) < config.page_size: break` | CAUGHT |
| M2 restore `if not results: break` | CAUGHT |
| M3 `if next_cursor is None` → `is not None` | CAUGHT |
| M4 send `"page": page` alongside `"cursor"` | CAUGHT |
| M5 drop the missing-`next_cursor` guard | CAUGHT |
| M6 `cursor = next_cursor` → `cursor = 0` | CAUGHT |
| M7 drop the empty-page-with-live-cursor raise | CAUGHT |
| M8 terminate on falsiness instead of `is None` | CAUGHT |

M6 deserves a note: an event-count assertion alone would **not** have caught it, because the mock
hands back the next response in its list regardless of what was requested. What catches it is
asserting the **request count** and the **sequence of cursors sent** —
`test_cursor_threads_through_three_pages` and
`test_walk_sends_the_cursors_acled_actually_issued`.

---

## 2. What we THINK we know (inferred from evidence)

### 2.1 The old short-page heuristic would probably have worked on this slice too

H4 came back **negative**: no page returned fewer than `limit` events while the cursor was still
live. Every non-terminal page was exactly full, and the final page was short *and* carried a null
cursor — so the deleted heuristic and the new terminator would have agreed.

That is worth stating plainly rather than quietly omitting, because it means **this measurement
does not vindicate the deletion.** The deletion is still correct — `next_cursor` is what the server
declares and page length is not evidence of anything under cursor pagination — but the risk it
guards against was not observed. It is defensive, not demonstrated.

What makes it more than defensive: the migration's termination logic is now the *only* thing
standing between a provider-side behaviour change and a short harvest, and the mutation drill shows
the tests constrain it. The argument for the deletion is structural, not empirical, and the honest
basis for believing it is M1 being caught rather than H4 being positive.

### 2.2 Parity on one week probably generalises

7,609 events across 8 pages is a real multi-page walk with real pagination boundaries, and the
agreement is exact rather than approximate. Nothing about the mechanism suggests it would behave
differently at 400,000 events across 80 pages.

Inferred, not confirmed. A full-year walk both ways would have cost roughly a full re-fetch's worth
of API load — ~480 pages per walk against a courtesy threshold that asks for an advance email at
that scale (`docs/guides/hetzner_deployment_guide.md`). The judgement was that exactness on a
smaller slice buys more than approximation on a larger one.

---

## 3. What we DON'T know (open questions)

### 3.1 Whether the empty-page raise can fire in production

`fetch_paginated()` raises when a response carries no events while `next_cursor` is non-null. The
alternatives were worse — continuing risks an unbounded walk against a rate-limited API, and
stopping is the silent truncation the whole migration exists to prevent — so raising is the ADR-011
answer.

But it is a **new production failure mode introduced on a deadline**, and the evidence for it is
one 8-page walk. A walk of 84 or 7,609 events cannot establish that the condition never arises on a
walk of 400,000. If it fires on the 21 October run, that is a finding about ACLED and not a bug in
this code — and the error message says what it refused to do and why, which is what makes it
actionable rather than mysterious.

### 3.2 Whether cursor pagination is stable across a restatement

ACLED issues retroactive corrections and the cursor appears to be a row identifier. If a
correction inserts or deletes rows *mid-walk*, a cursor-based walk could in principle skip or
repeat events in a way an offset walk would not — or vice versa. Not measured, and not measurable
without catching a restatement in the act.

This is the one place where the two mechanisms could genuinely differ in production while agreeing
on every static slice we can test. Recorded as C-359's neighbour rather than solved.

### 3.3 Whether a short harvest would be noticed

**It would not.** `_fetch_single_year()` writes `n_events` to the ledger and nothing reads it back;
`compare_snapshots()` computes `n_removed` and discards it. A zero-event year fails loud; any
non-zero shortfall is recorded as `outcome: "success"` with a new short digest.

Out of scope here, pre-existing, equally true of the offset path, and tracked as **#488** with a
register entry. What this change owns is narrower and stated so the narrowing is not silent: **the
pagination loop cannot silently truncate**, which the mutation drill demonstrates.

---

## 4. Recommendation

1. **Ship the migration.** H1, H2, H3, H5 and H6 all resolved in favour of it; H4 is neutral.
2. **Release and deploy before the 21 October cron.** The October run then exercises cursor code in
   production while offset still works at ACLED, so `git checkout v1.13.0` remains a live revert
   target. Deploying after the 27th means the first production run of the new code happens when
   the old code no longer runs at all.
3. **Amend C-153 and ADR-027.** Both name the short-page heuristic as ACLED's only completeness
   signal. That is now false; `next_cursor` replaces it, and is strictly more information because
   the server declares it rather than the client inferring it.
4. **Keep the fixtures.** `tests/fixtures/acled_cursor/` is the only artefact that keeps this claim
   checkable after 27 October, and `tests/test_acled_cursor_parity_fixture.py` is what re-checks
   it. Neither can be regenerated after the deadline by anyone.
5. **Do not fold #488 into this.** It is the better problem and it deserves its own change.

---

## References

- `scripts/verify_acled_pagination_parity.py` — both walks, the detection drill, the comparison
- `parity.json` — the headline measurement (7,609 events, all countries)
- `parity_fixture_slice.json` — the narrow run that produced the committed fixtures (84 events,
  Somalia); narrow because an ACLED event is ~1.4 KB, so the broad slice would have been a 10 MB
  fixture per walk
- `tests/fixtures/acled_cursor/{offset,cursor}_walk.json` — the recording, 113 KB each
- `tests/test_acled_cursor_parity_fixture.py` — the replay, including its own truncation drill
- `fetch_paginated()` in `acled.py` — the implementation
- GitHub: #487, #488 · register C-153, C-359 · ADR-011, ADR-027, ADR-032
- ACLED's notice, relayed: mapme-initiative/mapme.biodiversity#492,
  forecastingresearch/forecastbench#315; field-placement caveat: kwyjad/Pythia#949
