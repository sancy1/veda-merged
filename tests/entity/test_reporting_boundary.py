# filename: tests/entity/test_reporting_boundary.py
# title: Entity Layer - Reporting Boundary Tests
# layer: Test suite - entity
# status: Phase 1-6 test recovery
# description:
#     Verifies the ReportingBoundary classification. Given a resolved
#     entity, it decides:
#       - whether the entity is a public company, subsidiary, JV, or
#         unknown
#       - whether the entity's financials are consolidated at a parent
#       - the boundary_note that flows into the assessment limitations
#
#     This is the module that answers "whose financials am I actually
#     reading?" If it silently returns the wrong boundary, a
#     subsidiary's packet can be mislabeled as the parent's.
#
# source:
#     AUTHORED - Phase 3 had no saved test before recovery began.
#     The classifiers in src/veda/entity/reporting_boundary.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - for_resolved_entity() raises if the entity is not RESOLVED.
#       for_unresolved_entity() is the explicit alternative.
#     - boundary_note has a 64-character maximum. Any string the code
#       passes must fit; the tests confirm the existing notes do.

from __future__ import annotations

import pytest

from veda.entity.reporting_boundary import (
    ReportingBoundary,
    ReportingBoundaryResult,
)
from veda.shared.enums import EntityResolutionStatus, EntityType
from veda.shared.ids import entity_id as make_entity_id
from veda.shared.models import ResolvedEntity


# --------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------
def _public_company() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Lockheed Martin Corp",
        resolved_name="LOCKHEED MARTIN CORP",
        cik="0000936468",
        entity_id=make_entity_id("sec_edgar", "vendor", "0000936468"),
        entity_type=EntityType.PUBLIC_COMPANY,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _subsidiary() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Lockheed Martin Federal Solutions",
        resolved_name="LOCKHEED MARTIN CORP",
        cik="0000936468",
        entity_id=make_entity_id("sec_edgar", "vendor", "0000936468"),
        entity_type=EntityType.SUBSIDIARY,
        parent_entity="Lockheed Martin Corporation",
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _joint_venture() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Joint Venture Defense LLC",
        resolved_name="JOINT VENTURE DEFENSE LLC",
        cik="0009999999",
        entity_id=make_entity_id("sec_edgar", "vendor", "0009999999"),
        entity_type=EntityType.JOINT_VENTURE,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _unknown_type() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Unknown Entity",
        resolved_name="UNKNOWN ENTITY",
        cik="0001111111",
        entity_id=make_entity_id("sec_edgar", "vendor", "0001111111"),
        entity_type=EntityType.UNKNOWN,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _unresolved() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Fake Vendor",
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.NOT_FOUND,
        candidates=["Fake Vendor"],
    )


# ====================================================================
# 1. ReportingBoundaryResult model
# ====================================================================

def test_boundary_result_constructs_with_required_fields() -> None:
    result = ReportingBoundaryResult(boundary_type=EntityType.PUBLIC_COMPANY)
    assert result.boundary_type == EntityType.PUBLIC_COMPANY
    assert result.is_consolidated_at_parent is False


def test_boundary_result_rejects_malformed_parent_entity_id() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReportingBoundaryResult(
            boundary_type=EntityType.SUBSIDIARY,
            parent_entity_id="not an entity id",
        )


def test_boundary_result_accepts_canonical_parent_entity_id() -> None:
    parent_id = make_entity_id("sec_edgar", "vendor", "0000936468")
    result = ReportingBoundaryResult(
        boundary_type=EntityType.SUBSIDIARY,
        parent_entity_id=parent_id,
    )
    assert result.parent_entity_id == parent_id


# ====================================================================
# 2. for_resolved_entity - public company
# ====================================================================

def test_public_company_is_not_consolidated_at_parent() -> None:
    result = ReportingBoundary.for_resolved_entity(_public_company())
    assert result.boundary_type == EntityType.PUBLIC_COMPANY
    assert result.is_consolidated_at_parent is False
    assert result.boundary_note is None


# ====================================================================
# 3. for_resolved_entity - subsidiary
# ====================================================================

def test_subsidiary_is_consolidated_at_parent() -> None:
    result = ReportingBoundary.for_resolved_entity(_subsidiary())
    assert result.boundary_type == EntityType.SUBSIDIARY
    assert result.is_consolidated_at_parent is True


def test_subsidiary_uses_entity_parent_name() -> None:
    result = ReportingBoundary.for_resolved_entity(_subsidiary())
    assert result.parent_entity_name == "Lockheed Martin Corporation"


def test_subsidiary_explicit_parent_overrides_entity_field() -> None:
    result = ReportingBoundary.for_resolved_entity(
        _subsidiary(),
        parent_entity_name="Explicit Parent",
    )
    assert result.parent_entity_name == "Explicit Parent"


def test_subsidiary_boundary_note_is_set() -> None:
    result = ReportingBoundary.for_resolved_entity(_subsidiary())
    assert result.boundary_note == "parent_reporting_boundary"


def test_subsidiary_boundary_note_fits_model_limit() -> None:
    """boundary_note has max_length=64; the code must produce short notes."""
    result = ReportingBoundary.for_resolved_entity(_subsidiary())
    assert result.boundary_note is not None
    assert len(result.boundary_note) <= 64


def test_subsidiary_explicit_parent_entity_id_preserved() -> None:
    parent_id = make_entity_id("sec_edgar", "vendor", "0000936468")
    result = ReportingBoundary.for_resolved_entity(
        _subsidiary(),
        parent_entity_id=parent_id,
    )
    assert result.parent_entity_id == parent_id


# ====================================================================
# 4. for_resolved_entity - joint venture
# ====================================================================

def test_joint_venture_is_not_consolidated_at_parent() -> None:
    result = ReportingBoundary.for_resolved_entity(_joint_venture())
    assert result.boundary_type == EntityType.JOINT_VENTURE
    assert result.is_consolidated_at_parent is False


def test_joint_venture_boundary_note_is_set() -> None:
    result = ReportingBoundary.for_resolved_entity(_joint_venture())
    assert result.boundary_note == "jv_boundary_not_consolidated"


def test_joint_venture_boundary_note_fits_model_limit() -> None:
    result = ReportingBoundary.for_resolved_entity(_joint_venture())
    assert result.boundary_note is not None
    assert len(result.boundary_note) <= 64


# ====================================================================
# 5. for_resolved_entity - unknown
# ====================================================================

def test_unknown_type_returns_unknown_boundary() -> None:
    result = ReportingBoundary.for_resolved_entity(_unknown_type())
    assert result.boundary_type == EntityType.UNKNOWN
    assert result.is_consolidated_at_parent is False
    assert result.boundary_note is None


# ====================================================================
# 6. for_resolved_entity - guards against unresolved input
# ====================================================================

def test_resolved_only_raises_for_unresolved_entity() -> None:
    """
    for_resolved_entity must reject an unresolved entity. Callers who
    have an unresolved entity must use for_unresolved_entity instead.
    """
    with pytest.raises(ValueError):
        ReportingBoundary.for_resolved_entity(_unresolved())


# ====================================================================
# 7. for_unresolved_entity
# ====================================================================

def test_unresolved_returns_unknown_boundary() -> None:
    result = ReportingBoundary.for_unresolved_entity(_unresolved())
    assert result.boundary_type == EntityType.UNKNOWN
    assert result.is_consolidated_at_parent is False
    assert result.parent_entity_id is None
    assert result.parent_entity_name is None
    assert result.boundary_note is None


def test_unresolved_boundary_works_for_any_status() -> None:
    """for_unresolved_entity does not check the status; it just returns unknown."""
    result = ReportingBoundary.for_unresolved_entity(_public_company())
    assert result.boundary_type == EntityType.UNKNOWN