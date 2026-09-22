# filename: tests/providers/test_usaspending.py
# title: Provider Layer - USAspending Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies both USAspending providers: the fixture provider
#     (deterministic, no network) and the live provider (networked,
#     mocked via respx).
#
#     The USAspending provider is the second source. Its purpose is to
#     retrieve procurement obligations, which are never treated as
#     revenue. The provider itself only retrieves; the distinction is
#     enforced in normalization and conflict detection. But the
#     provider must return the obligation records with the correct
#     fiscal year filter, so the distinction has data to work with.
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The providers in src/veda/providers/usaspending.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The live provider posts to:
#         https://api.usaspending.gov/api/v2/search/spending_by_award/
#       with the fiscal year as a query parameter.
#     - The fixture provider looks up awards by lowercased
#       company_name, or by supported entity_id suffixes.

from __future__ import annotations

import httpx
import pytest
import respx

from veda.providers.results import ProviderRequest
from veda.providers.usaspending import (
    FixtureUSAspendingProvider,
    USAspendingProvider,
)
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
USASPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def _rp(year: int = 2024) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _request_lmt(year: int = 2024) -> ProviderRequest:
    return ProviderRequest(
        cik="0000936468",
        company_name="Lockheed Martin Corp",
        requested_period=_rp(year),
    )


def _request_unknown() -> ProviderRequest:
    return ProviderRequest(
        company_name="Nonexistent Vendor Corp",
        requested_period=_rp(),
    )


# ====================================================================
# 1. Fixture provider
# ====================================================================

def test_fixture_provider_source_type() -> None:
    p = FixtureUSAspendingProvider()
    assert p.source_type == SourceType.USASPENDING


def test_fixture_provider_is_fixture_true() -> None:
    p = FixtureUSAspendingProvider()
    assert p.is_fixture is True


def test_fixture_provider_returns_lockheed_2024_awards() -> None:
    p = FixtureUSAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) >= 1


def test_fixture_provider_award_has_obligation_amount() -> None:
    p = FixtureUSAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    record = result.raw_records[0]
    assert "total_obligated_amount" in record
    assert record["total_obligated_amount"] == 180000000


def test_fixture_provider_returns_no_awards_for_wrong_year() -> None:
    p = FixtureUSAspendingProvider()
    result = p.retrieve(_request_lmt(2023))
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_returns_not_found_for_unknown() -> None:
    p = FixtureUSAspendingProvider()
    result = p.retrieve(_request_unknown())
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_requires_company_name_or_entity_id() -> None:
    p = FixtureUSAspendingProvider()
    req = ProviderRequest(cik="0000000001", requested_period=_rp())
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_key_lowercased() -> None:
    """Lookup is case-insensitive for company_name."""
    p = FixtureUSAspendingProvider()
    req = ProviderRequest(
        company_name="LOCKHEED MARTIN CORP",
        requested_period=_rp(2024),
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.FOUND


def test_fixture_provider_metadata_includes_fiscal_year() -> None:
    p = FixtureUSAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.retrieval_metadata["fiscal_year"] == 2024


# ====================================================================
# 2. Live provider constructor
# ====================================================================

def test_live_provider_source_type() -> None:
    p = USAspendingProvider()
    assert p.source_type == SourceType.USASPENDING


def test_live_provider_is_fixture_false() -> None:
    p = USAspendingProvider()
    assert p.is_fixture is False


# ====================================================================
# 3. Live provider - HTTP responses
# ====================================================================

@respx.mock
def test_live_provider_200_with_results_returns_found() -> None:
    respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "Award ID": "USASPEND-LMT-2024-0001",
                        "Recipient Name": "LOCKHEED MARTIN CORP",
                        "Awarding Agency": "Department of Defense",
                        "Total Obligated Amount": 180000000,
                    }
                ]
            },
        )
    )
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) == 1


@respx.mock
def test_live_provider_200_with_empty_results_returns_not_found() -> None:
    respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.NOT_FOUND


@respx.mock
def test_live_provider_200_with_non_dict_returns_malformed() -> None:
    respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_200_with_non_list_results_returns_malformed() -> None:
    respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(200, json={"results": "not a list"})
    )
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_200_with_invalid_json_returns_malformed() -> None:
    respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(200, text="not json{")
    )
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_404_returns_not_found() -> None:
    respx.post(USASPENDING_URL).mock(return_value=httpx.Response(404))
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.NOT_FOUND


@respx.mock
def test_live_provider_429_returns_rate_limited() -> None:
    respx.post(USASPENDING_URL).mock(return_value=httpx.Response(429))
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.RATE_LIMITED


@respx.mock
def test_live_provider_400_returns_source_unavailable() -> None:
    respx.post(USASPENDING_URL).mock(return_value=httpx.Response(400))
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE


@respx.mock
def test_live_provider_500_retries_once() -> None:
    route = respx.post(USASPENDING_URL).mock(return_value=httpx.Response(500))
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_500_then_200_succeeds() -> None:
    route = respx.post(USASPENDING_URL)
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"results": [{"Award ID": "X"}]}),
    ]
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.FOUND


@respx.mock
def test_live_provider_timeout_retries_once() -> None:
    route = respx.post(USASPENDING_URL)
    route.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
    ]
    p = USAspendingProvider()
    result = p.retrieve(_request_lmt(2024))
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_passes_fiscal_year_as_query_param() -> None:
    route = respx.post(USASPENDING_URL).mock(
        return_value=httpx.Response(200, json={"results": [{"Award ID": "X"}]})
    )
    p = USAspendingProvider()
    p.retrieve(_request_lmt(2024))
    assert route.calls.last.request.url.params.get("fiscal_year") == "2024"