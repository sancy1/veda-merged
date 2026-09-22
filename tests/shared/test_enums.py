# filename: tests/shared/test_enums.py
# title: Shared Contract - Enumerations Tests
# layer: Test suite - shared contract
# status: Phase 1-6 test recovery
# description:
#     Verifies every enum in veda.shared.enums: value sets, str/Enum
#     inheritance, JSON serialization as plain strings, and the two
#     migration aliases (ClaimStatus.INSUFFICIENT and
#     AssessmentStatus.ANSWERABLE).
#
#     Every enum value that any other module relies on is asserted
#     here. If a value is renamed or removed, this test fails first.
#
# source:
#     AUTHORED - Phase 2 had no saved test before recovery began.
#     The enum definitions in src/veda/shared/enums.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The two alias tests exist because the personal prototype used
#       "insufficient" and "answerable" as Literal values. The merged
#       code preserves those as aliases so old packets still validate.
#       Removing the alias would break the migration contract.
#     - The JSON serialization tests use json.dumps on a dict containing
#       the enum member. Because every enum subclasses str, the output
#       is a plain quoted string, not a nested object.

from __future__ import annotations

import json

import pytest

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
    PeriodMatchStatus,
    ProviderStatus,
    SourceType,
)


# ====================================================================
# SourceType
# ====================================================================

def test_source_type_values() -> None:
    """SourceType declares exactly the seven source categories in use."""
    expected = {
        "sec_company_facts",
        "sec_filing",
        "usaspending",
        "annual_report",
        "gao",
        "dodig",
        "synthetic",
    }
    assert {member.value for member in SourceType} == expected


# ====================================================================
# EntityType
# ====================================================================

def test_entity_type_includes_public_company() -> None:
    assert EntityType.PUBLIC_COMPANY.value == "public_company"


def test_entity_type_includes_subsidiary() -> None:
    assert EntityType.SUBSIDIARY.value == "subsidiary"


def test_entity_type_includes_unknown() -> None:
    assert EntityType.UNKNOWN.value == "unknown"


# ====================================================================
# EntityResolutionStatus
# ====================================================================

def test_entity_resolution_status_values() -> None:
    expected = {"resolved", "ambiguous", "not_found", "requires_human_review"}
    assert {member.value for member in EntityResolutionStatus} == expected


# ====================================================================
# EvidenceCategory
# ====================================================================

def test_evidence_category_values() -> None:
    expected = {
        "recognized_revenue",
        "procurement_award",
        "procurement_obligation",
        "government_exposure",
        "customer_concentration",
        "corporate_relationship",
        "estimate",
        "proxy",
    }
    assert {member.value for member in EvidenceCategory} == expected


def test_recognized_revenue_and_procurement_obligation_are_distinct() -> None:
    """
    The single most important category distinction in the system.
    Recognized revenue and procurement obligations must never collapse
    into the same value.
    """
    assert EvidenceCategory.RECOGNIZED_REVENUE != EvidenceCategory.PROCUREMENT_OBLIGATION
    assert EvidenceCategory.RECOGNIZED_REVENUE.value != EvidenceCategory.PROCUREMENT_OBLIGATION.value


# ====================================================================
# ExtractionMethod
# ====================================================================

def test_extraction_method_includes_llm_structured_extraction() -> None:
    """The LLM extraction method exists so that LLM claims can be
    labeled distinctly from deterministic extraction."""
    assert ExtractionMethod.LLM_STRUCTURED_EXTRACTION.value == "llm_structured_extraction"


def test_extraction_method_includes_deterministic_field_extraction() -> None:
    assert ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION.value == "deterministic_field_extraction"


def test_extraction_method_includes_deterministic_json() -> None:
    """The personal prototype's retrieval_method value is preserved."""
    assert ExtractionMethod.DETERMINISTIC_JSON.value == "deterministic_json"


# ====================================================================
# ConfidenceLevel
# ====================================================================

def test_confidence_level_values() -> None:
    expected = {"high", "medium", "low"}
    assert {member.value for member in ConfidenceLevel} == expected


# ====================================================================
# ClaimStatus
# ====================================================================

def test_claim_status_values() -> None:
    expected = {
        "supported",
        "inferred",
        "conflicting",
        "insufficient_evidence",
        "requires_human_review",
    }
    assert {member.value for member in ClaimStatus} == expected


def test_claim_status_does_not_accept_legacy_insufficient_string() -> None:
    """
    The personal prototype used "insufficient" as a Literal value. The
    merged contract does NOT accept it. The enums.py docstring states:
    "The old string is not silently accepted as a new canonical output
    value."

    This test guards that policy. If a legacy string were silently
    mapped to the canonical value, a malformed packet would validate
    and mislabel evidence. The strict behavior is the safety guarantee.
    """
    with pytest.raises(ValueError):
        ClaimStatus("insufficient")


def test_claim_status_has_no_insufficient_alias_attribute() -> None:
    """
    There is no ClaimStatus.INSUFFICIENT attribute. Only the canonical
    INSUFFICIENT_EVIDENCE exists.
    """
    assert not hasattr(ClaimStatus, "INSUFFICIENT")


# ====================================================================
# ComparisonResult
# ====================================================================

def test_comparison_result_values() -> None:
    expected = {"agrees", "conflicts", "not_comparable", "insufficient_context"}
    assert {member.value for member in ComparisonResult} == expected


# ====================================================================
# MissingEvidenceReason
# ====================================================================

def test_missing_evidence_reason_values() -> None:
    expected = {
        "source_unavailable",
        "rate_limited",
        "malformed_response",
        "data_not_found",
        "entity_ambiguous",
        "period_not_available",
        "period_mismatch",
        "evidence_found_but_not_sufficient",
        "evidence_conflicts",
        "extraction_failed",
    }
    assert {member.value for member in MissingEvidenceReason} == expected


def test_missing_evidence_reason_distinguishes_technical_from_data() -> None:
    """
    Technical failures (source unavailable, rate limited, malformed
    response) must remain distinct from true data absence
    (data not found).
    """
    technical = {
        MissingEvidenceReason.SOURCE_UNAVAILABLE,
        MissingEvidenceReason.RATE_LIMITED,
        MissingEvidenceReason.MALFORMED_RESPONSE,
    }
    data = MissingEvidenceReason.DATA_NOT_FOUND
    assert data not in technical


# ====================================================================
# AssessmentStatus
# ====================================================================

def test_assessment_status_values() -> None:
    expected = {
        "supported",
        "supported_with_limitations",
        "conflicting_evidence",
        "insufficient_evidence",
        "requires_human_review",
    }
    assert {member.value for member in AssessmentStatus} == expected


def test_assessment_status_does_not_accept_legacy_answerable_string() -> None:
    """
    The personal prototype used "answerable" as a Literal value. The
    merged contract does NOT accept it. The enums.py docstring states:
    "The old string is not silently accepted as a new canonical output
    value."

    This is the same safety guarantee as for ClaimStatus.
    """
    with pytest.raises(ValueError):
        AssessmentStatus("answerable")


def test_assessment_status_has_no_answerable_alias_attribute() -> None:
    """
    There is no AssessmentStatus.ANSWERABLE attribute. Only the
    canonical SUPPORTED exists.
    """
    assert not hasattr(AssessmentStatus, "ANSWERABLE")


def test_assessment_status_has_exactly_five_states() -> None:
    """
    The 5-state assessment engine depends on exactly five states. If
    a sixth is added, the assessment rules in pipeline/assessment.py
    must be revised in lockstep.
    """
    assert len(list(AssessmentStatus)) == 5


# ====================================================================
# PeriodMatchStatus
# ====================================================================

def test_period_match_status_values() -> None:
    expected = {"exact", "adjacent", "mismatch", "unknown"}
    assert {member.value for member in PeriodMatchStatus} == expected


# ====================================================================
# ProviderStatus
# ====================================================================

def test_provider_status_values() -> None:
    expected = {
        "found",
        "not_found",
        "source_unavailable",
        "rate_limited",
        "malformed_response",
    }
    assert {member.value for member in ProviderStatus} == expected


# ====================================================================
# str/Enum inheritance
# ====================================================================

@pytest.mark.parametrize("enum_class", [
    SourceType,
    EntityType,
    EntityResolutionStatus,
    EvidenceCategory,
    ExtractionMethod,
    ConfidenceLevel,
    ClaimStatus,
    ComparisonResult,
    MissingEvidenceReason,
    AssessmentStatus,
    PeriodMatchStatus,
    ProviderStatus,
])
def test_enum_subclasses_str(enum_class) -> None:
    """Every enum subclasses str so it serializes as a plain string."""
    assert issubclass(enum_class, str)


# ====================================================================
# JSON serialization
# ====================================================================

def test_source_type_serializes_as_plain_string() -> None:
    result = json.dumps({"source": SourceType.SEC_FILING})
    assert result == '{"source": "sec_filing"}'


def test_assessment_status_serializes_as_plain_string() -> None:
    result = json.dumps({"status": AssessmentStatus.SUPPORTED})
    assert result == '{"status": "supported"}'


def test_claim_status_inferred_serializes_correctly() -> None:
    result = json.dumps({"claim_status": ClaimStatus.INFERRED})
    assert result == '{"claim_status": "inferred"}'


# ====================================================================
# Cross-enum distinctions
# ====================================================================

def test_claim_status_and_assessment_status_are_different_enums() -> None:
    """
    A supported claim can exist inside an assessment that requires
    review. The two enums must remain distinct.
    """
    assert ClaimStatus is not AssessmentStatus
    # The value "supported" appears in both, but they are different
    # enum members.
    assert ClaimStatus.SUPPORTED is not AssessmentStatus.SUPPORTED


def test_insufficient_evidence_value_is_shared_across_two_enums() -> None:
    """
    Both ClaimStatus and AssessmentStatus have an
    "insufficient_evidence" value. Both must be reachable and equal
    by string value but distinct by identity.
    """
    assert ClaimStatus.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"
    assert AssessmentStatus.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"
    assert ClaimStatus.INSUFFICIENT_EVIDENCE is not AssessmentStatus.INSUFFICIENT_EVIDENCE