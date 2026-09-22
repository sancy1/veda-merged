# filename: tests/interfaces/test_bundle_builder.py
# title: Interface Layer - Bundle Builder Tests
# layer: Test suite - interfaces
# status: Phase 7 — Sub-phase 7B
# description:
#     Verifies build_bundle, build_resolver, and build_extractor.
#     Proves fixture-only provider mode, correct resolver
#     construction, and composite rejection at the config boundary.

from __future__ import annotations

import pytest

from veda.entity.resolver import (
    FixtureEntityResolverSource,
    LiveEntityResolverSource,
)
from veda.interfaces.bundle_builder import (
    build_bundle,
    build_extractor,
    build_resolver,
)
from veda.interfaces.config import InterfaceConfig
from veda.interfaces.errors import InterfaceConfigError
from veda.pipeline.claim_extraction import RuleBasedClaimExtractor
from veda.pipeline.orchestrator import ProviderBundle
from veda.providers.annual_reports import FixtureAnnualReportProvider
from veda.providers.sec_company_facts import FixtureSECCompanyFactsProvider
from veda.providers.sec_filings import FixtureSECFilingsProvider
from veda.providers.usaspending import FixtureUSAspendingProvider


def _config(**overrides) -> InterfaceConfig:
    base = {"user_agent": "Test test@example.com"}
    base.update(overrides)
    return InterfaceConfig(**base)


def test_fixture_bundle_returns_provider_bundle() -> None:
    b = build_bundle(_config())
    assert isinstance(b, ProviderBundle)


def test_fixture_bundle_uses_fixture_company_facts() -> None:
    b = build_bundle(_config())
    assert isinstance(b.sec_company_facts, FixtureSECCompanyFactsProvider)


def test_fixture_bundle_uses_fixture_sec_filings() -> None:
    b = build_bundle(_config())
    assert isinstance(b.sec_filing, FixtureSECFilingsProvider)


def test_fixture_bundle_uses_fixture_usaspending() -> None:
    b = build_bundle(_config())
    assert isinstance(b.usaspending, FixtureUSAspendingProvider)


def test_fixture_bundle_uses_fixture_annual_reports() -> None:
    b = build_bundle(_config())
    assert isinstance(b.annual_report, FixtureAnnualReportProvider)


def test_sec_filing_metadata_flows_through() -> None:
    c = _config(
        sec_filing_accession_number="0000936468-25-000009",
        sec_filing_form="10-K",
        sec_filing_passage_hint="revenues",
    )
    b = build_bundle(c)
    assert b.sec_filing_accession_number == "0000936468-25-000009"
    assert b.sec_filing_form == "10-K"
    assert b.sec_filing_passage_hint == "revenues"


def test_fixture_resolver_returns_fixture_source() -> None:
    r = build_resolver(_config())
    assert isinstance(r, FixtureEntityResolverSource)


def test_live_provider_mode_constructs_live_providers() -> None:
    from veda.providers.sec_company_facts import SECCompanyFactsProvider
    from veda.providers.sec_filings import SECFilingsProvider
    from veda.providers.usaspending import USAspendingProvider

    c = _config(provider_mode="live")
    b = build_bundle(c)
    assert isinstance(b.sec_company_facts, SECCompanyFactsProvider)
    assert isinstance(b.sec_filing, SECFilingsProvider)
    assert isinstance(b.usaspending, USAspendingProvider)
    assert isinstance(b.annual_report, FixtureAnnualReportProvider)


def test_live_resolver_returns_live_source() -> None:
    r = build_resolver(_config(resolver_mode="live"))
    assert isinstance(r, LiveEntityResolverSource)


def test_rule_based_extractor_constructed() -> None:
    e = build_extractor(_config())
    assert isinstance(e, RuleBasedClaimExtractor)


def test_composite_extractor_rejected() -> None:
    c = _config(extractor_mode="composite")
    with pytest.raises(InterfaceConfigError) as exc_info:
        build_extractor(c)
    assert "reserved for a later phase" in str(exc_info.value)


def test_composite_error_is_interface_config_error() -> None:
    c = _config(extractor_mode="composite")
    with pytest.raises(InterfaceConfigError):
        build_extractor(c)