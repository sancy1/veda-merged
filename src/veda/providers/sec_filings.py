"""
File: src/veda/providers/sec_filings.py
Title: SEC Filing Providers
Layer: Provider retrieval layer
Status: Merged prototype foundation — Phase 4

Purpose
-------
Retrieves raw content for a specifically identified SEC filing using
CIK, accession number, filing form, and passage hint.

Public classes
--------------
SECFilingsProvider
FixtureSECFilingsProvider

Network policy
--------------
The live provider requires a non-empty SEC User-Agent and retries only
once for timeouts and HTTP 5xx responses. The fixture provider performs
no network I/O.
"""

from __future__ import annotations

from typing import Optional

import httpx

from veda.providers.base import EvidenceProvider
from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import ProviderStatus, SourceType


SEC_FILING_DOCUMENT_URL = (
    "https://www.sec.gov/Archives/edgar/data/"
    "{cik_no_zeros}/{accn_no_dashes}/{accn}-index.htm"
)
TIMEOUT_SECONDS = 30.0


def _normalize_cik(value: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.isdigit() or len(text) > 10:
        return None
    return text.zfill(10)


def _missing_identifier(request: ProviderRequest) -> Optional[str]:
    if not request.cik:
        return "cik"
    if not request.accession_number:
        return "accession_number"
    if not request.filing_form:
        return "filing_form"
    if not request.field_or_passage_hint:
        return "field_or_passage_hint"
    return None


def _result(
    provider: EvidenceProvider,
    status: ProviderStatus,
    *,
    raw_records: list[dict] | None = None,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> ProviderResult:
    return ProviderResult(
        status=status,
        source_type=provider.source_type,
        source_name=provider.source_name,
        is_fixture=provider.is_fixture,
        raw_records=raw_records or [],
        error_message=error_message,
        retrieval_metadata=metadata or {},
    )


class SECFilingsProvider(EvidenceProvider):
    def __init__(self, user_agent: str) -> None:
        if not isinstance(user_agent, str):
            raise ValueError(
                "SECFilingsProvider requires a non-empty user_agent"
            )
        stripped = user_agent.strip()
        if not stripped:
            raise ValueError(
                "SEC Filings requires a User-Agent of the form "
                "'Name email@example.com'. The supplied value is empty. "
                "SEC rejects requests without a descriptive User-Agent."
            )
        if "@" not in stripped or "." not in stripped.split("@")[-1]:
            raise ValueError(
                "SEC Filings requires a User-Agent that contains a "
                "name and a contact email (e.g. 'Jane Doe jane@example.com'). "
                f"The supplied value {stripped!r} does not appear to contain "
                "an email address. SEC rejects requests without one."
            )
        self._user_agent = stripped

    @property
    def source_type(self) -> SourceType:
        return SourceType.SEC_FILING

    @property
    def source_name(self) -> str:
        return "SEC Filings"

    @property
    def is_fixture(self) -> bool:
        return False

    def retrieve(self, request: ProviderRequest) -> ProviderResult:
        missing = _missing_identifier(request)
        if missing is not None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message=f"SECFilingsProvider requires request.{missing}",
            )

        cik = _normalize_cik(request.cik or "")
        if cik is None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message="A valid numeric CIK is required",
            )

        accession = request.accession_number or ""
        url = SEC_FILING_DOCUMENT_URL.format(
            cik_no_zeros=str(int(cik)),
            accn_no_dashes=accession.replace("-", ""),
            accn=accession,
        )
        headers = {"User-Agent": self._user_agent}
        last_error = "SEC filing source unavailable after retry"
        last_status: int | None = None

        for attempt in range(2):
            try:
                with httpx.Client(
                    headers=headers,
                    timeout=TIMEOUT_SECONDS,
                ) as client:
                    response = client.get(url)

                last_status = response.status_code

                if response.status_code == 200:
                    body = response.text.strip()
                    if not body:
                        return _result(
                            self,
                            ProviderStatus.MALFORMED_RESPONSE,
                            error_message="SEC filing returned an empty body",
                            metadata={"url": url, "status_code": 200},
                        )

                    return _result(
                        self,
                        ProviderStatus.FOUND,
                        raw_records=[{
                            "text": body,
                            "accession_number": accession,
                            "filing_form": request.filing_form,
                            "field_or_passage_hint": (
                                request.field_or_passage_hint
                            ),
                            "url": url,
                        }],
                        metadata={"url": url, "status_code": 200},
                    )

                if response.status_code == 404:
                    return _result(
                        self,
                        ProviderStatus.NOT_FOUND,
                        error_message="SEC filing not found",
                        metadata={"url": url, "status_code": 404},
                    )

                if response.status_code == 429:
                    return _result(
                        self,
                        ProviderStatus.RATE_LIMITED,
                        error_message="SEC rate limit (429)",
                        metadata={"url": url, "status_code": 429},
                    )

                if 400 <= response.status_code < 500:
                    return _result(
                        self,
                        ProviderStatus.SOURCE_UNAVAILABLE,
                        error_message=f"SEC returned HTTP {response.status_code}",
                        metadata={"url": url, "status_code": response.status_code},
                    )

                last_error = f"SEC returned HTTP {response.status_code}"
                if attempt == 0:
                    continue

            except httpx.TimeoutException:
                last_error = "SEC filing request timed out"
                if attempt == 0:
                    continue
            except httpx.HTTPError as exc:
                last_error = f"SEC filing transport error: {exc}"
                break

        return _result(
            self,
            ProviderStatus.SOURCE_UNAVAILABLE,
            error_message=last_error,
            metadata={"url": url, "last_status_code": last_status},
        )


class FixtureSECFilingsProvider(EvidenceProvider):
    @property
    def source_type(self) -> SourceType:
        return SourceType.SEC_FILING

    @property
    def source_name(self) -> str:
        return "SEC Filings (fixture)"

    @property
    def is_fixture(self) -> bool:
        return True

    def retrieve(self, request: ProviderRequest) -> ProviderResult:
        import veda.providers.fixtures as fixtures

        missing = _missing_identifier(request)
        if missing is not None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message=f"FixtureSECFilingsProvider requires request.{missing}",
            )

        cik = _normalize_cik(request.cik or "")
        if cik is None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message="A valid numeric CIK is required",
            )

        key = (
            cik,
            request.accession_number,
            request.filing_form,
            request.field_or_passage_hint.strip(),
        )
        passage = fixtures.SEC_FILING_PASSAGES.get(key)

        if passage is None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message=f"No fixture passage for {key!r}",
            )

        return _result(
            self,
            ProviderStatus.FOUND,
            raw_records=[{
                "text": passage["text"],
                "section": passage.get("section"),
                "accession_number": request.accession_number,
                "filing_form": request.filing_form,
                "field_or_passage_hint": request.field_or_passage_hint,
            }],
        )
