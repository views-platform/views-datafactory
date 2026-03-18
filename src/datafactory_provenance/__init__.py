"""Shared foundations — provenance utilities and content digests.

No outbound imports to other datafactory_* packages.
"""

from datafactory_provenance.provenance import (
    append_ledger_entry,
    compute_content_digest,
    last_digest,
    last_digest_for_version,
)

__all__ = [
    "append_ledger_entry",
    "compute_content_digest",
    "last_digest",
    "last_digest_for_version",
]

from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("views-datafactory")
