"""
File: src/veda/shared/validation.py
Title: Cross-Record Validation
Layer: Shared data contract
Status: Merged prototype foundation — File 10 v3

Purpose
-------
Enforce the cross-record invariants that models.py (File 9) cannot
check in isolation, because they require seeing every record of an
Assessment at once.

File 9 checks what a single model can decide about itself. This file
checks what the whole packet must satisfy: references between
records, uniqueness of identities within a packet, entity and period
scope consistency, and provenance completeness.

The function is pure. It reads the assessment, checks invariants, and
either returns None (valid) or raises ValueError naming the violated
rule and the offending ID or field. It never mutates the assessment
and never touches the network.

Rule count
----------
Eleven logical rules are implemented by ten check functions because
entity rules 7 and 8 share one function (_check_entity_scope_consistency).
The docstring of that function names both rules.

Composition
-----------
- Enums: imported from veda.shared.enums.
- Periods: Period and RequestedPeriod from veda.shared.periods.
- Models: Assessment from veda.shared.models.

This file does not:
-------------------
- Re-run any File 9 model-local validator. File 9 already enforced
  those at construction time.
- Generate IDs.
- Compare periods via any mechanism other than
  Period.match_status_against.
- Mutate the assessment.
- Make network calls.
- Perform a reverse-hash check on evidence IDs.
- Allow adjacent-period exceptions. Adjacent-period support is
  deferred until a per-record structured period-context field exists.
  Until then, the operational rule is exact match only.

The eleven cross-record rules
-----------------------------
  1. Every evidence_id referenced by a claim exists in the packet.
  2. Every claim_id referenced by a conflict exists in the packet.
  3. Every evidence_id referenced by a conflict exists in the packet.
  4. Evidence IDs are unique within the packet.
  5. Claim IDs are unique within the packet.
  6. Every evidence record is either referenced by a claim or has
     is_context_only=True. Prose is never consulted.
  7. If the vendor is RESOLVED, every claim and every evidence record
     carries the same entity_id as the vendor.
  8. If the vendor is not RESOLVED, the claims and evidence lists are
     both empty. (Rules 7 and 8 share one function.)
  9. Every claim and every conflict carries a reporting_period whose
     match_status_against(requested_period) is EXACT. Comparison is
     skipped entirely when claims and conflicts are both empty, so an
     abstention packet with an unknown period is valid.
 10. If human_review_reason is set, it is non-blank.
 11. Every evidence record has document or location non-None.
"""

from __future__ import annotations

from veda.shared.enums import EntityResolutionStatus, PeriodMatchStatus
from veda.shared.models import Assessment
from veda.shared.periods import RequestedPeriod


# ====================================================================
# Period scope helper
# ====================================================================

def _requested_period_from_assessment(assessment: Assessment) -> RequestedPeriod:
    """
    Build the RequestedPeriod that every claim and conflict is compared
    against, using the canonical Period API on the assessment's own
    reporting_period.

    Raises ValueError if the assessment's reporting_period has no
    fiscal year (i.e. no known end date). This function is called only
    from _check_period_scope_exact, and only after that function has
    confirmed there are claims or conflicts that need comparison. A
    valid abstention packet with no claims or conflicts never reaches
    this function.
    """
    period = assessment.reporting_period
    fiscal_year = period.fiscal_year()
    if fiscal_year is None:
        raise ValueError(
            "period scope: assessment reporting_period has no fiscal year "
            "(Period.end is None); cannot compare record periods"
        )
    return RequestedPeriod(
        fiscal_year=fiscal_year,
        start=period.start,
        end=period.end,
        raw=period.label or str(fiscal_year),
    )


# ====================================================================
# Individual checks
# ====================================================================

def _check_claim_evidence_ids_exist(assessment: Assessment) -> None:
    """Rule 1: every evidence_id referenced by a claim exists in the packet."""
    known = {ev.evidence_id for ev in assessment.evidence}
    for claim in assessment.claims:
        for ev_id in claim.evidence_ids:
            if ev_id not in known:
                raise ValueError(
                    f"claim evidence reference: claim {claim.claim_id!r} "
                    f"references evidence {ev_id!r} not present in assessment.evidence"
                )


def _check_conflict_claim_ids_exist(assessment: Assessment) -> None:
    """Rule 2: every claim_id referenced by a conflict exists in the packet."""
    known = {c.claim_id for c in assessment.claims}
    for conflict in assessment.conflicts:
        for cid in conflict.claim_ids:
            if cid not in known:
                raise ValueError(
                    f"conflict claim reference: conflict {conflict.conflict_id!r} "
                    f"references claim {cid!r} not present in assessment.claims"
                )


def _check_conflict_evidence_ids_exist(assessment: Assessment) -> None:
    """Rule 3: every evidence_id referenced by a conflict exists in the packet."""
    known = {ev.evidence_id for ev in assessment.evidence}
    for conflict in assessment.conflicts:
        for ev_id in conflict.evidence_ids:
            if ev_id not in known:
                raise ValueError(
                    f"conflict evidence reference: conflict {conflict.conflict_id!r} "
                    f"references evidence {ev_id!r} not present in assessment.evidence"
                )


def _check_no_duplicate_evidence_ids(assessment: Assessment) -> None:
    """Rule 4: evidence IDs are unique within the packet."""
    seen: set[str] = set()
    for ev in assessment.evidence:
        if ev.evidence_id in seen:
            raise ValueError(f"duplicate evidence_id: {ev.evidence_id!r}")
        seen.add(ev.evidence_id)


def _check_no_duplicate_claim_ids(assessment: Assessment) -> None:
    """Rule 5: claim IDs are unique within the packet."""
    seen: set[str] = set()
    for c in assessment.claims:
        if c.claim_id in seen:
            raise ValueError(f"duplicate claim_id: {c.claim_id!r}")
        seen.add(c.claim_id)


def _check_every_evidence_referenced_or_context_only(assessment: Assessment) -> None:
    """
    Rule 6: every evidence record is either referenced by at least one
    claim, or is explicitly marked is_context_only=True.

    Prose is never consulted. The only mechanism for allowlisting an
    unreferenced evidence record is the is_context_only flag.
    """
    referenced: set[str] = set()
    for claim in assessment.claims:
        referenced.update(claim.evidence_ids)

    for ev in assessment.evidence:
        if ev.evidence_id in referenced:
            continue
        if ev.is_context_only:
            continue
        raise ValueError(
            f"unreferenced evidence: {ev.evidence_id!r} is not referenced by "
            "any claim and is not marked is_context_only=True"
        )


def _check_entity_scope_consistency(assessment: Assessment) -> None:
    """
    Rules 7 and 8.

    Rule 7: if the vendor is RESOLVED, every claim and every evidence
    record carries the same entity_id as the vendor. Exact scope only;
    related-entity exceptions are deferred until a relationship model
    exists.

    Rule 8: if the vendor is not RESOLVED, the claims and evidence
    lists are both empty.
    """
    status = assessment.vendor.resolution_status

    if status == EntityResolutionStatus.RESOLVED:
        vendor_entity_id = assessment.vendor.entity_id
        if vendor_entity_id is None:
            raise ValueError(
                "entity scope: vendor.resolution_status is RESOLVED but "
                "vendor.entity_id is None"
            )
        for claim in assessment.claims:
            if claim.entity_id != vendor_entity_id:
                raise ValueError(
                    f"entity scope: claim {claim.claim_id!r} carries "
                    f"entity_id {claim.entity_id!r}, expected {vendor_entity_id!r}"
                )
        for ev in assessment.evidence:
            if ev.entity_id != vendor_entity_id:
                raise ValueError(
                    f"entity scope: evidence {ev.evidence_id!r} carries "
                    f"entity_id {ev.entity_id!r}, expected {vendor_entity_id!r}"
                )
        return

    if assessment.claims:
        raise ValueError(
            "entity scope: vendor is not RESOLVED, but assessment.claims is non-empty"
        )
    if assessment.evidence:
        raise ValueError(
            "entity scope: vendor is not RESOLVED, but assessment.evidence is non-empty"
        )


def _check_period_scope_exact(assessment: Assessment) -> None:
    """
    Rule 9: exact period scope.

    Every claim and every conflict's reporting_period must match the
    assessment's reporting_period exactly, as determined by the
    canonical Period.match_status_against(RequestedPeriod).

    MISMATCH, ADJACENT, and UNKNOWN are all rejected. Adjacent-period
    support is deferred until an explicit per-record structured
    period-context field exists. Prose explanations are not a
    substitute.

    If both assessment.claims and assessment.conflicts are empty, this
    check returns early without computing a requested period. That is
    what allows a valid abstention packet with an unknown period to
    pass.
    """
    if not assessment.claims and not assessment.conflicts:
        return

    requested = _requested_period_from_assessment(assessment)

    for claim in assessment.claims:
        status = claim.reporting_period.match_status_against(requested)
        if status != PeriodMatchStatus.EXACT:
            raise ValueError(
                f"period scope: claim {claim.claim_id!r} reporting_period "
                f"does not exactly match assessment period "
                f"(comparison: {status.value})"
            )

    for conflict in assessment.conflicts:
        status = conflict.reporting_period.match_status_against(requested)
        if status != PeriodMatchStatus.EXACT:
            raise ValueError(
                f"period scope: conflict {conflict.conflict_id!r} reporting_period "
                f"does not exactly match assessment period "
                f"(comparison: {status.value})"
            )


def _check_human_review_reason_not_blank(assessment: Assessment) -> None:
    """
    Rule 10: if human_review_reason is set, it must not be blank.

    File 9 already enforces this for REQUIRES_HUMAN_REVIEW, but a
    composed packet may have been mutated, and the check applies
    whenever the field is present regardless of status.
    """
    if assessment.human_review_reason is None:
        return
    if not assessment.human_review_reason.strip():
        raise ValueError(
            "human review reason: field is set but contains only whitespace"
        )


def _check_evidence_provenance_present(assessment: Assessment) -> None:
    """
    Rule 11: every evidence record has document or location non-None.

    File 9 already enforces this on construction. This is a
    belt-and-braces re-check on the composed packet, because a caller
    could produce an Assessment via model_construct or by mutation.
    """
    for ev in assessment.evidence:
        if ev.document is None and ev.location is None:
            raise ValueError(
                f"evidence provenance: {ev.evidence_id!r} has neither "
                "document nor location"
            )


# ====================================================================
# Public entry point
# ====================================================================

def validate_assessment(assessment: Assessment) -> None:
    """
    Validate every cross-record invariant on a fully constructed
    Assessment.

    Returns None if the packet satisfies all eleven rules. Raises
    ValueError with a descriptive message naming the violated rule and
    the offending ID or field otherwise.

    Pure and read-only. Same input always produces the same outcome.
    Never mutates the assessment. Never makes network calls.

    Eleven logical rules are implemented by ten check functions because
    entity rules 7 and 8 share _check_entity_scope_consistency.

    Checks are executed in a fixed order. The first violation raises;
    later checks are not attempted on an invalid packet.

    A public input-type guard rejects anything that is not an
    Assessment before any check runs.
    """
    if not isinstance(assessment, Assessment):
        raise ValueError(
            f"assessment validation: expected Assessment, got {type(assessment).__name__}"
        )

    _check_claim_evidence_ids_exist(assessment)
    _check_conflict_claim_ids_exist(assessment)
    _check_conflict_evidence_ids_exist(assessment)
    _check_no_duplicate_evidence_ids(assessment)
    _check_no_duplicate_claim_ids(assessment)
    _check_every_evidence_referenced_or_context_only(assessment)
    _check_entity_scope_consistency(assessment)
    _check_period_scope_exact(assessment)
    _check_human_review_reason_not_blank(assessment)
    _check_evidence_provenance_present(assessment)
    return None


__all__ = ["validate_assessment"]