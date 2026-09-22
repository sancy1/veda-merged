"""
File: src/veda/normalization/evidence_ids.py
Title: Deterministic Evidence ID Wrapper
Layer: Normalization layer
Status: Merged prototype foundation — Phase 5

Purpose
-------
Delegates Evidence ID generation to the frozen Phase 2 evidence_id
function. This module gives normalizers one stable entry point without
duplicating hashing or canonicalization logic.

Public API
----------
evidence_id_for
    Generate a deterministic canonical Evidence ID.

Does not
--------
Does not hash independently, use timestamps, access fixture data, or
make network calls.

Design notes
------------
IDs depend only on the supplied source type, entity, period label,
field or passage, and optional document context.
"""

from __future__ import annotations

from typing import Optional

from veda.shared.enums import SourceType
from veda.shared.ids import evidence_id as make_canonical_evidence_id


def evidence_id_for(
    source_type: SourceType,
    entity_id: str,
    reporting_period_label: str,
    field_or_passage: str,
    document_context: Optional[str] = None,
) -> str:
    """Return the deterministic Evidence ID from the Phase 2 helper."""
    return make_canonical_evidence_id(
        source_type,
        entity_id,
        reporting_period_label,
        field_or_passage,
        document_context,
    )


__all__ = ["evidence_id_for"]