# filename: src/veda/adapters/graph_adapter.py
# title: Provenance Graph Adapter
# layer: Adapter layer
# status: Phase 8
# description:
#     Converts an Assessment packet into a graph-shaped record.
#     The adapter emits nodes and edges as plain dictionaries.
#     It does not build a graph, does not traverse, and does
#     not persist. It declares the shape a later phase consumes.
#
# source:
#     AUTHORED - Phase 8 introduces the adapter.

from __future__ import annotations

from typing import Any

from veda.shared.models import Assessment


GRAPH_VERSION = "v0.1.0"


NODE_VENDOR = "vendor"
NODE_DOCUMENT = "document"
NODE_EVIDENCE = "evidence"
NODE_CLAIM = "claim"
NODE_CONFLICT = "conflict"
NODE_MISSING_EVIDENCE = "missing_evidence"
NODE_ASSESSMENT = "assessment"

EDGE_RESOLVED_TO = "vendor_resolved_to"
EDGE_CONTAINS = "document_contains_evidence"
EDGE_SUPPORTS = "evidence_supports_claim"
EDGE_USED_IN = "claim_used_in_assessment"
EDGE_CONFLICTS_WITH = "claim_conflicts_with_claim"
EDGE_REQUIRES = "assessment_requires_missing_evidence"
EDGE_YIELDS = "assessment_yields_status"


def _vendor_node_id(entity_id: str | None, fallback: str) -> str:
    if entity_id:
        return f"{NODE_VENDOR}:{entity_id}"
    return f"{NODE_VENDOR}:unresolved:{fallback}"


def _document_node_id(doc_id: str) -> str:
    return f"{NODE_DOCUMENT}:{doc_id}"


def _conflict_node_id(conflict_id: str) -> str:
    return f"{NODE_CONFLICT}:{conflict_id}"


def _missing_node_id(assessment_id: str, claim_type: str, reason: str) -> str:
    return f"{NODE_MISSING_EVIDENCE}:{assessment_id}:{claim_type}:{reason}"


def adapt_to_graph(packet: Assessment) -> dict[str, Any]:
    """Convert an Assessment packet into a graph-shaped dict."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # Vendor node
    vendor_id = _vendor_node_id(packet.vendor.entity_id, packet.vendor.input_name)
    nodes.append({
        "node_id": vendor_id,
        "node_type": NODE_VENDOR,
        "label": packet.vendor.resolved_name or packet.vendor.input_name,
        "metadata": {
            "input_name": packet.vendor.input_name,
            "resolved_name": packet.vendor.resolved_name,
            "cik": packet.vendor.cik,
            "entity_id": packet.vendor.entity_id,
            "resolution_status": packet.vendor.resolution_status.value,
            "resolution_method": packet.vendor.resolution_method,
            "sec_browse_url": packet.vendor.sec_browse_url,
        },
    })

    # Document nodes
    seen_doc_ids: set[str] = set()
    for ev in packet.evidence:
        if ev.document is None:
            continue
        doc_id = ev.document.doc_id
        if doc_id in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id)
        doc_node_id = _document_node_id(doc_id)
        nodes.append({
            "node_id": doc_node_id,
            "node_type": NODE_DOCUMENT,
            "label": ev.document.title,
            "metadata": {
                "doc_id": doc_id,
                "source_type": ev.document.source_type.value,
                "doc_type": ev.document.doc_type,
                "url": ev.document.url,
                "content_hash": ev.document.content_hash,
                "accession_number": ev.document.accession_number,
                "filing_form": ev.document.filing_form,
                "is_fixture": ev.document.is_fixture,
            },
        })

    # Evidence nodes
    for ev in packet.evidence:
        nodes.append({
            "node_id": ev.evidence_id,
            "node_type": NODE_EVIDENCE,
            "label": ev.location.field_or_passage if ev.location else ev.source_name,
            "metadata": {
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
                "sec_browse_url": ev.sec_browse_url,
                "source_url": ev.location.source_url if ev.location else None,
                "source_reference": ev.location.source_reference if ev.location else None,
            },
        })
        if ev.document is not None:
            edges.append({
                "edge_type": EDGE_CONTAINS,
                "source_id": _document_node_id(ev.document.doc_id),
                "target_id": ev.evidence_id,
                "metadata": {},
            })

    # Claim nodes
    for claim in packet.claims:
        nodes.append({
            "node_id": claim.claim_id,
            "node_type": NODE_CLAIM,
            "label": f"{claim.claim_type} = {claim.value}",
            "metadata": {
                "claim_type": claim.claim_type,
                "value": claim.value,
                "unit": claim.unit,
                "currency": claim.currency,
                "entity_id": claim.entity_id,
                "evidence_category": claim.evidence_category.value,
                "extraction_method": claim.extraction_method.value,
                "confidence": claim.confidence.value,
                "claim_status": claim.claim_status.value,
                "assumptions": list(claim.assumptions),
            },
        })
        for ev_id in claim.evidence_ids:
            edges.append({
                "edge_type": EDGE_SUPPORTS,
                "source_id": ev_id,
                "target_id": claim.claim_id,
                "metadata": {
                    "extraction_method": claim.extraction_method.value,
                    "confidence": claim.confidence.value,
                },
            })

    # Conflict nodes and edges
    for conflict in packet.conflicts:
        conflict_node_id = _conflict_node_id(conflict.conflict_id)
        nodes.append({
            "node_id": conflict_node_id,
            "node_type": NODE_CONFLICT,
            "label": conflict.claim_type,
            "metadata": {
                "claim_type": conflict.claim_type,
                "entity_id": conflict.entity_id,
                "comparison_result": conflict.comparison_result.value,
                "reason": conflict.reason,
                "requires_human_review": conflict.requires_human_review,
                "conflicting_values": list(conflict.conflicting_values),
            },
        })
        if len(conflict.claim_ids) >= 2:
            edges.append({
                "edge_type": EDGE_CONFLICTS_WITH,
                "source_id": conflict.claim_ids[0],
                "target_id": conflict.claim_ids[1],
                "metadata": {
                    "conflict_id": conflict.conflict_id,
                    "reason": conflict.reason,
                },
            })

    # Missing evidence nodes
    missing_node_ids: list[str] = []
    for missing in packet.missing_evidence:
        node_id = _missing_node_id(
            packet.assessment_id,
            missing.claim_type,
            missing.reason.value,
        )
        missing_node_ids.append(node_id)
        nodes.append({
            "node_id": node_id,
            "node_type": NODE_MISSING_EVIDENCE,
            "label": f"{missing.claim_type}: {missing.reason.value}",
            "metadata": {
                "claim_type": missing.claim_type,
                "reason": missing.reason.value,
                "explanation": missing.explanation,
                "entity_id": missing.entity_id,
                "sources_checked": list(missing.sources_checked),
            },
        })

    # Assessment node
    nodes.append({
        "node_id": packet.assessment_id,
        "node_type": NODE_ASSESSMENT,
        "label": packet.assessment_status.value,
        "metadata": {
            "assessment_status": packet.assessment_status.value,
            "human_review_reason": packet.human_review_reason,
            "recommended_next_step": packet.recommended_next_step,
            "limitations": list(packet.limitations),
            "schema_version": packet.run_metadata.schema_version,
            "pipeline_version": packet.run_metadata.pipeline_version,
        },
    })

    # vendor --resolved_to--> vendor
    edges.append({
        "edge_type": EDGE_RESOLVED_TO,
        "source_id": vendor_id,
        "target_id": vendor_id,
        "metadata": {
            "resolution_method": packet.vendor.resolution_method,
            "resolution_status": packet.vendor.resolution_status.value,
        },
    })

    # claim --used_in--> assessment
    for claim in packet.claims:
        edges.append({
            "edge_type": EDGE_USED_IN,
            "source_id": claim.claim_id,
            "target_id": packet.assessment_id,
            "metadata": {},
        })

    # assessment --requires--> missing_evidence
    for missing_node_id in missing_node_ids:
        edges.append({
            "edge_type": EDGE_REQUIRES,
            "source_id": packet.assessment_id,
            "target_id": missing_node_id,
            "metadata": {},
        })

    # assessment --yields--> status
    edges.append({
        "edge_type": EDGE_YIELDS,
        "source_id": packet.assessment_id,
        "target_id": f"status:{packet.assessment_status.value}",
        "metadata": {"assessment_status": packet.assessment_status.value},
    })

    # Deterministic sort
    nodes.sort(key=lambda n: (n["node_type"], n["node_id"]))
    edges.sort(key=lambda e: (e["edge_type"], e["source_id"], e["target_id"]))

    return {
        "graph_version": GRAPH_VERSION,
        "nodes": nodes,
        "edges": edges,
    }


__all__ = [
    "adapt_to_graph",
    "GRAPH_VERSION",
    "NODE_VENDOR",
    "NODE_DOCUMENT",
    "NODE_EVIDENCE",
    "NODE_CLAIM",
    "NODE_CONFLICT",
    "NODE_MISSING_EVIDENCE",
    "NODE_ASSESSMENT",
    "EDGE_RESOLVED_TO",
    "EDGE_CONTAINS",
    "EDGE_SUPPORTS",
    "EDGE_USED_IN",
    "EDGE_CONFLICTS_WITH",
    "EDGE_REQUIRES",
    "EDGE_YIELDS",
]
