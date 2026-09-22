# filename: tests/normalization/test_evidence_ids.py
# title: Normalization Layer - Evidence ID Wrapper Tests
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Verifies the evidence_id_for wrapper that gives normalizers one
#     stable entry point without duplicating the canonical hashing
#     logic from veda.shared.ids.
#
# source:
#     AUTHORED - Phase 5 had no saved test before recovery began.
#     The wrapper in src/veda/normalization/evidence_ids.py is the
#     specification; this file is the executable form of that spec.
#
# notes:
#     - The wrapper delegates to veda.shared.ids.evidence_id. This
#       test file confirms the delegation is exact: the same inputs
#       through both paths produce the same output.

from __future__ import annotations

from veda.normalization.evidence_ids import evidence_id_for
from veda.shared.enums import SourceType
from veda.shared.ids import evidence_id as canonical_evidence_id


ENTITY_ID = "entity:sec_edgar:vendor:0000936468"


def test_wrapper_matches_canonical_for_sec_company_facts() -> None:
    """Wrapper output equals the canonical generator output."""
    a = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    b = canonical_evidence_id(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    assert a == b


def test_wrapper_deterministic() -> None:
    a = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    b = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    assert a == b


def test_wrapper_differs_on_field() -> None:
    a = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    b = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "OtherTag")
    assert a != b


def test_wrapper_differs_on_period_label() -> None:
    a = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    b = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2023", "Revenues")
    assert a != b


def test_wrapper_accepts_document_context() -> None:
    """SEC_FILING evidence requires a document context."""
    doc_id = "doc:sec_edgar:10k:000093646825000009"
    result = evidence_id_for(
        SourceType.SEC_FILING,
        ENTITY_ID,
        "FY2024",
        "revenues",
        doc_id,
    )
    assert result.startswith("evidence:sec_edgar:")


def test_wrapper_sec_company_facts_has_sec_edgar_slug() -> None:
    result = evidence_id_for(SourceType.SEC_COMPANY_FACTS, ENTITY_ID, "FY2024", "Revenues")
    assert result.startswith("evidence:sec_edgar:")


def test_wrapper_usaspending_has_usaspending_slug() -> None:
    result = evidence_id_for(SourceType.USASPENDING, ENTITY_ID, "FY2024", "award-001")
    assert result.startswith("evidence:usaspending:")