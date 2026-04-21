# Credential Setup Guide

This guide covers all credentials needed to use views-datafactory,
whether as a consumer reading data or a developer running the
harvesting pipeline.

**Architectural reference:** ADR-026 (Credential Management Strategy)
governs how credentials work in this project. The key rules:
credentials live in environment variables or `~/.netrc`, never in
source code or config files distributed with the package.

---

## Overview

| Credential | Purpose | Mechanism | Who needs it |
|------------|---------|-----------|-------------|
| `UCDP_API_TOKEN` | Fetch UCDP event data | Environment variable | Pipeline operators |
| `~/.netrc` entry | HTTP auth for zarr data server | Standard Unix netrc | Data consumers |

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
| Hetzner HTTP | `_resolve_storage_options()` | `src/datafactory_query/dataset.py` |

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

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ValueError: UCDP API token required` | `UCDP_API_TOKEN` not set | Add to `~/.profile`, then `source ~/.profile` |
| Token set but harvester can't find it | Set in `.bashrc` only, running via cron | Move to `~/.profile` |
| `PermissionError: Authentication failed` | Wrong password or missing netrc entry | Check `~/.netrc` credentials |
| `netrc: bad permissions` | File permissions too open | `chmod 600 ~/.netrc` |
| `FileNotFoundError: Cannot open zarr store` | Server unreachable | Check network connectivity |
