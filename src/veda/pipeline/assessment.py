"""
File: src/veda/pipeline/assessment.py
Title: Five-State Assessment Engine
Layer: Pipeline layer
Status: Merged prototype foundation — Phase 6

Purpose
-------
Chooses exactly one of five assessment states from the claims,
conflicts, missing-evidence records, and reporting boundary. The
state rules are evaluated first-match-wins in a fixed order so the
result is deterministic and auditable.

Public API
----------
build_assessment_status(vendor, claims, conflicts,
                        missing_evidence, boundary) -> AssessmentStatus
choose_human_review_reason(status, vendor, conflicts) -> Optional[str]
choose_recommended_next_step(status) -> Optional[str]

Does not
--------
Does not make network calls.
Does not import veda.providers.fixtures.
Does not mutate inputs.
Does not produce more than one state.

Design notes
------------
Rule order, frozen. First match wins.

    1. Unresolved vendor                         -> REQUIRES_HUMAN_REVIEW
    2. Any conflict present                      -> CONFLICTING_EVIDENCE
    3. Missing evidence or zero claims           -> INSUFFICIENT_EVIDENCE
    4. INFERRED claim, LOW confidence, or
       consolidated-at-parent boundary           -> SUPPORTED_WITH_LIMITATIONS
    5. Otherwise                                 -> SUPPORTED
"""

from __future__ import annotations

from typing import Optional

from veda.shared.enums import (
    AssessmentStatus,
    ClaimStatus,
    ConfidenceLevel,
    EntityResolutionStatus,
)
from veda.shared.models import Claim, Conflict, MissingEvidence, ResolvedEntity


_UNRESOLVED_STATUSES = frozenset({
    EntityResolutionStatus.AMBIGUOUS,
    EntityResolutionStatus.NOT_FOUND,
    EntityResolutionStatus.REQUIRES_HUMAN_REVIEW,
})


def build_assessment_status(
    vendor: ResolvedEntity,
    claims: list[Claim],
    conflicts: list[Conflict],
    missing_evidence: list[MissingEvidence],
    boundary: Optional[object] = None,
) -> AssessmentStatus:
    """
    Return exactly one of the five assessment states.
    First matching rule wins.
    """
    if vendor.resolution_status in _UNRESOLVED_STATUSES:
        return AssessmentStatus.REQUIRES_HUMAN_REVIEW

    if conflicts:
        return AssessmentStatus.CONFLICTING_EVIDENCE

    if missing_evidence or not claims:
        return AssessmentStatus.INSUFFICIENT_EVIDENCE

    has_inferred = any(c.claim_status == ClaimStatus.INFERRED for c in claims)
    has_low_confidence = any(c.confidence == ConfidenceLevel.LOW for c in claims)
    consolidated = bool(
        boundary is not None
        and getattr(boundary, "is_consolidated_at_parent", False)
    )

    if has_inferred or has_low_confidence or consolidated:
        return AssessmentStatus.SUPPORTED_WITH_LIMITATIONS

    return AssessmentStatus.SUPPORTED


def choose_human_review_reason(
    status: AssessmentStatus,
    vendor: ResolvedEntity,
    conflicts: list[Conflict],
) -> Optional[str]:
    """Return a structured reason string, or None when not applicable."""
    if status == AssessmentStatus.REQUIRES_HUMAN_REVIEW:
        return (
            f"Vendor {vendor.input_name!r} could not be resolved to a "
            "single canonical entity."
        )
    if status == AssessmentStatus.CONFLICTING_EVIDENCE:
        if any(c.requires_human_review for c in conflicts):
            return "Comparable claims from independent sources disagree."
    return None


def choose_recommended_next_step(status: AssessmentStatus) -> Optional[str]:
    """Return the recommended next step for the state, or None."""
    if status == AssessmentStatus.REQUIRES_HUMAN_REVIEW:
        return "Disambiguate the vendor identity before proceeding."
    if status == AssessmentStatus.CONFLICTING_EVIDENCE:
        return "Human review of conflicting sources required."
    if status == AssessmentStatus.INSUFFICIENT_EVIDENCE:
        return "Seek additional authoritative disclosure."
    return None


__all__ = [
    "build_assessment_status",
    "choose_human_review_reason",
    "choose_recommended_next_step",
]