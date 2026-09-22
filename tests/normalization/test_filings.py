# filename: tests/normalization/test_filings.py
# title: Normalization Layer - SEC Filing Passage Tests
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Verifies the SEC Filing passage normalizer: it converts a
#     provider passage record into a canonical Evidence with a
#     SourceDocument, an EvidenceLocation, and a content hash.
#
#     The filing passage is where the "government_exposure" and
#     "customer_concentration" narrative claims come from. The
#     normalizer decides the evidence_category based on the passage
#     hint the caller supplied.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The normalizer in src/veda/normalization/filings.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - SEC_FILING evidence requires BOTH a document and a location.
#     - The passage hint maps to an evidence_category:
#         subsidiary_relationship  -> CORPORATE_RELATIONSHIP
#         government_exposure      -> GOVERNMENT_EXPOSURE
#         customer_concentration   -> CUSTOMER_CONCENTRATION
#       An unknown hint falls back to GOVERNMENT_EXPOSURE.
#     - If record fields are missing or blank, the record is skipped.

from __future__ import annotations

from datetime import datetime, timezone

from veda.normalization.filings import normalize_filing_passage
from veda.providers.results import ProviderResult
from veda.shared.enums import (
    EvidenceCategory,
    ExtractionMethod,
    ProviderStatus,
    SourceType,
)
from veda.shared.periods import RequestedPeriod


ENTITY_ID = "entity:sec_edgar:vendor:0000936468"
ACCN = "0000936468-25-000009"
FORM = "10-K"


def _requested(year: int = 2024) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _record(
    *,
    text: str = "Total revenues were $71,043 million for the year ended December 31, 2024.",
    accession_number: str = ACCN,
    filing_form: str = FORM,
    field_or_passage_hint: str = "revenues",
    section: str | None = "MD&A",
    url: str | None = "https://www.sec.gov/Archives/edgar/data/936468/000093646825000009/0000936468-25-000009-index.htm",
) -> dict:
    return {
        "text": text,
        "accession_number": accession_number,
        "filing_form": filing_form,
        "field_or_passage_hint": field_or_passage_hint,
        "section": section,
        "url": url,
    }


def _result(*records: dict) -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_FILING,
        source_name="SEC Filings",
        is_fixture=False,
        raw_records=list(records) if records else [_record()],
        retrieved_at=datetime(2025, 1, 28, tzinfo=timezone.utc),
    )


def _not_found_result() -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_FILING,
        source_name="SEC Filings",
        is_fixture=False,
        error_message="not found for test",
    )


# ====================================================================
# 1. Basic success
# ====================================================================

def test_returns_one_evidence_for_valid_record() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1


def test_evidence_has_document() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].document is not None
    assert evidence[0].document.accession_number == ACCN


def test_evidence_has_location() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].location is not None
    assert evidence[0].location.field_or_passage == "revenues"


def test_evidence_content_hash_is_sha256() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].document is not None
    content_hash = evidence[0].document.content_hash
    assert content_hash is not None
    assert len(content_hash) == 64
    assert all(c in "0123456789abcdef" for c in content_hash)


def test_evidence_retrieval_method_is_text_extraction() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].retrieval_method == ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION


def test_evidence_accession_number_on_record() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].accession_number == ACCN


# ====================================================================
# 2. Hint-to-category mapping
# ====================================================================

def test_subsidiary_relationship_maps_to_corporate_relationship() -> None:
    rec = _record(field_or_passage_hint="subsidiary_relationship")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.CORPORATE_RELATIONSHIP


def test_government_exposure_maps_to_government_exposure() -> None:
    rec = _record(field_or_passage_hint="government_exposure")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.GOVERNMENT_EXPOSURE


def test_customer_concentration_maps_to_customer_concentration() -> None:
    rec = _record(field_or_passage_hint="customer_concentration")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.CUSTOMER_CONCENTRATION


def test_unknown_hint_falls_back_to_government_exposure() -> None:
    rec = _record(field_or_passage_hint="unknown_hint")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.GOVERNMENT_EXPOSURE


# ====================================================================
# 3. Document ID generation
# ====================================================================

def test_document_id_uses_form_slug() -> None:
    evidence = normalize_filing_passage(_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].document is not None
    assert evidence[0].document.doc_id == f"doc:sec_edgar:10k:{ACCN}"


def test_document_id_lowercases_form() -> None:
    rec = _record(filing_form="10-K")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].document is not None
    assert "10k" in evidence[0].document.doc_id


# ====================================================================
# 4. Malformed record skipping
# ====================================================================

def test_missing_text_skips_record() -> None:
    rec = _record()
    del rec["text"]
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_accession_skips_record() -> None:
    rec = _record()
    del rec["accession_number"]
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_form_skips_record() -> None:
    rec = _record()
    del rec["filing_form"]
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_hint_skips_record() -> None:
    rec = _record()
    del rec["field_or_passage_hint"]
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_blank_text_skips_record() -> None:
    rec = _record(text="   ")
    evidence = normalize_filing_passage(_result(rec), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_malformed_record_does_not_break_valid_one() -> None:
    bad = _record()
    del bad["text"]
    good = _record(field_or_passage_hint="government_exposure")
    evidence = normalize_filing_passage(_result(bad, good), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1


# ====================================================================
# 5. Provider result handling
# ====================================================================

def test_not_found_result_returns_empty() -> None:
    evidence = normalize_filing_passage(_not_found_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_wrong_source_type_returns_empty() -> None:
    result = ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        is_fixture=False,
        raw_records=[_record()],
    )
    evidence = normalize_filing_passage(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


# ====================================================================
# 6. Multiple records
# ====================================================================

def test_multiple_valid_records_produce_multiple_evidence() -> None:
    rec_a = _record(field_or_passage_hint="government_exposure")
    rec_b = _record(field_or_passage_hint="subsidiary_relationship")
    evidence = normalize_filing_passage(_result(rec_a, rec_b), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 2


def test_evidence_ids_are_unique() -> None:
    rec_a = _record(field_or_passage_hint="government_exposure")
    rec_b = _record(field_or_passage_hint="subsidiary_relationship")
    evidence = normalize_filing_passage(_result(rec_a, rec_b), entity_id=ENTITY_ID, requested_period=_requested(2024))
    ids = [e.evidence_id for e in evidence]
    assert len(ids) == len(set(ids))