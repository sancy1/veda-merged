"""
File: src/veda/entity/reporting_boundary.py
Title: Reporting Boundary Classification
Layer: Entity resolution and reporting boundary
Status: Merged prototype foundation — Phase 3
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from veda.shared.enums import EntityResolutionStatus, EntityType
from veda.shared.ids import parse_entity_id
from veda.shared.models import ResolvedEntity


class ReportingBoundaryResult(BaseModel):
    """Structured reporting-boundary classification."""

    boundary_type: EntityType
    parent_entity_id: Optional[str] = None
    parent_entity_name: Optional[str] = None
    is_consolidated_at_parent: bool = False
    boundary_note: Optional[str] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _validate_parent_id(self) -> "ReportingBoundaryResult":
        if self.parent_entity_id is not None:
            if parse_entity_id(self.parent_entity_id) is None:
                raise ValueError(
                    "parent_entity_id must be a canonical entity ID, "
                    f"got {self.parent_entity_id!r}"
                )
        return self


class ReportingBoundary:
    """Pure reporting-boundary classification helpers."""

    @staticmethod
    def for_resolved_entity(
        entity: ResolvedEntity,
        parent_entity_id: Optional[str] = None,
        parent_entity_name: Optional[str] = None,
    ) -> ReportingBoundaryResult:
        """
        Classify a resolved entity.

        Raises ValueError for unresolved entities. Call
        for_unresolved_entity() explicitly for unresolved input.
        """
        if entity.resolution_status != EntityResolutionStatus.RESOLVED:
            raise ValueError(
                "for_resolved_entity requires RESOLVED entity; "
                "call for_unresolved_entity() instead"
            )

        entity_type = entity.entity_type or EntityType.UNKNOWN

        if entity_type == EntityType.PUBLIC_COMPANY:
            return ReportingBoundaryResult(
                boundary_type=EntityType.PUBLIC_COMPANY,
                is_consolidated_at_parent=False,
            )

        if entity_type == EntityType.SUBSIDIARY:
            return ReportingBoundaryResult(
                boundary_type=EntityType.SUBSIDIARY,
                parent_entity_id=parent_entity_id,
                parent_entity_name=(
                    parent_entity_name or entity.parent_entity
                ),
                is_consolidated_at_parent=True,
                boundary_note="parent_reporting_boundary",
            )

        if entity_type == EntityType.JOINT_VENTURE:
            return ReportingBoundaryResult(
                boundary_type=EntityType.JOINT_VENTURE,
                is_consolidated_at_parent=False,
                boundary_note="jv_boundary_not_consolidated",
            )

        return ReportingBoundaryResult(
            boundary_type=EntityType.UNKNOWN,
            is_consolidated_at_parent=False,
        )

    @staticmethod
    def for_unresolved_entity(
        entity: ResolvedEntity,
    ) -> ReportingBoundaryResult:
        """Return an unknown boundary for an unresolved entity."""
        return ReportingBoundaryResult(
            boundary_type=EntityType.UNKNOWN,
            parent_entity_id=None,
            parent_entity_name=None,
            is_consolidated_at_parent=False,
            boundary_note=None,
        )