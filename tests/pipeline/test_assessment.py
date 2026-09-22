# filename: tests/pipeline/test_assessment.py
# title: Pipeline Layer - Assessment Engine Tests
# layer: Test suite - pipeline
# status: Phase 1-6 test recovery
# description:
#     Verifies the 5-state assessment engine: build_assessment_status
#     plus the two helper functions choose_human_review_reason and
#     choose_recommended_next_step.
#
#     The engine evaluates five rules in a FIXED ORDER. First match
#     wins. The order is the contract:
#
#       1. Unresolved vendor               -> REQUIRES_HUMAN_REVIEW
#       2. Any conflict                    -> CONFLICTING_EVIDENCE
#       3. Missing evidence or no claims   -> INSUFFICIENT_EVIDENCE
#       4. INFERRED / LOW / consolidated   -> SUPPORTED_WITH_LIMITATIONS
#       5. Otherwise                       -> SUPPORTED
#
#     This file tests each rule in isolation AND the order between
#     adjacent rules. If the order is wrong, a packet with both a
#     conflict and an unresolved vendor would produce the wrong state.
#
# source:
#     AUTHORED - Phase 6 had no saved test before recovery began.
#     The engine in src/veda/pipeline/assessment.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The boundary argument is optional. When None, the engine
#       treats the entity as not consolidated-at-parent.
#     - The helpers return the same string for the same status; the
#       exact wording is part of the contract and is asserted here.

from __future__ import annotations

from datetime import date

from veda.pipeline.assessment import (
    build_assessment_status,
    choose_human_review_reason,
    choose_recommended_next_step,
)
from veda.shared.enums import (
    AssessmentStatus,
    ClaimStatus,
    ComparisonResult,
    ConfidenceLevel,
    EntityResolutionStatus,
    EvidenceCategory,
    ExtractionMethod,
)
from veda.shared.ids import claim_id as make_claim_id
from veda.shared.ids import conflict_id as make_conflict_id
from veda.shared.ids import entity_id as make_entity_id
from veda.shared.ids import evidence_id as make_evidence_id
from veda.shared.models import (
    Claim,
    Conflict,
    EvidenceLocation,
    MissingEvidence,
    ResolvedEntity,
)
from veda.shared.enums import MissingEvidenceReason
from veda.shared.periods import Period


# --------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------
ENTITY_ID = make_entity_id("sec_edgar", "vendor", "0000936468")
DATED_PERIOD = Period(start=date(2024, 1, 1), end=date(2024, 12, 31), label="FY2024")


def _resolved_vendor() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Lockheed Martin Corp",
        resolved_name="LOCKHEED MARTIN CORP",
        cik="0000936468",
        entity_id=ENTITY_ID,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _unresolved_vendor() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Fake Vendor",
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.NOT_FOUND,
        candidates=["Fake Vendor"],
    )


def _supported_claim(
    *,
    value: float = 71043000000,
    suffix: str = "a",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> Claim:
    ev_id = f"evidence:sec_edgar:{suffix * 16}"
    cid = make_claim_id(ENTITY_ID, "total_revenue", "FY2024", [ev_id])
    return Claim(
        claim_id=cid,
        claim_type="total_revenue",
        value=value,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_ids=[ev_id],
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        extraction_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        confidence=confidence,
        claim_status=ClaimStatus.SUPPORTED,
    )


def _inferred_claim(*, suffix: str = "b") -> Claim:
    ev_id = f"evidence:sec_edgar:{suffix * 16}"
    cid = make_claim_id(ENTITY_ID, "government_exposure", "FY2024", [ev_id])
    return Claim(
        claim_id=cid,
        claim_type="government_exposure",
        value=None,
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_ids=[ev_id],
        evidence_category=EvidenceCategory.GOVERNMENT_EXPOSURE,
        extraction_method=ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION,
        confidence=ConfidenceLevel.MEDIUM,
        claim_status=ClaimStatus.INFERRED,
    )


def _conflict(claim_a: Claim, claim_b: Claim) -> Conflict:
    sorted_ids = sorted([claim_a.claim_id, claim_b.claim_id])
    cid = make_conflict_id(sorted_ids[0], sorted_ids[1])
    return Conflict(
        conflict_id=cid,
        claim_type=claim_a.claim_type,
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        claim_ids=sorted_ids,
        evidence_ids=sorted(set(claim_a.evidence_ids) | set(claim_b.evidence_ids)),
        conflicting_values=[claim_a.value, claim_b.value],
        comparison_result=ComparisonResult.CONFLICTS,
        reason="Two sources disagree.",
    )


def _missing() -> MissingEvidence:
    return MissingEvidence(
        claim_type="any_evidence",
        reason=MissingEvidenceReason.DATA_NOT_FOUND,
        explanation="No data.",
    )


# ====================================================================
# 1. Rule 5 — SUPPORTED
# ====================================================================

def test_resolved_vendor_with_supported_claims_is_supported() -> None:
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim()],
        [],
        [],
    )
    assert status == AssessmentStatus.SUPPORTED


# ====================================================================
# 2. Rule 4 — SUPPORTED_WITH_LIMITATIONS
# ====================================================================

def test_inferred_claim_produces_supported_with_limitations() -> None:
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim(), _inferred_claim()],
        [],
        [],
    )
    assert status == AssessmentStatus.SUPPORTED_WITH_LIMITATIONS


def test_low_confidence_claim_produces_supported_with_limitations() -> None:
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim(confidence=ConfidenceLevel.LOW)],
        [],
        [],
    )
    assert status == AssessmentStatus.SUPPORTED_WITH_LIMITATIONS


def test_consolidated_at_parent_boundary_produces_supported_with_limitations() -> None:
    class Boundary:
        is_consolidated_at_parent = True

    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim()],
        [],
        [],
        boundary=Boundary(),
    )
    assert status == AssessmentStatus.SUPPORTED_WITH_LIMITATIONS


# ====================================================================
# 3. Rule 3 — INSUFFICIENT_EVIDENCE
# ====================================================================

def test_missing_evidence_produces_insufficient() -> None:
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim()],
        [],
        [_missing()],
    )
    assert status == AssessmentStatus.INSUFFICIENT_EVIDENCE


def test_zero_claims_produces_insufficient() -> None:
    status = build_assessment_status(
        _resolved_vendor(),
        [],
        [],
        [],
    )
    assert status == AssessmentStatus.INSUFFICIENT_EVIDENCE


# ====================================================================
# 4. Rule 2 — CONFLICTING_EVIDENCE
# ====================================================================

def test_conflict_produces_conflicting() -> None:
    a = _supported_claim(value=4200000000, suffix="a")
    b = _supported_claim(value=4000000000, suffix="b")
    cf = _conflict(a, b)
    status = build_assessment_status(
        _resolved_vendor(),
        [a, b],
        [cf],
        [],
    )
    assert status == AssessmentStatus.CONFLICTING_EVIDENCE


# ====================================================================
# 5. Rule 1 — REQUIRES_HUMAN_REVIEW
# ====================================================================

def test_unresolved_vendor_produces_requires_human_review() -> None:
    status = build_assessment_status(
        _unresolved_vendor(),
        [],
        [],
        [],
    )
    assert status == AssessmentStatus.REQUIRES_HUMAN_REVIEW


def test_ambiguous_vendor_produces_requires_human_review() -> None:
    ambiguous = ResolvedEntity(
        input_name="ABC Technologies",
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.AMBIGUOUS,
        candidates=["ABC Inc", "ABC LLC"],
    )
    status = build_assessment_status(ambiguous, [], [], [])
    assert status == AssessmentStatus.REQUIRES_HUMAN_REVIEW


# ====================================================================
# 6. Rule ORDER — the critical tests
# ====================================================================

def test_unresolved_vendor_takes_precedence_over_conflict() -> None:
    """
    Rule 1 fires before Rule 2. Even with a conflict, an unresolved
    vendor must produce REQUIRES_HUMAN_REVIEW, not CONFLICTING_EVIDENCE.
    """
    a = _supported_claim(value=4200000000, suffix="a")
    b = _supported_claim(value=4000000000, suffix="b")
    cf = _conflict(a, b)
    status = build_assessment_status(
        _unresolved_vendor(),
        [a, b],
        [cf],
        [],
    )
    assert status == AssessmentStatus.REQUIRES_HUMAN_REVIEW


def test_conflict_takes_precedence_over_missing_evidence() -> None:
    """
    Rule 2 fires before Rule 3. A packet with both a conflict and
    missing evidence produces CONFLICTING_EVIDENCE, not
    INSUFFICIENT_EVIDENCE.
    """
    a = _supported_claim(value=4200000000, suffix="a")
    b = _supported_claim(value=4000000000, suffix="b")
    cf = _conflict(a, b)
    status = build_assessment_status(
        _resolved_vendor(),
        [a, b],
        [cf],
        [_missing()],
    )
    assert status == AssessmentStatus.CONFLICTING_EVIDENCE


def test_missing_evidence_takes_precedence_over_inferred() -> None:
    """
    Rule 3 fires before Rule 4. A packet with missing evidence and
    an INFERRED claim produces INSUFFICIENT_EVIDENCE, not
    SUPPORTED_WITH_LIMITATIONS.
    """
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim(), _inferred_claim()],
        [],
        [_missing()],
    )
    assert status == AssessmentStatus.INSUFFICIENT_EVIDENCE


def test_inferred_takes_precedence_over_supported() -> None:
    """
    Rule 4 fires before Rule 5. An INFERRED claim + a SUPPORTED
    claim produces SUPPORTED_WITH_LIMITATIONS, not SUPPORTED.
    """
    status = build_assessment_status(
        _resolved_vendor(),
        [_supported_claim(), _inferred_claim()],
        [],
        [],
    )
    assert status == AssessmentStatus.SUPPORTED_WITH_LIMITATIONS


# ====================================================================
# 7. choose_human_review_reason
# ====================================================================

def test_human_review_reason_for_unresolved_vendor() -> None:
    reason = choose_human_review_reason(
        AssessmentStatus.REQUIRES_HUMAN_REVIEW,
        _unresolved_vendor(),
        [],
    )
    assert reason is not None
    assert "Fake Vendor" in reason


def test_human_review_reason_for_conflict_with_review_flag() -> None:
    a = _supported_claim(value=4200000000, suffix="a")
    b = _supported_claim(value=4000000000, suffix="b")
    cf = _conflict(a, b)   # requires_human_review defaults True
    reason = choose_human_review_reason(
        AssessmentStatus.CONFLICTING_EVIDENCE,
        _resolved_vendor(),
        [cf],
    )
    assert reason is not None
    assert "disagree" in reason.lower()


def test_human_review_reason_none_for_supported() -> None:
    reason = choose_human_review_reason(
        AssessmentStatus.SUPPORTED,
        _resolved_vendor(),
        [],
    )
    assert reason is None


def test_human_review_reason_none_for_insufficient() -> None:
    reason = choose_human_review_reason(
        AssessmentStatus.INSUFFICIENT_EVIDENCE,
        _resolved_vendor(),
        [],
    )
    assert reason is None


# ====================================================================
# 8. choose_recommended_next_step
# ====================================================================

def test_recommended_next_step_for_requires_human_review() -> None:
    step = choose_recommended_next_step(AssessmentStatus.REQUIRES_HUMAN_REVIEW)
    assert step is not None
    assert "isambiguate" in step or "identity" in step.lower()


def test_recommended_next_step_for_conflicting() -> None:
    step = choose_recommended_next_step(AssessmentStatus.CONFLICTING_EVIDENCE)
    assert step is not None
    assert "review" in step.lower()


def test_recommended_next_step_for_insufficient() -> None:
    step = choose_recommended_next_step(AssessmentStatus.INSUFFICIENT_EVIDENCE)
    assert step is not None
    assert "disclosure" in step.lower() or "evidence" in step.lower()


def test_recommended_next_step_none_for_supported() -> None:
    step = choose_recommended_next_step(AssessmentStatus.SUPPORTED)
    assert step is None


def test_recommended_next_step_none_for_supported_with_limitations() -> None:
    step = choose_recommended_next_step(AssessmentStatus.SUPPORTED_WITH_LIMITATIONS)
    assert step is None