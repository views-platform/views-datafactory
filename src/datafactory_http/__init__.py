"""HTTP request utilities — retry with exponential backoff.

No outbound imports to other datafactory_* packages.
"""

# `redact_url` is the package's public name for `retry._redact_url`, which
# stays module-private: `retry.py` owns the implementation, this file
# declares what the package exposes.
#
# Exported for the ACLED failed-fetch ledger entry (#513), which writes an
# exception message to a world-readable file and so must mask credentials
# at the write rather than trust its caller. C-332's trigger already named
# "export it" as the remedy; the reason it was not done then was
# `datafactory_query`, which may not import this package at all and
# therefore keeps its own local `_safe_url` (backends_zarr.py:45).
# `datafactory_harvester` may (tests/test_import_enforcement.py), so the
# single hard-won redactor is reachable there without a second copy —
# duplicating credential masking is the one duplication that must not
# drift.
from datafactory_http.retry import _redact_url as redact_url
from datafactory_http.retry import request_with_retry

__all__ = [
    "redact_url",
    "request_with_retry",
]
