"""Diagnostic: print periods produced by the pipeline for a bare request."""
from veda.entity.resolver import FixtureEntityResolverSource
from veda.pipeline.orchestrator import ProviderBundle, run_assessment
from veda.providers.annual_reports import FixtureAnnualReportProvider
from veda.providers.sec_company_facts import FixtureSECCompanyFactsProvider
from veda.providers.sec_filings import FixtureSECFilingsProvider
from veda.providers.usaspending import FixtureUSAspendingProvider
from veda.shared.periods import RequestedPeriod

bundle = ProviderBundle(
    sec_company_facts=FixtureSECCompanyFactsProvider(),
    sec_filing=FixtureSECFilingsProvider(),
    usaspending=FixtureUSAspendingProvider(),
    annual_report=FixtureAnnualReportProvider(),
)
resolver = FixtureEntityResolverSource({
    "lockheed martin corp": [
        {"cik": 936468, "ticker": "LMT", "title": "LOCKHEED MARTIN CORP"},
    ],
})
requested = RequestedPeriod(fiscal_year=2024, raw="2024")

# Run the pipeline but bypass validation to see the raw packet.
import veda.pipeline.orchestrator as orch
orig = orch.validate_assessment
orch.validate_assessment = lambda x: None

packet = run_assessment(
    vendor_name="Lockheed Martin Corp",
    requested_period=requested,
    bundle=bundle,
    resolver_source=resolver,
    user_agent="Test test@example.com",
)

orch.validate_assessment = orig

print("Packet period:", packet.reporting_period)
print()
for c in packet.claims:
    print(f"Claim: {c.claim_id}")
    print(f"  type:        {c.claim_type}")
    print(f"  status:      {c.claim_status.value}")
    print(f"  period:      {c.reporting_period}")
    print(f"  period.start: {c.reporting_period.start}")
    print(f"  period.end:   {c.reporting_period.end}")
    print(f"  fiscal_year:  {c.reporting_period.fiscal_year()}")
    print(f"  evidence:    {c.evidence_ids}")
    print()

print("Evidence periods:")
for e in packet.evidence:
    print(f"  {e.evidence_id}")
    print(f"    category: {e.evidence_category.value}")
    print(f"    period:   {e.reporting_period}")
    print(f"    start:    {e.reporting_period.start}")
    print(f"    end:      {e.reporting_period.end}")