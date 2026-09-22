# filename: tests/entity/test_candidate.py
# title: Entity Layer - EntityCandidate Model Tests
# layer: Test suite - entity
# status: Phase 1-6 test recovery
# description:
#     Verifies EntityCandidate's field validators: CIK normalization
#     and ticker normalization. These are the raw inputs that flow
#     through the resolver, so a bad CIK here propagates everywhere.
#
# source:
#     AUTHORED - Phase 3 had no saved test before recovery began.
#     The validators in src/veda/entity/resolver.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The CIK is normalized to exactly 10 digits with left-padding.
#       SEC's ticker file provides CIKs as bare integers; the canonical
#       form is a 10-digit zero-padded string.
#     - The ticker is uppercased and stripped. Empty tickers become
#       None rather than empty strings.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from veda.entity.resolver import EntityCandidate


def test_candidate_constructs_with_minimum_fields() -> None:
    candidate = EntityCandidate(cik="936468", title="Lockheed Martin Corp")
    assert candidate.title == "Lockheed Martin Corp"


def test_candidate_requires_cik() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(title="Lockheed Martin Corp")   # type: ignore[call-arg]


def test_candidate_requires_title() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(cik="936468")   # type: ignore[call-arg]


def test_candidate_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(cik="936468", title="")


def test_cik_is_left_padded_to_ten_digits() -> None:
    candidate = EntityCandidate(cik="936468", title="Lockheed Martin Corp")
    assert candidate.cik == "0000936468"


def test_cik_already_ten_digits_unchanged() -> None:
    candidate = EntityCandidate(cik="0000936468", title="Lockheed Martin Corp")
    assert candidate.cik == "0000936468"


def test_cik_accepts_integer_and_coerces_to_string() -> None:
    candidate = EntityCandidate(cik=936468, title="Lockheed Martin Corp")   # type: ignore[arg-type]
    assert candidate.cik == "0000936468"


def test_cik_rejects_non_numeric() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(cik="abc123", title="Lockheed Martin Corp")


def test_cik_rejects_empty_string() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(cik="", title="Lockheed Martin Corp")


def test_cik_rejects_more_than_ten_digits() -> None:
    with pytest.raises(ValidationError):
        EntityCandidate(cik="00000936468", title="Lockheed Martin Corp")


def test_cik_strips_whitespace_before_validating() -> None:
    candidate = EntityCandidate(cik="  936468  ", title="Lockheed Martin Corp")
    assert candidate.cik == "0000936468"


def test_ticker_is_uppercased() -> None:
    candidate = EntityCandidate(cik="936468", ticker="lmt", title="Lockheed Martin Corp")
    assert candidate.ticker == "LMT"


def test_ticker_strips_whitespace() -> None:
    candidate = EntityCandidate(cik="936468", ticker="  lmt  ", title="Lockheed Martin Corp")
    assert candidate.ticker == "LMT"


def test_ticker_empty_becomes_none() -> None:
    candidate = EntityCandidate(cik="936468", ticker="", title="Lockheed Martin Corp")
    assert candidate.ticker is None


def test_ticker_whitespace_only_becomes_none() -> None:
    candidate = EntityCandidate(cik="936468", ticker="   ", title="Lockheed Martin Corp")
    assert candidate.ticker is None


def test_ticker_none_stays_none() -> None:
    candidate = EntityCandidate(cik="936468", ticker=None, title="Lockheed Martin Corp")
    assert candidate.ticker is None


def test_ticker_default_is_none() -> None:
    candidate = EntityCandidate(cik="936468", title="Lockheed Martin Corp")
    assert candidate.ticker is None


def test_entity_type_defaults_to_none() -> None:
    candidate = EntityCandidate(cik="936468", title="Lockheed Martin Corp")
    assert candidate.entity_type is None


def test_parent_entity_defaults_to_none() -> None:
    candidate = EntityCandidate(cik="936468", title="Lockheed Martin Corp")
    assert candidate.parent_entity is None