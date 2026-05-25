"""Provenance tracking — content digests and JSONL ledger operations.

Every datafactory_* operation that produces output records provenance here.
No outbound imports to other datafactory_* packages.
"""

from datafactory_provenance.constants import VIEWS_EPOCH_YEAR
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
from datafactory_provenance.health import (
    FRESHNESS_SLO_HOURS,
    SOURCE_SLO,
    check_export_freshness,
    read_last_entries,
    report_ledger,
)
from datafactory_provenance.registry import Registry
from datafactory_provenance.source_registry import (
    PIPELINE_SOURCES,
    SourceEntry,
    get_all_features,
    get_required_env_vars,
    get_source_slo,
    validate_preflight,
)

__all__ = [
    "DIGEST_SCHEME",
    "FRESHNESS_SLO_HOURS",
    "LEDGER_VERSION",
    "PIPELINE_SOURCES",
    "Registry",
    "SOURCE_SLO",
    "SourceEntry",
    "VIEWS_EPOCH_YEAR",
    "append_ledger_entry",
    "check_export_freshness",
    "compute_content_digest",
    "compute_file_digest",
    "file_lock",
    "get_all_features",
    "get_required_env_vars",
    "get_source_slo",
    "last_digest",
    "last_digest_for_version",
    "read_last_entries",
    "report_ledger",
    "validate_preflight",
]

from importlib.metadata import version as _pkg_version

__version__ = _pkg_version("views-datafactory")
