"""
File: src/veda/normalization/usaspending.py
Title: USAspending Award Normalizer
Layer: Normalization layer
Status: Merged prototype foundation — Phase 5

Purpose
-------
Converts USAspending award records into Evidence while preserving
obligations as procurement obligations rather than revenue.

Public API
----------
normalize_usaspending_award
    Convert valid award records into Evidence objects.

Does not
--------
Does not make network calls, import fixture data, relabel obligations
as revenue, infer dates, or build assessments.

Design notes
------------
Each valid record requires award_id and total_obligated_amount.
Malformed records are skipped individually.
"""

from __future__ import annotations

from veda.normalization.evidence_ids import evidence_id_for
from veda.normalization.helpers import (
    provider_status_gate,
    validate_caller_entity_id,
    validate_requested_period,
)
from veda.providers.results import ProviderResult
from veda.shared.enums import EvidenceCategory, ExtractionMethod, SourceType
from veda.shared.models import Evidence, EvidenceLocation
from veda.shared.periods import Period, RequestedPeriod


def normalize_usaspending_award(
    result: ProviderResult,
    *,
    entity_id: str,
    requested_period: RequestedPeriod,
) -> list[Evidence]:
    """Normalize valid USAspending awards into procurement Evidence."""
    validate_caller_entity_id(entity_id)
    validate_requested_period(requested_period)

    if provider_status_gate(result) is not None:
        return []
    if result.source_type != SourceType.USASPENDING:
        return []

    period_label = f"FY{requested_period.fiscal_year}"
    output: list[Evidence] = []

    for record in result.raw_records:
        if not isinstance(record, dict):
            continue

        award_id = record.get("award_id")
        amount = record.get("total_obligated_amount")

        if not isinstance(award_id, str) or not award_id.strip():
            continue
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            continue

        try:
            output.append(
                Evidence(
                    evidence_id=evidence_id_for(
                        SourceType.USASPENDING,
                        entity_id,
                        period_label,
                        award_id,
                    ),
                    source_type=SourceType.USASPENDING,
                    source_name=result.source_name,
                    location=EvidenceLocation(field_or_passage=award_id),
                    raw_value=amount,
                    unit="USD",
                    currency="USD",
                    entity_id=entity_id,
                    reporting_period=Period(label=period_label),
                    evidence_category=EvidenceCategory.PROCUREMENT_OBLIGATION,
                    retrieval_method=ExtractionMethod.DETERMINISTIC_JSON,
                    retrieved_at=result.retrieved_at,
                    is_fixture=result.is_fixture,
                )
            )
        except Exception:
            continue

    return output


__all__ = ["normalize_usaspending_award"]