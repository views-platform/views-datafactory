"""Viewpoint builders: opinionated, versioned views over consolidated data.

A viewpoint is a disposable, rebuildable, materialized view that applies
explicit rules (survivorship, temporal distribution, uncertainty handling)
to produce a single perspective on the consolidated event store. Multiple
viewpoints coexist. This implements the golden record concept (ADR-014).

Access specific builders via:
    from datafactory_viewpoint.builders.ucdp_v1 import build_ucdp_v1

Or use the registry:
    from datafactory_viewpoint.builders import build_viewpoint
    build_viewpoint("ucdp_v1", config=...)
"""

__all__: list[str] = []
