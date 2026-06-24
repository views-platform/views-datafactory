# Class Intent Contract: RemoteConfig

**Status:** Active
**Owner:** Simon Polichinel von der Maase
**Last reviewed:** 2026-04-22
**Related ADRs:** ADR-009, ADR-026

---

## 1. Purpose

> Immutable configuration for the remote VIEWS data server. Centralizes the server address, URL scheme, and resource paths so that consumers import a single constant instead of hardcoding IP addresses.

Default values point to the Hetzner deployment at `204.168.219.108`. Follows the same frozen-dataclass pattern as `GridConfig`.

---

## 2. Non-Goals (Explicit Exclusions)

- This class does **not** perform any network I/O (no HTTP requests, no connection checks)
- This class does **not** store or resolve credentials (that is `~/.netrc` per ADR-026)
- This class does **not** manage server health, availability, or failover
- This class does **not** know about data formats (zarr internals, parquet schema)
- This class does **not** know about consumers or model configurations

---

## 3. Responsibilities and Guarantees

- Guarantees immutability (frozen dataclass)
- Guarantees a well-formed `zarr_url` property: `{scheme}://{server}{zarr_path}`
- Guarantees a well-formed `parquet_url` property: `{scheme}://{server}/dataframe.parquet` (path is fixed, not configurable)
- Provides a module-level `DEFAULT_REMOTE` singleton for standard use

---

## 4. Inputs and Assumptions

- `server`: str, server hostname or IP address (default: `"204.168.219.108"`)
- `zarr_path`: str, URL path to the zarr store (default: `"/grid.zarr"`)
- `scheme`: str, URL scheme (default: `"http"`)

No `__post_init__` validation beyond frozen enforcement. Fields are trusted as strings — URL validity is the caller's responsibility.

---

## 5. Outputs and Side Effects

- No side effects. Pure configuration container.
- Properties `zarr_url` and `parquet_url` are computed from stored fields.

---

## 6. Failure Modes and Loudness

- `AttributeError` on any attempt to mutate fields (frozen)
- No validation errors — fields are unconstrained strings

All failures are immediate and loud. No silent fallbacks.

---

## 7. Boundaries and Interactions

- Used by `get_last_valid_month_id()` in the same module for metadata fetches
- Used by `load_dataset()` in `datafactory_query` as the default remote endpoint
- Used by consumer scripts (e.g., `generate_consumer_data.py`) for data retrieval
- Must not depend on any other `datafactory_*` config class
- Credential resolution is entirely separate (ADR-026: `~/.netrc`)

---

## 8. Examples of Correct Usage

```python
from datafactory_query.defaults import DEFAULT_REMOTE

url = DEFAULT_REMOTE.zarr_url  # "http://204.168.219.108/grid.zarr"

# Custom server for testing
cfg = RemoteConfig(server="localhost", scheme="http")
```

---

## 9. Examples of Incorrect Usage

```python
# WRONG: Adding credentials to RemoteConfig
RemoteConfig(server="user:pass@host")  # Credentials belong in ~/.netrc

# WRONG: Adding network logic to RemoteConfig
RemoteConfig().fetch()  # This class does not perform I/O
```

---

## 10. Test Alignment

- **Green:** Default URL construction, custom overrides
- **Beige:** None (no validation to test)
- **Red:** Mutation attempt (frozen enforcement)

Tests in `tests/test_query.py` (TestRemoteConfigGreen, TestRemoteConfigBeige).

---

## End of Contract

This document defines the **intended meaning** of `RemoteConfig`.

Changes to behavior that violate this intent are bugs.
Changes to intent must update this contract.
