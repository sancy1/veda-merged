# filename: tests/providers/test_base.py
# title: Provider Layer - EvidenceProvider ABC Conformance Tests
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Verifies the EvidenceProvider abstract base class enforces its
#     four abstract members: source_type, source_name, is_fixture,
#     and retrieve.
#
#     The ABC is a contract. If it silently permits a subclass missing
#     a member, a malformed provider could enter the pipeline and the
#     orchestrator would fail with an AttributeError at runtime,
#     deep in a stage that is hard to diagnose.
#
#     The tests here construct incomplete subclasses and assert the
#     ABC rejects them at instantiation.
#
# source:
#     AUTHORED - Phase 4 had no saved test before recovery began.
#     The ABC in src/veda/providers/base.py is the specification;
#     this file is the executable form of that spec.
#
# notes:
#     - The four concrete providers (SEC Company Facts, SEC Filings,
#       USAspending, Annual Reports) each have their own test file.
#       This file tests the ABC itself, not any specific provider.

from __future__ import annotations

import pytest

from veda.providers.base import EvidenceProvider
from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _request() -> ProviderRequest:
    return ProviderRequest(
        company_name="Lockheed Martin Corp",
        requested_period=RequestedPeriod(fiscal_year=2024, raw="2024"),
    )


def _result(provider: EvidenceProvider) -> ProviderResult:
    return ProviderResult(
        status=ProviderStatus.NOT_FOUND,
        source_type=provider.source_type,
        source_name=provider.source_name,
        is_fixture=provider.is_fixture,
        error_message="not found for test",
    )


# ====================================================================
# 1. ABC cannot be instantiated directly
# ====================================================================

def test_evidence_provider_is_abstract() -> None:
    """EvidenceProvider has abstract methods; direct instantiation fails."""
    with pytest.raises(TypeError):
        EvidenceProvider()   # type: ignore[abstract]


# ====================================================================
# 2. Incomplete subclasses are rejected
# ====================================================================

def test_subclass_missing_source_type_is_rejected() -> None:
    class Incomplete(EvidenceProvider):
        @property
        def source_name(self) -> str:
            return "test"

        @property
        def is_fixture(self) -> bool:
            return True

        def retrieve(self, request: ProviderRequest) -> ProviderResult:
            return _result(self)

    with pytest.raises(TypeError):
        Incomplete()   # type: ignore[abstract]


def test_subclass_missing_source_name_is_rejected() -> None:
    class Incomplete(EvidenceProvider):
        @property
        def source_type(self) -> SourceType:
            return SourceType.SYNTHETIC

        @property
        def is_fixture(self) -> bool:
            return True

        def retrieve(self, request: ProviderRequest) -> ProviderResult:
            return _result(self)

    with pytest.raises(TypeError):
        Incomplete()   # type: ignore[abstract]


def test_subclass_missing_is_fixture_is_rejected() -> None:
    class Incomplete(EvidenceProvider):
        @property
        def source_type(self) -> SourceType:
            return SourceType.SYNTHETIC

        @property
        def source_name(self) -> str:
            return "test"

        def retrieve(self, request: ProviderRequest) -> ProviderResult:
            return _result(self)

    with pytest.raises(TypeError):
        Incomplete()   # type: ignore[abstract]


def test_subclass_missing_retrieve_is_rejected() -> None:
    class Incomplete(EvidenceProvider):
        @property
        def source_type(self) -> SourceType:
            return SourceType.SYNTHETIC

        @property
        def source_name(self) -> str:
            return "test"

        @property
        def is_fixture(self) -> bool:
            return True

    with pytest.raises(TypeError):
        Incomplete()   # type: ignore[abstract]


# ====================================================================
# 3. A complete subclass can be instantiated
# ====================================================================

def test_complete_subclass_instantiates() -> None:
    class Complete(EvidenceProvider):
        @property
        def source_type(self) -> SourceType:
            return SourceType.SYNTHETIC

        @property
        def source_name(self) -> str:
            return "test"

        @property
        def is_fixture(self) -> bool:
            return True

        def retrieve(self, request: ProviderRequest) -> ProviderResult:
            return _result(self)

    provider = Complete()
    assert provider.source_type == SourceType.SYNTHETIC
    assert provider.source_name == "test"
    assert provider.is_fixture is True


def test_complete_subclass_retrieve_returns_result() -> None:
    class Complete(EvidenceProvider):
        @property
        def source_type(self) -> SourceType:
            return SourceType.SYNTHETIC

        @property
        def source_name(self) -> str:
            return "test"

        @property
        def is_fixture(self) -> bool:
            return True

        def retrieve(self, request: ProviderRequest) -> ProviderResult:
            return _result(self)

    provider = Complete()
    result = provider.retrieve(_request())
    assert isinstance(result, ProviderResult)
    assert result.status == ProviderStatus.NOT_FOUND