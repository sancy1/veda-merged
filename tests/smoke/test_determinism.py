# filename: tests/smoke/test_determinism.py
# title: Determinism Test — Byte-Identical Packet Structure
# layer: Test suite - smoke
# status: Phase 1-6 test recovery
# description:
#     Proves the pipeline is deterministic. Two runs with the same
#     inputs produce packets that differ ONLY in the volatile ID
#     fields (assessment_id, request_id, run_metadata.run_id,
#     generated_at, retrieved_at). Every content field — claims,
#     evidence, periods, statuses, conflicts, missing_evidence — is
#     byte-identical.
#
#     This is the assertion that makes the smoke test reproducible.
#     Without determinism, the smoke test would produce different
#     output on every run and could not serve as a frozen baseline.
#
# source:
#     AUTHORED - Phase 6 had no saved determinism test before recovery
#     began. The inline Phase 6 smoke test was run once; this file
#     asserts that running it twice produces the same result.
#
# notes:
#     - The volatile fields are:
#         assessment_id        (timestamp + random suffix)
#         request_id           (same generator)
#         run_metadata.run_id  (same generator)
#         generated_at         (datetime.now)
#         retrieved_at on each Evidence (datetime.now)
#         retrieved_at on each ProviderResult (datetime.now)
#     - The canonical content fields are:
#         claim_id             (content-addressed)
#         evidence_id          (content-addressed)
#         conflict_id          (content-addressed)
#         all period fields
#         all status fields
#         all narrative fields
#     - The comparison is done by serializing each packet to a
#       canonical JSON and comparing after stripping volatile keys.

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date

import pytest

from veda.entity.resolver import FixtureEntityResolverSource
from veda.pipeline.orchestrator import ProviderBundle, run_assessment
from veda.providers.annual_reports import FixtureAnnualReportProvider
from veda.providers.sec_company_facts import FixtureSECCompanyFactsProvider
from veda.providers.sec_filings import FixtureSECFilingsProvider
from veda.providers.usaspending import FixtureUSAspendingProvider
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------
LOCKHEED_ENTRIES = {
    "lockheed martin corp": [
        {"cik": 936468, "ticker": "LMT", "title": "LOCKHEED MARTIN CORP"},
    ],
}


def _bundle() -> ProviderBundle:
    return ProviderBundle(
        sec_company_facts=FixtureSECCompanyFactsProvider(),
        sec_filing=FixtureSECFilingsProvider(),
        usaspending=FixtureUSAspendingProvider(),
        annual_report=FixtureAnnualReportProvider(),
        sec_filing_accession_number="0000936468-25-000009",
        sec_filing_form="10-K",
        sec_filing_passage_hint="revenues",
    )


def _resolver() -> FixtureEntityResolverSource:
    return FixtureEntityResolverSource(LOCKHEED_ENTRIES)


def _requested() -> RequestedPeriod:
    return RequestedPeriod(
        fiscal_year=2024,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        raw="2024",
    )


def _run_once():
    return run_assessment(
        vendor_name="Lockheed Martin Corp",
        requested_period=_requested(),
        bundle=_bundle(),
        resolver_source=_resolver(),
        user_agent="Test test@example.com",
    )


# --------------------------------------------------------------------
# Stripping volatile fields
# --------------------------------------------------------------------
VOLATILE_TOP_LEVEL = {
    "assessment_id",
    "request_id",
    "generated_at",
}

VOLATILE_RUN_METADATA = {
    "run_id",
    "started_at",
    "finished_at",
}

VOLATILE_EVIDENCE = {
    "retrieved_at",
}


def _canonicalize(packet) -> dict:
    """
    Serialize a packet to a canonical dict with volatile fields
    stripped, so two runs can be compared for content equality.
    """
    raw = packet.model_dump(mode="json")
    data = deepcopy(raw)

    for key in VOLATILE_TOP_LEVEL:
        data.pop(key, None)

    if "run_metadata" in data and isinstance(data["run_metadata"], dict):
        for key in VOLATILE_RUN_METADATA:
            data["run_metadata"].pop(key, None)

    for ev in data.get("evidence", []):
        for key in VOLATILE_EVIDENCE:
            ev.pop(key, None)
        if isinstance(ev.get("document"), dict):
            ev["document"].pop("retrieved_at", None)

    return data


def _canonical_json(packet) -> str:
    return json.dumps(_canonicalize(packet), sort_keys=True, indent=2)


# ====================================================================
# 1. Content determinism
# ====================================================================

def test_two_runs_produce_identical_canonical_content() -> None:
    """The stripped packets must be byte-identical."""
    a = _run_once()
    b = _run_once()
    assert _canonical_json(a) == _canonical_json(b)


def test_two_runs_produce_same_assessment_status() -> None:
    a = _run_once()
    b = _run_once()
    assert a.assessment_status == b.assessment_status


def test_two_runs_produce_same_claim_ids() -> None:
    a = _run_once()
    b = _run_once()
    assert sorted(c.claim_id for c in a.claims) == sorted(c.claim_id for c in b.claims)


def test_two_runs_produce_same_evidence_ids() -> None:
    a = _run_once()
    b = _run_once()
    assert sorted(e.evidence_id for e in a.evidence) == sorted(e.evidence_id for e in b.evidence)


def test_two_runs_produce_same_conflict_ids() -> None:
    a = _run_once()
    b = _run_once()
    assert sorted(c.conflict_id for c in a.conflicts) == sorted(c.conflict_id for c in b.conflicts)


def test_two_runs_produce_same_claim_values() -> None:
    a = _run_once()
    b = _run_once()
    values_a = sorted((c.claim_type, c.value) for c in a.claims if c.value is not None)
    values_b = sorted((c.claim_type, c.value) for c in b.claims if c.value is not None)
    assert values_a == values_b


def test_two_runs_produce_same_period() -> None:
    a = _run_once()
    b = _run_once()
    assert a.reporting_period.start == b.reporting_period.start
    assert a.reporting_period.end == b.reporting_period.end
    assert a.reporting_period.label == b.reporting_period.label


def test_two_runs_produce_same_vendor_resolution() -> None:
    a = _run_once()
    b = _run_once()
    assert a.vendor.resolution_status == b.vendor.resolution_status
    assert a.vendor.cik == b.vendor.cik
    assert a.vendor.entity_id == b.vendor.entity_id


# ====================================================================
# 2. Volatile fields differ
# ====================================================================

def test_two_runs_produce_different_assessment_ids() -> None:
    a = _run_once()
    b = _run_once()
    assert a.assessment_id != b.assessment_id


def test_two_runs_produce_different_run_ids() -> None:
    a = _run_once()
    b = _run_once()
    assert a.run_metadata.run_id != b.run_metadata.run_id


# ====================================================================
# 3. Ordering is deterministic
# ====================================================================

def test_claims_are_sorted_by_claim_id() -> None:
    packet = _run_once()
    ids = [c.claim_id for c in packet.claims]
    assert ids == sorted(ids)


def test_evidence_is_sorted_by_evidence_id() -> None:
    packet = _run_once()
    ids = [e.evidence_id for e in packet.evidence]
    assert ids == sorted(ids)


def test_missing_evidence_is_sorted() -> None:
    packet = _run_once()
    keys = [(m.claim_type, m.reason.value) for m in packet.missing_evidence]
    assert keys == sorted(keys)


def test_limitations_are_sorted() -> None:
    packet = _run_once()
    assert packet.limitations == sorted(packet.limitations)


# ====================================================================
# 4. Cross-run stability under repeated invocation
# ====================================================================

def test_three_runs_produce_same_canonical_content() -> None:
    """
    A third run confirms the determinism holds beyond the two-run
    case. Some nondeterminism can appear only on the third iteration.
    """
    a = _run_once()
    b = _run_once()
    c = _run_once()
    assert _canonical_json(a) == _canonical_json(b)
    assert _canonical_json(b) == _canonical_json(c)


# ====================================================================
# 5. Canonical form is stable across serialization
# ====================================================================

def test_canonical_json_round_trips() -> None:
    """
    The canonical JSON is valid JSON and re-serializing it produces
    the same string. This proves the canonicalization is
    deterministic.
    """
    packet = _run_once()
    s1 = _canonical_json(packet)
    parsed = json.loads(s1)
    s2 = json.dumps(parsed, sort_keys=True, indent=2)
    assert s1 == s2


def test_canonical_json_contains_no_volatile_fields() -> None:
    packet = _run_once()
    s = _canonical_json(packet)
    data = json.loads(s)
    for key in VOLATILE_TOP_LEVEL:
        assert key not in data
    for key in VOLATILE_RUN_METADATA:
        assert key not in data.get("run_metadata", {})