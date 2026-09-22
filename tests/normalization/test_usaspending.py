# filename: tests/normalization/test_usaspending.py
# title: Normalization Layer - USAspending Award Tests
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Verifies the USAspending normalizer. Its one job is to convert
#     an award record into Evidence whose evidence_category is
#     PROCUREMENT_OBLIGATION — never RECOGNIZED_REVENUE.
#
#     This distinction is the "critical distinction" the employer
#     named. Revenue and obligations are different measures. If the
#     normalizer mislabels an obligation as revenue, the conflict
#     detector compares incomparable numbers, and a false conflict
#     appears in the packet. This file guards against that.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The normalizer in src/veda/normalization/usaspending.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - Each valid record requires award_id and
#       total_obligated_amount (numeric, not bool).
#     - The period is a label-only period. The orchestrator backfills
#       the dates from the requested period before claim extraction.

from __future__ import annotations

from datetime import datetime, timezone

from veda.normalization.usaspending import normalize_usaspending_award
from veda.providers.results import ProviderResult
from veda.shared.enums import (
    EvidenceCategory,
    ExtractionMethod,
    ProviderStatus,
    SourceType,
)
from veda.shared.periods import RequestedPeriod


ENTITY_ID = "entity:sec_edgar:vendor:0000936468"
AWARD_ID = "USASPEND-LMT-2024-0001"


def _requested(year: int = 2024) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _record(
    *,
    award_id: str = AWARD_ID,
    total_obligated_amount: float = 180000000,
    recipient_name: str = "LOCKHEED MARTIN CORP",
    awarding_agency: str = "Department of Defense",
    fiscal_year: int = 2024,
) -> dict:
    return {
        "award_id": award_id,
        "recipient_name": recipient_name,
        "awarding_agency": awarding_agency,
        "fiscal_year": fiscal_year,
        "total_obligated_amount": total_obligated_amount,
    }


def _result(*records: dict) -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.USASPENDING,
        source_name="USAspending",
        is_fixture=False,
        raw_records=list(records) if records else [_record()],
        retrieved_at=datetime(2025, 1, 28, tzinfo=timezone.utc),
    )


def _not_found_result() -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.USASPENDING,
        source_name="USAspending",
        is_fixture=False,
        error_message="not found for test",
    )


# ====================================================================
# 1. Basic success
# ====================================================================

def test_returns_one_evidence_for_valid_record() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1


def test_evidence_raw_value_matches_obligation() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].raw_value == 180000000


def test_evidence_unit_is_usd() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].unit == "USD"
    assert evidence[0].currency == "USD"


def test_evidence_source_type_is_usaspending() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].source_type == SourceType.USASPENDING


def test_evidence_retrieval_method_is_deterministic_json() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].retrieval_method == ExtractionMethod.DETERMINISTIC_JSON


def test_evidence_location_field_is_award_id() -> None:
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].location is not None
    assert evidence[0].location.field_or_passage == AWARD_ID


# ====================================================================
# 2. THE CRITICAL ASSERTION
# ====================================================================

def test_evidence_category_is_procurement_obligation() -> None:
    """
    The single most important assertion in this file.
    A USAspending obligation must be labeled as PROCUREMENT_OBLIGATION
    and must NEVER become RECOGNIZED_REVENUE.
    """
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.PROCUREMENT_OBLIGATION


def test_evidence_category_is_not_recognized_revenue() -> None:
    """
    The negative form of the critical assertion. Even if the amount
    happens to equal a revenue figure, the category must remain
    PROCUREMENT_OBLIGATION.
    """
    rec = _record(total_obligated_amount=71043000000)   # same as a revenue figure
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category != EvidenceCategory.RECOGNIZED_REVENUE


# ====================================================================
# 3. Period label
# ====================================================================

def test_evidence_period_is_label_only() -> None:
    """The normalizer produces a label-only period; the orchestrator backfills dates."""
    evidence = normalize_usaspending_award(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].reporting_period.start is None
    assert evidence[0].reporting_period.end is None
    assert evidence[0].reporting_period.label == "FY2024"


# ====================================================================
# 4. Malformed records are skipped
# ====================================================================

def test_missing_award_id_skips_record() -> None:
    rec = _record()
    del rec["award_id"]
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_blank_award_id_skips_record() -> None:
    rec = _record(award_id="   ")
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_amount_skips_record() -> None:
    rec = _record()
    del rec["total_obligated_amount"]
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_string_amount_skips_record() -> None:
    rec = _record(total_obligated_amount="180000000")   # type: ignore[arg-type]
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_bool_amount_skips_record() -> None:
    """A bool is a subclass of int; the code must reject it."""
    rec = _record(total_obligated_amount=True)   # type: ignore[arg-type]
    evidence = normalize_usaspending_award(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_malformed_record_does_not_break_valid_one() -> None:
    bad = _record()
    del bad["award_id"]
    good = _record(award_id="USASPEND-LMT-2024-0002")
    evidence = normalize_usaspending_award(_result(bad, good), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1


# ====================================================================
# 5. Provider result handling
# ====================================================================

def test_not_found_result_returns_empty() -> None:
    evidence = normalize_usaspending_award(_not_found_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_wrong_source_type_returns_empty() -> None:
    result = ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        is_fixture=False,
        raw_records=[_record()],
    )
    evidence = normalize_usaspending_award(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


# ====================================================================
# 6. Multiple records
# ====================================================================

def test_multiple_valid_records_produce_multiple_evidence() -> None:
    rec_a = _record(award_id="USASPEND-LMT-2024-0001")
    rec_b = _record(award_id="USASPEND-LMT-2024-0002")
    evidence = normalize_usaspending_award(_result(rec_a, rec_b), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 2


def test_evidence_ids_are_unique_across_awards() -> None:
    rec_a = _record(award_id="USASPEND-LMT-2024-0001")
    rec_b = _record(award_id="USASPEND-LMT-2024-0002")
    evidence = normalize_usaspending_award(_result(rec_a, rec_b), entity_id=ENTITY_ID, requested_period=_requested(2024))
    ids = [e.evidence_id for e in evidence]
    assert len(ids) == len(set(ids))