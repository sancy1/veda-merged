# filename: src/veda/interfaces/bundle_builder.py
# title: Bundle Builder
# layer: Interface layer
# status: Phase 7 — Sub-phase 7B
# description:
#     Constructs the objects the pipeline needs from one
#     InterfaceConfig:
#
#         build_bundle(config)           -> ProviderBundle
#         build_resolver(config)         -> EntityResolverSource
#         build_extractor(config)        -> ClaimExtractor
#
#     Phase 7 accepts only fixture-backed providers. Live provider
#     mode is reserved for a later phase; requesting it raises
#     InterfaceConfigError.
#
#     Extractor mode "rule_based" is constructed. Extractor mode
#     "composite" is rejected at this boundary because the composite
#     would contain the disabled LLM stub, which cannot produce a
#     claim. The rejection is a config error, not a
#     NotImplementedError from inside the pipeline.
#
#     The bundle builder imports:
#         - the four fixture providers
#         - the two resolver sources
#         - RuleBasedClaimExtractor
#         - the interface error classes
#
#     It does NOT import:
#         - any live provider (SEC, USAspending)
#         - LLMClaimExtractor
#         - CompositeClaimExtractor
#         - any model SDK
#
#     This keeps the default path free of network dependencies and
#     free of any reference to an LLM.

from __future__ import annotations

from veda.entity.resolver import (
    EntityResolverSource,
    FixtureEntityResolverSource,
    LiveEntityResolverSource,
)
from veda.interfaces.config import InterfaceConfig
from veda.interfaces.errors import InterfaceConfigError
from veda.pipeline.claim_extraction import RuleBasedClaimExtractor
from veda.pipeline.extraction_protocol import ClaimExtractor
from veda.pipeline.orchestrator import ProviderBundle
from veda.providers.annual_reports import FixtureAnnualReportProvider
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


# --------------------------------------------------------------------
# Demo resolver registry
# --------------------------------------------------------------------
# The fixture resolver needs entries. This registry supplies a small
# deterministic set that matches the provider fixtures: Lockheed
# Martin, Apple, and Example Vendor Holdings.
#
# This is interface-layer data, not shared-contract data. It is used
# only when resolver_mode="fixture".
_FIXTURE_RESOLVER_ENTRIES: dict[str, list[dict]] = {
    "lockheed martin corp": [
        {"cik": 936468, "ticker": "LMT", "title": "LOCKHEED MARTIN CORP"},
    ],
    "lockheed martin": [
        {"cik": 936468, "ticker": "LMT", "title": "LOCKHEED MARTIN CORP"},
    ],
    "apple inc.": [
        {"cik": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    ],
    "example vendor holdings, inc.": [
        {"cik": 8888888, "ticker": None, "title": "Example Vendor Holdings, Inc."},
    ],
}


def build_bundle(config: InterfaceConfig) -> ProviderBundle:
    """
    Construct a ProviderBundle from the configuration.

    Phase 7 accepts only provider_mode="fixture". Every provider is
    fixture-backed. No network calls are made.

    Raises
    ------
    InterfaceConfigError
        If provider_mode is not "fixture".
    """
    if config.provider_mode == "fixture":
        return ProviderBundle(
            sec_company_facts=FixtureSECCompanyFactsProvider(),
            sec_filing=FixtureSECFilingsProvider(),
            usaspending=FixtureUSAspendingProvider(),
            annual_report=FixtureAnnualReportProvider(),
            sec_filing_accession_number=config.sec_filing_accession_number,
            sec_filing_form=config.sec_filing_form,
            sec_filing_passage_hint=config.sec_filing_passage_hint,
        )

    if config.provider_mode == "live":
        if not config.user_agent or not config.user_agent.strip():
            raise InterfaceConfigError(
                "Live provider mode requires a SEC User-Agent of the form "
                "'Name email@example.com'. Provide one in the dashboard's "
                "User-Agent field, or set the SEC_API_USER_AGENT environment "
                "variable on the server."
            )
        try:
            sec_facts = SECCompanyFactsProvider(config.user_agent)
            sec_filings = SECFilingsProvider(config.user_agent)
        except ValueError as exc:
            raise InterfaceConfigError(str(exc))
        return ProviderBundle(
            sec_company_facts=sec_facts,
            sec_filing=sec_filings,
            usaspending=USAspendingProvider(),
            annual_report=FixtureAnnualReportProvider(),
            sec_filing_accession_number=config.sec_filing_accession_number,
            sec_filing_form=config.sec_filing_form,
            sec_filing_passage_hint=config.sec_filing_passage_hint,
        )

    raise InterfaceConfigError(
        f"Unsupported provider_mode: {config.provider_mode!r}"
    )


def build_resolver(config: InterfaceConfig) -> EntityResolverSource:
    """
    Construct an EntityResolverSource from the configuration.

    resolver_mode="fixture" -> FixtureEntityResolverSource with the
                               demo registry.
    resolver_mode="live"    -> LiveEntityResolverSource(user_agent).
                               The live source is not called during
                               Phase 7's default runs; it is
                               constructed only when the caller
                               explicitly requests it.
    """
    if config.resolver_mode == "fixture":
        return FixtureEntityResolverSource(_FIXTURE_RESOLVER_ENTRIES)

    if config.resolver_mode == "live":
        return LiveEntityResolverSource(user_agent=config.user_agent)

    # Unreachable — the Literal type prevents other values.
    raise InterfaceConfigError(
        f"Unsupported resolver_mode: {config.resolver_mode!r}"
    )


def build_extractor(config: InterfaceConfig) -> ClaimExtractor:
    """
    Construct a ClaimExtractor from the configuration.

    extractor_mode="rule_based" -> RuleBasedClaimExtractor.

    extractor_mode="composite"  -> rejected at this boundary. A
                                    composite in Phase 7 would
                                    contain the disabled LLM stub,
                                    whose extract() raises
                                    NotImplementedError. The
                                    caller sees a config error
                                    here, before the pipeline runs.
    """
    if config.extractor_mode == "rule_based":
        return RuleBasedClaimExtractor()

    if config.extractor_mode == "composite":
        raise InterfaceConfigError(
            "Composite extraction requires a live LLM adapter, "
            "which is reserved for a later phase. This "
            "configuration is not available."
        )

    # Unreachable — the Literal type prevents other values.
    raise InterfaceConfigError(
        f"Unsupported extractor_mode: {config.extractor_mode!r}"
    )


__all__ = [
    "build_bundle",
    "build_resolver",
    "build_extractor",
]