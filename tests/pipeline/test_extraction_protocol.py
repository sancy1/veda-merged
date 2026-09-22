# filename: tests/pipeline/test_extraction_protocol.py
# title: Pipeline Layer - ClaimExtractor ABC Tests
# layer: Test suite - pipeline
# status: Phase 7 — Sub-phase 7A
# description:
#     Verifies the ClaimExtractor ABC: it is abstract, it declares
#     exactly three members, and every concrete implementation
#     satisfies the contract.
#
# source:
#     AUTHORED — Phase 7 introduces the ABC; this file locks its
#     shape.

from __future__ import annotations

import pytest

from veda.pipeline.claim_extraction import RuleBasedClaimExtractor
from veda.pipeline.composite_extraction import CompositeClaimExtractor
from veda.pipeline.extraction_protocol import ClaimExtractor
from veda.pipeline.llm_extraction import LLMClaimExtractor
from veda.shared.models import Claim, Evidence


def _complete_subclass():
    class Complete(ClaimExtractor):
        @property
        def extraction_method_name(self) -> str:
            return "test"

        @property
        def is_llm_backed(self) -> bool:
            return False

        def extract(self, evidence: list[Evidence]) -> list[Claim]:
            return []
    return Complete


def _missing_method_name():
    class Missing(ClaimExtractor):
        @property
        def is_llm_backed(self) -> bool:
            return False

        def extract(self, evidence: list[Evidence]) -> list[Claim]:
            return []
    return Missing


def _missing_is_llm_backed():
    class Missing(ClaimExtractor):
        @property
        def extraction_method_name(self) -> str:
            return "test"

        def extract(self, evidence: list[Evidence]) -> list[Claim]:
            return []
    return Missing


def _missing_extract():
    class Missing(ClaimExtractor):
        @property
        def extraction_method_name(self) -> str:
            return "test"

        @property
        def is_llm_backed(self) -> bool:
            return False
    return Missing


# ====================================================================
# 1. ABC is abstract
# ====================================================================

def test_claim_extractor_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ClaimExtractor()   # type: ignore[abstract]


# ====================================================================
# 2. Incomplete subclasses are rejected
# ====================================================================

def test_subclass_missing_method_name_rejected() -> None:
    with pytest.raises(TypeError):
        _missing_method_name()()   # type: ignore[abstract]


def test_subclass_missing_is_llm_backed_rejected() -> None:
    with pytest.raises(TypeError):
        _missing_is_llm_backed()()   # type: ignore[abstract]


def test_subclass_missing_extract_rejected() -> None:
    with pytest.raises(TypeError):
        _missing_extract()()   # type: ignore[abstract]


# ====================================================================
# 3. A complete subclass instantiates
# ====================================================================

def test_complete_subclass_instantiates() -> None:
    instance = _complete_subclass()()
    assert instance.extraction_method_name == "test"
    assert instance.is_llm_backed is False
    assert instance.extract([]) == []


# ====================================================================
# 4. Concrete extractors satisfy the ABC
# ====================================================================

def test_rule_based_satisfies_abc() -> None:
    assert isinstance(RuleBasedClaimExtractor(), ClaimExtractor)


def test_llm_extractor_class_satisfies_abc() -> None:
    """The class itself is a subclass of the ABC."""
    assert issubclass(LLMClaimExtractor, ClaimExtractor)


def test_composite_satisfies_abc() -> None:
    composite = CompositeClaimExtractor(
        primary=RuleBasedClaimExtractor(),
        secondary=RuleBasedClaimExtractor(),
    )
    assert isinstance(composite, ClaimExtractor)