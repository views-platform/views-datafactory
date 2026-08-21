# Credential Setup Guide

This guide covers all credentials needed to use views-datafactory,
whether as a consumer reading data or a developer running the
harvesting pipeline.

**Architectural reference:** ADR-026 (Credential Management Strategy)
governs how credentials work in this project. The key rules:
credentials live in environment variables or `~/.netrc`, never in
source code or config files distributed with the package.

<!-- PIN: appwrite-seam-v1.7.1. Not `main` — a bare main link is not a pin, and this
     one already changed meaning underneath us once (#393).

     Moving this pin obliges a diff-read; it is not a version bump. The registry at
     `docs/ADRs/platform/coordinate_registry.toml` in views-appwrite states the rule:

         conformant  <=>  your_pin >= obliges_consumers_since   (currently 1.5.2)

     Read the [edition."X.Y.Z"] table there and look only at editions with
     obliges_consumers = true; the rest are console observations that ask nothing.

     Diff-read done 2026-08-21, v1.2.0 -> v1.7.1. Three obliging editions in that range:
       1.3.0  the rename PLATFORM-001 -> The Appwrite Seam Contract. APPLIES TO US (#395).
       1.5.0  [contract.*] table + UNFAO_CONSUMER_DOCUMENT_NAME. Parties are
              views-postprocessing and views-faoapi. Not us.
       1.5.2  UNCRAFD_CONSUMER_DOCUMENT_NAME. Parties are views-postprocessing and
              views-crafdapi. Not us.
     Section 5 is byte-identical across the two tags, so §5.6 — the redaction clause
     cited in src/datafactory_http/retry.py — has not moved. -->
**The platform's other seam:** this guide governs the **datafactory
seam** (features served over HTTP). Forecast storage and delivery run
over the **Appwrite seam**, governed by
[The Appwrite Seam Contract — Identity, Secrets & Configuration](https://github.com/views-platform/views-appwrite/blob/appwrite-seam-v1.7.1/docs/ADRs/platform/appwrite_seam_contract.md)
(formerly `PLATFORM-001`; homed in views-appwrite, reciprocally
cross-linked per þing-01). A full modeling/delivery runtime needs
**both** seams' credentials in one environment — from this seam,
the `~/.netrc` entry is the sole co-resident secret. The harvest
tokens below are needed **only where harvests run**; no model,
postprocessing, or serving runtime ever needs them.

---

## Overview

| Credential | Purpose | Mechanism | Who needs it |
|------------|---------|-----------|-------------|
| `UCDP_API_TOKEN` | Fetch UCDP event data | Environment variable | Pipeline operators |
| `ACLED_USERNAME` / `ACLED_PASSWORD` | Fetch ACLED event data | Environment variables | Pipeline operators |
| `GDL_API_TOKEN` | Fetch SHDI data (Global Data Lab) | Environment variable | Pipeline operators |
| `~/.netrc` entry | HTTP auth for zarr data server | Standard Unix netrc | Data consumers |

**Not every source needs credentials.** GHS-POP, GHS-BUILT-S, V-Dem,
PRIO-GRID static, and GAUL admin boundaries are fetched anonymously —
no registration, no token.

---

## UCDP API Token

### Get a token

Register at [UCDP](https://ucdp.uu.se) and request an API key.

### Set it up

Add to your shell profile:

```bash
echo 'export UCDP_API_TOKEN="your-token-here"' >> ~/.profile
source ~/.profile
```

**Why `~/.profile` and not `~/.bashrc`?** Non-interactive shells
(cron, systemd) skip `.bashrc`. The harvester runs as a cron job on
the production server, so the token must be in a file that
non-interactive shells source. See the
[Hetzner deployment guide](hetzner_deployment_guide.md) Phase 1.6.

### Verify

```bash
echo $UCDP_API_TOKEN
```

If this prints your token, the harvester will find it.

### What happens if it's missing

`get_ucdp_token()` raises `ValueError` with a message telling you
exactly which environment variable to set. No silent fallback, no
anonymous access.

---

## ACLED API Credentials

### Get credentials

Register at [ACLED](https://acleddata.com/) and request API access.
You will receive a username (email) and password.

### Set them up

Add to your shell profile:

```bash
echo 'export ACLED_USERNAME="your-email@example.com"' >> ~/.profile
echo 'export ACLED_PASSWORD="your-password-here"' >> ~/.profile
source ~/.profile
```

**Why two variables?** ACLED uses OAuth2 password grant — the
username and password are exchanged for a short-lived access token
at harvest time. The token lifecycle is managed automatically by
the harvester (ADR-026).

### Verify

```bash
echo $ACLED_USERNAME
echo $ACLED_PASSWORD
```

If both print values, the harvester will find them.

### What happens if they're missing

`get_acled_credentials()` raises `ValueError` with a message naming
exactly which variable(s) to set. No silent fallback, no anonymous
access.

---

## GDL API Token (SHDI)

### Get a token

Register for a free account at [Global Data Lab](https://globaldatalab.org),
then go to **My GDL → API Access** to obtain your token.

### Set it up

Add to your shell profile:

```bash
echo 'export GDL_API_TOKEN="your-token-here"' >> ~/.profile
source ~/.profile
```

(Same `~/.profile`-not-`.bashrc` rationale as the UCDP token above —
the harvester must find it from non-interactive shells.)

### Verify

```bash
echo $GDL_API_TOKEN
```

### What happens if it's missing

`get_gdl_token()` raises `ValueError` pointing you at `GDL_API_TOKEN`
and the GDL registration page. No silent fallback, no anonymous access.

---

## Hetzner Data Server (HTTP Auth)

### Get credentials

Ask the data factory administrator for the HTTP basic auth password.

### Set it up

Add an entry to `~/.netrc`:

```bash
cat >> ~/.netrc << 'EOF'
machine 204.168.219.108
login views
password yourpassword
EOF
chmod 600 ~/.netrc
```

The `chmod 600` is required — tools reject netrc files with open
permissions.

### Verify

```bash
curl -n http://204.168.219.108/grid.zarr/.zmetadata | head -10
```

If this returns JSON metadata, authentication is working.

### What happens if it's missing

`load_dataset()` with a remote URL raises `PermissionError` with a
message pointing you to `~/.netrc`. No silent degradation.

---

## For Package Developers

### Where credential resolution lives

| Source | Function | File |
|--------|----------|------|
| UCDP | `get_ucdp_token()` | `src/datafactory_harvester/sources/ucdp_annual.py` |
| ACLED | `get_acled_credentials()` | `src/datafactory_harvester/sources/acled.py` |
| GDL (SHDI) | `get_gdl_token()` | `src/datafactory_harvester/sources/shdi.py` |
| Hetzner HTTP | `_resolve_storage_options()` | `src/datafactory_query/backends_zarr.py` |

### Resolution order

Every credential resolver follows the same precedence (ADR-026):

1. **Function argument** — highest priority, for testing and scripting
2. **Environment variable** — primary mechanism (12-factor compatible)
3. **`~/.netrc`** — HTTP basic auth only (standard Unix)
4. **Fail-loud** — actionable error message naming the missing credential

### Adding a new source

Implement a `get_<source>_credential()` function following the same
pattern as `get_ucdp_token()`. Do not create a generic resolver until
two or more sources share identical auth flows.

### What is forbidden

- Credentials in source code, frozen dataclasses, or version-controlled files
- `.env` files in or near the project directory
- `python-dotenv` as a dependency
- Silent fallback to anonymous access
- Shared service accounts for sources that prohibit credential sharing
- Credentials in any carrier — env var, netrc entry, header, or URL
  query value — reaching a log line or exception message; endpoints may
  be logged (The Appwrite Seam Contract's redaction clause, enforced
  for query-param tokens at the shared HTTP layer in
  `datafactory_http.retry`)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ValueError: UCDP API token required` | `UCDP_API_TOKEN` not set | Add to `~/.profile`, then `source ~/.profile` |
| Token set but harvester can't find it | Set in `.bashrc` only, running via cron | Move to `~/.profile` |
| `PermissionError: Authentication failed` | Wrong password or missing netrc entry | Check `~/.netrc` credentials |
| `netrc: bad permissions` | File permissions too open | `chmod 600 ~/.netrc` |
| `ValueError: ACLED credentials required` | `ACLED_USERNAME` or `ACLED_PASSWORD` not set | Add to `~/.profile`, then `source ~/.profile` |
| `ValueError: GDL API token required` | `GDL_API_TOKEN` not set | Register at globaldatalab.org (My GDL → API Access), add to `~/.profile` |
| `FileNotFoundError: Cannot open zarr store` | Server unreachable | Check network connectivity |
