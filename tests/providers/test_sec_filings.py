# filename: tests/providers/test_sec_filings.py
# title: Provider Layer - SEC Filings Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies both SEC Filings providers: the fixture provider
#     (deterministic, no network) and the live provider (networked,
#     mocked via respx).
#
#     The SEC Filings provider is different from SEC Company Facts:
#     it requires a specific filing to be identified by accession
#     number, form, and passage hint. Without any of those, it
#     returns NOT_FOUND immediately.
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The providers in src/veda/providers/sec_filings.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The URL template is:
#         https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accn_no_dashes}/{accn}-index.htm
#       where cik_no_zeros strips leading zeros and accn_no_dashes
#       removes the dashes from the accession number.

from __future__ import annotations

import httpx
import pytest
import respx

from veda.providers.results import ProviderRequest
from veda.providers.sec_filings import (
    FixtureSECFilingsProvider,
    SECFilingsProvider,
)
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
LOCKHEED_CIK = "0000936468"
LOCKHEED_ACCN = "0000936468-25-000009"
LOCKHEED_FORM = "10-K"
LOCKHEED_HINT = "revenues"


def _rp() -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=2024, raw="2024")


def _request_full() -> ProviderRequest:
    return ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="Lockheed Martin Corp",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint=LOCKHEED_HINT,
    )


def _url() -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        "936468/000093646825000009/0000936468-25-000009-index.htm"
    )


# ====================================================================
# 1. Fixture provider
# ====================================================================

def test_fixture_provider_source_type() -> None:
    p = FixtureSECFilingsProvider()
    assert p.source_type == SourceType.SEC_FILING


def test_fixture_provider_is_fixture_true() -> None:
    p = FixtureSECFilingsProvider()
    assert p.is_fixture is True


def test_fixture_provider_returns_passage() -> None:
    p = FixtureSECFilingsProvider()
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) == 1
    assert "text" in result.raw_records[0]


def test_fixture_provider_missing_cik_returns_not_found() -> None:
    p = FixtureSECFilingsProvider()
    req = ProviderRequest(
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint=LOCKHEED_HINT,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_missing_accession_returns_not_found() -> None:
    p = FixtureSECFilingsProvider()
    req = ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="X",
        requested_period=_rp(),
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint=LOCKHEED_HINT,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_missing_form_returns_not_found() -> None:
    p = FixtureSECFilingsProvider()
    req = ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        field_or_passage_hint=LOCKHEED_HINT,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_missing_hint_returns_not_found() -> None:
    p = FixtureSECFilingsProvider()
    req = ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_fixture_provider_unknown_passage_returns_not_found() -> None:
    p = FixtureSECFilingsProvider()
    req = ProviderRequest(
        cik=LOCKHEED_CIK,
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint="nonexistent_passage",
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


# ====================================================================
# 2. Live provider constructor
# ====================================================================

def test_live_provider_requires_user_agent() -> None:
    with pytest.raises(ValueError):
        SECFilingsProvider(user_agent="")


def test_live_provider_source_type() -> None:
    p = SECFilingsProvider(user_agent="Test test@example.com")
    assert p.source_type == SourceType.SEC_FILING


def test_live_provider_is_fixture_false() -> None:
    p = SECFilingsProvider(user_agent="Test test@example.com")
    assert p.is_fixture is False


# ====================================================================
# 3. Live provider - missing identifiers
# ====================================================================

def test_live_provider_missing_cik_returns_not_found() -> None:
    p = SECFilingsProvider(user_agent="Test test@example.com")
    req = ProviderRequest(
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint=LOCKHEED_HINT,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_live_provider_invalid_cik_returns_not_found() -> None:
    p = SECFilingsProvider(user_agent="Test test@example.com")
    req = ProviderRequest(
        cik="abc",
        company_name="X",
        requested_period=_rp(),
        accession_number=LOCKHEED_ACCN,
        filing_form=LOCKHEED_FORM,
        field_or_passage_hint=LOCKHEED_HINT,
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


# ====================================================================
# 4. Live provider - HTTP responses
# ====================================================================

@respx.mock
def test_live_provider_200_returns_found() -> None:
    respx.get(_url()).mock(
        return_value=httpx.Response(200, text="<html>filing body</html>")
    )
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.FOUND
    assert "text" in result.raw_records[0]
    assert "filing body" in result.raw_records[0]["text"]


@respx.mock
def test_live_provider_empty_body_returns_malformed_response() -> None:
    respx.get(_url()).mock(return_value=httpx.Response(200, text=""))
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.MALFORMED_RESPONSE


@respx.mock
def test_live_provider_404_returns_not_found() -> None:
    respx.get(_url()).mock(return_value=httpx.Response(404))
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.NOT_FOUND


@respx.mock
def test_live_provider_404_not_retried() -> None:
    route = respx.get(_url()).mock(return_value=httpx.Response(404))
    p = SECFilingsProvider(user_agent="Test test@example.com")
    p.retrieve(_request_full())
    assert route.call_count == 1


@respx.mock
def test_live_provider_429_returns_rate_limited() -> None:
    respx.get(_url()).mock(return_value=httpx.Response(429))
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.RATE_LIMITED


@respx.mock
def test_live_provider_500_retries_once() -> None:
    route = respx.get(_url()).mock(return_value=httpx.Response(500))
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_500_then_200_succeeds() -> None:
    route = respx.get(_url())
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, text="<html>filing body</html>"),
    ]
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.FOUND


@respx.mock
def test_live_provider_timeout_retries_once() -> None:
    route = respx.get(_url())
    route.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
    ]
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.status == ProviderStatus.SOURCE_UNAVAILABLE
    assert route.call_count == 2


@respx.mock
def test_live_provider_record_contains_accession() -> None:
    respx.get(_url()).mock(
        return_value=httpx.Response(200, text="<html>filing body</html>")
    )
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.raw_records[0]["accession_number"] == LOCKHEED_ACCN


@respx.mock
def test_live_provider_record_contains_form() -> None:
    respx.get(_url()).mock(
        return_value=httpx.Response(200, text="<html>filing body</html>")
    )
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert result.raw_records[0]["filing_form"] == LOCKHEED_FORM


@respx.mock
def test_live_provider_record_contains_url() -> None:
    respx.get(_url()).mock(
        return_value=httpx.Response(200, text="<html>filing body</html>")
    )
    p = SECFilingsProvider(user_agent="Test test@example.com")
    result = p.retrieve(_request_full())
    assert "url" in result.raw_records[0]