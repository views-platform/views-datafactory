# R&D Roadmap v03 — Expanding the Data Graph

**Date:** 2026-03-26
**Supersedes:** rd_roadmap02.md (2026-03-25)
**Status:** Active

---

## Where We Are

The data factory is feature-complete for UCDP conflict data on the
PRIO-GRID. Five data sources, 4-layer pipeline, production parity
achieved. Infrastructure in place: zarr export (1.8 GB servable
store), consumer guides, deployment documentation, CI/CD for
main + development branches, 381 tests, 22 ADRs.

The Hetzner server is available but not yet configured for serving.
The `development` branch is the active working branch; `main` is
production.

---

## Completed Phases

### Phase 0-2c: UCDP Production Parity — COMPLETE
Full pipeline: harvest (5 sources) → consolidate → viewpoint →
compile → assemble → export (zarr + parquet). 100% event-level
match. See `rd_roadmap02.md` for details.

---

## Active Directions

### Direction 1: Data Serving (infrastructure)

Make the assembled grid accessible online via zarr-over-HTTP.

**Status:** Zarr export working locally (1.8 GB store). Deployment
guides written. Hetzner server available. Next: configure server.

**See:** `docs/guides/data_serving_guide.md`, `docs/guides/hetzner_deployment_guide.md`

### Direction 2: Three New Data Sources

Three sources are under investigation. Each has its own R&D roadmap
and product development plan in `reports/sources/`.

| Source | Type | Resolution | Access | Integration | Status |
|--------|------|-----------|--------|-------------|--------|
| **V-Dem** | Democracy indicators | Country-year | Free | Easy | Investigation |
| **ACLED** | Conflict + protests | Point events | Registration | Medium | Blocked (access) |
| **WID** | Inequality | Country-year | Free | Hard (conceptual) | Investigation |

**Recommended order:** V-Dem first (easiest, builds broadcast
infrastructure), then ACLED (second conflict source, high value),
then WID (hardest research decisions, benefits from V-Dem infra).

**Per-source documents:**
- V-Dem: `reports/sources/vdem_roadmap.md`, `reports/sources/vdem_plan.md`
- ACLED: `reports/sources/acled_roadmap.md`, `reports/sources/acled_plan.md`
- WID: `reports/sources/wid_roadmap.md`, `reports/sources/wid_plan.md`

**New architectural pattern needed:** Country-level sources (V-Dem,
WID) require a broadcast step: country values → PRIO-GRID cells via
GAUL admin codes. This infrastructure is built once for V-Dem and
reused for WID and any future country-level source.

### Direction 3: Raster Sources — BLOCKED on rasterio

Population (WorldPop), built-up area (GHSL), nightlights require
raster-to-grid aggregation. Blocked on adding rasterio/GDAL as a
dependency. Investigation findings from 2026-03-23 documented in
`rd_roadmap02.md`.

---

## Research Questions

### Existing (from v02)

| RQ | Topic | Status | Depends on |
|----|-------|--------|------------|
| RQ-1 | What is the .9 data stream? | Awaiting UCDP response | Email sent 2026-03-21 |
| RQ-2 | Candidate mutability | Partially answered | — |
| RQ-3 | Can .9 be reconstructed? | Answered: NO | — |
| RQ-4 | What is production parity? | Answered | — |
| RQ-5 | Statistical profile of data | Ready to start | Assembled grid exists |
| RQ-6 | Revision history analysis | Needs full harvest | Full .9 + candidate history |

### New (from source expansion)

| RQ | Topic | Status | Depends on |
|----|-------|--------|------------|
| RQ-7 | Do democracy indicators predict conflict? | Not started | V-Dem integration |
| RQ-8 | Does ACLED coverage predict UCDP violence? | Not started | ACLED integration |
| RQ-9 | Does inequality predict subnational conflict? | Not started | WID integration |
| RQ-10 | How do UCDP and ACLED compare? | Not started | ACLED integration |
| RQ-11 | Can inequality trends serve as risk indicators? | Not started | WID integration |

---

## Phase Roadmap

```
DONE:  Phase 0-2c (UCDP production parity + infrastructure)
       ↓
NOW:   Direction 1 — Data serving (Hetzner setup)
       Direction 2 — Source investigation (V-Dem, ACLED, WID)
       ↓
NEXT:  Phase 5 — V-Dem integration (country-level broadcast pattern)
       Phase 6 — ACLED integration (second conflict source)
       Phase 7 — WID integration (inequality indicators)
       ↓
LATER: Phase 3 — Raster sources (blocked on rasterio)
       Phase 4 — Synthetic generation
       Phase 8 — Cross-source analysis (RQ-7 through RQ-11)
```

---

## Risk Register

Active concerns tracked in `reports/technical_risk_register.md`
(ADR-020). 56 of 80 concerns resolved. 24 deferred with explicit
trigger conditions.

New risks from source expansion:
- ACLED access may be restricted (registration, terms of use)
- Country-level broadcasting is a strong assumption for WID/V-Dem
- Three new sources will trigger several deferred concerns:
  C-44 (harvest template on 4th source), C-61 (schema evolution
  on 3rd source), C-80 (6th registry)
