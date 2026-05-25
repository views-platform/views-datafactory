# ADR-033: Data Source Catalog

**Status:** Accepted
**Date:** 2026-05-22
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Applies:** ADR-003 (Authority of Declarations), ADR-012 (Four-Layer Data Architecture), ADR-029 (GHS-POP Source Selection)

---

## Context

The data factory now integrates 5 external data sources (UCDP annual/candidate/.9, ACLED, GHS-POP) plus 2 spatial infrastructure sources (PRIO-GRID static, GAUL admin). Each source was documented through its selection ADR (ADR-028, ADR-029) and its config CIC, but there is no single place where a reader — a new team member, a reviewer, a grant evaluator — can look up "what data does this system consume, where does it come from, and what do we do with it?"

Source metadata is currently scattered across three artifacts:

1. **`SourceEntry` registry** (`source_registry.py`) — operational: features, SLOs, env vars, ledger paths. This is what the pipeline reads at runtime.
2. **ADRs** (028, 029, 030) — decision rationale: why this source, what alternatives, what trade-offs. These are one-time decisions, not living references.
3. **CICs** — config contracts: what parameters each harvester/viewpoint/compiler accepts. These describe our code, not the upstream data.

None of these capture upstream provenance in a structured, scannable form: who publishes the data, what URL, what license, what spatial/temporal coverage, what native format, what version we're using, when it was last updated. This information exists in ADR prose (e.g., ADR-029's "Implementation Notes" section has download URLs and resolution details), but it is buried in narrative text and not maintained as a living reference.

This gap is visible in the VIEWS publications themselves. Hegre et al. (2019, JPR 56(2)) documents data sources across Table II, Table III, and a single paragraph on p.161 — scattered across the paper, not consolidated. The 2020 update (Hegre et al. 2021, JPR 58(3)) doubles the source count but uses the same scattered pattern. The VIEWS Pipeline Handbook (Von der Maase et al. 2025) has a Section 2.4 titled "External Dependencies and Data Sources" — an empty placeholder. The closest existing template is the VIEWS Prediction Challenge (Hegre et al. 2024), which had to produce structured source documentation when external teams needed to use the data: target definition, spatial unit, temporal range, format, index columns. That is a catalog card emerging under pressure.

The gap matters for four reasons:

1. **Onboarding.** A new contributor needs 15 minutes of reading ADRs and grepping source code to answer "what data do we have?" A catalog answers it in one page.
2. **Reproducibility.** A paper reviewer or replication attempt needs to know exactly which data versions, resolutions, and temporal ranges produced a given result. The FAIR principles (Wilkinson et al. 2016) require rich metadata (F2) and detailed provenance (R1.2) for data to be findable and reusable. The catalog is the citable artifact that satisfies these requirements.
3. **Downstream transparency.** VIEWS forecasts inform decisions about humanitarian response, resource allocation, and early warning. Downstream stakeholders — policymakers, NGOs, partner organizations — have a legitimate need to know what data enters the system, regardless of whether they draw the right conclusions from that knowledge. A trustworthy forecasting system must be auditable, and auditability starts with knowing what went in. This is a governance requirement, not a convenience feature. The catalog is the public-facing answer to "what data does VIEWS use?" — a question that should not require reading source code or ADRs to answer.
4. **Source expansion.** When evaluating the next source (V-Dem, WDI, nightlights), the catalog shows at a glance what coverage we already have and where the gaps are.

---

## Decision

This repository maintains a **data source catalog** in `docs/sources/`, with one markdown file per upstream data source and an index file that summarizes all sources in a single table.

### Structure

```
docs/sources/
├── README.md              # Index: one-line-per-source table + coverage summary
├── ucdp.md                # UCDP (annual + candidate + .9 combined) — planned
├── acled.md               # ACLED — planned
├── ghspop.md              # GHS-POP R2023A ✓
├── ghsbuilts.md           # GHS-BUILT-S R2023A ✓
├── priogrid_static.md     # PRIO-GRID static variables — planned
└── gaul_admin.md          # GAUL admin boundaries — planned
```

### Catalog card schema

Each source file follows a fixed structure:

The schema draws on Gebru et al. (2021, "Datasheets for Datasets"), the W3C DCAT vocabulary (Version 3), and the FAIR principles (Wilkinson et al. 2016), adapted to the scale and domain of a conflict forecasting pipeline with 5–10 sources. Fields are chosen for what a new contributor, a paper reviewer, or a grant evaluator would need to understand each source without reading the selection ADR.

```markdown
# <Source Name>

| Field | Value |
|-------|-------|
| Provider | <institution> |
| Product | <official product name and version> |
| URL | <canonical product page> |
| DOI | <persistent identifier for the dataset version, if available> |
| License | <license name or terms> |
| Citation | <recommended citation for publications> |
| Codebook | <link to upstream variable definitions / methodology docs> |
| Upstream contact | <name or team for data questions, if known> |
| Native format | <file format as delivered> |
| Native CRS | <coordinate reference system> |
| Native resolution | <spatial resolution as delivered> |
| Spatial extent | <Global / Africa / bounding box> |
| Temporal coverage | <range of available data> |
| Temporal granularity | <resolution of the data itself: daily, monthly, 5-year epochs> |
| Update cadence | <how often the provider publishes new releases> |
| Access method | <API, direct download, registration required?> |
| Authentication | <what credentials, if any> |
| Features produced | <list of features in assembled grid> |
| Grid layers | <which layers this source traverses> |
| Selection ADR | <link to source selection ADR> |
| Provenance ledger | <path to ledger file for current harvest status and versions> |

## Description

<2-3 sentences: what this data measures, how it's produced, why we use it.>

## Pipeline path

<Which layers: harvest → [consolidation →] viewpoint → compilation → assembly.
 Note any layers skipped and why.>

## Known limitations

<Temporal sparsity, spatial gaps, known biases, update lag, etc.>
```

### Schema field rationale

The schema has 21 fields — 20 static, 1 pointer. Each maps to an established metadata standard:

| Field | Source | Why included |
|-------|--------|--------------|
| Provider | DCAT `dcterms:publisher` | Institutional provenance |
| Product | DCAT `dcterms:title` | Distinguishes versions (R2023A vs R2022A) |
| URL | DCAT `dcat:landingPage` | Canonical product page (stable, not download-specific) |
| DOI | FAIR F1, Gebru §6 "Distribution" | Persistent identifier for reproducibility; not all sources have DOIs |
| License | FAIR R1.1, Gebru §6, DCAT `dcterms:license` | Every standard agrees: license must be explicit |
| Citation | Gebru §6 | ACLED and UCDP both have specific citation requirements |
| Codebook | Holland et al. (2018) "Variables" module | Pointer to upstream variable definitions — avoids duplicating the data dictionary |
| Upstream contact | DCAT `dcat:contactPoint`, Gebru §7 "Maintenance" | Who to ask about the data (e.g., Katayoun at ACLED) |
| Native format | DCAT `dcat:distribution` | File format as delivered — GeoTIFF, API JSON, Parquet |
| Native CRS | DCAT `dcterms:conformsTo` | Coordinate reference system; critical for raster sources |
| Native resolution | DCAT `dcat:spatialResolutionInMeters` | Spatial resolution before our aggregation |
| Spatial extent | DCAT `dcterms:spatial` | "Global" vs "Africa only" — distinct from resolution |
| Temporal coverage | DCAT `dcterms:temporal`, FAIR | Start-end range of available data |
| Temporal granularity | DCAT `dcat:temporalResolution` | Resolution of the data itself (daily events, 5-year epochs) |
| Update cadence | DCAT `dcterms:accrualPeriodicity` | How often the provider publishes — distinct from granularity |
| Access method | FAIR A1 | API, direct download, registration wall? |
| Authentication | Gebru §6 (export controls) | What credentials are needed |
| Features produced | Holland "Variables" module | What this source contributes to our assembled grid |
| Grid layers | (domain-specific) | Which layers in our graph architecture (ADR-012) |
| Selection ADR | DCAT `dcterms:relation` | Link to the decision rationale |
| Provenance ledger | ADR-003, ADR-008 | Pointer to source of truth for current version and harvest status |

### Dynamic state lives in the ledger, not the card

The catalog card documents what is *stable about the source* — who publishes it, what format, what license. This information changes when the upstream provider changes something fundamental, not when we run the pipeline.

Dynamic operational state — current version, last harvest date, digest, outcome — lives in the provenance ledger. The card points to the ledger; it does not duplicate it. This is a deliberate design choice:

1. **Single source of truth.** The ledger is machine-written, append-only, never manually edited. If "current version" appeared in both the card and the ledger, readers would not know which to trust when they diverge. They will diverge.
2. **Change frequency mismatch.** The card changes when we add a source or when an upstream provider changes something about their data. The ledger changes on every harvest cycle. Mixing fields with different change frequencies in one artifact creates maintenance friction (Martin, Common Closure Principle).
3. **No manual synchronization.** A field that must be manually copied from the ledger to the card after every harvest is a process that will be skipped. Rather than automate the copying (which adds tooling and a new failure mode), we eliminate the duplication.

To check current harvest status and versions for all sources, run:

```bash
uv run python scripts/check_health.py
```

Or inspect the ledger directly at the path given in the card's "Provenance ledger" field.

### Fields deliberately excluded

Several fields recommended by the literature are excluded with explicit rationale:

- **Intended/prohibited uses** (Gebru §5): Relevant for ML training datasets with bias concerns. Our sources (UCDP, ACLED, JRC) define their own terms of use — paraphrasing adds maintenance burden without value. The selection ADR discusses fitness for our purpose.
- **Upstream coding methodology** (Bender & Friedman 2018, "annotator demographics"): Who codes UCDP events? What training do ACLED coders have? This is critical for bias assessment in conflict data but is deep methodological content — it belongs in the selection ADR or a research methodology document, not a quick-reference catalog card.
- **Summary statistics / missingness rates** (Holland et al. 2018, "Statistics" module): Value ranges and missing data rates change with each harvest and belong in the provenance system, not a manually-maintained markdown file.
- **RDF/SKOS vocabulary alignment** (W3C DCAT): Overkill at 5 sources. If the catalog grows to 15+ sources, structured metadata with DCAT alignment becomes worthwhile.
- **Keywords/tags** (DCAT `dcat:keyword`): Useful for search in large catalogs. Unnecessary when you can read the entire index in 10 seconds.

### What the catalog is NOT

- **Not a replacement for ADRs.** The selection rationale, alternatives considered, and architectural consequences stay in the source selection ADR. The catalog card links to the ADR but does not duplicate it.
- **Not a replacement for SourceEntry.** The operational pipeline config (features, SLOs, env vars, ledger paths) stays in `source_registry.py`. The catalog is documentation for humans; the registry is config for code.
- **Not a replacement for CICs.** Config class contracts stay in `docs/CICs/`. The catalog describes upstream data; CICs describe our code.
- **Not a data dictionary.** Individual feature definitions (what `ged_sb_best` means, what `acled_battles` counts) belong in a feature dictionary, not the source catalog. The catalog says "this source produces these features" but does not define them.

### Index file

`docs/sources/README.md` contains a summary table:

```markdown
| Source | Provider | Features | Temporal coverage | Granularity | Spatial | Update cadence |
|--------|----------|----------|-------------------|-------------|---------|----------------|
| UCDP | Uppsala | 6 | 1989– | Daily events | events → 0.5° | Annual (GED) + monthly (candidate) |
| ACLED | ACLED | 8 | 1997– | Daily events | events → 0.5° | Weekly |
| GHS-POP | JRC/Copernicus | 1 | 1975–2030 | 5-year epochs | 30″ → 0.5° | ~2–3 year releases |
| PRIO-GRID Static | PRIO | 33 | Static | — | 0.5° | One-time |
| GAUL Admin | FAO | 3 | Static | — | Polygons → 0.5° | One-time |
```

Plus a coverage heatmap (text-based) showing temporal coverage per source and a note on total feature count in the assembled grid.

---

## Rationale

### Why markdown, not code

The catalog serves humans — contributors, reviewers, grant evaluators. Markdown is readable without tooling, renders on GitHub, and is version-controlled alongside the code. A YAML/JSON schema would require a renderer and would separate the "readable" version from the "authoritative" version. For 5–10 sources, markdown is simpler.

The W3C DCAT vocabulary defines an RDF schema for dataset catalogs — `dcat:Dataset` with properties like `dcterms:publisher`, `dcterms:spatial`, `dcat:temporalResolution`. This is the right approach for a national data portal or a large institutional repository. For a 5-source research pipeline, it would be premature tooling. Our schema maps to DCAT properties (see field rationale table above) so migration is possible if needed.

**Revisit condition:** If the catalog exceeds 15 sources or consumers need programmatic access (e.g., auto-generating data availability tables for papers), consider migrating to a structured format (YAML or TOML) with a markdown renderer.

### Why one file per source, not one big file

Each source has enough metadata and context (limitations, version history, pipeline path) that a single-file catalog would become unwieldy at 5+ sources. Separate files allow targeted updates when a source is re-harvested or upgraded, without merge conflicts on unrelated sources. This follows the same principle as Gebru et al. (2021): each dataset gets its own datasheet, not a row in a shared spreadsheet.

### Why a separate directory, not embedded in ADRs

ADRs are decisions — they record *why something was chosen* at a specific point in time (Nygard 2011, "Documenting Architecture Decisions"). The catalog is a living reference — it records *what is currently true*. An ADR should not be edited to update "last harvested" dates or add new version history entries. The catalog card links to the ADR for rationale but lives separately so it can be updated without touching governance documents.

Gebru et al. (2021) recommend that datasheets be "stored alongside the data or its documentation." Our `docs/sources/` directory satisfies this — version-controlled in the same repo as the code and the data pipeline that consumes it.

### Why scope boundaries follow from ownership, not convenience

The catalog card's scope — what it includes and excludes — is not arbitrary. It follows from applying Martin's Common Closure Principle (CCP) and Common Reuse Principle (CRP) to documentation artifacts, not just code.

CCP says: things that change together should live together. CRP says: things not reused together should not be packaged together. Applied to data source documentation:

- Upstream facts (provider, format, license, cadence) change when the upstream provider changes something. They belong together → **catalog card**.
- Decision rationale (why this source, why this SLO, what alternatives) changes when we reconsider a decision. It belongs together → **source selection ADR**.
- Declared operational values (SLO hours, feature names, env vars) change when we tune our pipeline config. They belong together → **SourceEntry in code**.
- Volatile operational state (last harvest, current version, digest) changes on every harvest cycle. It belongs together → **provenance ledger**.

Each artifact has one owner, one change frequency, and one audience. The catalog card does not contain SLOs (operational decision, different owner), does not contain last harvest dates (volatile state, different frequency), and does not contain decision rationale (one-time reasoning, different audience). These boundaries are not conventions to be memorized — they fall out of asking "what changes this, and who reads it?" (See also ADR-003, Corollary: Declaration Ownership.)

### Why "temporal granularity" and "update cadence" are separate fields

UCDP GED has annual temporal resolution (events are coded per calendar year for finalized data) but monthly candidate releases. ACLED has daily event resolution but weekly publication cadence. These are different things — the data's time grain vs. the provider's publication rhythm. Conflating them (as the original draft did) obscures an operationally important distinction. The UCDP Candidate paper (Hegre et al. 2020) makes this trade-off explicit: the candidate's value is timeliness (monthly updates), at the cost of accuracy (relaxed coding criteria compared to the annual GED).

### Temporal properties: four artifacts, four facets

Each data source has four temporal properties, each owned by a different artifact:

| Property | What it describes | Owned by | Example (ACLED) |
|----------|-------------------|----------|-----------------|
| Temporal granularity | Resolution of the data itself | Catalog card | Daily events |
| Update cadence | How often the provider publishes | Catalog card | Weekly |
| SLO (`slo_hours`) | Our staleness tolerance | `SourceEntry` (code) | 744 hours |
| Last harvest timestamp | When we actually fetched | Provenance ledger | 2026-05-21T14:30Z |

The catalog card owns upstream facts (granularity, cadence). `SourceEntry` owns our operational declaration (SLO). The provenance ledger owns the volatile state (last harvest). No artifact duplicates another.

The SLO is a **decision**, not a derivation from upstream cadence. It is informed by cadence but declared independently (ADR-003). The rationale for a specific SLO value — why 744 hours for ACLED, why 8760 for UCDP annual, why `None` for GHS-POP — belongs in the source selection ADR, where the decision is documented alongside its reasoning. The catalog card does not own SLO decisions and does not encourage readers to infer an SLO from the update cadence field.

---

## Considered Alternatives

### Alternative A: Extend SourceEntry with upstream metadata

Add fields like `provider_url`, `license`, `citation`, `native_crs` to the `SourceEntry` dataclass.

- **Pros:** Single source of truth, machine-readable, colocated with operational config.
- **Cons:** Mixes two concerns — pipeline runtime config and human-readable documentation. Adds fields the pipeline never reads. Makes `SourceEntry` grow with every metadata need. Forces documentation updates through Python code changes.
- **Reason for rejection:** `SourceEntry` is operational config (ADR-003). Adding documentation fields violates its CIC (Section 2: "does not read or write files," "does not define aggregation strategies"). The catalog is a docs concern, not a code concern.

### Alternative B: Structured YAML/TOML catalog

```yaml
# sources/ghspop.yaml
provider: JRC/Copernicus
product: GHS-POP R2023A
license: EU Open Data
...
```

- **Pros:** Machine-parseable, auto-generates markdown tables, enforceable schema. Aligns with DCAT's structured metadata approach. Holland et al. (2018, "Dataset Nutrition Label") use a structured JSON schema for similar reasons.
- **Cons:** Requires a build step or rendering script. The YAML is the authority but the rendered markdown is what people read — creates a two-artifact maintenance burden. Overkill for 5 sources.
- **Reason for rejection:** Premature tooling. Markdown is sufficient at current scale.
- **Revisit condition:** When source count exceeds 15 or consumers need programmatic catalog access.

### Alternative C: Wiki or external documentation

Maintain source documentation in a GitHub wiki, Notion, or Confluence page.

- **Pros:** Richer formatting, cross-linking, search.
- **Cons:** Not version-controlled with the code. Drifts from the codebase. Cannot be validated by CI. Not citable (URLs change). Violates FAIR A2: metadata should remain accessible even when the hosting platform changes.
- **Reason for rejection:** Documentation that drifts from code is worse than no documentation. Gebru et al. (2021) recommend storing datasheets alongside the data or its documentation, not in an external system. ADR-003 requires declarations to be authoritative — a wiki is not version-controlled with the code.

### Alternative D: Adopt the full Gebru "Datasheets for Datasets" template

Use all 57 questions from Gebru et al. (2021) as the catalog card schema.

- **Pros:** Comprehensive. Covers motivation, composition, collection process, preprocessing, uses, distribution, and maintenance. The most thorough dataset documentation framework in the literature.
- **Cons:** Designed for ML training datasets, not upstream data sources consumed by a pipeline. Many questions (annotator demographics, consent, offensive content) are not applicable. The full template is ~3 pages per dataset — at 5 sources that is 15 pages of documentation to maintain.
- **Reason for rejection:** Too heavy for our scale and domain. We adopt Gebru's structural insight (each dataset gets a standardized card) and selected fields (license, citation, DOI, maintenance) without the full questionnaire. The fields we exclude are documented in the "Fields deliberately excluded" section above.
- **Revisit condition:** If a funding body or publication venue requires Gebru-style datasheets, the catalog cards can be expanded to full datasheets without restructuring.

---

## Consequences

### Positive

- One-page answer to "what data does this system consume?" — serves both internal contributors and external stakeholders
- Citable artifact for papers and grant applications
- Structured onboarding for new contributors
- Governance artifact: downstream users can audit what data enters the forecasting system without reading source code
- Gap analysis for source expansion planning (temporal/spatial coverage visible at a glance)
- Upstream provenance (license, citation, version) tracked alongside code

### Negative

- Maintenance burden when upstream providers change something structural (new URL, new license, new format). Mitigated by keeping the schema minimal, linking to ADRs for rationale, and excluding dynamic state (which lives in the provenance ledger).
- Risk of drift: if an upstream provider changes their product page or license and we don't update the card. Mitigated by reviewing cards at the same cadence as the deployment guide. This risk is low because upstream structural changes are rare and typically accompany a new data release that triggers a selection-level review.

---

## Implementation Notes

### Initial population

Create catalog cards for all 5 current sources by extracting metadata from existing ADRs, config classes, and upstream documentation. This is a one-time documentation effort, not a code change.

### Maintenance protocol

Because dynamic state (current version, last harvest) lives in the provenance ledger, **re-harvesting a source does not require editing the catalog card.** The card only changes when:

- The upstream provider changes something structural (new product version, new license, new URL, changed resolution or format)
- We add or remove features derived from this source
- We change which pipeline layers the source traverses

When a new source is added:

1. Write the source selection ADR — should include SLO decision with rationale (why this value, informed by what upstream cadence)
2. Create a catalog card from the ADR metadata (upstream facts only — no SLO, no dynamic state)
3. Add a row to the index table
4. Add the `SourceEntry` to `source_registry.py` with the SLO value declared in the ADR

### Existing SLO rationale gap

The current source selection ADRs (028, 029) do not all document SLO rationale explicitly. The `slo_hours` values in `SourceEntry` (744 for ACLED/candidate, 8760 for UCDP annual, None for GHS-POP) were set during implementation without ADR-level justification. This is a documentation gap to address when those ADRs are next reviewed — it is not in scope for this ADR.

### Validation

A future CI check could verify that every source in `PIPELINE_SOURCES` with `features` has a corresponding catalog card in `docs/sources/`. Not implemented now — the source count is small enough to maintain manually.

---

## Validation & Monitoring

- Every source in `PIPELINE_SOURCES` that produces features should have a catalog card
- Catalog cards should be reviewed when the deployment guide is updated (same cadence)
- Dynamic state (current version, last harvest) is validated by `check_health.py`, not by the catalog — the catalog is not the source of truth for operational state

---

## Resolved Questions

1. **Placeholder cards for planned sources?** Yes — include cards with status "Planned" or "Evaluated" for sources under consideration (V-Dem, WDI, nightlights). This makes coverage gap analysis explicit and costs little to maintain since the card is mostly empty until integration begins.

2. **Feature dictionary as a separate artifact?** No — excluded. Upstream raw variables are covered by the "Codebook" field (pointer to provider documentation). Our derived features (`ged_sb_best` at the 0.5° grid cell level) are defined by the viewpoint layer: viewpoint profiles declare which strategies produce which output, and the viewpoint CICs (ViewpointConfig, ViewpointResult) document the contracts. Creating a separate feature dictionary would duplicate information owned by the viewpoint layer at a different change frequency — viewpoints are volatile and will multiply as research evolves (ADR-014, ADR-016). A stable document describing concrete viewpoint outputs violates both CCP (different change frequency from the catalog) and SAP (concrete details in a stable artifact). The catalog card says "this source produces these features"; *how* those features are constructed is documented where the construction logic lives.

3. **Upstream coding methodology section?** No — excluded. How UCDP codes events or what training ACLED coders receive is upstream-owned information. If we maintain our own copy and the provider changes their methodology, our copy is stale and misleading. The "Codebook" field already points readers to the provider's own methodology documentation — that is the right indirection. The catalog card says *where* to find methodology, not *what* the methodology is. Deeper methodological discussion (fitness for purpose, known coding biases) belongs in the source selection ADR, which is written once at decision time and references the provider's own documentation.

---

## References

### Data documentation standards

- Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J.W., Wallach, H., Daumé III, H. & Crawford, K. (2021). Datasheets for Datasets. *Communications of the ACM*, 64(12), 86–92. https://doi.org/10.1145/3458723 — Structured dataset documentation framework (57 questions, 7 sections). Our schema adopts the structural insight and selected fields.
- Wilkinson, M.D. et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018. https://doi.org/10.1038/sdata.2016.18 — Findable, Accessible, Interoperable, Reusable. Our schema satisfies F2 (rich metadata), R1.1 (license), R1.2 (provenance).
- Holland, S., Hosny, A., Newman, S., Joseph, J. & Chmielinski, K. (2018). The Dataset Nutrition Label. *arXiv:1805.03677*. https://arxiv.org/abs/1805.03677 — Structured "nutrition label" for datasets. Our "Codebook" field draws from their Variables module.
- Bender, E.M. & Friedman, B. (2018). Data Statements for Natural Language Processing: Toward Mitigating System Bias and Enabling Better Science. *Transactions of the ACL*, 6, 587–604. https://doi.org/10.1162/tacl_a_00041 — Data statements for NLP. Our exclusion of "annotator demographics" is deliberate (see excluded fields).
- W3C (2024). Data Catalog Vocabulary (DCAT) — Version 3. https://www.w3.org/TR/vocab-dcat-3/ — The W3C standard for dataset catalog metadata. Our field-to-DCAT mapping is in the schema rationale table.
- Nygard, M.T. (2011). Documenting Architecture Decisions. https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions — ADR pattern. Basis for our separation of catalog (living reference) from ADRs (immutable decisions).

### VIEWS system and data sources

- Hegre, H. et al. (2019). ViEWS: A political violence early-warning system. *Journal of Peace Research*, 56(2), 155–174. — Original VIEWS paper; data sources documented in Tables II–III and a single paragraph (p.161).
- Hegre, H. et al. (2021). ViEWS 2020: Revising and evaluating the ViEWS political violence early-warning system. *Journal of Peace Research*, 58(3), 599–611. — 2020 update; expanded source roster, same scattered documentation pattern.
- Hegre, H. et al. (2024). The VIEWS Prediction Challenge: Estimating the future of armed conflict. *International Interactions*. — Prediction challenge; most structured data documentation in any VIEWS publication (external teams required explicit source metadata).
- Hegre, H. et al. (2020). Introducing the UCDP Candidate Events Dataset. *Journal of Peace Research*, 57(3), 450–461. — UCDP Candidate documentation; update cadence, quality model, timeliness-accuracy trade-off. Informs our separation of "temporal granularity" from "update cadence."
- Raleigh, C. & Hegre, H. (2005). Introducing ACLED: An Armed Conflict Location and Event Dataset. *Conference paper*. — ACLED codebook (Appendix 1): relational schema with five tables, field-level definitions. Gold standard for source-level data documentation in this domain.
- Von der Maase, S.P. et al. (2025). The VIEWS Pipeline Handbook 1.0. — Section 2.4 "External Dependencies and Data Sources" (empty placeholder). The gap this ADR fills.
- Tollefsen, A.F., Strand, H. & Buhaug, H. (2012). PRIO-GRID: A unified spatial data structure. *Journal of Peace Research*, 49(2), 363–374. — PRIO-GRID spatial backbone.

### Internal references

- ADR-003: Authority of Declarations Over Inference
- ADR-012: Four-Layer Data Architecture
- ADR-028: ACLED Consolidation and Viewpoint Specifics
- ADR-029: GHS-POP as First Population Data Source
- ADR-030: Raster Tooling Selection
- `src/datafactory_provenance/source_registry.py` — operational pipeline registry

### Upstream data portals

- JRC GHSL Data Catalogue: https://data.jrc.ec.europa.eu/collection/ghsl
- UCDP: https://ucdp.uu.se/
- ACLED: https://acleddata.com/
- PRIO-GRID: https://grid.prio.org/
- FAO GAUL: https://data.apps.fao.org/
