# Sprint Plan S1: Risk Register Curation

**Date:** 2026-05-26
**Branch:** `development` (register-only changes, no code modifications)
**Goal:** Apply the 13 mechanical fixes identified by the strategic review (2026-05-26) to bring the register into a clean state before documentation and deployment sprints.
**Estimated effort:** 30–45 minutes.
**Source:** `/review-rr strategic` (2026-05-26), `/review-rr prioritize` (2026-05-26).
**Prerequisite:** None. This sprint can begin immediately.
**Blocking:** Sprint S2 (V-Dem documentation) and S3 (Hetzner deployment) benefit from accurate register state but are not blocked by this sprint.

---

## Context

The strategic review found 13 issues across 4 categories:

1. **Stale [RESOLVING] entries (3):** C-133, C-137, C-139 have code fixes merged and verified but remain marked as [RESOLVING] because the original narrative conflated code completion with Hetzner deployment. The Hetzner deployment dependency is tracked by C-130 and C-132 — these three entries' own fixes are complete.

2. **Status conflict (1):** C-155 is shown as resolved in the summary table (line 93, strikethrough) but remains open in the full entry body (line 594, `[DEFER]`). The V-Dem verify script was created on 2026-05-26 (resolving the immediate trigger), but the underlying concern — 5 bespoke verify scripts with no shared framework — remains valid.

3. **Trigger quality (3):** Three triggers are vague or perpetual and need rewriting to be actionable.

4. **Signal-to-noise demotions (4):** Four entries (C-75, C-93, C-96, C-21) are observations rather than risks. They were flagged in both the 2026-05-24 and 2026-05-26 strategic reviews.

After all changes, the register should drop from 67 open entries to 60 — a meaningful noise reduction that makes the register usable for sprint planning.

---

## Task 1: Resolve C-133, C-137, C-139

**Why:** These three T2 entries have been in [RESOLVING] status since April 2026. Each has a code fix that was merged, tested, and confirmed working. The original [RESOLVING] status reflected that the fix hadn't been deployed to Hetzner, but that deployment dependency belongs to C-130 and C-132 — not to these individual entries. Leaving them in [RESOLVING] inflates the Tier 2 count and gives a false sense of urgency.

### C-133: Zero-padding warning only fires for integer `end` parameter

**Evidence fix is complete:**
- `src/datafactory_query/dataset.py`: Warning moved to after time slicing. Now computes effective end month_id from `time_steps[-1]` (the actual loaded data), not from the `end` parameter.
- Fires for all three calling patterns: integer end, string end, `end=None`.
- Confirmed by falsification tests P4 and P6 (2026-04-22).

**Steps:**
1. In the summary table, strike through the C-133 row: `| ~~C-133~~ | ~~3~~ | ~~Zero-padding warning only fires for integer `end` parameter~~ | Resolved 2026-05-26 | Data boundary |`
2. In the full entry (Tier 3 section), change the heading to `### ~~C-133~~: Zero-padding warning only fires for integer `end` parameter — RESOLVED`
3. Add resolution note at the end of the narrative: `**Resolved 2026-05-26.** Code fix complete and merged. Warning fires for all calling patterns (integer, string, None). The Hetzner deployment dependency (remote zarr store lacking `last_valid_month_id` attribute) is tracked by C-130, not by this entry.`
4. Move the full entry text to `reports/archive/technical_risk_register_resolved.md`.

### C-137: No round-trip integrity check after zarr export

**Evidence fix is complete:**
- `scripts/export_zarr.py`: After writing and consolidating the zarr store, reads back each feature and asserts `zarr_sum == grid_sum`. Exits with code 1 on mismatch, halting the pipeline.
- Fix applied 2026-04-24 in response to the stale-zarr incident.

**Steps:**
1. In the summary table, strike through the C-137 row: `| ~~C-137~~ | ~~2~~ | ~~No round-trip integrity check after zarr export~~ | Resolved 2026-05-26 | Data integrity |`
2. In the full entry (Tier 2 section), change heading to `### ~~C-137~~: No round-trip integrity check after zarr export — RESOLVED`
3. Add resolution note: `**Resolved 2026-05-26.** Round-trip sum verification added to `export_zarr.py` on 2026-04-24. Each feature's zarr sum is compared against grid sum; exit code 1 on mismatch. Fix has been in production since v1.2.7.`
4. Move full entry text to resolved archive.

### C-139: Consumer parity tests check per-cell rates but not aggregate totals

**Evidence fix is complete:**
- `tests/test_consumer_parity.py`: Global sum assertion added to `assert_consumer_parity()`. For each feature column, asserts `abs(factory_total - reference_total) / reference_total <= 0.1%`.
- Fix applied 2026-04-24.

**Steps:**
1. In the summary table, strike through the C-139 row.
2. In the full entry (Tier 2 section), mark as resolved.
3. Add resolution note: `**Resolved 2026-05-26.** Global sum assertion added on 2026-04-24. For each feature column, asserts aggregate totals match within 0.1%.`
4. Move to resolved archive.

### Header count update after Task 1

- Resolved: 129 → 132
- Open: 67 → 64
- Tier 2: 8 → 6 (C-137 and C-139 were T2)
- Tier 3: 16 → 15 (C-133 was T3)

### Acceptance criteria

- All three entries are struck through in the summary table with "Resolved 2026-05-26."
- All three full entries have RESOLVED in the heading and a resolution note.
- All three are present in `reports/archive/technical_risk_register_resolved.md`.
- `grep -c "RESOLVING" reports/technical_risk_register.md` returns the expected count (should decrease by 3).

---

## Task 2: Fix C-155 Status Conflict

**Why:** The summary table (line 93) shows C-155 as resolved with full strikethrough, but the body entry (line 594) still reads `[DEFER]` under Tier 4. This contradiction means a reader checking the summary table sees 66 open entries while a reader scanning the full text sees 67. The V-Dem verify script was created on 2026-05-26 (resolving the immediate trigger "V-Dem is 5th pipeline source, no verify script"), but the underlying concern — 5 bespoke verify scripts with ~60% structural overlap and no shared framework — is still valid.

**Decision:** Un-resolve in the summary table. The trigger was addressed but the concern remains open. The summary table should say the trigger was closed, not that the entry is resolved.

### Steps

1. In the summary table, un-strike the C-155 row. Change from:
   ```
   | ~~C-155~~ | ~~4~~ | ~~No shared visual audit framework...~~ | Resolved 2026-05-26 | Visual audit |
   ```
   To:
   ```
   | C-155 | 4 | No shared visual audit framework — per-source scripts are idiosyncratic | Before 6th pipeline source (WDI) requires a verify script | Visual audit |
   ```

2. In the full entry body, add a note after the 2026-05-26 note:
   ```
   **Note (2026-05-26, review-rr strategic curation):** V-Dem verify script created (`scripts/verify_vdem_grid.py`, 15 plots), resolving the "5th source, no verify script" trigger. Underlying concern remains: 5 bespoke verify scripts (UCDP 1,015 lines, GHS-POP 811 lines, GHS-BUILT-S 978 lines, ACLED ~600 lines, V-Dem ~1,770 lines = ~5,174 lines total) with ~60% structural overlap. Trigger updated to 6th source (WDI).
   ```

3. Update the trigger in the full entry from `"6th pipeline source... **trigger fired**"` to:
   ```
   **Trigger:** Before 6th pipeline source (WDI) requires a verify script, or when shared verify framework is prioritized in refactor sprint. Previous trigger (5th source, V-Dem) resolved 2026-05-26.
   ```

### Header count impact

None — C-155 was already counted as open (T4) in the body. The summary table was wrong; we're fixing it to match.

### Acceptance criteria

- C-155 row in summary table has no strikethrough.
- C-155 full entry body has the note and updated trigger.
- Summary table open count matches body open count.

---

## Task 3: Rewrite 3 Triggers

**Why:** Three triggers are vague or use status language instead of action language. Actionable triggers answer: "What specific thing might someone do next that would make this concern a problem?"

### Trigger rewrites

| ID | Current Trigger | Proposed Trigger |
|----|----------------|-----------------|
| C-21 | "No migration planned" (status, not action) | "When views-metric-lab plans to migrate a model that depends on viewser-transformed features" |
| C-164 | "Reassess before WDI integration or next refactor sprint" (vague — "next refactor sprint" is perpetual) | "Before WDI integration, or when 6th pipeline source is planned" |
| C-74 | "When a new developer writes a CompilationConfig and the strategy string enum is needed for IDE discoverability" (already rewritten 2026-05-24, currently acceptable) | No change — keep current wording |

**Note:** On re-examination, C-74's trigger was already rewritten during the 2026-05-24 review-rr session. It's specific enough. Only C-21 and C-164 need rewriting.

### Steps

1. **C-21:** In the full entry body, change the trigger line. Append `(trigger rewritten during review-rr 2026-05-26)`.
2. **C-164:** In the full entry body, change the trigger field in the table. Append `(trigger rewritten during review-rr 2026-05-26)`. Also update the summary table trigger column.

### Acceptance criteria

- `grep -c "trigger rewritten during review-rr 2026-05-26" reports/technical_risk_register.md` returns 2.
- C-21 trigger no longer says "No migration planned."
- C-164 trigger no longer says "next refactor sprint."

---

## Task 4: Demote 4 Entries to Tech-Debt Backlog

**Why:** Four entries are observations rather than risks. They have no actionable trigger, no incidents, and no correctness or reliability impact. Keeping them in the risk register adds noise without providing governance value. Both the 2026-05-24 and 2026-05-26 strategic reviews flagged them for demotion.

The register is at 64 open entries (after Task 1). Removing 4 observations drops it to 60 — a healthy size for governance.

### Entries to demote

#### C-75: FeatureFrame shallow abstraction (T4)

**Why demote:** Observation from the initial 8-expert review (2026-03-17). 8 public methods wrapping numpy arrays. No incidents. No consumers have reported confusion. The entry itself says "Acceptable for a data wrapper; monitor if callers misuse." Two months of monitoring: no misuse observed. This is a code quality observation, not a risk.

**Action:** Add note: `**Note (2026-05-26, review-rr strategic):** Demoted to tech-debt backlog — observation from initial review, no incidents, shallow abstraction is acceptable for a data wrapper.` Strike through in summary table. Move to resolved archive with status "Demoted to tech-debt backlog."

#### C-93: `_count_outcomes` mixes raw counts with derived computation (T4)

**Why demote:** Pure code quality observation from PR #2 review (2026-03-30). Single function in `harvest_ucdp.py`. Never triggered. Never caused confusion. The mixing of enumeration with derivation is a naming/responsibility ambiguity in a 15-line function.

**Action:** Add note: `**Note (2026-05-26, review-rr strategic):** Demoted to tech-debt backlog — pure code quality, never triggered, single function.` Strike through and archive.

#### C-96: fsspec does not auto-read `~/.netrc` (T4)

**Why demote:** External dependency behavior. fsspec's `HTTPFileSystem` doesn't read `~/.netrc` — this is fsspec's design, not our bug. The workaround is documented in the consumer guide. We have no influence over fsspec's roadmap.

**Action:** Add note: `**Note (2026-05-26, review-rr strategic):** Demoted to tech-debt backlog — external dependency behavior, out of our control, workaround documented.` Strike through and archive.

#### C-21: No characterization tests for migration (T4)

**Why demote:** No migration is planned. Partially addressed by 15 verification examples (`examples/ex_*.py`) that cover the consumer API surface. The entry was already tier-recalibrated from T3 → T4 during the 2026-05-24 review. Two months at T4 with no trigger proximity.

**Action:** Add note: `**Note (2026-05-26, review-rr strategic):** Demoted to tech-debt backlog — no migration planned, partially addressed by verification examples, tier already reduced from 3→4.` Strike through and archive.

### Header count update after Task 4

- Resolved: 132 → 136
- Open: 64 → 60
- Tier 4: 37 → 33

### Steps (all 4 entries)

For each entry:
1. Add the demotion note to the full entry body.
2. Strike through the summary table row with `| ~~C-xx~~ | ~~4~~ | ~~Title~~ | Demoted to tech-debt backlog 2026-05-26 | — |`
3. Move the full entry text to `reports/archive/technical_risk_register_resolved.md` with "Demoted to tech-debt backlog" in the resolution.

### Acceptance criteria

- All 4 entries are struck through in the summary table.
- All 4 appear in the resolved archive with "Demoted to tech-debt backlog."
- Header counts: 60 open (6 T2, 15 T3, 33 T4, 6 deferred).
- `grep -c "Demoted to tech-debt backlog" reports/technical_risk_register.md` returns 4 (the notes in each entry, before archive move).

---

## Task 5: Update Work Packages

**Why:** The WET-before-DRY work package (line 176) lists C-155 and C-195. C-155's immediate trigger was resolved (V-Dem verify script created). The V-Dem documentation work package was just created. Ensure packages reflect current state.

### Steps

1. **WET-before-DRY package:** The package currently lists `C-44, C-07, C-155, C-164, C-195`. C-155 is still open (per Task 2 fix), so the reference is correct. No change needed.

2. **V-Dem documentation package:** Verify the package (line 180) correctly lists `C-217, C-218, C-219, C-220, C-221` with trigger "Before V-Dem data used by external consumers." This was added during `/register-risk` earlier today. Verify it's accurate.

3. **Data integrity package:** C-137 and C-139 are now resolved (Task 1). Remove them from the "Data integrity" package (line 171). Update to: `C-138, C-149` only. Add note: `(C-137, C-139 resolved)`.

### Acceptance criteria

- Data integrity package lists only C-138 and C-149.
- V-Dem documentation package lists C-217–C-221.
- WET-before-DRY package still lists C-155.

---

## Task 6: Update Header and Date

**Why:** The header counts must match reality. This is the final step after all changes.

### Steps

1. Update `**Date:**` line: `(updated 2026-05-26)` — already says this; verify.
2. Add `review-rr strategic curation 2026-05-26` to the source line — already present from earlier today; verify.
3. Update status line to:
   ```
   221 concern IDs assigned (C-28 merged into C-31, C-107 merged into C-60, C-183 merged into C-44, C-03 merged into C-176):
   136 resolved, 60 open concerns (6 Tier 2, 15 Tier 3, 33 Tier 4, 6 deferred by design; 2 with fired triggers),
   4 open disagreements. 116 resolved concerns as full entries + 19 early-archive reference rows + 25 resolved disagreements in archive.
   29 disagreement IDs total: 25 resolved, 4 open.
   ```

**Note on fired triggers:** After C-133 resolved, the count drops. Check: C-44 (fired, accepted), C-29 (fired, accepted), C-164 (fired). That's 3, not 2. But C-44 and C-29 say "trigger fired, accepted at v1.0" which is a historical note, not an active fired trigger. C-164 is the only active fired trigger. Verify by counting entries whose trigger text contains "**trigger fired**" and are still open. Adjust count accordingly.

### Acceptance criteria

- Mechanical count verification: `grep -c "^### C-" reports/technical_risk_register.md` per tier section matches header.
- `grep -c "^### ~~C-" reports/technical_risk_register.md` + resolved archive count = total resolved.
- Open + resolved = 221.
- Date and source line are current.

---

## Commit

```
docs: risk register curation — resolve C-133/C-137/C-139, fix C-155 status, demote C-21/C-75/C-93/C-96, rewrite 2 triggers
```

---

## Final Verification

After all tasks, run:

```bash
# Count open entries per tier section
echo "=== Tier 2 ===" && sed -n '/^## Tier 2/,/^## Tier 3/p' reports/technical_risk_register.md | grep -c "^### C-"
echo "=== Tier 3 ===" && sed -n '/^## Tier 3/,/^## Tier 4/p' reports/technical_risk_register.md | grep -c "^### C-"
echo "=== Tier 4 ===" && sed -n '/^## Tier 4/,/^## Deferred/p' reports/technical_risk_register.md | grep -c "^### C-"
echo "=== Deferred ===" && sed -n '/^## Deferred/,$p' reports/technical_risk_register.md | grep -c "^### C-"
```

Expected output: Tier 2 = 6, Tier 3 = 15, Tier 4 = 33, Deferred = 6. Total open: 60.
