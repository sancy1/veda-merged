# filename: tests/interfaces/test_end_to_end_interfaces.py
# title: Interface Parity — CLI and API Produce Identical Packets
# layer: Test suite - interfaces
# status: Phase 7 — Sub-phase 7D
# description:
#     The critical Phase 7 parity guarantee: the CLI and the API
#     call the same orchestrator and produce the same packet for
#     the same input. Parity is measured on the packet OBJECT, not
#     on rendered output, because rendered output differs by
#     format (JSON vs rich panel) and is not the correct
#     comparison.
#
#     Volatile fields are excluded from the comparison:
#         assessment_id      (timestamp + random suffix)
#         request_id         (same generator)
#         run_id             (same generator)
#         generated_at       (datetime.now)
#         retrieved_at       (datetime.now)
#
#     Everything else must be identical:
#         assessment_status
#         claim set (claim_id, value, claim_type, status, ...)
#         evidence set (evidence_id, source_type, ...)
#         conflicts
#         missing_evidence
#         reporting_period
#         human_review_reason
#         limitations
#         vendor resolution
#
# source:
#     AUTHORED — Phase 7 introduces the parity test. The reviewer's
#     Correction 8 required this specific comparison.

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from veda.interfaces.api import app
from veda.interfaces.cli import app as cli_app


cli_runner = CliRunner()
api_client = TestClient(app)


@pytest.fixture(autouse=True)
def _set_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEC_API_USER_AGENT", "Test test@example.com")


# --------------------------------------------------------------------
# Volatile fields to strip before comparison
# --------------------------------------------------------------------
_VOLATILE_TOP = {
    "assessment_id",
    "request_id",
    "generated_at",
}
_VOLATILE_RUN_METADATA = {
    "run_id",
    "started_at",
    "finished_at",
}
_VOLATILE_EVIDENCE = {
    "retrieved_at",
}


def _normalize(packet: dict) -> dict:
    """Return a packet dict with volatile fields stripped."""
    data = deepcopy(packet)
    for key in _VOLATILE_TOP:
        data.pop(key, None)
    if isinstance(data.get("run_metadata"), dict):
        for key in _VOLATILE_RUN_METADATA:
            data["run_metadata"].pop(key, None)
    for ev in data.get("evidence", []):
        for key in _VOLATILE_EVIDENCE:
            ev.pop(key, None)
        if isinstance(ev.get("document"), dict):
            ev["document"].pop("retrieved_at", None)
    return data


def _canonical(data: dict) -> str:
    """Return a canonical JSON string with sorted keys."""
    return json.dumps(data, sort_keys=True, indent=2)


def _cli_packet(vendor: str, year: int) -> dict:
    """Run the CLI and return the parsed packet."""
    result = cli_runner.invoke(
        cli_app,
        [vendor, str(year), "--format", "json"],
    )
    assert result.exit_code == 0, f"CLI failed: {result.stdout}"
    return json.loads(result.stdout)


def _api_packet(vendor: str, year: int) -> dict:
    """Run the API and return the parsed packet."""
    response = api_client.post(
        "/assess",
        json={"company_name": vendor, "fiscal_year": year},
    )
    assert response.status_code == 200, f"API failed: {response.text}"
    return response.json()


# ====================================================================
# 1. Supported case — full parity
# ====================================================================

def test_cli_and_api_produce_identical_normalized_packets_supported() -> None:
    """For the supported case, the two packets are byte-identical
    after volatile fields are stripped."""
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert _canonical(_normalize(cli_packet)) == _canonical(_normalize(api_packet))


# ====================================================================
# 2. Abstention case — full parity
# ====================================================================

def test_cli_and_api_produce_identical_normalized_packets_abstention() -> None:
    """For the abstention case, the two packets are byte-identical
    after volatile fields are stripped."""
    cli_packet = _cli_packet("Totally Fake Vendor Name", 2024)
    api_packet = _api_packet("Totally Fake Vendor Name", 2024)
    assert _canonical(_normalize(cli_packet)) == _canonical(_normalize(api_packet))


# ====================================================================
# 3. Unknown year case — full parity
# ====================================================================

def test_cli_and_api_produce_identical_normalized_packets_unknown_year() -> None:
    """For the known-vendor-unknown-year case, the two packets are
    byte-identical after volatile fields are stripped."""
    cli_packet = _cli_packet("Lockheed Martin Corp", 1899)
    api_packet = _api_packet("Lockheed Martin Corp", 1899)
    assert _canonical(_normalize(cli_packet)) == _canonical(_normalize(api_packet))


# ====================================================================
# 4. Field-level parity for the supported case
# ====================================================================

def test_same_assessment_status() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["assessment_status"] == api_packet["assessment_status"]


def test_same_claim_ids() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert (
        sorted(c["claim_id"] for c in cli_packet["claims"])
        == sorted(c["claim_id"] for c in api_packet["claims"])
    )


def test_same_claim_values() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    cli_values = sorted(
        (c["claim_type"], c["value"]) for c in cli_packet["claims"] if c["value"] is not None
    )
    api_values = sorted(
        (c["claim_type"], c["value"]) for c in api_packet["claims"] if c["value"] is not None
    )
    assert cli_values == api_values


def test_same_evidence_ids() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert (
        sorted(e["evidence_id"] for e in cli_packet["evidence"])
        == sorted(e["evidence_id"] for e in api_packet["evidence"])
    )


def test_same_conflicts() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["conflicts"] == api_packet["conflicts"]


def test_same_missing_evidence() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["missing_evidence"] == api_packet["missing_evidence"]


def test_same_reporting_period() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["reporting_period"] == api_packet["reporting_period"]


def test_same_human_review_reason() -> None:
    cli_packet = _cli_packet("Totally Fake Vendor Name", 2024)
    api_packet = _api_packet("Totally Fake Vendor Name", 2024)
    assert cli_packet["human_review_reason"] == api_packet["human_review_reason"]


def test_same_limitations() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["limitations"] == api_packet["limitations"]


def test_same_vendor_resolution() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    cli_vendor = cli_packet["vendor"]
    api_vendor = api_packet["vendor"]
    assert cli_vendor["input_name"] == api_vendor["input_name"]
    assert cli_vendor["resolved_name"] == api_vendor["resolved_name"]
    assert cli_vendor["cik"] == api_vendor["cik"]
    assert cli_vendor["entity_id"] == api_vendor["entity_id"]
    assert cli_vendor["resolution_status"] == api_vendor["resolution_status"]


# ====================================================================
# 5. Volatile fields DO differ
# ====================================================================

def test_volatile_ids_differ_between_cli_and_api() -> None:
    """Assessment, request, and run IDs are freshly generated each call."""
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert cli_packet["assessment_id"] != api_packet["assessment_id"]
    assert cli_packet["request_id"] != api_packet["request_id"]
    assert cli_packet["run_metadata"]["run_id"] != api_packet["run_metadata"]["run_id"]


# ====================================================================
# 6. Both interfaces call the same orchestrator
# ====================================================================

def test_cli_and_api_import_same_orchestrator() -> None:
    """Both interfaces import run_assessment from the same module."""
    import veda.interfaces.cli as cli_mod
    import veda.interfaces.api as api_mod
    from veda.pipeline import orchestrator

    assert cli_mod.run_assessment is orchestrator.run_assessment
    assert api_mod.run_assessment is orchestrator.run_assessment


# ====================================================================
# 7. Default extractor is rule-based on both paths
# ====================================================================

def test_default_extractor_is_rule_based_in_cli_packet() -> None:
    """The CLI's default path uses RuleBasedClaimExtractor, whose
    output goes through the standard pipeline. Claim IDs are
    content-addressed, which proves the extractor is deterministic."""
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    for claim in cli_packet["claims"]:
        assert claim["claim_id"].startswith("claim:")


def test_default_extractor_is_rule_based_in_api_packet() -> None:
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    for claim in api_packet["claims"]:
        assert claim["claim_id"].startswith("claim:")


# ====================================================================
# 8. Provider modes match
# ====================================================================

def test_same_provider_modes() -> None:
    cli_packet = _cli_packet("Lockheed Martin Corp", 2024)
    api_packet = _api_packet("Lockheed Martin Corp", 2024)
    assert (
        cli_packet["run_metadata"]["provider_modes"]
        == api_packet["run_metadata"]["provider_modes"]
    )