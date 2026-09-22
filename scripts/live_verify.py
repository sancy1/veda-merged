# filename: scripts/live_verify.py
# title: Live Provider Verification
# layer: Verification tooling
# status: Phase 7 verification track
# description:
#     Runs the merged VEDA pipeline against real SEC and USAspending
#     endpoints. Not part of the pytest suite. Invoked manually.
#
#     Without optional filing arguments:
#         Structured SEC Company Facts only.
#
#     With --accession, --form, and --hint:
#         Structured facts PLUS a live SEC filing passage fetch.
#         The pipeline produces a narrative claim derived from the
#         actual filing index page on www.sec.gov.
#
# usage:
#     python scripts/live_verify.py "Lockheed Martin Corp" 2024
#     python scripts/live_verify.py "Lockheed Martin Corp" 2024 --accession 0000936468-25-000009 --form 10-K --hint revenues
#
# source:
#     AUTHORED - Phase 7 live-verification track.

from __future__ import annotations

import os
import sys

from veda.entity.resolver import LiveEntityResolverSource
from veda.interfaces.bundle_builder import build_bundle
from veda.interfaces.config import InterfaceConfig
from veda.pipeline.orchestrator import run_assessment
from veda.shared.periods import RequestedPeriod


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 3:
        print("Usage: python scripts/live_verify.py <vendor> <year> [options]")
        print()
        print("Options:")
        print("  --accession ACCN   SEC accession number (e.g. 0000936468-25-000009)")
        print("  --form FORM        SEC form (e.g. 10-K, 10-Q)")
        print("  --hint HINT        Passage hint (e.g. revenues, government_exposure)")
        sys.exit(2)

    vendor = argv[1]
    try:
        year = int(argv[2])
    except ValueError:
        print(f"Year must be an integer, got {argv[2]!r}")
        sys.exit(2)

    accession = None
    form = None
    hint = None

    i = 3
    while i < len(argv):
        token = argv[i]
        if token == "--accession" and i + 1 < len(argv):
            accession = argv[i + 1]
            i += 2
        elif token == "--form" and i + 1 < len(argv):
            form = argv[i + 1]
            i += 2
        elif token == "--hint" and i + 1 < len(argv):
            hint = argv[i + 1]
            i += 2
        else:
            print(f"Unknown argument: {token}")
            sys.exit(2)

    return {
        "vendor": vendor,
        "year": year,
        "accession": accession,
        "form": form,
        "hint": hint,
    }


def main() -> int:
    args = _parse_args(sys.argv)
    vendor = args["vendor"]
    year = args["year"]
    accession = args["accession"]
    form = args["form"]
    hint = args["hint"]

    user_agent = os.environ.get("SEC_API_USER_AGENT", "")
    if not user_agent.strip() or "not set" in user_agent.lower():
        print("SEC_API_USER_AGENT must be set to a real User-Agent.")
        print("Example: $env:SEC_API_USER_AGENT = 'Your Name your_email@example.com'")
        return 2

    print(f"=== LIVE verification: {vendor!r} {year} ===")
    print(f"User-Agent: {user_agent}")
    if accession:
        print(f"Filing accession: {accession}")
        print(f"Filing form:      {form}")
        print(f"Passage hint:     {hint}")
    print()

    config = InterfaceConfig(
        user_agent=user_agent,
        provider_mode="live",
        resolver_mode="live",
        extractor_mode="rule_based",
        sec_filing_accession_number=accession,
        sec_filing_form=form,
        sec_filing_passage_hint=hint,
    )

    try:
        bundle = build_bundle(config)
    except Exception as exc:
        print(f"Bundle error: {exc}")
        return 3

    resolver = LiveEntityResolverSource(user_agent)

    print("Running pipeline against live endpoints...")
    print()

    try:
        packet = run_assessment(
            vendor_name=vendor,
            requested_period=RequestedPeriod(fiscal_year=year, raw=str(year)),
            bundle=bundle,
            resolver_source=resolver,
            user_agent=user_agent,
        )
    except Exception as exc:
        print(f"Pipeline error: {type(exc).__name__}: {exc}")
        return 4

    print("=== Full JSON packet ===")
    print(packet.model_dump_json(indent=2))
    print()

    print("=== Summary ===")
    print(f"Status:      {packet.assessment_status.value}")
    print(f"Vendor:      {packet.vendor.input_name} -> {packet.vendor.resolved_name}")
    print(f"CIK:         {packet.vendor.cik}")
    print(f"Period:      {packet.reporting_period.label}")
    print(f"Claims:      {len(packet.claims)}")
    print(f"Evidence:    {len(packet.evidence)}")
    print(f"Conflicts:   {len(packet.conflicts)}")
    print(f"Missing:     {len(packet.missing_evidence)}")
    print()
    for claim in packet.claims:
        unit = claim.unit or ""
        print(f"  [{claim.claim_status.value}] {claim.claim_type} = {claim.value} {unit}")
    print()
    print("Evidence ledger:")
    for ev in packet.evidence:
        src = ev.source_type.value
        fixture = "fixture" if ev.is_fixture else "LIVE"
        print(f"  [{fixture:7s}] {src:20s} {ev.evidence_id}")
    print()
    print("Provider modes:")
    for name, mode in sorted(packet.run_metadata.provider_modes.items()):
        print(f"  {name}: {mode}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
