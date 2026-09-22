# filename: tests/pipeline/test_composite_extraction.py
# title: Pipeline Layer - Composite Extractor Tests
# layer: Test suite - pipeline
# status: Phase 7 — Sub-phase 7A
# description:
#     Verifies CompositeClaimExtractor: it combines two extractors,
#     deduplicates by claim_id, preserves the primary's claim on
#     duplicate IDs, sorts deterministically, and does not mutate its
#     inputs.
#
# source:
#     AUTHORED — Phase 7 introduces the composite; the reviewer
#     required the primary-wins-on-duplicate rule to be explicit.

from __future__ import annotations

from datetime import date
from hashlib import sha1

import pytest

from veda.pipeline.claim_extraction import RuleBasedClaimExtractor
from veda.pipeline.composite_extraction import CompositeClaimExtractor
from veda.pipeline.extraction_protocol import ClaimExtractor
from veda.pipeline.llm_extraction import LLMClaimExtractor
from veda.shared.enums import (
    ClaimStatus,
    ConfidenceLevel,
    EvidenceCategory,
    ExtractionMethod,
    SourceType,
)
from veda.shared.ids import claim_id as make_claim_id
from veda.shared.models import Claim, Evidence, EvidenceLocation
from veda.shared.periods import Period


ENTITY_ID = "entity:sec_edgar:vendor:0000936468"
PERIOD = Period(start=date(2024, 1, 1), end=date(2024, 12, 31), label="FY2024")


def _evid(suffix: str) -> str:
    """Build a valid canonical evidence ID from an arbitrary suffix."""
    digest = sha1(suffix.encode("utf-8")).hexdigest()[:16]
    return f"evidence:sec_edgar:{digest}"


def _claim(suffix: str, value: float = 100.0) -> Claim:
    """Build a claim with a deterministic ID keyed off suffix."""
    ev_id = _evid(suffix)
    cid = make_claim_id(ENTITY_ID, "total_revenue", "FY2024", [ev_id])
    return Claim(
        claim_id=cid,
        claim_type="total_revenue",
        value=value,
        unit="USD",
        currency="USD",
        entity_id=ENTITY_ID,
        reporting_period=PERIOD,
        evidence_ids=[ev_id],
        evidence_category=EvidenceCategory.RECOGNIZED_REVENUE,
        extraction_method=ExtractionMethod.DETERMINISTIC_FIELD_EXTRACTION,
        confidence=ConfidenceLevel.HIGH,
        claim_status=ClaimStatus.SUPPORTED,
    )


class _StubExtractor(ClaimExtractor):
    """A controllable extractor for tests."""

    def __init__(self, *, name: str, claims: list[Claim], llm: bool = False):
        self._name = name
        self._claims = list(claims)
        self._llm = llm
        self.call_count = 0

    @property
    def extraction_method_name(self) -> str:
        return self._name

    @property
    def is_llm_backed(self) -> bool:
        return self._llm

    def extract(self, evidence: list[Evidence]) -> list[Claim]:
        self.call_count += 1
        return list(self._claims)


# ====================================================================
# 1. Combination
# ====================================================================

def test_composite_combines_both_extractors() -> None:
    a = _StubExtractor(name="a", claims=[_claim("a")])
    b = _StubExtractor(name="b", claims=[_claim("b")])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    result = composite.extract([])
    assert len(result) == 2


def test_composite_calls_both_extractors() -> None:
    a = _StubExtractor(name="a", claims=[])
    b = _StubExtractor(name="b", claims=[])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    composite.extract([])
    assert a.call_count == 1
    assert b.call_count == 1


# ====================================================================
# 2. Deduplication by claim_id
# ====================================================================

def test_composite_deduplicates_by_claim_id() -> None:
    shared = _claim("x")
    a = _StubExtractor(name="a", claims=[shared])
    b = _StubExtractor(name="b", claims=[shared])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    result = composite.extract([])
    assert len(result) == 1


def test_composite_primary_wins_on_duplicate_claim_id() -> None:
    """
    When primary and secondary produce claims with the same claim_id,
    the primary's claim is preserved and the secondary's is discarded.
    The rule is: first writer (primary) wins.
    """
    shared_id = _claim("shared").claim_id
    primary_claim = _claim("shared", value=1.0)
    secondary_claim = _claim("shared", value=2.0)
    # Force same ID.
    primary_claim = primary_claim.model_copy(update={"claim_id": shared_id})
    secondary_claim = secondary_claim.model_copy(update={"claim_id": shared_id})

    a = _StubExtractor(name="a", claims=[primary_claim])
    b = _StubExtractor(name="b", claims=[secondary_claim])

    composite = CompositeClaimExtractor(primary=a, secondary=b)
    result = composite.extract([])

    assert len(result) == 1
    assert result[0].value == 1.0, "primary claim must win on duplicate ID"


# ====================================================================
# 3. Determinism
# ====================================================================

def test_composite_sorts_by_claim_id() -> None:
    a = _StubExtractor(name="a", claims=[_claim("c"), _claim("a")])
    b = _StubExtractor(name="b", claims=[_claim("b")])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    result = composite.extract([])
    ids = [c.claim_id for c in result]
    assert ids == sorted(ids)


def test_composite_two_runs_produce_same_order() -> None:
    a = _StubExtractor(name="a", claims=[_claim("c"), _claim("a")])
    b = _StubExtractor(name="b", claims=[_claim("b")])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    first = [c.claim_id for c in composite.extract([])]
    second = [c.claim_id for c in composite.extract([])]
    assert first == second


# ====================================================================
# 4. Metadata
# ====================================================================

def test_composite_is_llm_backed_false_for_two_rule_based() -> None:
    a = _StubExtractor(name="a", claims=[], llm=False)
    b = _StubExtractor(name="b", claims=[], llm=False)
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    assert composite.is_llm_backed is False


def test_composite_is_llm_backed_true_when_primary_is_llm() -> None:
    a = _StubExtractor(name="a", claims=[], llm=True)
    b = _StubExtractor(name="b", claims=[], llm=False)
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    assert composite.is_llm_backed is True


def test_composite_is_llm_backed_true_when_secondary_is_llm() -> None:
    a = _StubExtractor(name="a", claims=[], llm=False)
    b = _StubExtractor(name="b", claims=[], llm=True)
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    assert composite.is_llm_backed is True


def test_composite_method_name_composes() -> None:
    a = _StubExtractor(name="rule", claims=[])
    b = _StubExtractor(name="llm", claims=[])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    assert composite.extraction_method_name == "composite(rule+llm)"


# ====================================================================
# 5. No mutation
# ====================================================================

def test_composite_does_not_mutate_primary_output() -> None:
    original = _claim("a")
    a = _StubExtractor(name="a", claims=[original])
    b = _StubExtractor(name="b", claims=[])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    composite.extract([])
    assert a._claims == [original]


# ====================================================================
# 6. Construction validation
# ====================================================================

def test_composite_rejects_non_extractor_primary() -> None:
    with pytest.raises(TypeError):
        CompositeClaimExtractor(
            primary="not an extractor",   # type: ignore[arg-type]
            secondary=RuleBasedClaimExtractor(),
        )


def test_composite_rejects_non_extractor_secondary() -> None:
    with pytest.raises(TypeError):
        CompositeClaimExtractor(
            primary=RuleBasedClaimExtractor(),
            secondary="not an extractor",   # type: ignore[arg-type]
        )


# ====================================================================
# 7. Composite with a stub secondary raises on call
# ====================================================================

def test_composite_with_stub_secondary_raises_on_extract() -> None:
    """
    A composite containing the disabled LLM stub raises
    NotImplementedError when extract is called. The composite is
    available in Phase 7 but not enabled by default.
    """
    composite = CompositeClaimExtractor(
        primary=RuleBasedClaimExtractor(),
        secondary=LLMClaimExtractor(enabled=True),
    )
    with pytest.raises(NotImplementedError):
        composite.extract([])


# ====================================================================
# 8. Empty input
# ====================================================================

def test_composite_empty_extractors_produce_empty_result() -> None:
    a = _StubExtractor(name="a", claims=[])
    b = _StubExtractor(name="b", claims=[])
    composite = CompositeClaimExtractor(primary=a, secondary=b)
    assert composite.extract([]) == []