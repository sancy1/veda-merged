"""
File: src/veda/entity/__init__.py
Title: Entity Resolution Package
Layer: Entity resolution and reporting boundary
Status: Merged prototype foundation — Phase 3
"""

from veda.entity.reporting_boundary import (
    ReportingBoundary,
    ReportingBoundaryResult,
)
from veda.entity.resolver import (
    EntityCandidate,
    EntityResolver,
    EntityResolverSource,
    FixtureEntityResolverSource,
    LiveEntityResolverSource,
)

__all__ = [
    "EntityResolver",
    "EntityCandidate",
    "EntityResolverSource",
    "FixtureEntityResolverSource",
    "LiveEntityResolverSource",
    "ReportingBoundary",
    "ReportingBoundaryResult",
]