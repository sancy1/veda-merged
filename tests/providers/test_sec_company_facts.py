# filename: tests/providers/test_sec_company_facts.py
# title: Provider Layer - SEC Company Facts Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies both SEC Company Facts providers: the fixture provider
#     (deterministic, no network) and the live provider (networked,
#     mocked via respx).
#
#     The live provider is the only source the pipeline reads through
#     live in production. It must:
#       - require a non-empty user agent
#       - normalize CIK to 10 digits
#       - retry once on timeout and 5xx
#       - return NOT_FOUND on 404 without retry
#       - return RATE_LIMITED on 429 without retry
#       - return SOURCE_UNAVAILABLE on other 4xx
#       - return MALFORMED_RESPONSE on non-JSON 200
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The providers in src/veda/providers/sec_company_facts.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The URL is https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
#       where {cik} is zero-padded to 10 digits.

from __future__ import annotations

import httpx
import pytest
import respx

from veda.providers.results import ProviderRequest
from veda.providers.sec_company_facts import (
    FixtureSECCompanyFactsProvider,
    SECCompanyFactsProvider,
)
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
LOCKHEED_CIK = "0000936468"


def _rp() -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=2024, raw="2024")


def _request_lmt() -> ProviderRequest:
    return ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="Lockheed Martin Corp",
        requested_period=_rp(),
    )


def _request_unknown() -> ProviderRequest:
    return ProviderRequest(
        cik="0000000001",
        company_name="Nonexistent Corp",
        requested_period=_rp(),
    )


def _url(cik: str) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


# ====================================================================
# 1. Fixture provider
# ====================================================================

def test_fixture_provider_source_type() -> None:
    p = FixtureSECCompanyFactsProvider()
    assert p.source_type == SourceType.SEC_COMPANY_FACTS


def test_fixture_provider_is_fixture_true() -> None:
    p = FixtureSECCompanyFactsProvider()
    assert p.is_fixture is True


def test_fixture_provider_lookup_lockheed() -> None:
    p = FixtureSECCompanyFactsProvider()
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) == 1


def test_fixture_provider_lookup_unknown_returns_not_found() -> None:
    p = FixtureSECCompanyFactsProvider()
    result = p.retrieve(_request_unknown())
    assert result.status == ProviderStatus.NOT_FOUND
    assert result.raw_records == []


def test_fixture_provider_invalid_cik_returns_not_found() -> None:
    p = FixtureSECCompanyFactsProvider()
    req = ProviderRequest(cik="abc", company_name="X", requested_period=_rp())
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_normalizes_cik() -> None:
    """A bare integer CIK is padded to 10 digits before lookup."""
    p = FixtureSECCompanyFactsProvider()
    req = ProviderRequest(cik="936468", company_name="X", requested_period=_rp())
    result = p.retrieve(req)
    assert result.status == ProviderStatus.FOUND


# ====================================================================
# 2. Live provider constructor
# ====================================================================

def test_live_provider_requires_user_agent() -> None:
    with pytest.raises(ValueError):
        SECCompanyFactsProvider(user_agent="")


def test_live_provider_rejects_whitespace_user_agent() -> None:
    with pytest.raises(ValueError):
        SECCompanyFactsProvider(user_agent="   ")


def test_live_provider_source_type() -> None:
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    assert p.source_type == SourceType.SEC_COMPANY_FACTS


def test_live_provider_is_fixture_false() -> None:
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    assert p.is_fixture is False


def test_live_provider_invalid_cik_returns_not_found() -> None:
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    req = ProviderRequest(cik="abc", company_name="X", requested_period=_rp())
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


# ====================================================================
# 3. Live provider - HTTP responses
# ====================================================================

@respx.mock
def test_live_provider_200_returns_found() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(
        return_value=httpx.Response(200, json={"cik": "0000936468", "facts": {}})
    )
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) == 1


@respx.mock
def test_live_provider_404_returns_not_found() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(404))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.NOT_FOUND


@respx.mock
def test_live_provider_404_is_not_retried() -> None:
    """404 is not transient; the provider must not retry."""
    route = respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(404))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    p.retrieve(_request_lmt())
    assert route.call_count == 1


@respx.mock
def test_live_provider_429_returns_rate_limited() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(429))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.RATE_LIMITED


@respx.mock
def test_live_provider_429_is_not_retried() -> None:
    route = respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(429))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    p.retrieve(_request_lmt())
    assert route.call_count == 1


@respx.mock
def test_live_provider_400_returns_source_unavailable() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(400))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE


@respx.mock
def test_live_provider_500_retries_once() -> None:
    """5xx is transient; the provider must retry once."""
    route = respx.get(_url(LOCKHEED_CIK)).mock(return_value=httpx.Response(500))
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_500_then_200_succeeds() -> None:
    route = respx.get(_url(LOCKHEED_CIK))
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"cik": "0000936468", "facts": {}}),
    ]
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.FOUND
    assert route.call_count == 2


@respx.mock
def test_live_provider_timeout_retries_once() -> None:
    route = respx.get(_url(LOCKHEED_CIK))
    route.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
    ]
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_timeout_then_200_succeeds() -> None:
    route = respx.get(_url(LOCKHEED_CIK))
    route.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.Response(200, json={"cik": "0000936468", "facts": {}}),
    ]
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.FOUND


@respx.mock
def test_live_provider_malformed_json_returns_malformed_response() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(
        return_value=httpx.Response(200, text="not json{")
    )
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_json_non_dict_returns_malformed_response() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_metadata_includes_url() -> None:
    respx.get(_url(LOCKHEED_CIK)).mock(
        return_value=httpx.Response(200, json={"cik": "0000936468", "facts": {}})
    )
    p = SECCompanyFactsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_lmt())
    assert "url" in result.retrieval_metadata