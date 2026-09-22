"""
File: src/veda/normalization/helpers.py
Title: Shared Normalization Helpers
Layer: Normalization layer
Status: Merged prototype foundation — Phase 5

Purpose
-------
Provides shared validation and conversion helpers for all Phase 5
normalizers. Helpers delegate identity, period, and document-ID rules
to frozen Phase 2 contracts.

Public API
----------
normalize_cik
validate_caller_entity_id
validate_requested_period
cik_from_entity_id
provider_status_gate
make_document_id

Does not
--------
Does not make network calls, import fixture data, define enums, or
construct Evidence objects.

Design notes
------------
Caller errors raise ValueError. Provider failures and malformed source
records are handled by the normalizers and return empty output or skip
individual records.
"""

from __future__ import annotations

from typing import Optional

from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import ProviderStatus
from veda.shared.ids import document_id as make_canonical_document_id
from veda.shared.ids import parse_entity_id
from veda.shared.periods import RequestedPeriod


def normalize_cik(value: str) -> Optional[str]:
    """Return a zero-padded ten-digit CIK, or None for invalid input."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.isdigit() or len(text) > 10:
        return None
    return text.zfill(10)


def validate_caller_entity_id(entity_id: str) -> str:
    """Validate and return a canonical entity ID, raising ValueError if invalid."""
    if not isinstance(entity_id, str) or parse_entity_id(entity_id) is None:
        raise ValueError(f"Invalid canonical entity_id: {entity_id!r}")
    return entity_id


def validate_requested_period(
    requested_period: RequestedPeriod,
) -> RequestedPeriod:
    """Validate and return a requested period, raising ValueError if invalid."""
    if requested_period is None:
        raise ValueError("requested_period is required")

    fiscal_year = getattr(requested_period, "fiscal_year", None)
    if not isinstance(fiscal_year, int):
        raise ValueError("requested_period.fiscal_year must be an integer")

    return requested_period


def cik_from_entity_id(entity_id: str) -> Optional[str]:
    """Extract and normalize the final CIK component from a valid entity ID."""
    return normalize_cik(entity_id.rsplit(":", 1)[-1])


def provider_status_gate(result: ProviderResult) -> Optional[str]:
    """Return None for FOUND, otherwise return a short provider-status reason."""
    if result.status == ProviderStatus.FOUND:
        return None
    return f"provider returned {result.status.value}"


def document_native_token(value: str) -> str:
    """
    Convert a document-ID component into a canonical safe token.

    Allowed output characters are letters, digits, underscore, period,
    and hyphen. The transformation is deterministic.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("document-ID component must be non-empty")

    token = value.strip()
    output = []

    for char in token:
        if char.isalnum() or char in "._-":
            output.append(char)
        else:
            output.append("_")

    normalized = "".join(output).strip("_")

    if not normalized:
        raise ValueError("document-ID component produced an empty token")

    return normalized


def make_document_id(source: str, doc_type: str, native_id: str) -> str:
    """Delegate document-ID generation to the frozen Phase 2 helper."""
    return make_canonical_document_id(source, doc_type, native_id)


__all__ = [
    "normalize_cik",
    "validate_caller_entity_id",
    "validate_requested_period",
    "cik_from_entity_id",
    "provider_status_gate",
    "make_document_id",
]
