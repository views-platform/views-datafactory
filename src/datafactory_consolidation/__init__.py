"""Consolidation of raw source snapshots into lossless event stores.

Combines multiple vintages (annual releases, candidate versions) from
each data source into a single, append-only, version-aware store.
No opinions applied — survivorship and temporal distribution belong
to the viewpoint layer (datafactory_viewpoint).

Access specific consolidators via:
    from datafactory_consolidation.consolidators.ucdp import consolidate_ucdp

Or use the registry:
    from datafactory_consolidation.consolidators import consolidate_source
    consolidate_source("ucdp", config=...)
"""

from datafactory_consolidation.consolidation_result import ConsolidationResult
from datafactory_consolidation.consolidators import (
    consolidate_source,
    list_consolidators,
    register_consolidator,
)

__all__ = [
    "ConsolidationResult",
    "consolidate_source",
    "list_consolidators",
    "register_consolidator",
]
