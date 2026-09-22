# filename: tests/normalization/test_sec.py
# title: Normalization Layer - SEC Company Facts Tests (CRITICAL)
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     THE SINGLE MOST IMPORTANT TEST FILE IN THE SUITE.
#
#     This file guards every SEC correctness rule the personal
#     prototype discovered against live data:
#
#       1. The "fy" label lies. SEC stamps a comparative entry with
#          the FILING's fy, not the value's year. Selection must be
#          derived from the actual end date.
#
#       2. The "fp" label lies. SEC can mark a three-month span as
#          fp="FY". A full year is 350-380 days; a quarter is not.
#
#       3. When the same value appears in multiple filings, the
#          earliest filing is the one that was actually about the
#          period. The tie-break is: unchanged value -> earliest
#          filing; changed value (restatement) -> newest filing.
#
#       4. Two XBRL tags may be used by different filers. Try
#          RevenueFromContractWithCustomerExcludingAssessedTax first,
#          then Revenues.
#
#       5. Malformed records are skipped, not raised.
#
#     If any of these tests fail, the pipeline is producing wrong
#     revenue figures, and every downstream test is suspect.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The extractor rules in src/veda/normalization/sec.py come from
#     the personal prototype's prototype/extractor.py, which found
#     these bugs against live SEC data.
#
# notes:
#     - The fixture data in providers/fixtures.py contains the exact
#       case the personal prototype discovered: FY2022 and FY2023
#       entries both labeled fy=2024 in the same filing.
#     - The tests use a small in-test payload builder rather than the
#       provider fixture, so each test can construct the exact SEC
#       shape it needs.

from __future__ import annotations

from datetime import date, datetime, timezone

from veda.normalization.sec import normalize_company_facts
from veda.providers.results import ProviderResult
from veda.shared.enums import EvidenceCategory, ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


ENTITY_ID = "entity:sec_edgar:vendor:0000936468"


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _requested(year: int = 2024) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _result(payload: dict) -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        is_fixture=False,
        raw_records=[payload],
        retrieved_at=datetime(2025, 1, 28, tzinfo=timezone.utc),
    )


def _empty_result() -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC Company Facts",
        is_fixture=False,
        error_message="not found for test",
    )


def _facts_payload(tag: str, entries: list[dict]) -> dict:
    return {
        "cik": "0000936468",
        "entityName": "LOCKHEED MARTIN CORP",
        "facts": {
            "us-gaap": {
                tag: {
                    "units": {
                        "USD": entries,
                    }
                }
            }
        },
    }


def _entry(
    start: str,
    end: str,
    val: float,
    *,
    fy: int = 2024,
    fp: str = "FY",
    form: str = "10-K",
    filed: str = "2025-01-28",
    accn: str = "0000936468-25-000009",
) -> dict:
    return {
        "start": start,
        "end": end,
        "val": val,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "accn": accn,
    }


TAG_PRIMARY = "RevenueFromContractWithCustomerExcludingAssessedTax"
TAG_LEGACY = "Revenues"


# ====================================================================
# 1. Basic success
# ====================================================================

def test_returns_one_evidence_for_valid_revenue() -> None:
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", 71043000000)])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1
    assert evidence[0].raw_value == 71043000000


def test_evidence_category_is_recognized_revenue() -> None:
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", 71043000000)])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].evidence_category == EvidenceCategory.RECOGNIZED_REVENUE


def test_evidence_has_dated_period() -> None:
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", 71043000000)])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].reporting_period.start == date(2024, 1, 1)
    assert evidence[0].reporting_period.end == date(2024, 12, 31)


def test_evidence_has_xbrl_tag() -> None:
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", 71043000000)])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].xbrl_tag == TAG_LEGACY


# ====================================================================
# 2. The fy-label bug — comparative year entries
# ====================================================================

def test_comparative_prior_years_are_excluded() -> None:
    """
    The exact bug the personal prototype found: SEC returns 2022,
    2023, and 2024 entries all labeled fy=2024 in the same filing.
    Only the entry whose end year matches the request should survive.
    """
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2022-01-01", "2022-12-31", 65984000000, fy=2024),
        _entry("2023-01-01", "2023-12-31", 67571000000, fy=2024),
        _entry("2024-01-01", "2024-12-31", 71043000000, fy=2024),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1
    assert evidence[0].raw_value == 71043000000


def test_requesting_2023_ignores_2024_entry() -> None:
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2022-01-01", "2022-12-31", 65984000000, fy=2024),
        _entry("2023-01-01", "2023-12-31", 67571000000, fy=2024),
        _entry("2024-01-01", "2024-12-31", 71043000000, fy=2024),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2023))
    assert len(evidence) == 1
    assert evidence[0].raw_value == 67571000000


# ====================================================================
# 3. The fp-label bug — quarterly entries mislabeled as FY
# ====================================================================

def test_quarterly_entry_mislabeled_fy_is_excluded() -> None:
    """
    SEC can label a Jan-Mar span as fp="FY". The period length check
    (350-380 days) must exclude it.
    """
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-03-31", 20000000000, fp="FY"),
        _entry("2024-01-01", "2024-12-31", 71043000000, fp="FY"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1
    assert evidence[0].raw_value == 71043000000


def test_only_quarterly_entry_leaves_no_evidence() -> None:
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-03-31", 20000000000, fp="FY"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


# ====================================================================
# 4. Form filter - only 10-K
# ====================================================================

def test_10q_entry_is_excluded() -> None:
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-12-31", 71043000000, form="10-Q"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_8k_entry_is_excluded() -> None:
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-12-31", 71043000000, form="8-K"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


# ====================================================================
# 5. Duplicate-filing tie-break
# ====================================================================

def test_unchanged_value_uses_earliest_filing() -> None:
    """
    The exact case the personal prototype's extractor.py handles:
    the same FY2024 revenue appears in both the FY2024 filing
    (filed 2025) and the FY2025 filing as a comparative (filed 2026).
    The earlier filing is the one actually about that period, so it
    must be selected.
    """
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-12-31", 71043000000,
               filed="2025-01-28", accn="0000936468-25-000009"),
        _entry("2024-01-01", "2024-12-31", 71043000000,
               filed="2026-01-29", accn="0000936468-26-000031"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1
    assert evidence[0].accession_number == "0000936468-25-000009"


def test_restated_value_uses_newest_filing() -> None:
    """
    When the two entries differ, the newer one is a restatement. The
    newest must be selected.
    """
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-12-31", 70000000000,
               filed="2025-01-28", accn="0000936468-25-000009"),
        _entry("2024-01-01", "2024-12-31", 71043000000,
               filed="2026-01-29", accn="0000936468-26-000031"),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1
    assert evidence[0].raw_value == 71043000000
    assert evidence[0].accession_number == "0000936468-26-000031"


# ====================================================================
# 6. Multi-tag fallback
# ====================================================================

def test_legacy_revenues_tag_used_when_primary_missing() -> None:
    payload = _facts_payload(TAG_LEGACY, [
        _entry("2024-01-01", "2024-12-31", 71043000000),
    ])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].xbrl_tag == TAG_LEGACY


def test_primary_tag_used_when_both_present() -> None:
    payload = {
        "cik": "0000936468",
        "facts": {
            "us-gaap": {
                TAG_PRIMARY: {
                    "units": {
                        "USD": [_entry("2024-01-01", "2024-12-31", 71043000000)],
                    }
                },
                TAG_LEGACY: {
                    "units": {
                        "USD": [_entry("2024-01-01", "2024-12-31", 99999999999)],
                    }
                },
            }
        },
    }
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].xbrl_tag == TAG_PRIMARY
    assert evidence[0].raw_value == 71043000000


def test_primary_tag_missing_falls_back_to_legacy() -> None:
    payload = {
        "cik": "0000936468",
        "facts": {
            "us-gaap": {
                TAG_PRIMARY: {"units": {"USD": []}},
                TAG_LEGACY: {
                    "units": {
                        "USD": [_entry("2024-01-01", "2024-12-31", 71043000000)],
                    }
                },
            }
        },
    }
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence[0].xbrl_tag == TAG_LEGACY


# ====================================================================
# 7. Malformed records are skipped
# ====================================================================

def test_entry_without_start_is_skipped() -> None:
    entry = _entry("2024-01-01", "2024-12-31", 71043000000)
    del entry["start"]
    payload = _facts_payload(TAG_LEGACY, [entry])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_entry_without_end_is_skipped() -> None:
    entry = _entry("2024-01-01", "2024-12-31", 71043000000)
    del entry["end"]
    payload = _facts_payload(TAG_LEGACY, [entry])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_entry_with_bool_value_is_skipped() -> None:
    """A bool is a subclass of int; the code must exclude it explicitly."""
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", True)])   # type: ignore[arg-type]
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_entry_with_string_value_is_skipped() -> None:
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", "abc")])   # type: ignore[arg-type]
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_malformed_entry_does_not_break_valid_entry() -> None:
    bad = _entry("2024-01-01", "2024-12-31", 71043000000)
    del bad["start"]
    good = _entry("2024-01-01", "2024-12-31", 71043000000)
    payload = _facts_payload(TAG_LEGACY, [bad, good])
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert len(evidence) == 1


# ====================================================================
# 8. Provider failure handling
# ====================================================================

def test_not_found_result_returns_empty() -> None:
    evidence = normalize_company_facts(_empty_result(), entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_wrong_source_type_returns_empty() -> None:
    result = ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.USASPENDING,
        source_name="USAspending",
        is_fixture=False,
        raw_records=[{"foo": "bar"}],
    )
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_facts_key_returns_empty() -> None:
    payload = {"cik": "0000936468"}   # no facts
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


def test_missing_us_gaap_returns_empty() -> None:
    payload = {"cik": "0000936468", "facts": {}}
    result = _result(payload)
    evidence = normalize_company_facts(result, entity_id=ENTITY_ID, requested_period=_requested(2024))
    assert evidence == []


# ====================================================================
# 9. Caller input validation
# ====================================================================

def test_invalid_entity_id_raises() -> None:
    import pytest
    payload = _facts_payload(TAG_LEGACY, [_entry("2024-01-01", "2024-12-31", 71043000000)])
    result = _result(payload)
    with pytest.raises(ValueError):
        normalize_company_facts(result, entity_id="not an entity id", requested_period=_requested(2024))