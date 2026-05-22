# Data Source Catalog

Upstream data sources consumed by the VIEWS data factory. One card per source — see [ADR-033](../ADRs/033_data_source_catalog.md) for the schema and design rationale.

## Sources

| Source | Provider | Features | Temporal coverage | Granularity | Spatial | Update cadence |
|--------|----------|----------|-------------------|-------------|---------|----------------|
| [UCDP](ucdp.md) | Uppsala | 6 | 1989– | Daily events | Events → 0.5° | Annual (GED) + monthly (candidate) |
| [ACLED](acled.md) | ACLED | 8 | 1997– | Daily events | Events → 0.5° | Weekly |
| [GHS-POP](ghspop.md) | JRC/Copernicus | 1 | 1975–2030 | 5-year epochs | 30″ → 0.5° | ~2–3 year releases |
| [GHS-BUILT-S](ghsbuilts.md) | JRC/Copernicus | 1 | 1975–2030 | 5-year epochs | 30″ → 0.5° | ~2–3 year releases |
| [PRIO-GRID Static](priogrid_static.md) | PRIO | 34 | Static | — | 0.5° | One-time |
| [GAUL Admin](gaul_admin.md) | FAO | 3 | Static | — | Polygons → 0.5° | One-time |

**Total features in assembled grid:** 53

## Current status

For current harvest status, data versions, and content digests, run:

```bash
uv run python scripts/check_health.py
```

Or inspect the provenance ledger paths listed in each catalog card. The catalog documents what is stable about each source — dynamic operational state lives in the provenance ledgers.
