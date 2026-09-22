# filename: tests/normalization/test_helpers.py
# title: Normalization Layer - Shared Helpers Tests
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Verifies the shared helpers every normalizer calls: CIK
#     normalization, entity ID validation, requested period
#     validation, the provider status gate, document-native token
#     sanitization, and document ID construction.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The helpers in src/veda/normalization/helpers.py are the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - validate_caller_entity_id and validate_requested_period raise
#       ValueError for invalid caller input.
#     - provider_status_gate returns None for FOUND, a string otherwise.

from __future__ import annotations

import pytest

from veda.normalization.helpers import (
    cik_from_entity_id,
    document_native_token,
    make_document_id,
    normalize_cik,
    provider_status_gate,
    validate_caller_entity_id,
    validate_requested_period,
)
from veda.providers.results import ProviderResult
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod


# ====================================================================
# 1. normalize_cik
# ====================================================================

def test_normalize_cik_pads_to_ten_digits() -> None:
    assert normalize_cik("936468") == "0000936468"


def test_normalize_cik_already_ten_digits_unchanged() -> None:
    assert normalize_cik("0000936468") == "0000936468"


def test_normalize_cik_strips_whitespace() -> None:
    assert normalize_cik("  936468  ") == "0000936468"


def test_normalize_cik_rejects_non_string() -> None:
    assert normalize_cik(936468) is None   # type: ignore[arg-type]


def test_normalize_cik_rejects_non_numeric() -> None:
    assert normalize_cik("abc123") is None


def test_normalize_cik_rejects_empty() -> None:
    assert normalize_cik("") is None


def test_normalize_cik_rejects_more_than_ten_digits() -> None:
    assert normalize_cik("00000936468") is None


# ====================================================================
# 2. validate_caller_entity_id
# ====================================================================

def test_validate_entity_id_returns_valid_input() -> None:
    entity = "entity:sec_edgar:vendor:0000936468"
    assert validate_caller_entity_id(entity) == entity


def test_validate_entity_id_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        validate_caller_entity_id(12345)   # type: ignore[arg-type]


def test_validate_entity_id_rejects_malformed() -> None:
    with pytest.raises(ValueError):
        validate_caller_entity_id("not an entity id")


def test_validate_entity_id_rejects_empty_string() -> None:
    with pytest.raises(ValueError):
        validate_caller_entity_id("")


# ====================================================================
# 3. validate_requested_period
# ====================================================================

def test_validate_requested_period_returns_valid_input() -> None:
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert validate_requested_period(rp) is rp


def test_validate_requested_period_rejects_none() -> None:
    with pytest.raises(ValueError):
        validate_requested_period(None)   # type: ignore[arg-type]


# ====================================================================
# 4. cik_from_entity_id
# ====================================================================

def test_cik_from_entity_id_extracts_and_pads() -> None:
    assert cik_from_entity_id("entity:sec_edgar:vendor:936468") == "0000936468"


def test_cik_from_entity_id_returns_none_for_bad_suffix() -> None:
    assert cik_from_entity_id("entity:sec_edgar:vendor:abc") is None


# ====================================================================
# 5. provider_status_gate
# ====================================================================

def _result(status: ProviderStatus) -> ProviderResult:
    kwargs = dict(
        status=status,
        source_type=SourceType.SEC_COMPANY_FACTS,
        source_name="test",
        is_fixture=True,
    )
    if status == ProviderStatus.FOUND:
        kwargs["raw_records"] = [{"x": 1}]
    elif status in (
        ProviderStatus.SOURCE_UNAVAILABLE,
        ProviderStatus.RATE_LIMITED,
        ProviderStatus.MALFORMED_RESPONSE,
    ):
        kwargs["error_message"] = "error"
    return ProviderResult(**kwargs)


def test_gate_returns_none_for_found() -> None:
    assert provider_status_gate(_result(ProviderStatus.FOUND)) is None


def test_gate_returns_reason_for_not_found() -> None:
    reason = provider_status_gate(_result(ProviderStatus.NOT_FOUND))
    assert reason is not None
    assert "not_found" in reason


def test_gate_returns_reason_for_source_unavailable() -> None:
    reason = provider_status_gate(_result(ProviderStatus.SOURCE_UNAVAILABLE))
    assert reason is not None
    assert "source_unavailable" in reason


def test_gate_returns_reason_for_rate_limited() -> None:
    reason = provider_status_gate(_result(ProviderStatus.RATE_LIMITED))
    assert reason is not None
    assert "rate_limited" in reason


def test_gate_returns_reason_for_malformed() -> None:
    reason = provider_status_gate(_result(ProviderStatus.MALFORMED_RESPONSE))
    assert reason is not None
    assert "malformed_response" in reason


# ====================================================================
# 6. document_native_token
# ====================================================================

def test_native_token_accepts_alphanumeric() -> None:
    assert document_native_token("abc123") == "abc123"


def test_native_token_preserves_dot() -> None:
    assert document_native_token("file.txt") == "file.txt"


def test_native_token_preserves_hyphen() -> None:
    assert document_native_token("0000936468-25-000009") == "0000936468-25-000009"


def test_native_token_preserves_underscore() -> None:
    assert document_native_token("a_b_c") == "a_b_c"


def test_native_token_replaces_slash() -> None:
    assert document_native_token("a/b") == "a_b"


def test_native_token_replaces_space() -> None:
    assert document_native_token("a b") == "a_b"


def test_native_token_replaces_colon() -> None:
    assert document_native_token("a:b") == "a_b"


def test_native_token_strips_leading_trailing_underscores() -> None:
    assert document_native_token("__abc__") == "abc"


def test_native_token_rejects_empty() -> None:
    with pytest.raises(ValueError):
        document_native_token("")


def test_native_token_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError):
        document_native_token("   ")


# ====================================================================
# 7. make_document_id
# ====================================================================

def test_make_document_id_matches_canonical() -> None:
    result = make_document_id("sec_edgar", "10k", "000093646825000009")
    assert result == "doc:sec_edgar:10k:000093646825000009"


def test_make_document_id_rejects_uppercase_type() -> None:
    with pytest.raises(ValueError):
        make_document_id("sec_edgar", "10K", "abc")