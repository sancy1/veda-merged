"""
File: src/veda/normalization/filings.py
Title: SEC Filing Passage Normalizer
Layer: Normalization layer
Status: Merged prototype foundation — Phase 5
"""

from __future__ import annotations

from hashlib import sha256

from veda.normalization.evidence_ids import evidence_id_for
from veda.normalization.helpers import (
    cik_from_entity_id,
    make_document_id,
    provider_status_gate,
    validate_caller_entity_id,
    validate_requested_period,
)
from veda.providers.results import ProviderResult
from veda.shared.enums import (
    EvidenceCategory,
    ExtractionMethod,
    SourceType,
)
from veda.shared.models import (
    Evidence,
    EvidenceLocation,
    SourceDocument,
)
from veda.shared.periods import Period, RequestedPeriod


_HINT_TO_CATEGORY = {
    "subsidiary_relationship": EvidenceCategory.CORPORATE_RELATIONSHIP,
    "government_exposure": EvidenceCategory.GOVERNMENT_EXPOSURE,
    "customer_concentration": EvidenceCategory.CUSTOMER_CONCENTRATION,
}


def _form_slug(form: str) -> str:
    """Convert an SEC form into a valid document-type slug."""
    slug = form.strip().lower().replace("-", "")

    return "".join(
        character if character.isalnum() else "_"
        for character in slug
    )


def _content_hash(text: str) -> str:
    """Return a deterministic lowercase SHA-256 hash."""
    return sha256(text.encode("utf-8")).hexdigest()


def normalize_filing_passage(
    result: ProviderResult,
    *,
    entity_id: str,
    requested_period: RequestedPeriod,
) -> list[Evidence]:
    """Normalize valid SEC filing passages into Evidence objects."""
    validate_caller_entity_id(entity_id)
    validate_requested_period(requested_period)

    if provider_status_gate(result) is not None:
        return []

    if result.source_type != SourceType.SEC_FILING:
        return []

    period_label = f"FY{requested_period.fiscal_year}"
    output: list[Evidence] = []

    for record in result.raw_records:
        if not isinstance(record, dict):
            continue

        text = record.get("text")
        accession = record.get("accession_number")
        form = record.get("filing_form")
        hint = record.get("field_or_passage_hint")
        url = record.get("url")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                text,
                accession,
                form,
                hint,
            )
        ):
            continue

        try:
            form_slug = _form_slug(form)

            cik = cik_from_entity_id(entity_id)
            browse_url = (
                f"https://www.sec.gov/edgar/browse/?CIK={cik}"
                if cik is not None
                else None
            )

            document_id = make_document_id(
                "sec_edgar",
                form_slug,
                accession,
            )

            document = SourceDocument(
                doc_id=document_id,
                source_type=SourceType.SEC_FILING,
                doc_type=form_slug,
                title=f"SEC filing {accession}",
                url=url if isinstance(url, str) else None,
                retrieved_at=result.retrieved_at,
                is_fixture=result.is_fixture,
                content_hash=_content_hash(text),
                accession_number=accession,
                filing_form=form,
            )

            location = EvidenceLocation(
                field_or_passage=hint,
                source_url=url if isinstance(url, str) else None,
                source_reference=hint,
                section=record.get("section"),
            )

            evidence = Evidence(
                evidence_id=evidence_id_for(
                    SourceType.SEC_FILING,
                    entity_id,
                    period_label,
                    hint,
                    document_id,
                ),
                source_type=SourceType.SEC_FILING,
                source_name=result.source_name,
                document=document,
                location=location,
                entity_id=entity_id,
                reporting_period=Period(label=period_label),
                evidence_category=_HINT_TO_CATEGORY.get(
                    hint,
                    EvidenceCategory.GOVERNMENT_EXPOSURE,
                ),
                retrieval_method=(
                    ExtractionMethod.DETERMINISTIC_TEXT_EXTRACTION
                ),
                retrieved_at=result.retrieved_at,
                is_fixture=result.is_fixture,
                sec_browse_url=browse_url,
                accession_number=accession,
                form=form,
            )

        except Exception as exc:
            print(
                "SEC filing normalization skipped record: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        output.append(evidence)

    return output


__all__ = ["normalize_filing_passage"]