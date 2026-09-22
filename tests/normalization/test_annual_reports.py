# filename: tests/normalization/test_annual_reports.py
# title: Normalization Layer - Annual Report Passage Tests
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Verifies the annual report passage normalizer. Annual reports
#     are the secondary revenue source that produces the reference
#     conflict case (SEC revenue vs annual-report revenue).
#
#     The normalizer converts a passage record into Evidence with a
#     SourceDocument, a content hash, and RECOGNIZED_REVENUE category.
#     Records whose fiscal_year does not match the request are skipped.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The normalizer in src/veda/normalization/annual_reports.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - Record fields required: text, source_name, source_url,
#       fiscal_year (int).
#     - fiscal_year must equal requested_period.fiscal_year; otherwise
#       the record is skipped.
#     - The period on the Evidence is label-only.

from __future__ import annotations

from datetime import datetime, timezone

from veda.normalization.annual_reports import normalize_annual_report_passage
from veda.providers.results import ProviderResult
from veda.shared.enums import (
    EvidenceCategory,
    ExtractionMethod,
    ProviderStatus,
    SourceType,
)
from veda.shared.periods import RequestedPeriod


ENTITY_ID = "entity:sec_edgar:vendor:0008888888"


def _requested(year: int = 2025) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _record(
    *,
    text: str = "Total revenue for fiscal year 2025 was approximately $4.0 billion.",
    source_name: str = "Annual Report (Investor Relations PDF)",
    source_url: str = "https://example-vendor.example/annual-report-2025.pdf",
    fiscal_year: int = 2025,
) -> dict:
    return {
        "text": text,
        "source_name": source_name,
        "source_url": source_url,
        "fiscal_year": fiscal_year,
    }


def _result(*records: dict) -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.ANNUAL_REPORT,
        source_name="Annual Reports (fixture)",
        is_fixture=True,
        raw_records=list(records) if records else [_record()],
        retrieved_at=datetime(2025, 1, 28, tzinfo=timezone.utc),
    )


def _not_found_result() -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.ANNUAL_REPORT,
        source_name="Annual Reports (fixture)",
        is_fixture=True,
        error_message="not found for test",
    )


# ====================================================================
# 1. Basic success
# ====================================================================

def test_returns_one_evidence_for_valid_record() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert len(evidence) == 1


def test_evidence_has_document() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].document is not None


def test_evidence_has_content_hash() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].document is not None
    content_hash = evidence[0].document.content_hash
    assert content_hash is not None
    assert len(content_hash) == 64
    assert all(c in "0123456789abcdef" for c in content_hash)


def test_evidence_has_location_with_url() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].location is not None
    assert evidence[0].location.source_url is not None
    assert "annual-report" in evidence[0].location.source_url


def test_evidence_category_is_recognized_revenue() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].evidence_category == EvidenceCategory.RECOGNIZED_REVENUE


def test_evidence_retrieval_method_is_text_extraction() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].retrieval_method == ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION


def test_evidence_source_type_is_annual_report() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].source_type == SourceType.ANNUAL_REPORT


def test_evidence_period_is_label_only() -> None:
    evidence = normalize_annual_report_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence[0].reporting_period.start is None
    assert evidence[0].reporting_period.end is None
    assert evidence[0].reporting_period.label == "FY2025"


# ====================================================================
# 2. Fiscal year matching
# ====================================================================

def test_wrong_fiscal_year_skips_record() -> None:
    rec = _record(fiscal_year=2024)
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_missing_fiscal_year_skips_record() -> None:
    rec = _record()
    del rec["fiscal_year"]
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_non_int_fiscal_year_skips_record() -> None:
    rec = _record(fiscal_year="2025")   # type: ignore[arg-type]
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


# ====================================================================
# 3. Malformed records are skipped
# ====================================================================

def test_missing_text_skips_record() -> None:
    rec = _record()
    del rec["text"]
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_missing_source_name_skips_record() -> None:
    rec = _record()
    del rec["source_name"]
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_missing_source_url_skips_record() -> None:
    rec = _record()
    del rec["source_url"]
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_blank_text_skips_record() -> None:
    rec = _record(text="   ")
    evidence = normalize_annual_report_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_malformed_record_does_not_break_valid_one() -> None:
    bad = _record(fiscal_year=2024)   # wrong year
    good = _record(fiscal_year=2025)
    evidence = normalize_annual_report_passage(_result(bad, good), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert len(evidence) == 1


# ====================================================================
# 4. Provider result handling
# ====================================================================

def test_not_found_result_returns_empty() -> None:
    evidence = normalize_annual_report_passage(_not_found_result(), entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []


def test_wrong_source_type_returns_empty() -> None:
    result = ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_FILING,
        source_name="SEC Filings",
        is_fixture=False,
        raw_records=[_record()],
    )
    evidence = normalize_annual_report_passage(result, entity_id=ENTITY_ID, requested_period=_requested(2025))
    assert evidence == []