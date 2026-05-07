# ADR-026: Credential Management Strategy

**Status:** Accepted
**Date:** 2026-04-21
**Deciders:** Simon, views-datafactory maintainers
**Consulted:** ADR-003 (declarations over inference), ADR-008 (fail-loud), ADR-009 (configuration validation)

---

## Context

The data factory fetches from external APIs (UCDP, ACLED, future: V-Dem) and serves derived data over HTTP (Hetzner zarr store). Each interaction requires credentials. The codebase already has a working pattern -- UCDP uses an environment variable (`UCDP_API_TOKEN`), Hetzner uses standard Unix `~/.netrc` -- but this pattern was never declared as an architectural decision. It exists as implicit knowledge in operational guides.

This matters for three reasons:

1. **PyPI publishability.** The package will be distributed on PyPI. No credential material can exist in the source tree or the published package. The env-var pattern is PyPI-safe by construction (the package ships code that *reads* a variable name, not a secret), but this guarantee needs to be explicit.

2. **ACLED integration.** ACLED uses an API key + email credential pair. Their EULA prohibits credential sharing. Each user must authenticate independently. This is architecturally different from UCDP's static API token but follows the same resolution pattern. ACLED credential management is now implemented: `get_acled_credentials()` in `src/datafactory_harvester/sources/acled.py` resolves credentials using the documented arg -> env (`ACLED_ACCESS_KEY`, `ACLED_EMAIL`) -> fail-loud order.

3. **Contributor guidance.** Without a declared strategy, a new contributor might add `python-dotenv`, embed a shared token in a config file, or put credentials in a frozen dataclass (where they leak via `repr()`).

---

## Decision

### 1. Credentials are not configuration

Credentials are **never** stored in frozen dataclasses, `__init__.py` exports, or any file distributed with the package. They are resolved at call time by per-source functions, not at import time.

Rationale: frozen dataclasses are designed to be inspectable (`repr()`, `str()`, logging). Credentials must not appear in tracebacks, log output, or provenance records.

### 2. Resolution order

Each source's credential resolver follows this precedence:

1. **Function argument** -- highest priority. Enables testing (`fetch(..., token="test")`) and scripting without env mutation.
2. **Environment variable** -- primary mechanism. 12-factor compatible. Works in CI/CD, cron, containers, Jupyter, and interactive shells.
3. **`~/.netrc`** -- HTTP basic auth only. Standard Unix mechanism read natively by `requests` (with `trust_env=True`) and `curl`. Used for the Hetzner data server.
4. **Fail-loud** -- if no credential is found, raise with an actionable error message naming the expected env var and setup instructions. No silent degradation, no anonymous fallback (ADR-008).

### 3. Per-source credential functions

Each data source owns its credential resolution. The existing `get_ucdp_token()` in `ucdp_annual.py` is the reference implementation:

```python
def get_ucdp_token(token: str | None = None) -> str:
    resolved = token or os.environ.get("UCDP_API_TOKEN")
    if not resolved:
        raise ValueError(
            "UCDP API token required. Set UCDP_API_TOKEN "
            "environment variable or pass token= ..."
        )
    return resolved
```

ACLED implements its own resolver (`get_acled_credentials()`) following the same pattern. Future sources (V-Dem) will do likewise. A generic `_resolve_credential()` utility is deferred until two or more sources share identical resolution logic -- premature abstraction before that point.

### 4. No config file fallback (deferred)

XDG config support (`~/.config/views-datafactory/credentials.toml`) is explicitly deferred. Environment variables are sufficient for the current credential set (UCDP token, ACLED key + email, netrc entry). Revisit if a future source requires persistent credential storage beyond env vars.

### 5. ACLED-specific constraints (implemented)

ACLED's EULA (as of 2025) imposes constraints that shape credential handling:

- **API key + email authentication.** Requires `ACLED_ACCESS_KEY` and `ACLED_EMAIL` environment variables. Resolved by `get_acled_credentials()` in `src/datafactory_harvester/sources/acled.py` using the same arg -> env -> fail-loud precedence as UCDP.
- **Credential sharing prohibited.** Each user authenticates with their own account. No shared service account for harvesting on behalf of others.
- **Redistribution restrictions.** Raw or lightly-transformed ACLED data cannot be redistributed. Grid-aggregated features (e.g., event counts per PRIO-GRID cell-month) are defensible as transformative. PRIO has a separate data agreement covering what is served via the zarr store.
- **AI/ML clause.** Models trained on ACLED data must not "create a substitute for ACLED." VIEWS conflict forecasting does not create a substitute (it forecasts, not provides event data).

### 6. What is forbidden

- Credentials in source code, frozen dataclasses, or any version-controlled file
- `.env` files in or near the project directory (git accident vector)
- `python-dotenv` as a dependency (encourages project-local `.env` files)
- Silent fallback to anonymous or degraded access
- Credential caching in package-distributed files
- Shared service accounts for sources that prohibit credential sharing (ACLED)

---

## Alternatives Rejected

| Alternative | Reason |
|-------------|--------|
| `keyring` (OS keychain) | Doesn't work on HPC clusters, headless servers, SSH sessions, or containers. Our users run on all of these. |
| `python-dotenv` | Encourages `.env` files next to source code. GitHub secret scanning exists precisely because this pattern fails at scale. |
| Credentials in frozen dataclasses | Would leak via `repr()`, `str()`, and logging. Provenance records would contain secrets. |
| Central `_resolve_credential()` utility | Premature -- UCDP (static token header) and ACLED (OAuth2 password grant) have fundamentally different auth flows. A generic resolver would either be too simple (string lookup) or too complex (token refresh). Wait for 2+ sources with identical patterns. |
| XDG config file (`~/.config/.../credentials.toml`) | Adds complexity and a second place to look. Env vars are sufficient for current credential count (1 token + 1 netrc entry). Revisit when ACLED requires persistent username + password storage. |

---

## Consequences

- **Package is PyPI-safe.** No credentials in the source tree, no credentials in the built distribution.
- **Public GitHub is safe.** The repo contains env var *names* (`UCDP_API_TOKEN`), not secrets.
- **New sources follow a pattern.** Implement a `get_<source>_credential()` function with the same arg -> env -> fail precedence.
- **ACLED integration has a clear architectural home.** OAuth2 token lifecycle lives in the ACLED harvester. Credentials come from env vars (`ACLED_USERNAME`, `ACLED_PASSWORD`).
- **`.gitignore` must defensively exclude** `.env*` and `credentials.toml` even though these files don't exist yet.

---

## References

- ADR-003: Authority of Declarations Over Inference -- env var names are the "declaration"
- ADR-008: Observability and Explicit Failure -- fail-loud on missing credentials
- ADR-009: Boundary Contracts and Configuration Validation -- credentials are explicitly excluded from the config validation pattern
- 12-Factor App, Factor III: Config -- store config in the environment
- ACLED EULA (2025): credential sharing prohibition, redistribution restrictions, AI/ML clause
- `get_ucdp_token()` in `src/datafactory_harvester/sources/ucdp_annual.py:132-142` -- reference implementation
- `_resolve_storage_options()` in `src/datafactory_query/dataset.py:54-97` -- netrc implementation
