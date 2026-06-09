# ADR-041: Content-Addressed Skip for Assembly and Export

**Status:** Accepted
**Date:** 2026-06-09
**Deciders:** Simon Polichinel von der Maase, Claude Code
**Extends:** ADR-032 (Harvest Idempotence and Caching), ADR-011 (Fail Loud, No Stale Data Serving)

---

## Context

The full pipeline takes ~6 hours on the Hetzner server. Assembly (~46 min) and export (~57 min) are the most expensive downstream steps. When inputs have not changed between runs (common during development or when only one source updates), these steps produce identical output — pure waste.

ADR-032 established content-addressed caching for harvest, using SHA-256 digests and a two-key cache (file existence + successful ledger entry). Assembly and export needed an analogous pattern.

### Incidents

Investigation of the initial inline skip implementation (risk register C-259 through C-262) found four correctness gaps:

- **C-259:** Static and admin Parquet directories were not digested, allowing false skips when these files changed.
- **C-260:** The skip check compared only current input keys against provenance, missing the case where a source was removed between runs.
- **C-261:** No provenance ledger entry was written on skip, leaving temporal gaps in the audit trail. No `--force` flag existed for operator override.
- **C-262:** The output file (grid.npy) was not verified on the skip path, meaning a truncated or corrupted output would be served indefinitely.

---

## Decision

### Skip logic lives in `datafactory_provenance/skip.py`

The skip decision is encapsulated in two functions:

- `check_assembly_skip(current_digests, provenance_path, output_path) -> SkipVerdict`
- `check_export_skip(provenance_path, export_path) -> SkipVerdict`

`SkipVerdict` is a frozen dataclass with fields: `should_skip`, `reason`, `changed_keys`, `missing_keys`, `output_valid`.

Scripts call these functions and act on the verdict. The skip module reads provenance JSON and computes output digests internally. Callers are responsible for computing input digests (domain-specific: which files to digest).

### Assembly skip contract

Assembly may skip if and only if all five conditions hold:

1. `provenance.json` exists from a previous run.
2. The output file (`grid.npy`) exists.
3. The set of digest keys in `current_digests` equals the set of non-null `*_digest` keys in the previous provenance sources. (Key-set equality — detects both addition and removal of sources.)
4. Every digest value in `current_digests` matches the corresponding value in the previous provenance.
5. The output file's actual digest matches the recorded `output_digest` in provenance. (Output integrity — catches truncation, corruption, or external modification.)

If any condition fails, assembly rebuilds.

### Export skip contract

Export (zarr) may skip if and only if:

1. `provenance.json` exists.
2. The zarr store exists with a `.zattrs` file.
3. The `source_digest` in `.zattrs` matches the `output_digest` in provenance.

### Static and admin directory digests

Static and admin directories contain multiple Parquet files. Their composite digest is computed by:

1. Sorting `*.parquet` files alphabetically.
2. Computing `compute_file_digest` for each file.
3. Concatenating the hex digests with `|` separator.
4. Computing `compute_content_digest` of the concatenated bytes.

This produces a single digest that changes when any constituent file changes, is added, or is removed. The computation is inline in the assembly script because only assembly knows which files in these directories are relevant.

### Outcome vocabulary and ledger entries

Following ADR-032, every run records a ledger entry:

| Outcome | Meaning |
|---------|---------|
| `success` | Full build/export completed |
| `unchanged` | Skip — inputs match, output intact |
| `failed` | Build/export failed (crash-stop, ADR-011) |

Ledger paths:
- Assembly: `data/assembled/ledger.jsonl`
- Export: `data/assembled/export_ledger.jsonl`

### `--force` flag

Both assembly and export accept `--force`, which bypasses the skip check entirely. The step runs as if `--skip-if-unchanged` were not set. The resulting ledger entry records `outcome: "success"`.

`--force` is for manual operator intervention (e.g., after a code change that affects output without changing input data). It is never set in `refresh_pipeline.sh`.

---

## Scope

This ADR covers assembly and export only. It does not cover:

- **Harvest:** Governed by ADR-032 with its own two-key cache pattern.
- **Compilation:** No skip logic. Compilation is fast enough (~2 min per source) that skip would add complexity for marginal benefit.
- **Digest gates:** The abort-on-mismatch gates in `export_zarr.py` and `generate_consumer_data.py` are a separate concern (preventing stale data serving, not avoiding redundant work).

---

## Consequences

- **No-change deploys drop from ~103 min to ~30 sec** (digest computation only).
- **Provenance trail is complete:** every pipeline run has a ledger entry, whether it built or skipped.
- **Output integrity is verified on every skip:** a corrupt grid.npy triggers a rebuild, not silent serving.
- **Source set changes are detected:** adding or removing a source (e.g., adding SHDI) prevents false skips.
- **Operator override exists:** `--force` provides an escape hatch when data hasn't changed but code has.
