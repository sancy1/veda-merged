"""
File: src/veda/providers/__init__.py
Title: Providers Package
Layer: Provider retrieval layer
Status: Merged prototype foundation — Phase 4

Purpose
-------
Exports the provider contract, request/result models, and all concrete
live and fixture-backed providers.

Public API
----------
EvidenceProvider
ProviderRequest
ProviderResult
SECCompanyFactsProvider
FixtureSECCompanyFactsProvider
SECFilingsProvider
FixtureSECFilingsProvider
USAspendingProvider
FixtureUSAspendingProvider
FixtureAnnualReportProvider

Import policy
-------------
This package exports provider classes only. Fixture data remains in
veda.providers.fixtures and is not re-exported.
"""

from veda.providers.base import EvidenceProvider
from veda.providers.results import ProviderRequest, ProviderResult
from veda.providers.sec_company_facts import (
    FixtureSECCompanyFactsProvider,
    SECCompanyFactsProvider,
)
from veda.providers.sec_filings import (
    FixtureSECFilingsProvider,
    SECFilingsProvider,
)
from veda.providers.usaspending import (
    FixtureUSAspendingProvider,
    USAspendingProvider,
)
from veda.providers.annual_reports import FixtureAnnualReportProvider

__all__ = [
    "EvidenceProvider",
    "ProviderRequest",
    "ProviderResult",
    "SECCompanyFactsProvider",
    "FixtureSECCompanyFactsProvider",
    "SECFilingsProvider",
    "FixtureSECFilingsProvider",
    "USAspendingProvider",
    "FixtureUSAspendingProvider",
    "FixtureAnnualReportProvider",
]
