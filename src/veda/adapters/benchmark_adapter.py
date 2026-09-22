# filename: src/veda/adapters/benchmark_adapter.py
# title: Benchmark Adapter
# layer: Adapter layer
# status: Phase 8
# description:
#     Converts an Assessment packet into a benchmark-shaped record.
#     The adapter emits the frozen output of one pipeline run
#     which a benchmark scores against ground truth. It does not
#     build a benchmark. It does not generate questions. It does
#     not run retrieval. It declares the shape.
#
# source:
#     AUTHORED - Phase 8 introduces the adapter.

from __future__ import annotations

from typing import Any

from veda.shared.models import Assessment


BENCHMARK_VERSION = "v0.1.0"


def adapt_to_benchmark(packet: Assessment) -> dict[str, Any]:
    """Convert an Assessment packet into a benchmark-shaped dict."""
    return {
        "benchmark_version": BENCHMARK_VERSION,

        "entity": {
            "input_name": packet.vendor.input_name,
            "resolved_name": packet.vendor.resolved_name,
            "cik": packet.vendor.cik,
            "entity_id": packet.vendor.entity_id,
            "entity_type": (
                packet.vendor.entity_type.value
                if packet.vendor.entity_type is not None
                else None
            ),
            "resolution_status": packet.vendor.resolution_status.value,
            "resolution_method": packet.vendor.resolution_method,
        },

        "period": {
            "start": (
                packet.reporting_period.start.isoformat()
                if packet.reporting_period.start is not None
                else None
            ),
            "end": (
                packet.reporting_period.end.isoformat()
                if packet.reporting_period.end is not None
                else None
            ),
            "label": packet.reporting_period.label,
        },

        "evidence": [
            {
                "evidence_id": ev.evidence_id,
                "source_type": ev.source_type.value,
                "source_name": ev.source_name,
                "evidence_category": ev.evidence_category.value,
                "retrieval_method": ev.retrieval_method.value,
                "raw_value": ev.raw_value,
                "unit": ev.unit,
                "currency": ev.currency,
                "is_fixture": ev.is_fixture,
                "is_context_only": ev.is_context_only,
                "accession_number": ev.accession_number,
                "xbrl_tag": ev.xbrl_tag,
                "form": ev.form,
                "source_url": (
                    ev.location.source_url if ev.location else None
                ),
                "source_reference": (
                    ev.location.source_reference if ev.location else None
                ),
                "document_id": (
                    ev.document.doc_id if ev.document else None
                ),
            }
            for ev in packet.evidence
        ],

        "claims": [
            {
                "claim_id": claim.claim_id,
                "claim_type": claim.claim_type,
                "value": claim.value,
                "unit": claim.unit,
                "currency": claim.currency,
                "evidence_category": claim.evidence_category.value,
                "extraction_method": claim.extraction_method.value,
                "confidence": claim.confidence.value,
                "claim_status": claim.claim_status.value,
                "evidence_ids": list(claim.evidence_ids),
                "assumptions": list(claim.assumptions),
            }
            for claim in packet.claims
        ],

        "conflicts": [
            {
                "conflict_id": conflict.conflict_id,
                "claim_type": conflict.claim_type,
                "claim_ids": list(conflict.claim_ids),
                "evidence_ids": list(conflict.evidence_ids),
                "conflicting_values": list(conflict.conflicting_values),
                "comparison_result": conflict.comparison_result.value,
                "reason": conflict.reason,
                "requires_human_review": conflict.requires_human_review,
            }
            for conflict in packet.conflicts
        ],

        "missing_evidence": [
            {
                "claim_type": missing.claim_type,
                "reason": missing.reason.value,
                "explanation": missing.explanation,
                "entity_id": missing.entity_id,
                "sources_checked": list(missing.sources_checked),
            }
            for missing in packet.missing_evidence
        ],

        "limitations": list(packet.limitations),

        "assessment_status": packet.assessment_status.value,
        "human_review_reason": packet.human_review_reason,
        "recommended_next_step": packet.recommended_next_step,

        "run_metadata": {
            "schema_version": packet.run_metadata.schema_version,
            "pipeline_version": packet.run_metadata.pipeline_version,
            "provider_modes": dict(packet.run_metadata.provider_modes),
        },
    }


__all__ = ["adapt_to_benchmark", "BENCHMARK_VERSION"]
