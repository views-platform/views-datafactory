# FeatureFrame Conformance Fixture (ADR-050)

This directory is the **executable specification** of the platform's
FeatureFrame contract.

- `frame/` — a real `views_frames.FeatureFrame.save()` output
  (2 months × 3 PRIO-GRID cells × 2 features × 1 sample). It is
  **committed generator output, never hand-edited** (fixture policy,
  ADR-050; lesson C-315: fixtures that don't mirror real artifact
  shapes validate readers against themselves).
- `contract.json` — the language-neutral contract: output formats,
  identifier semantics, dtype, tensor shape, layout file list, and
  the pinned `fixture_digest`. Consumers who cannot install the
  views-datafactory wheel read this file; Python consumers may
  import `datafactory_query.OutputFormat` instead. Both are
  first-class (ADR-050).

## Provenance / regeneration

```
uv run python scripts/generate_contract_fixture.py          # regenerate
uv run python scripts/generate_contract_fixture.py --check  # verify
```

Regeneration on the same views-frames version is byte-identical
(save() pins zip timestamps — verified 2026-07-21). If regeneration
produces a diff after a views-frames upgrade, **that is the drift
alarm working**: the on-disk layout changed. Review the diff, bump
`contract_version`, record the new digest, and coordinate with
consumers per ADR-050's stability promise. Never silence the alarm
by regenerating without review.

## For consumer CIs (pipeline-core, views-baseline, …)

Vendor or fetch this directory and assert:
1. your reader loads `frame/` and round-trips the values below;
2. the directory's composite digest equals `contract.json.fixture_digest`.

Expected content: `time = [541,541,541,542,542,542]`,
`unit = [149426,150146,150866] × 2`, features
`["ged_sb_best", "acled_fatalities"]`, values `1..6` and `10..60`
(float32, shape (6, 2, 1)).
