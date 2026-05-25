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
| Access method | REST API, OAuth2 password grant (ADR-026) |
| Authentication | OAuth2 (username + API key → bearer token). Credential sharing prohibited by EULA. |
| Features produced | `acled_battles`, `acled_explosions`, `acled_violence_against_civilians`, `acled_protests`, `acled_riots`, `acled_strategic_developments`, `acled_fatalities`, `acled_count` |
| Grid layers | Harvest → Consolidation → Viewpoint → Compilation → Assembly |
| Selection ADR | [ADR-030](../ADRs/030_acled_as_second_conflict_source.md) |
| Provenance ledger | `provenance/acled/ingestion_ledger.jsonl` |

## Description

ACLED provides real-time data on political violence and protest events worldwide. Unlike UCDP, ACLED covers a broader taxonomy including protests, riots, and strategic developments alongside battles and violence against civilians. Events are single-day atomic records — no multi-day spanning — which simplifies temporal assignment compared to UCDP.

ACLED is the second conflict data source in the data factory, complementing UCDP's focus on organised violence with broader coverage of political contention.

## Pipeline path

**Harvest → Consolidation → Viewpoint → Compilation → Assembly.**

- **Harvest:** Fetches events from the ACLED API using OAuth2 authentication. Year-by-year pagination adopted May 2026 (courtesy protocol — contact Katayoun before large re-fetches). ~4.2 GB total across all years.
- **Consolidation:** Merges weekly snapshots into a version-aware event store. Simpler than UCDP — single stream, no candidate/annual distinction.
- **Viewpoint:** Applies event type filtering and aggregation. No survivorship rules needed (single stream). No temporal distribution needed (single-day events).
- **Compilation:** Places events onto the PRIO-GRID (latlon → pgid) and aggregates per cell-month using declared strategies.
- **Assembly:** Combined with UCDP, GHS-POP, GHS-BUILT-S, PRIO-GRID static, and GAUL admin into the final grid.

## Known limitations

- **Authentication required.** Each user must have their own ACLED credentials. OAuth2 tokens expire and must be refreshed.
- **Rate limiting.** The API has rate limits. The harvester respects these, but large historical re-fetches should be coordinated with ACLED.
- **Taxonomy differences.** ACLED's event taxonomy does not map 1:1 to UCDP's. The 8 features in the compiled grid are ACLED-native categories, not harmonised with UCDP.
- **Historical revisions.** ACLED may revise historical events in weekly updates. The consolidation layer handles this via append-only storage with version tracking.
