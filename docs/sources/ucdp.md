# UCDP/GED

| Field | Value |
|-------|-------|
| Provider | Uppsala University, Department of Peace and Conflict Research |
| Product | UCDP Georeferenced Event Dataset (GED) — annual, candidate monthly, .9 consolidated monthly |
| URL | https://ucdp.uu.se/apidocs/ |
| DOI | 10.1177/0022343311431070 |
| License | Creative Commons Attribution 4.0 (CC-BY-4.0) |
| Citation | Sundberg, R. & Melander, E. (2013). Introducing the UCDP Georeferenced Event Dataset. Journal of Peace Research 50(4): 523–532. doi:10.1177/0022343311431070 |
| Codebook | https://ucdp.uu.se/downloads/ged/ged-codebook.pdf |
| Upstream contact | UCDP (ucdp@pcr.uu.se) |
| Native format | JSON (API) |
| Native CRS | WGS84 (EPSG:4326) — point events with latitude/longitude |
| Native resolution | Point events (latitude, longitude) |
| Spatial extent | Global |
| Temporal coverage | 1989– |
| Temporal granularity | Daily events |
| Update cadence | Annual (GED release) + monthly (candidate + .9 consolidated) |
| Access method | REST API, no authentication |
| Authentication | None |
| Features produced | `sb_best`, `ns_best`, `os_best`, `sb_count`, `ns_count`, `os_count` |
| Grid layers | Harvest → Consolidation → Viewpoint → Compilation → Assembly |
| Selection ADR | Original source — no selection ADR (foundational) |
| Provenance ledger | `provenance/ucdp_annual/`, `provenance/ucdp_candidate/`, `provenance/ucdp_dot9/` |

## Description

The UCDP Georeferenced Event Dataset provides individual events of organised violence — state-based conflict, non-state conflict, and one-sided violence — with geographic coordinates and casualty estimates. Three data streams are harvested independently:

- **Annual (GED):** Definitive dataset released once per year, covering events through the previous calendar year. The most thoroughly coded and verified stream.
- **Candidate Monthly:** Preliminary monthly data with events coded in near real-time. Subject to revision.
- **.9 Consolidated Monthly:** Monthly aggregation retaining all candidate versions from January 2018 onward. Includes version metadata for tracking revisions.

UCDP is the foundational conflict data source for the VIEWS project and was the first source integrated into the data factory.

## Pipeline path

**Harvest → Consolidation → Viewpoint → Compilation → Assembly.** All three streams pass through every layer.

- **Harvest:** Fetches events from the UCDP API. Annual fetches all events; candidate and .9 discover and fetch all available versions. Digest-based caching skips unchanged versions.
- **Consolidation:** Merges annual, candidate, and .9 snapshots into a single version-aware event store with bitemporal metadata (`_source_type`, `_source_version`, `_ingested_at`).
- **Viewpoint:** Applies survivorship rules (which version of a duplicated event wins), temporal distribution (spreading multi-month summary events), and event filters (type_of_violence, precision).
- **Compilation:** Places events onto the PRIO-GRID (latlon → pgid) and aggregates per cell-month using declared strategies (count, sum_best, max_best).
- **Assembly:** Combined with ACLED, GHS-POP, GHS-BUILT-S, PRIO-GRID static, and GAUL admin into the final grid.

## Known limitations

- **Candidate revision.** Candidate events are preliminary and may be revised or removed in the next annual release. The consolidation layer preserves all versions; the viewpoint layer chooses which wins.
- **Geocoding precision.** Events vary in spatial precision from exact coordinates to country centroids. The `where_prec` field encodes this — viewpoints can filter by precision.
- **Summary events.** Some events span multiple months (`date_start` ≠ `date_end`). Temporal distribution strategies handle this, but the choice of strategy affects results.
- **Annual lag.** The definitive GED release lags ~6 months behind real-time. Candidate data fills this gap but at lower confidence.
