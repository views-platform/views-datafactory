# ACLED

| Field | Value |
|-------|-------|
| Provider | ACLED (Armed Conflict Location & Event Data Project) |
| Product | ACLED event-level conflict and protest data |
| URL | https://acleddata.com/ |
| DOI | 10.1177/0022343310378914 |
| License | ACLED Terms of Use — free for academic use, registration required |
| Citation | Raleigh, C., Linke, A., Hegre, H. & Karlsen, J. (2010). Introducing ACLED: An Armed Conflict Location and Event Dataset. Journal of Peace Research 47(5): 651–660. doi:10.1177/0022343310378914 |
| Codebook | https://acleddata.com/acleddatanew/wp-content/uploads/dlm_uploads/2019/04/ACLED-Codebook_2019FINAL.docx.pdf |
| Upstream contact | Katayoun (ACLED data team) — contact before large re-fetches |
| Native format | JSON (API) |
| Native CRS | WGS84 (EPSG:4326) — point events with latitude/longitude |
| Native resolution | Point events (latitude, longitude) |
| Spatial extent | Global |
| Temporal coverage | 1997– |
| Temporal granularity | Daily events |
| Update cadence | Weekly |
| Access method | REST API, OAuth2 password grant (ADR-026), cursor pagination (`&cursor=X`) |
| Authentication | OAuth2 (username + API key → bearer token). Credential sharing prohibited by EULA. |
| Features produced | `acled_battles`, `acled_explosions`, `acled_violence_against_civilians`, `acled_protests`, `acled_riots`, `acled_strategic_developments`, `acled_fatalities`, `acled_count` |
| Grid layers | Harvest → Consolidation → Viewpoint → Compilation → Assembly |
| Selection ADR | [ADR-028](../ADRs/028_acled_consolidation_and_viewpoint.md) |
| Provenance ledger | `provenance/acled/ingestion_ledger.jsonl` |

## Description

ACLED provides real-time data on political violence and protest events worldwide. Unlike UCDP, ACLED covers a broader taxonomy including protests, riots, and strategic developments alongside battles and violence against civilians. Events are single-day atomic records — no multi-day spanning — which simplifies temporal assignment compared to UCDP.

ACLED is the second conflict data source in the data factory, complementing UCDP's focus on organised violence with broader coverage of political contention.

## Pipeline path

**Harvest → Consolidation → Viewpoint → Compilation → Assembly.**

- **Harvest:** Fetches events from the ACLED API using OAuth2 authentication. Year-by-year harvesting adopted May 2026 (courtesy protocol — contact Katayoun before large re-fetches). Within a year, `fetch_paginated()` in `acled.py` walks the API with **cursor pagination** (see below). ~4.2 GB total across all years.
- **Consolidation:** Merges weekly snapshots into a version-aware event store. Simpler than UCDP — single stream, no candidate/annual distinction.
- **Viewpoint:** Applies event type filtering and aggregation. No survivorship rules needed (single stream). No temporal distribution needed (single-day events).
- **Compilation:** Places events onto the PRIO-GRID (latlon → pgid) and aggregates per cell-month using declared strategies.
- **Assembly:** Combined with UCDP, GHS-POP, GHS-BUILT-S, PRIO-GRID static, and GAUL admin into the final grid.

## Pagination

ACLED deprecated offset (`&page=N`) pagination on **2026-10-27** and we migrated to cursors
before that date (#487). The contract, confirmed against a live response on 2026-10-10:

| Thing | Value |
|---|---|
| Parameter | `&cursor=X`, starting at `&cursor=0` |
| Continuation token | `next_cursor`, a **top-level key in the JSON body** |
| Type | integer (observed values are monotonically increasing, consistent with row ids) |
| End of series | `next_cursor` is `null` — **the only authoritative terminator** |
| Precedence | if both `cursor` and `page` are sent, cursor wins and `page` is ignored *silently* |
| CSV | under `_format=csv` the value moves to an `X-Next-Cursor` response header; we use `_format=json` |
| Unsupported | `export_type=monadic` must keep `&page=X`. We never request monadic exports |

**A short page is not the end of the series.** Under offset pagination it was, and
`fetch_paginated()` used to stop on `len(results) < page_size`. That inference is invalid under
cursor pagination and the break was deleted; keeping it is how the migration would have silently
truncated a harvest. Two conditions now raise rather than guess (ADR-011): a response with no
`next_cursor` key, and a response with no events while the cursor is still live.

Because the cursor is an integer, `0` is both the starting value and falsy — so termination tests
`is None` and never falsiness.

Parity between the two methods was measured before the deadline and the recording is kept, because
the comparison cannot be repeated: see `reports/investigation_acled_cursor/findings.md` and
`tests/test_acled_cursor_parity_fixture.py`.

## Known limitations

- **Authentication required.** Each user must have their own ACLED credentials. OAuth2 tokens expire and must be refreshed.
- **No server-declared total.** The response reports `count: null` and `total_count: null`, re-confirmed under cursor pagination on 2026-10-10, so there is no figure to verify a harvest against (C-153). This is why ACLED is exempt from [ADR-027](../ADRs/027_harvest_count_verification.md)'s count-tolerance rule, and why a *partially* short harvest is currently recorded as a success (#488). A zero-event year does fail loud.
- **Rate limiting.** The API has rate limits. The harvester respects these, but large historical re-fetches should be coordinated with ACLED.
- **Taxonomy differences.** ACLED's event taxonomy does not map 1:1 to UCDP's. The 8 features in the compiled grid are ACLED-native categories, not harmonised with UCDP.
- **Historical revisions.** ACLED may revise historical events in weekly updates. The consolidation layer handles this via append-only storage with version tracking.
