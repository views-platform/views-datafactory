
# ADR-020: Technical Risk Register

**Status:** Accepted
**Date:** 2026-03-25
**Deciders:** Simon

---

## Context

During the development of views-datafactory, a document (`concerns00.md`)
emerged organically from expert code reviews. It tracked technical concerns,
deferred decisions, and cross-expert disagreements. Over 4 review cycles it
grew to 80 entries and became a central governance artifact — but it was
never formally recognized as one.

The existing governance documents serve prescriptive roles:
- **ADRs** record what was decided and why
- **CICs** record what classes promise (behavioral contracts)

Neither has a place for: *what we know is imperfect, why we accept it for
now, and what would change our mind.* The concerns document fills this gap.

At 80 entries and ~380 lines, the single-file format hit its scaling limit
(C-66). This ADR formalizes the pattern that proved itself before attempting
to improve it.

---

## Decision

Maintain a **technical risk register** as a first-class governance artifact,
split into two files:

- `reports/technical_risk_register.md` — active concerns (open, deferred)
- `reports/archive/technical_risk_register_resolved.md` — resolved concerns and
  disagreements (historical archive)

The register is the canonical location for tracking known imperfections,
accepted risks, and deferred decisions in the codebase.

---

## Rationale

The register emerged from practice, not planning. Its value was proven
before being formalized:

1. **Trigger-based deferrals** turn vague "fix later" into falsifiable
   contracts: "extract `Registry[T]` on 6th registry" is testable.
2. **Cross-expert disagreement tracking** preserves the losing argument,
   not just the winner — future readers understand both sides.
3. **In-flow updates** keep it accurate: concerns are recorded during
   reviews, not reconstructed after the fact.
4. **Tiered ranking** (impact x likelihood x detectability) prevents
   both "fix everything now" perfectionism and "ignore everything" neglect.

Formalizing it prevents accidental deletion and signals to contributors
that the register is maintained, not abandoned.

---

## Considered Alternatives

### Alternative A: JSONL append log + markdown view
- **Pros:** Immutable audit trail, programmatic queries.
- **Cons:** Two mechanisms to maintain. The markdown *is* the working
  document — generating it from a log adds ceremony without value at
  current scale.
- **Reason for rejection:** Over-engineering. Revisit if programmatic
  querying becomes needed (e.g., CI checking trigger conditions).

### Alternative B: GitHub Issues / Linear tickets
- **Pros:** Standard project management tooling.
- **Cons:** Loses the single-document overview. Disagreements and
  trigger conditions don't map well to ticket fields. Resolved items
  disappear into closed-ticket graveyards.
- **Reason for rejection:** The register's value is the overview and
  the historical arc, both of which external tools fragment.

---

## Consequences

### Positive
- Active file drops from ~380 to ~150 lines (scannable)
- Summary table at top enables quick triage
- Historical record preserved in archive
- Contributors know where to record new concerns

### Negative
- Two files to maintain instead of one
- Concern must appear in exactly one file (active or archive)

---

## Implementation Notes

### Structure

**Active file** (`technical_risk_register.md`):
- Header with metadata and status counts
- Summary table of all open items (ID, title, tier, trigger)
- Full entries grouped by tier (1, 3, 4, deferred-by-design)
- Pointer to archive file

**Archive file** (`technical_risk_register_resolved.md`):
- All resolved concerns (grouped by original tier)
- All resolved expert disagreements
- Early concerns reference table

### Concern format

Each concern has:
- **ID:** Sequential (`C-xx` for concerns, `D-xx` for disagreements)
- **Title:** Short description
- **Body:** What the issue is, where in code, why it matters
- **Source:** Which expert perspective or audit raised it
- **Trigger:** Specific condition under which the concern becomes actionable
  (for deferred items)

### Lifecycle

1. **Opened** during expert review, tech debt audit, or falsification audit
2. **Resolved** when fixed — entry gets `~~strikethrough~~ RESOLVED`,
   stays in active file until next archive sweep
3. **Deferred** with explicit trigger — marked `[DEFER]`
4. **Archived** when resolved entries are swept to the archive file

### Tier definitions

| Tier | Meaning | Examples |
|------|---------|---------|
| 1 | Fix before production | Data integrity, silent failures |
| 2 | Fix before scaling | Memory, performance, concurrency |
| 3 | Improve quality | Test gaps, code clarity |
| 4 | Accept or defer | Accepted risks with trigger conditions |

---

## Validation & Monitoring

- `test_falsification_tech_debt.py` validates the register header
  (concern count matches actual entries)
- New concerns should be added during reviews, not as a separate ceremony
- Archive sweep: move resolved concerns when active file exceeds ~40 entries

---

## References

- `reports/technical_risk_register.md` — active concerns
- `reports/archive/technical_risk_register_resolved.md` — historical archive
- ADR-008: Observability and explicit failure (motivates fail-loud concerns)
- ADR-005: Testing as mandatory infrastructure (motivates test gap concerns)
