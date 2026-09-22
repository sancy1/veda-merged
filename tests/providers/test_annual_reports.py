# filename: tests/providers/test_annual_reports.py
# title: Provider Layer - Annual Reports Fixture Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies the Annual Report fixture provider. There is no live
#     annual report provider; this layer is fixture-only by design.
#     Annual reports are the secondary revenue source that produces
#     the reference conflict case (SEC revenue vs annual-report
#     revenue).
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The provider in src/veda/providers/annual_reports.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - Lookup is by lowercased company_name, or by the specific
#       entity_id suffix :0008888888 (Example Vendor Holdings).
#     - The provider filters records by fiscal_year.

from __future__ import annotations

import pytest

from veda.providers.annual_reports import FixtureAnnualReportProvider
from veda.providers.results import ProviderRequest
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _rp(year: int = 2025) -> RequestedPeriod:
    return RequestedPeriod(fiscal_year=year, raw=str(year))


def _request_example(year: int = 2025) -> ProviderRequest:
    return ProviderRequest(
        company_name="Example Vendor Holdings, Inc.",
        requested_period=_rp(year),
    )


# ====================================================================
# 1. Provider metadata
# ====================================================================

def test_provider_source_type() -> None:
    p = FixtureAnnualReportProvider()
    assert p.source_type == SourceType.ANNUAL_REPORT


def test_provider_is_fixture_true() -> None:
    p = FixtureAnnualReportProvider()
    assert p.is_fixture is True


def test_provider_source_name_includes_fixture() -> None:
    p = FixtureAnnualReportProvider()
    assert "fixture" in p.source_name.lower()


# ====================================================================
# 2. Lookup by company name
# ====================================================================

def test_lookup_returns_passages() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert result.status == ProviderStatus.FOUND
    assert len(result.raw_records) >= 1


def test_passage_has_text() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert "text" in result.raw_records[0]
    assert result.raw_records[0]["text"]


def test_passage_has_source_name() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert "source_name" in result.raw_records[0]


def test_passage_has_source_url() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert "source_url" in result.raw_records[0]


def test_passage_has_fiscal_year() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert result.raw_records[0]["fiscal_year"] == 2025


def test_lookup_case_insensitive() -> None:
    p = FixtureAnnualReportProvider()
    req = ProviderRequest(
        company_name="EXAMPLE VENDOR HOLDINGS, INC.",
        requested_period=_rp(2025),
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.FOUND


# ====================================================================
# 3. Lookup by entity_id suffix
# ====================================================================

def test_lookup_by_entity_id_suffix() -> None:
    p = FixtureAnnualReportProvider()
    req = ProviderRequest(
        entity_id="entity:sec_edgar:vendor:0008888888",
        requested_period=_rp(2025),
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.FOUND


# ====================================================================
# 4. Filters by fiscal year
# ====================================================================

def test_wrong_fiscal_year_returns_not_found() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2020))
    assert result.status == ProviderStatus.NOT_FOUND


def test_missing_fiscal_year_returns_not_found() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2099))
    assert result.status == ProviderStatus.NOT_FOUND


# ====================================================================
# 5. Unknown company returns NOT_FOUND
# ====================================================================

def test_unknown_company_returns_not_found() -> None:
    p = FixtureAnnualReportProvider()
    req = ProviderRequest(
        company_name="Nonexistent Vendor",
        requested_period=_rp(2025),
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


def test_no_company_name_returns_not_found() -> None:
    p = FixtureAnnualReportProvider()
    req = ProviderRequest(
        cik="0009999999",
        requested_period=_rp(2025),
    )
    result = p.retrieve(req)
    assert result.status == ProviderStatus.NOT_FOUND


# ====================================================================
# 6. Metadata
# ====================================================================

def test_metadata_includes_fiscal_year() -> None:
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2025))
    assert result.retrieval_metadata["fiscal_year"] == 2025


# ====================================================================
# 7. Only one fixture exists; empty for other years
# ====================================================================

def test_returns_empty_for_year_without_fixture() -> None:
    """The fixture only has one year of data; other years are empty."""
    p = FixtureAnnualReportProvider()
    result = p.retrieve(_request_example(2023))
    assert result.status == ProviderStatus.NOT_FOUND
    assert result.raw_records == []