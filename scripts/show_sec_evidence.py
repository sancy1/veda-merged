"""Show the SEC Company Facts evidence fields after normalization."""
from veda.normalization.sec import normalize_company_facts
from veda.providers.results import ProviderResult
from veda.providers.fixtures import SEC_COMPANY_FACTS_BY_CIK
from veda.shared.enums import ProviderStatus, SourceType
from veda.shared.periods import RequestedPeriod

payload = SEC_COMPANY_FACTS_BY_CIK["0000936468"]
result = ProviderResult(
    status=ProviderStatus.FOUND,
    source_type=SourceType.SEC_COMPANY_FACTS,
    source_name="SEC Company Facts",
    is_fixture=True,
    raw_records=[payload],
)
requested = RequestedPeriod(fiscal_year=2024, start=None, end=None, raw="2024")

evidence = normalize_company_facts(
    result,
    entity_id="entity:sec_edgar:vendor:0000936468",
    requested_period=requested,
)

for e in evidence:
    print(f"evidence_id:        {e.evidence_id}")
    print(f"accession_number:   {e.accession_number}")
    print(f"form:               {e.form}")
    print(f"xbrl_tag:           {e.xbrl_tag}")
    print(f"sec_browse_url:     {e.sec_browse_url}")
    print(f"location.source_url: {e.location.source_url if e.location else None}")
    print(f"location.source_ref: {e.location.source_reference if e.location else None}")
    print(f"document:           {e.document}")