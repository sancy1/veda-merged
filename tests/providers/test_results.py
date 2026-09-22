# filename: tests/providers/test_results.py
# title: Provider Layer - ProviderRequest and ProviderResult Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies the typed request and result models crossing the
#     provider boundary. ProviderResult enforces strict invariants on
#     its five status values so a provider cannot silently report a
#     FOUND with no records, or a SOURCE_UNAVAILABLE with no error
#     message, or any other mixed state.
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The models in src/veda/providers/results.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - ProviderRequest requires at least one non-blank lookup key
#       (entity_id, cik, or company_name).
#     - ProviderResult's validator groups the five statuses into three
#       buckets:
#         FOUND                        -> raw_records required, no error
#         NOT_FOUND                    -> raw_records empty, error optional
#         SOURCE_UNAVAILABLE/RATE_LIMITED/MALFORMED_RESPONSE
#                                      -> raw_records empty, error required

from __future__ import annotations

import pytest
from pydantic import ValidationError

from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _rp() -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=2024, raw="2024")


# ====================================================================
# 1. ProviderRequest
# ====================================================================

def test_request_with_company_name_only() -> None:
    req = ProviderRequest(company_name="Lockheed Martin Corp", requested_period=_rp())
    assert req.company_name == "Lockheed Martin Corp"


def test_request_with_cik_only() -> None:
    req = ProviderRequest(cik="0000936468", requested_period=_rp())
    assert req.cik == "0000936468"


def test_request_with_entity_id_only() -> None:
    req = ProviderRequest(entity_id="entity:sec_edgar:vendor:0000936468", requested_period=_rp())
    assert req.entity_id == "entity:sec_edgar:vendor:0000936468"


def test_request_rejects_no_lookup_key() -> None:
    """All three lookup keys are empty -> the model must reject."""
    with pytest.raises(ValidationError):
        ProviderRequest(requested_period=_rp())


def test_request_rejects_blank_lookup_keys_only() -> None:
    """Whitespace-only values are treated as blank."""
    with pytest.raises(ValidationError):
        ProviderRequest(company_name="   ", requested_period=_rp())


def test_request_requires_requested_period() -> None:
    with pytest.raises(ValidationError):
        ProviderRequest(company_name="Lockheed Martin Corp")   # type: ignore[call-arg]


def test_request_optional_sec_fields_default_to_none() -> None:
    req = ProviderRequest(company_name="Lockheed Martin Corp", requested_period=_rp())
    assert req.field_or_passage_hint is None
    assert req.accession_number is None
    assert req.filing_form is None


def test_request_accepts_all_optional_sec_fields() -> None:
    req = ProviderRequest(
        cik="0000936468",
        company_name="Lockheed Martin Corp",
        requested_period=_rp(),
        field_or_passage_hint="revenues",
        accession_number="0000936468-25-000009",
        filing_form="10-K",
    )
    assert req.accession_number == "0000936468-25-000009"
    assert req.filing_form == "10-K"


# ====================================================================
# 2. ProviderResult - FOUND
# ====================================================================

def test_result_found_requires_records() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.FOUND,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
            raw_records=[],
        )


def test_result_found_with_records_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
        raw_records=[{"data": "value"}],
    )
    assert r.status == ProviderStatus.FOUND


def test_result_found_rejects_error_message() -> None:
    """FOUND cannot carry an error message; if there is data, no error."""
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.FOUND,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
            raw_records=[{"data": "value"}],
            error_message="should not be here",
        )


# ====================================================================
# 3. ProviderResult - NOT_FOUND
# ====================================================================

def test_result_not_found_requires_no_records() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.NOT_FOUND,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
            raw_records=[{"data": "value"}],
        )


def test_result_not_found_without_error_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
    )
    assert r.status == ProviderStatus.NOT_FOUND
    assert r.error_message is None


def test_result_not_found_with_error_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
        error_message="No SEC data for CIK",
    )
    assert r.error_message == "No SEC data for CIK"


def test_result_not_found_rejects_blank_error_message() -> None:
    """NOT_FOUND with only whitespace as error_message is rejected."""
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.NOT_FOUND,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
            error_message="   ",
        )


# ====================================================================
# 4. ProviderResult - error statuses require non-empty error
# ====================================================================

def test_result_source_unavailable_requires_error() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.SOURCE_UNAVAILABLE,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
        )


def test_result_source_unavailable_with_error_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.SOURCE_UNAVAILABLE,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
        error_message="SEC returned HTTP 500",
    )
    assert r.status == ProviderStatus.SOURCE_UNAVAILABLE


def test_result_rate_limited_requires_error() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.RATE_LIMITED,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
        )


def test_result_rate_limited_with_error_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.RATE_LIMITED,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
        error_message="SEC rate limit (429)",
    )
    assert r.status == ProviderStatus.RATE_LIMITED


def test_result_malformed_response_requires_error() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.MALFORMED_RESPONSE,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
        )


def test_result_malformed_response_with_error_succeeds() -> None:
    r = ProviderResult(
        status=ProviderStatus.MALFORMED_RESPONSE,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
        error_message="Response was not valid JSON",
    )
    assert r.status == ProviderStatus.MALFORMED_RESPONSE


# ====================================================================
# 5. ProviderResult - error statuses reject raw_records
# ====================================================================

def test_result_source_unavailable_rejects_records() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            status=ProviderStatus.SOURCE_UNAVAILABLE,
            source_type=SourceType.SEC_COMPANY_FACTS,
            source_name="SEC",
            is_fixture=False,
            raw_records=[{"data": "value"}],
            error_message="Server error",
        )


# ====================================================================
# 6. Defaults
# ====================================================================

def test_result_default_raw_records_is_empty() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
    )
    assert r.raw_records == []


def test_result_default_error_message_is_none() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
    )
    assert r.error_message is None


def test_result_default_metadata_is_empty_dict() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
    )
    assert r.retrieval_metadata == {}


def test_result_retrieved_at_is_set_automatically() -> None:
    r = ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="SEC",
        is_fixture=False,
    )
    assert r.retrieved_at is not None