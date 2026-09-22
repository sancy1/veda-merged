"""
File: src/veda/pipeline/abstention.py
Title: Missing-Evidence Computation
Layer: Pipeline layer
Status: Merged prototype foundation — Phase 6

Purpose
-------
Produces MissingEvidence records describing what the assessment
expected to find but did not. The abstention module does not choose
the assessment state; the assessment engine does.

Public API
----------
compute_missing_evidence(
    vendor, claims, evidences, requested_period
) -> list[MissingEvidence]

Does not
--------
Does not make network calls.
Does not import veda.providers.fixtures.
Does not choose an assessment state.
Does not create missing-revenue evidence for procurement-only or
corporate-relationship-only entities.
Does not flag narrative claims as insufficient.

Design notes
------------
Four triggers:

    1. Entity unresolved
    2. No claims and no evidence at all
    3. Recognized-revenue evidence exists but no supported or
       inferred revenue claim was produced.
    4. An INFERRED claim whose type is numeric (total_revenue or
       procurement_obligation) and whose value is None.

Trigger 4 is deliberately narrow. Narrative claim types
(government_exposure, customer_concentration, corporate_relationship)
never carry a numeric value by design. Their value being None is not
insufficient evidence; it is the intended state. Trigger 4 does not
fire for them.

Records are sorted by (claim_type, reason.value) ascending.
"""

from __future__ import annotations

from veda.shared.enums import (
    ClaimStatus,
    EntityResolutionStatus,
    EvidenceCategory,
    MissingEvidenceReason,
)
from veda.shared.models import Claim, Evidence, MissingEvidence, ResolvedEntity
from veda.shared.periods import Period, RequestedPeriod


# Claim types whose value is expected to be numeric. Trigger 4 only
# fires for these.
_NUMERIC_CLAIM_TYPES = frozenset({
    "total_revenue",
    "procurement_obligation",
})


def _reason_sort_key(record: MissingEvidence) -> tuple[str, str]:
    return (record.claim_type, record.reason.value)


def compute_missing_evidence(
    vendor: ResolvedEntity,
    claims: list[Claim],
    evidences: list[Evidence],
    requested_period: RequestedPeriod,
) -> list[MissingEvidence]:
    """
    Return every MissingEvidence record for the assessment.
    Empty list when nothing is missing. Sorted deterministically.
    """
    records: list[MissingEvidence] = []

    # Trigger 1: unresolved entity.
    if vendor.resolution_status != EntityResolutionStatus.RESOLVED:
        records.append(
            MissingEvidence(
                claim_type="vendor_identity",
                reason=MissingEvidenceReason.ENTITY_AMBIGUOUS,
                explanation=(
                    f"Vendor {vendor.input_name!r} could not be resolved "
                    "to a canonical entity; no authoritative assessment "
                    "is possible."
                ),
                entity_id=vendor.entity_id,
            )
        )
        records.sort(key=_reason_sort_key)
        return records

    # Trigger 2: no claims and no evidence at all.
    if not claims and not evidences:
        records.append(
            MissingEvidence(
                claim_type="any_evidence",
                reason=MissingEvidenceReason.DATA_NOT_FOUND,
                explanation=(
                    "No evidence was retrieved for the requested entity "
                    "and period from any configured source."
                ),
                entity_id=vendor.entity_id,
            )
        )
        records.sort(key=_reason_sort_key)
        return records

    # A revenue claim is present and usable.
    has_revenue_claim = any(
        claim.claim_type == "total_revenue"
        and claim.claim_status in (ClaimStatus.SUPPORTED, ClaimStatus.INFERRED)
        for claim in claims
    )

    # Recognized-revenue evidence was retrieved.
    has_revenue_evidence = any(
        evidence.evidence_category == EvidenceCategory.RECOGNIZED_REVENUE
        for evidence in evidences
    )

    # Trigger 3: revenue evidence exists but no usable revenue claim.
    if has_revenue_evidence and not has_revenue_claim:
        records.append(
            MissingEvidence(
                claim_type="total_revenue",
                reason=MissingEvidenceReason.EVIDENCE_FOUND_BUT_NOT_SUFFICIENT,
                explanation=(
                    "Recognized-revenue evidence was found for the "
                    "requested entity and period, but no supported or "
                    "inferred revenue claim is available."
                ),
                entity_id=vendor.entity_id,
                reporting_period=Period(
                    start=requested_period.start,
                    end=requested_period.end,
                    label=requested_period.raw,
                ),
            )
        )

    # Trigger 4: INFERRED claim of a NUMERIC type with no value.
    # Narrative claim types are excluded by design.
    for claim in claims:
        if (
            claim.claim_status == ClaimStatus.INFERRED
            and claim.claim_type in _NUMERIC_CLAIM_TYPES
            and claim.value is None
        ):
            records.append(
                MissingEvidence(
                    claim_type=claim.claim_type,
                    reason=MissingEvidenceReason.EVIDENCE_FOUND_BUT_NOT_SUFFICIENT,
                    explanation=(
                        f"The {claim.claim_type!r} claim is based on a "
                        "qualitative disclosure and carries no numeric value."
                    ),
                    entity_id=claim.entity_id,
                    reporting_period=claim.reporting_period,
                )
            )

    records.sort(key=_reason_sort_key)
    return records


__all__ = ["compute_missing_evidence"]