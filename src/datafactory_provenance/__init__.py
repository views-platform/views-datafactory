"""Provenance tracking — content digests and JSONL ledger operations.

Every datafactory_* operation that produces output records provenance here.
No outbound imports to other datafactory_* packages.
"""

from datafactory_provenance.digests_and_ledgers import (
    DIGEST_SCHEME,
    LEDGER_VERSION,
    append_ledger_entry,
    compute_content_digest,
    compute_file_digest,
    file_lock,
    last_digest,
    last_digest_for_version,
)
from datafactory_provenance.registry import Registry

__all__ = [
    "DIGEST_SCHEME",
    "LEDGER_VERSION",
    "Registry",
    "append_ledger_entry",
    "compute_content_digest",
    "compute_file_digest",
    "file_lock",
    "last_digest",
    "last_digest_for_version",
]

from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("views-datafactory")
