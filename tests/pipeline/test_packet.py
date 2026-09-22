# filename: tests/pipeline/test_packet.py
# title: Pipeline Layer - Packet Assembly Tests
# layer: Test suite - pipeline
# status: Phase 1-6 test recovery
# description:
#     Verifies build_packet: the function that assembles the final
#     Assessment packet from the outputs of every prior pipeline stage.
#
#     The single most important property is DETERMINISTIC ORDERING.
#     build_packet sorts four of the packet's lists before constructing
#     the Assessment:
#
#         claims              sorted by claim_id
#         evidence            sorted by evidence_id
#         conflicts           sorted by conflict_id
#         missing_evidence    sorted by (claim_type, reason.value)
#         limitations         sorted lexicographically
#
#     If any list is not sorted, two identical pipeline runs would
#     produce byte-different packets, and the Phase 6 smoke test's
#     determinism assertion would fail.
#
# source:
#     AUTHORED - Phase 6 had no saved test before recovery began.
#     The builder in src/veda/pipeline/packet.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - build_packet constructs the Assessment directly, not via a
#       dict. The Assessment model's validators fire on construction.
#       A malformed packet raises ValidationError from the model, not
#       from build_packet.
#     - The function does not mutate its inputs. The tests confirm
#       this by passing unsorted lists and verifying the inputs are
#       unchanged after the call.

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from veda.pipeline.packet import build_packet
from veda.shared.enums import (
    AssessmentStatus,
    ClaimStatus,
    ConfidenceLevel,
    EntityResolutionStatus,
    EvidenceCategory,
    ExtractionMethod,
    MissingEvidenceReason,
)
from veda.shared.ids import assessment_id as make_assessment_id
from veda.shared.ids import claim_id as make_claim_id
from veda.shared.ids import entity_id as make_entity_id
from veda.shared.ids import evidence_id as make_evidence_id
from veda.shared.models import (
    Assessment,
    Claim,
    Evidence,
    EvidenceLocation,
    MissingEvidence,
    ResolvedEntity,
    RunMetadata,
)
from veda.shared.periods import Period


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


def _run_metadata() -> RunMetadata:
    return RunMetadata(
        run_id=make_assessment_id(),
        schema_version="v0.1.0",
        pipeline_version="v0.1.0",
    )


def _evidence(suffix: str = "a") -> Evidence:
    ev_id = make_evidence_id(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", suffix)
    return Evidence(
        evidence_id=ev_id,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        location=EvidenceLocation(field_or_passage=suffix, source_reference=suffix),
        raw_value=71043000000,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        retrieval_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        xbrl_tag=suffix,
    )


def _claim(suffix: str = "a") -> Claim:
    ev = _evidence(suffix)
    cid = make_claim_id(ENTITY_ID, "total_revenue", "FY2024", [ev.evidence_id])
    return Claim(
        claim_id=cid,
        claim_type="total_revenue",
        value=71043000000,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_ids=[ev.evidence_id],
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        extraction_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        confidence=ConfidenceLevel.HIGH,
        claim_status=ClaimStatus.SUPPORTED,
    )


def _missing(claim_type: str = "any_evidence", reason: MissingEvidenceReason = MissingEvidenceReason.DATA_NOT_FOUND) -> MissingEvidence:
    return MissingEvidence(
        claim_type=claim_type,
        reason=reason,
        explanation=f"Missing {claim_type}.",
    )


from veda.shared.enums import SourceType  # placed here to keep import grouping readable


def _base_kwargs(**overrides) -> dict:
    """Return the base keyword arguments for build_packet."""
    claims = overrides.pop("claims", [_claim()])
    evidence = overrides.pop("evidence", [_evidence()])
    kwargs = dict(
        request_id=make_assessment_id(),
        assessment_id=make_assessment_id(),
        vendor=_resolved_vendor(),
        reporting_period=DATED_PERIOD,
        claims=claims,
        evidence=evidence,
        conflicts=[],
        missing_evidence=[],
        assessment_status=AssessmentStatus.SUPPORTED,
        limitations=[],
        run_metadata=_run_metadata(),
    )
    kwargs.update(overrides)
    return kwargs


# ====================================================================
# 1. Return type
# ====================================================================

def test_build_packet_returns_assessment() -> None:
    packet = build_packet(**_base_kwargs())
    assert isinstance(packet, Assessment)


def test_build_packet_preserves_assessment_id() -> None:
    aid = make_assessment_id()
    packet = build_packet(**_base_kwargs(assessment_id=aid))
    assert packet.assessment_id == aid


def test_build_packet_preserves_request_id() -> None:
    rid = make_assessment_id()
    packet = build_packet(**_base_kwargs(request_id=rid))
    assert packet.request_id == rid


# ====================================================================
# 2. Deterministic sorting — claims
# ====================================================================

def test_claims_sorted_by_claim_id() -> None:
    c1 = _claim(suffix="a")
    c2 = _claim(suffix="b")
    c3 = _claim(suffix="c")
    # Pass in reverse order; builder must sort.
    kwargs = _base_kwargs(
        claims=[c3, c1, c2],
        evidence=[_evidence("a"), _evidence("b"), _evidence("c")],
    )
    packet = build_packet(**kwargs)
    ids = [c.claim_id for c in packet.claims]
    assert ids == sorted(ids)


# ====================================================================
# 3. Deterministic sorting — evidence
# ====================================================================

def test_evidence_sorted_by_evidence_id() -> None:
    e1 = _evidence("a")
    e2 = _evidence("b")
    e3 = _evidence("c")
    c1 = _claim("a")
    c2 = _claim("b")
    c3 = _claim("c")
    kwargs = _base_kwargs(
        claims=[c1, c2, c3],
        evidence=[e3, e1, e2],
    )
    packet = build_packet(**kwargs)
    ids = [e.evidence_id for e in packet.evidence]
    assert ids == sorted(ids)


# ====================================================================
# 4. Deterministic sorting — missing evidence
# ====================================================================

def test_missing_evidence_sorted_by_claim_type_then_reason() -> None:
    m1 = _missing("z_type", MissingEvidenceReason.DATA_NOT_FOUND)
    m2 = _missing("a_type", MissingEvidenceReason.EVIDENCE_CONFLICTS)
    m3 = _missing("a_type", MissingEvidenceReason.DATA_NOT_FOUND)
    kwargs = _base_kwargs(
        claims=[],
        evidence=[],
        missing_evidence=[m1, m2, m3],
        assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
    )
    packet = build_packet(**kwargs)
    keys = [(m.claim_type, m.reason.value) for m in packet.missing_evidence]
    assert keys == sorted(keys)


# ====================================================================
# 5. Deterministic sorting — limitations
# ====================================================================

def test_limitations_sorted_lexicographically() -> None:
    kwargs = _base_kwargs(
        limitations=["z limitation", "a limitation", "m limitation"],
    )
    packet = build_packet(**kwargs)
    assert packet.limitations == sorted(packet.limitations)


# ====================================================================
# 6. No mutation of inputs
# ====================================================================

def test_build_packet_does_not_mutate_claims_input() -> None:
    c1 = _claim("a")
    c2 = _claim("b")
    c3 = _claim("c")
    input_claims = [c3, c1, c2]
    snapshot = list(input_claims)
    _base_kwargs_copy = _base_kwargs(
        claims=input_claims,
        evidence=[_evidence("a"), _evidence("b"), _evidence("c")],
    )
    build_packet(**_base_kwargs_copy)
    assert input_claims == snapshot


def test_build_packet_does_not_mutate_evidence_input() -> None:
    e1 = _evidence("a")
    e2 = _evidence("b")
    input_evidence = [e2, e1]
    snapshot = list(input_evidence)
    kwargs = _base_kwargs(
        claims=[_claim("a"), _claim("b")],
        evidence=input_evidence,
    )
    build_packet(**kwargs)
    assert input_evidence == snapshot


def test_build_packet_does_not_mutate_limitations_input() -> None:
    input_limitations = ["z", "a", "m"]
    snapshot = list(input_limitations)
    kwargs = _base_kwargs(limitations=input_limitations)
    build_packet(**kwargs)
    assert input_limitations == snapshot


# ====================================================================
# 7. Determinism
# ====================================================================

def test_same_inputs_produce_same_packet_structure() -> None:
    """
    Two calls with the same inputs produce packets whose field values
    match (excluding volatile fields: assessment_id, request_id,
    generated_at, run_metadata.run_id).
    """
    c1 = _claim("a")
    c2 = _claim("b")
    kwargs = _base_kwargs(
        claims=[c2, c1],
        evidence=[_evidence("a"), _evidence("b")],
    )
    packet_a = build_packet(**kwargs)
    packet_b = build_packet(**kwargs)
    assert [c.claim_id for c in packet_a.claims] == [c.claim_id for c in packet_b.claims]
    assert [e.evidence_id for e in packet_a.evidence] == [e.evidence_id for e in packet_b.evidence]


# ====================================================================
# 8. Model validators fire on construction
# ====================================================================

def test_insufficient_status_without_missing_evidence_raises() -> None:
    """The Assessment model rejects INSUFFICIENT_EVIDENCE with no missing records."""
    with pytest.raises(ValidationError):
        build_packet(**_base_kwargs(
            claims=[],
            evidence=[],
            assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
            missing_evidence=[],
        ))


def test_supported_status_without_dated_period_raises() -> None:
    """The Assessment model rejects SUPPORTED with an undated period."""
    with pytest.raises(ValidationError):
        build_packet(**_base_kwargs(
            reporting_period=Period(label="FY2024"),
        ))


# ====================================================================
# 9. Empty lists are fine
# ====================================================================

def test_empty_claims_and_evidence_and_conflicts_allowed() -> None:
    packet = build_packet(**_base_kwargs(
        claims=[],
        evidence=[],
        assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
        missing_evidence=[_missing()],
    ))
    assert packet.claims == []
    assert packet.evidence == []


# ====================================================================
# 10. Human summary accessible
# ====================================================================

def test_packet_human_summary_is_callable() -> None:
    packet = build_packet(**_base_kwargs())
    summary = packet.human_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0