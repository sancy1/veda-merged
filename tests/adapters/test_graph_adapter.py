# filename: tests/adapters/test_graph_adapter.py
# title: Adapter Layer - Graph Adapter Tests
# layer: Test suite - adapters
# status: Phase 8
# description:
#     Verifies adapt_to_graph: node and edge shape, node and edge
#     types, deterministic sort, and the empty-packet case.

from __future__ import annotations

from veda.adapters.graph_adapter import (
    adapt_to_graph,
    EDGE_CONTAINS,
    EDGE_RESOLVED_TO,
    EDGE_SUPPORTS,
    EDGE_USED_IN,
    EDGE_YIELDS,
    GRAPH_VERSION,
    NODE_ASSESSMENT,
    NODE_CLAIM,
    NODE_DOCUMENT,
    NODE_EVIDENCE,
    NODE_VENDOR,
)
from veda.entity.resolver import FixtureEntityResolverSource
from veda.pipeline.orchestrator import ProviderBundle, run_assessment
from veda.providers.annual_reports import FixtureAnnualReportProvider
from veda.providers.sec_company_facts import FixtureSECCompanyFactsProvider
from veda.providers.sec_filings import FixtureSECFilingsProvider
from veda.providers.usaspending import FixtureUSAspendingProvider
from veda.shared.periods import RequestedPeriod


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        sec_company_facts=FixtureSECCompanyFactsProvider(),
        sec_filing=FixtureSECFilingsProvider(),
        usaspending=FixtureUSAspendingProvider(),
        annual_report=FixtureAnnualReportProvider(),
    )


def _resolver() -> FixtureEntityResolverSource:
    return FixtureEntityResolverSource({
        "lockheed martin corp": [
            {"cik": 936468, "ticker": "LMT", "title": "LOCKHEED MARTIN CORP"},
        ],
    })


def _packet(vendor: str = "Lockheed Martin Corp", year: int = 2024):
    return run_assessment(
        vendor_name=vendor,
        requested_period=RequestedPeriod(fiscal_year=year, raw=str(year)),
        bundle=_bundle(),
        resolver_source=_resolver(),
        user_agent="Test test@example.com",
    )


def test_graph_version() -> None:
    graph = adapt_to_graph(_packet())
    assert graph["graph_version"] == GRAPH_VERSION


def test_returns_dict_with_nodes_and_edges() -> None:
    graph = adapt_to_graph(_packet())
    assert isinstance(graph, dict)
    assert "nodes" in graph
    assert "edges" in graph


def test_vendor_node_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_VENDOR in types


def test_document_node_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_DOCUMENT in types


def test_evidence_nodes_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_EVIDENCE in types


def test_claim_nodes_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_CLAIM in types


def test_assessment_node_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_ASSESSMENT in types


def test_every_node_has_required_fields() -> None:
    graph = adapt_to_graph(_packet())
    for node in graph["nodes"]:
        assert "node_id" in node
        assert "node_type" in node
        assert "label" in node
        assert "metadata" in node


def test_every_edge_has_required_fields() -> None:
    graph = adapt_to_graph(_packet())
    for edge in graph["edges"]:
        assert "edge_type" in edge
        assert "source_id" in edge
        assert "target_id" in edge
        assert "metadata" in edge


def test_evidence_supports_claim_edge_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {e["edge_type"] for e in graph["edges"]}
    assert EDGE_SUPPORTS in types


def test_claim_used_in_assessment_edge_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {e["edge_type"] for e in graph["edges"]}
    assert EDGE_USED_IN in types


def test_document_contains_evidence_edge_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {e["edge_type"] for e in graph["edges"]}
    assert EDGE_CONTAINS in types


def test_vendor_resolved_to_edge_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {e["edge_type"] for e in graph["edges"]}
    assert EDGE_RESOLVED_TO in types


def test_assessment_yields_status_edge_present() -> None:
    graph = adapt_to_graph(_packet())
    types = {e["edge_type"] for e in graph["edges"]}
    assert EDGE_YIELDS in types


def test_nodes_are_sorted() -> None:
    graph = adapt_to_graph(_packet())
    keys = [(n["node_type"], n["node_id"]) for n in graph["nodes"]]
    assert keys == sorted(keys)


def test_edges_are_sorted() -> None:
    graph = adapt_to_graph(_packet())
    keys = [(e["edge_type"], e["source_id"], e["target_id"]) for e in graph["edges"]]
    assert keys == sorted(keys)


def test_deterministic_on_same_packet() -> None:
    """
    The adapter is deterministic given the same packet. Two adapts
    of one packet produce identical graphs. Different packets have
    different assessment IDs (by pipeline design), so the correct
    test uses one packet adapted twice, not two packets.
    """
    packet = _packet()
    g1 = adapt_to_graph(packet)
    g2 = adapt_to_graph(packet)
    ids1 = [n["node_id"] for n in g1["nodes"]]
    ids2 = [n["node_id"] for n in g2["nodes"]]
    assert ids1 == ids2


def test_unresolved_vendor_produces_assessment_node() -> None:
    graph = adapt_to_graph(_packet("Totally Fake Vendor Name"))
    types = {n["node_type"] for n in graph["nodes"]}
    assert NODE_ASSESSMENT in types


def test_missing_evidence_node_present_for_abstention() -> None:
    graph = adapt_to_graph(_packet("Totally Fake Vendor Name"))
    types = {n["node_type"] for n in graph["nodes"]}
    assert "missing_evidence" in types
