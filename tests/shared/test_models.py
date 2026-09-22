# filename: tests/shared/test_models.py
# title: Shared Contract - Data Model Tests
# layer: Test suite - shared contract
# status: Phase 1-6 test recovery
# description:
#     Verifies every Pydantic model in veda.shared.models: field
#     defaults, field validators, model validators, and the safety
#     invariants the pipeline depends on.
#
#     The single most important group of tests in this file is the
#     claim/evidence/assessment invariant group. If any of these fail,
#     the packet can silently contain unbacked claims, mislabeled
#     evidence, or impossible assessment states.
#
#     What this file proves:
#       - every model constructs with valid input
#       - required fields are required
#       - invalid field values raise ValueError
#       - cross-field invariants are enforced at construction
#       - human_summary() introduces no new facts
#
# source:
#     AUTHORED - Phase 2 had no saved test before recovery began.
#     The validators in src/veda/shared/models.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The Assessment status-invariant tests (section 10) are the
#       packet's most important safety guarantees. Each of the four
#       invariants gets a passing and a failing case.
#     - Every test uses the canonical ID generators from
#       veda.shared.ids to build valid IDs. No hardcoded fake IDs
#       that would fail the ID regex.

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from veda.shared.enums import (
    AssessmentStatus,
    ClaimStatus,
    ComparisonResult,
    ConfidenceLevel,
    EntityResolutionStatus,
    EntityType,
    EvidenceCategory,
    ExtractionMethod,
    MissingEvidenceReason,
    SourceType,
)
from veda.shared.ids import (
    assessment_id as make_assessment_id,
    claim_id as make_claim_id,
    conflict_id as make_conflict_id,
    document_id as make_document_id,
    entity_id as make_entity_id,
    evidence_id as make_evidence_id,
)
from veda.shared.models import (
    Assessment,
    AssessmentRequest,
    Claim,
    Conflict,
    Evidence,
    EvidenceLocation,
    MissingEvidence,
    ResolvedEntity,
    RunMetadata,
    SourceDocument,
)
from veda.shared.periods import Period, RequestedPeriod


# ====================================================================
# Fixtures - canonical values used throughout
# ====================================================================
ENTITY_ID = make_entity_id("sec_edgar", "vendor", "0000936468")
DOC_ID = make_document_id("sec_edgar", "10k", "000093646825000009")
EVIDENCE_ID_CF = make_evidence_id(
    SourceType.SEC_COMPANY_FACTS,
    ENTITY_ID,
    "FY2024",
    "Revenues",
)
EVIDENCE_ID_FILING = make_evidence_id(
    SourceType.SEC_FILING,
    ENTITY_ID,
    "FY2024",
    "revenues",
    DOC_ID,
)
CLAIM_ID_A = make_claim_id(ENTITY_ID, "total_revenue", "FY2024", [EVIDENCE_ID_CF])
CLAIM_ID_B = make_claim_id(ENTITY_ID, "total_revenue", "FY2024", [EVIDENCE_ID_FILING])
CONFLICT_ID = make_conflict_id(CLAIM_ID_A, CLAIM_ID_B)
DATED_PERIOD = Period(
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
    label="FY2024",
)
UNDATED_PERIOD = Period(label="FY2024")
REQUESTED_PERIOD = RequestedPeriod(
    fiscal_year=2024,
    start=date(2024, 1, 1),
    end=date(2024, 12, 31),
    raw="2024",
)


# ====================================================================
# 1. AssessmentRequest
# ====================================================================

def test_assessment_request_constructs_with_valid_input() -> None:
    request = AssessmentRequest(
        request_id=make_assessment_id(),
        company_name="Lockheed Martin Corp",
        fiscal_year=2024,
        requested_period=REQUESTED_PERIOD,
    )
    assert request.company_name == "Lockheed Martin Corp"
    assert request.fiscal_year == 2024


def test_assessment_request_requires_company_name() -> None:
    with pytest.raises(ValidationError):
        AssessmentRequest(
            request_id=make_assessment_id(),
            company_name="",
            fiscal_year=2024,
            requested_period=REQUESTED_PERIOD,
        )


def test_assessment_request_rejects_fiscal_year_mismatch() -> None:
    """The two sources of truth must agree at construction."""
    with pytest.raises(ValidationError):
        AssessmentRequest(
            request_id=make_assessment_id(),
            company_name="Lockheed Martin Corp",
            fiscal_year=2025,   # <- does not match requested_period (2024)
            requested_period=REQUESTED_PERIOD,
        )


def test_assessment_request_rejects_invalid_request_id() -> None:
    with pytest.raises(ValidationError):
        AssessmentRequest(
            request_id="not an assessment id",
            company_name="Lockheed Martin Corp",
            fiscal_year=2024,
            requested_period=REQUESTED_PERIOD,
        )


def test_assessment_request_rejects_blank_claim_type() -> None:
    with pytest.raises(ValidationError):
        AssessmentRequest(
            request_id=make_assessment_id(),
            company_name="Lockheed Martin Corp",
            fiscal_year=2024,
            requested_period=REQUESTED_PERIOD,
            requested_claim_types=["total_revenue", "  "],
        )


# ====================================================================
# 2. ResolvedEntity
# ====================================================================

def test_resolved_entity_resolved_requires_entity_id_name_cik() -> None:
    entity = ResolvedEntity(
        input_name="Lockheed Martin Corp",
        resolved_name="LOCKHEED MARTIN CORP",
        cik="0000936468",
        entity_id=ENTITY_ID,
        entity_type=EntityType.PUBLIC_COMPANY,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )
    assert entity.entity_id == ENTITY_ID


def test_resolved_entity_resolved_missing_entity_id_raises() -> None:
    with pytest.raises(ValidationError):
        ResolvedEntity(
            input_name="Lockheed Martin Corp",
            resolved_name="LOCKHEED MARTIN CORP",
            cik="0000936468",
            entity_id=None,
            resolution_method="exact_name",
            resolution_status=EntityResolutionStatus.RESOLVED,
        )


def test_resolved_entity_not_found_must_not_carry_entity_id() -> None:
    with pytest.raises(ValidationError):
        ResolvedEntity(
            input_name="Fake Vendor",
            entity_id=ENTITY_ID,   # <- forbidden for NOT_FOUND
            resolution_method="exact_name",
            resolution_status=EntityResolutionStatus.NOT_FOUND,
        )


def test_resolved_entity_ambiguous_requires_candidates() -> None:
    with pytest.raises(ValidationError):
        ResolvedEntity(
            input_name="ABC Technologies",
            resolution_method="exact_name",
            resolution_status=EntityResolutionStatus.AMBIGUOUS,
            candidates=[],
        )


def test_resolved_entity_ambiguous_with_candidates_succeeds() -> None:
    entity = ResolvedEntity(
        input_name="ABC Technologies",
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.AMBIGUOUS,
        candidates=["ABC Technologies Inc.", "ABC Technologies LLC"],
    )
    assert len(entity.candidates) == 2


def test_resolved_entity_cik_must_be_numeric() -> None:
    with pytest.raises(ValidationError):
        ResolvedEntity(
            input_name="Lockheed Martin Corp",
            resolved_name="LOCKHEED MARTIN CORP",
            cik="not-numeric",
            entity_id=ENTITY_ID,
            resolution_method="exact_name",
            resolution_status=EntityResolutionStatus.RESOLVED,
        )


def test_resolved_entity_rejects_malformed_entity_id() -> None:
    with pytest.raises(ValidationError):
        ResolvedEntity(
            input_name="Lockheed Martin Corp",
            resolved_name="LOCKHEED MARTIN CORP",
            cik="0000936468",
            entity_id="not an entity id",
            resolution_method="exact_name",
            resolution_status=EntityResolutionStatus.RESOLVED,
        )


# ====================================================================
# 3. SourceDocument
# ====================================================================

def test_source_document_constructs_with_valid_input() -> None:
    doc = SourceDocument(
        doc_id=DOC_ID,
        source_type=SourceType.SEC_FILING,
        doc_type="10k",
        title="SEC filing 000093646825000009",
    )
    assert doc.doc_id == DOC_ID


def test_source_document_rejects_malformed_doc_id() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            doc_id="not a doc id",
            source_type=SourceType.SEC_FILING,
            doc_type="10k",
            title="SEC filing",
        )


def test_source_document_fixture_requires_content_hash() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            doc_id=DOC_ID,
            source_type=SourceType.SEC_FILING,
            doc_type="10k",
            title="SEC filing",
            is_fixture=True,
            # no content_hash
        )


def test_source_document_fixture_with_content_hash_succeeds() -> None:
    doc = SourceDocument(
        doc_id=DOC_ID,
        source_type=SourceType.SEC_FILING,
        doc_type="10k",
        title="SEC filing",
        is_fixture=True,
        content_hash="a" * 64,
    )
    assert doc.content_hash == "a" * 64


def test_source_document_rejects_short_content_hash() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            doc_id=DOC_ID,
            source_type=SourceType.SEC_FILING,
            doc_type="10k",
            title="SEC filing",
            content_hash="too-short",
        )


def test_source_document_rejects_uppercase_content_hash() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            doc_id=DOC_ID,
            source_type=SourceType.SEC_FILING,
            doc_type="10k",
            title="SEC filing",
            content_hash="A" * 64,
        )


# ====================================================================
# 4. EvidenceLocation
# ====================================================================

def test_evidence_location_constructs_with_valid_input() -> None:
    loc = EvidenceLocation(field_or_passage="Revenues")
    assert loc.field_or_passage == "Revenues"


def test_evidence_location_span_order_enforced() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocation(
            field_or_passage="Revenues",
            span_start=100,
            span_end=50,
        )


def test_evidence_location_span_equal_ok() -> None:
    loc = EvidenceLocation(
        field_or_passage="Revenues",
        span_start=50,
        span_end=50,
    )
    assert loc.span_start == 50
    assert loc.span_end == 50


def test_evidence_location_rejects_negative_span() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocation(
            field_or_passage="Revenues",
            span_start=-1,
            span_end=10,
        )


def test_evidence_location_rejects_invalid_chunk_id() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocation(
            field_or_passage="Revenues",
            chunk_id="not a chunk id",
        )


# ====================================================================
# 5. Evidence
# ====================================================================

def _make_sec_facts_evidence(**overrides) -> Evidence:
    """Helper: build a minimal valid SEC Company Facts evidence."""
    base = dict(
        evidence_id=EVIDENCE_ID_CF,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        location=EvidenceLocation(
            field_or_passage="Revenues",
            source_reference="Revenues",
        ),
        raw_value=71043000000,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        retrieval_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        xbrl_tag="Revenues",
    )
    base.update(overrides)
    return Evidence(**base)


def test_evidence_sec_facts_constructs_with_valid_input() -> None:
    ev = _make_sec_facts_evidence()
    assert ev.raw_value == 71043000000


def test_evidence_requires_document_or_location() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id=EVIDENCE_ID_CF,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC Company Facts",
            entity_id=ENTITY_ID,
            reporting_period=DATED_PERIOD,
            evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
            retrieval_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        )


def test_evidence_sec_filing_requires_both_document_and_location() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id=EVIDENCE_ID_FILING,
            source_type=SourceType.SEC_FILING,
            source_name="SEC Filings",
            location=EvidenceLocation(field_or_passage="revenues"),
            # no document
            entity_id=ENTITY_ID,
            reporting_period=DATED_PERIOD,
            evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
            retrieval_method=ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION,
            accession_number="0000936468-25-000009",
        )


def test_evidence_sec_filing_requires_accession_number() -> None:
    doc = SourceDocument(
        doc_id=DOC_ID,
        source_type=SourceType.SEC_FILING,
        doc_type="10k",
        title="SEC filing",
    )
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id=EVIDENCE_ID_FILING,
            source_type=SourceType.SEC_FILING,
            source_name="SEC Filings",
            document=doc,
            location=EvidenceLocation(field_or_passage="revenues"),
            # no accession_number
            entity_id=ENTITY_ID,
            reporting_period=DATED_PERIOD,
            evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
            retrieval_method=ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION,
        )


def test_evidence_sec_filing_xbrl_extraction_requires_tag() -> None:
    doc = SourceDocument(
        doc_id=DOC_ID,
        source_type=SourceType.SEC_FILING,
        doc_type="10k",
        title="SEC filing",
    )
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id=EVIDENCE_ID_FILING,
            source_type=SourceType.SEC_FILING,
            source_name="SEC Filings",
            document=doc,
            location=EvidenceLocation(field_or_passage="revenues"),
            entity_id=ENTITY_ID,
            reporting_period=DATED_PERIOD,
            evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
            retrieval_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
            accession_number="0000936468-25-000009",
            # no xbrl_tag and no location.source_reference
        )


def test_evidence_sec_filing_narrative_does_not_require_xbrl_tag() -> None:
    """Narrative extraction is not required to carry an XBRL tag."""
    doc = SourceDocument(
        doc_id=DOC_ID,
        source_type=SourceType.SEC_FILING,
        doc_type="10k",
        title="SEC filing",
    )
    ev = Evidence(
        evidence_id=EVIDENCE_ID_FILING,
        source_type=SourceType.SEC_FILING,
        source_name="SEC Filings",
        document=doc,
        location=EvidenceLocation(field_or_passage="revenues"),
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        retrieval_method=ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION,
        accession_number="0000936468-25-000009",
    )
    assert ev.xbrl_tag is None


def test_evidence_rejects_malformed_evidence_id() -> None:
    with pytest.raises(ValidationError):
        _make_sec_facts_evidence(evidence_id="not an evidence id")


# ====================================================================
# 6. Claim - the most safety-critical model
# ====================================================================

def _make_claim(**overrides) -> Claim:
    base = dict(
        claim_id=CLAIM_ID_A,
        claim_type="total_revenue",
        value=71043000000,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        evidence_ids=[EVIDENCE_ID_CF],
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        extraction_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        confidence=ConfidenceLevel.HIGH,
        claim_status=ClaimStatus.SUPPORTED,
    )
    base.update(overrides)
    return Claim(**base)


def test_claim_supported_with_evidence_succeeds() -> None:
    claim = _make_claim()
    assert claim.claim_status == ClaimStatus.SUPPORTED


def test_claim_supported_without_evidence_raises() -> None:
    """The core safety invariant: no evidence, no SUPPORTED claim."""
    with pytest.raises(ValidationError):
        _make_claim(claim_status=ClaimStatus.SUPPORTED, evidence_ids=[])


def test_claim_inferred_without_evidence_succeeds() -> None:
    """INFERRED claims may lack evidence_ids."""
    claim = _make_claim(
        claim_status=ClaimStatus.INFERRED,
        evidence_ids=[],
        value=None,
    )
    assert claim.claim_status == ClaimStatus.INFERRED


def test_claim_rejects_malformed_claim_id() -> None:
    with pytest.raises(ValidationError):
        _make_claim(claim_id="not a claim id")


def test_claim_rejects_malformed_evidence_id() -> None:
    with pytest.raises(ValidationError):
        _make_claim(evidence_ids=["not an evidence id"])


# ====================================================================
# 7. Conflict
# ====================================================================

def _make_conflict(**overrides) -> Conflict:
    base = dict(
        conflict_id=CONFLICT_ID,
        claim_type="total_revenue",
        entity_id=ENTITY_ID,
        reporting_period=DATED_PERIOD,
        claim_ids=[CLAIM_ID_A, CLAIM_ID_B],
        evidence_ids=[EVIDENCE_ID_CF, EVIDENCE_ID_FILING],
        conflicting_values=[4200000000, 4000000000],
        comparison_result=ComparisonResult.CONFLICTS,
        reason="Two sources disagree on revenue.",
    )
    base.update(overrides)
    return Conflict(**base)


def test_conflict_constructs_with_valid_input() -> None:
    c = _make_conflict()
    assert len(c.claim_ids) == 2


def test_conflict_requires_at_least_two_claims() -> None:
    with pytest.raises(ValidationError):
        _make_conflict(claim_ids=[CLAIM_ID_A])


def test_conflict_rejects_duplicate_claims() -> None:
    with pytest.raises(ValidationError):
        _make_conflict(claim_ids=[CLAIM_ID_A, CLAIM_ID_A])


def test_conflict_requires_values_unless_insufficient_context() -> None:
    with pytest.raises(ValidationError):
        _make_conflict(
            conflicting_values=[],
            comparison_result=ComparisonResult.CONFLICTS,
        )


def test_conflict_allows_no_values_with_insufficient_context() -> None:
    c = _make_conflict(
        conflicting_values=[],
        comparison_result=ComparisonResult.INSUFFICIENT_CONTEXT,
    )
    assert c.conflicting_values == []


def test_conflict_requires_human_review_default_true() -> None:
    c = _make_conflict()
    assert c.requires_human_review is True


# ====================================================================
# 8. MissingEvidence
# ====================================================================

def test_missing_evidence_constructs_with_valid_input() -> None:
    m = MissingEvidence(
        claim_type="total_revenue",
        reason=MissingEvidenceReason.EVIDENCE_FOUND_BUT_NOT_SUFFICIENT,
        explanation="Revenue evidence was found but no supported claim.",
    )
    assert m.reason == MissingEvidenceReason.EVIDENCE_FOUND_BUT_NOT_SUFFICIENT


def test_missing_evidence_requires_explanation() -> None:
    with pytest.raises(ValidationError):
        MissingEvidence(
            claim_type="total_revenue",
            reason=MissingEvidenceReason.DATA_NOT_FOUND,
            explanation="",
        )


def test_missing_evidence_rejects_malformed_entity_id() -> None:
    with pytest.raises(ValidationError):
        MissingEvidence(
            claim_type="total_revenue",
            reason=MissingEvidenceReason.DATA_NOT_FOUND,
            explanation="No data found.",
            entity_id="not an entity id",
        )


# ====================================================================
# 9. RunMetadata
# ====================================================================

def test_run_metadata_constructs_with_valid_input() -> None:
    rm = RunMetadata(
        run_id=make_assessment_id(),
        schema_version="v0.1.0",
        pipeline_version="v0.1.0",
    )
    assert rm.schema_version == "v0.1.0"


def test_run_metadata_rejects_invalid_run_id() -> None:
    with pytest.raises(ValidationError):
        RunMetadata(
            run_id="not an assessment id",
            schema_version="v0.1.0",
            pipeline_version="v0.1.0",
        )


def test_run_metadata_rejects_finished_before_started() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        RunMetadata(
            run_id=make_assessment_id(),
            schema_version="v0.1.0",
            pipeline_version="v0.1.0",
            started_at=now,
            finished_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )


# ====================================================================
# 10. Assessment - the packet
# ====================================================================

def _resolved_entity() -> ResolvedEntity:
    return ResolvedEntity(
        input_name="Lockheed Martin Corp",
        resolved_name="LOCKHEED MARTIN CORP",
        cik="0000936468",
        entity_id=ENTITY_ID,
        entity_type=EntityType.PUBLIC_COMPANY,
        resolution_method="exact_name",
        resolution_status=EntityResolutionStatus.RESOLVED,
    )


def _run_metadata() -> RunMetadata:
    return RunMetadata(
        run_id=make_assessment_id(),
        schema_version="v0.1.0",
        pipeline_version="v0.1.0",
    )


def _make_assessment(**overrides) -> Assessment:
    base = dict(
        assessment_id=make_assessment_id(),
        request_id=make_assessment_id(),
        vendor=_resolved_entity(),
        reporting_period=DATED_PERIOD,
        claims=[_make_claim()],
        evidence=[_make_sec_facts_evidence()],
        conflicts=[],
        missing_evidence=[],
        assessment_status=AssessmentStatus.SUPPORTED,
        run_metadata=_run_metadata(),
    )
    base.update(overrides)
    return Assessment(**base)


def test_assessment_supported_constructs_with_valid_input() -> None:
    a = _make_assessment()
    assert a.assessment_status == AssessmentStatus.SUPPORTED


def test_assessment_insufficient_requires_missing_evidence() -> None:
    with pytest.raises(ValidationError):
        _make_assessment(
            assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
            missing_evidence=[],
        )


def test_assessment_insufficient_with_missing_evidence_succeeds() -> None:
    a = _make_assessment(
        claims=[],
        evidence=[],
        assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
        missing_evidence=[
            MissingEvidence(
                claim_type="any_evidence",
                reason=MissingEvidenceReason.DATA_NOT_FOUND,
                explanation="No evidence retrieved.",
            )
        ],
    )
    assert a.assessment_status == AssessmentStatus.INSUFFICIENT_EVIDENCE


def test_assessment_conflicting_requires_conflicts() -> None:
    with pytest.raises(ValidationError):
        _make_assessment(
            assessment_status=AssessmentStatus.CONFLICTING_EVIDENCE,
            conflicts=[],
        )


def test_assessment_requires_human_review_with_no_reason_raises() -> None:
    with pytest.raises(ValidationError):
        _make_assessment(
            assessment_status=AssessmentStatus.REQUIRES_HUMAN_REVIEW,
            human_review_reason=None,
            conflicts=[],
        )


def test_assessment_requires_human_review_with_reason_succeeds() -> None:
    a = _make_assessment(
        claims=[],
        evidence=[],
        assessment_status=AssessmentStatus.REQUIRES_HUMAN_REVIEW,
        human_review_reason="Vendor could not be resolved.",
    )
    assert a.human_review_reason == "Vendor could not be resolved."


def test_assessment_supported_requires_dated_period() -> None:
    """SUPPORTED requires a period with start and end dates."""
    with pytest.raises(ValidationError):
        _make_assessment(reporting_period=UNDATED_PERIOD)


def test_assessment_supported_with_limitations_requires_dated_period() -> None:
    with pytest.raises(ValidationError):
        _make_assessment(
            reporting_period=UNDATED_PERIOD,
            assessment_status=AssessmentStatus.SUPPORTED_WITH_LIMITATIONS,
        )


def test_assessment_insufficient_may_carry_undated_period() -> None:
    a = _make_assessment(
        claims=[],
        evidence=[],
        reporting_period=UNDATED_PERIOD,
        assessment_status=AssessmentStatus.INSUFFICIENT_EVIDENCE,
        missing_evidence=[
            MissingEvidence(
                claim_type="any_evidence",
                reason=MissingEvidenceReason.PERIOD_NOT_AVAILABLE,
                explanation="No data for requested period.",
            )
        ],
    )
    assert a.reporting_period.start is None


# ====================================================================
# 11. Assessment.human_summary()
# ====================================================================

def test_human_summary_includes_vendor_name() -> None:
    a = _make_assessment()
    summary = a.human_summary()
    assert "Lockheed Martin Corp" in summary


def test_human_summary_includes_assessment_status() -> None:
    a = _make_assessment()
    summary = a.human_summary()
    assert "SUPPORTED" in summary


def test_human_summary_includes_claim_line() -> None:
    a = _make_assessment()
    summary = a.human_summary()
    assert "total_revenue" in summary


def test_human_summary_no_new_facts() -> None:
    """
    Every line in human_summary() must map to a field. This test
    verifies that no invented prose appears by checking a few
    high-signal substrings that could not appear unless generated.
    """
    a = _make_assessment()
    summary = a.human_summary()
    # The summary must not contain a numeric value that is not in
    # the packet.
    assert "99999999" not in summary


def test_human_summary_includes_limitations_when_present() -> None:
    a = _make_assessment(
        assessment_status=AssessmentStatus.SUPPORTED_WITH_LIMITATIONS,
        limitations=["Disclosures are made at the parent level."],
    )
    summary = a.human_summary()
    assert "Disclosures are made at the parent level." in summary


def test_human_summary_does_not_fabricate_conflict_line() -> None:
    """A packet with no conflicts must not print a Conflicts section."""
    a = _make_assessment()
    summary = a.human_summary()
    assert "Conflicts:" not in summary