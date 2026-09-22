"""
File: src/veda/providers/usaspending.py
Title: USAspending Providers
Layer: Provider retrieval layer
Status: Merged prototype foundation — Phase 4

Purpose
-------
Retrieves bounded USAspending award records for a company and fiscal
year through either the live API or deterministic fixtures.

Public classes
--------------
USAspendingProvider
FixtureUSAspendingProvider

Network policy
--------------
The live provider sends the fiscal year as a query parameter and does
not send a User-Agent. It retries only once for timeouts and HTTP 5xx
responses. The fixture provider performs no network I/O.
"""

from __future__ import annotations

import httpx

from veda.providers.base import EvidenceProvider
from veda.providers.results import ProviderRequest, ProviderResult
from veda.shared.enums import ProviderStatus, SourceType


USASPENDING_SEARCH_URL = (
    "https://api.usaspending.gov/api/v2/search/spending_by_award/"
)
TIMEOUT_SECONDS = 30.0


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


def _fixture_key(request: ProviderRequest) -> str | None:
    if request.company_name and request.company_name.strip():
        return request.company_name.strip().lower()

    if (request.entity_id or "").endswith(":0000936468"):
        return "lockheed martin corp"

    return None


class USAspendingProvider(EvidenceProvider):
    @property
    def source_type(self) -> SourceType:
        return SourceType.USASPENDING

    @property
    def source_name(self) -> str:
        return "USAspending"

    @property
    def is_fixture(self) -> bool:
        return False

    def retrieve(self, request: ProviderRequest) -> ProviderResult:
        fiscal_year = request.requested_period.fiscal_year
        recipient = request.company_name or request.entity_id or ""

        payload = {
            "filters": {
                "recipient_search_text": [recipient],
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Awarding Agency",
                "Total Obligated Amount",
            ],
            "page": 1,
            "limit": 50,
            "sort": "Award Amount",
            "order": "desc",
        }
        params = {"fiscal_year": str(fiscal_year)}
        last_error = "USAspending source unavailable after retry"

        for attempt in range(2):
            try:
                with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                    response = client.post(
                        USASPENDING_SEARCH_URL,
                        params=params,
                        json=payload,
                    )

                if response.status_code == 200:
                    try:
                        body = response.json()
                    except ValueError:
                        return _result(
                            self,
                            ProviderStatus.MALFORMED_RESPONSE,
                            error_message="USAspending response was not valid JSON",
                        )

                    if not isinstance(body, dict):
                        return _result(
                            self,
                            ProviderStatus.MALFORMED_RESPONSE,
                            error_message="USAspending response was not a JSON object",
                        )

                    records = body.get("results", [])
                    if not isinstance(records, list):
                        return _result(
                            self,
                            ProviderStatus.MALFORMED_RESPONSE,
                            error_message="USAspending 'results' was not a list",
                        )

                    if not records:
                        return _result(
                            self,
                            ProviderStatus.NOT_FOUND,
                            error_message=(
                                f"No awards for fiscal year {fiscal_year}"
                            ),
                            metadata={"fiscal_year": fiscal_year},
                        )

                    return _result(
                        self,
                        ProviderStatus.FOUND,
                        raw_records=records,
                        metadata={"fiscal_year": fiscal_year},
                    )

                if response.status_code == 404:
                    return _result(
                        self,
                        ProviderStatus.NOT_FOUND,
                        error_message="USAspending endpoint returned 404",
                    )

                if response.status_code == 429:
                    return _result(
                        self,
                        ProviderStatus.RATE_LIMITED,
                        error_message="USAspending rate limit (429)",
                    )

                if 400 <= response.status_code < 500:
                    return _result(
                        self,
                        ProviderStatus.SOURCE_UNAVAILABLE,
                        error_message=f"USAspending returned HTTP {response.status_code}",
                    )

                last_error = f"USAspending returned HTTP {response.status_code}"
                if attempt == 0:
                    continue

            except httpx.TimeoutException:
                last_error = "USAspending request timed out"
                if attempt == 0:
                    continue
            except httpx.HTTPError as exc:
                last_error = f"USAspending transport error: {exc}"
                break

        return _result(
            self,
            ProviderStatus.SOURCE_UNAVAILABLE,
            error_message=last_error,
            metadata={"fiscal_year": fiscal_year},
        )


class FixtureUSAspendingProvider(EvidenceProvider):
    @property
    def source_type(self) -> SourceType:
        return SourceType.USASPENDING

    @property
    def source_name(self) -> str:
        return "USAspending (fixture)"

    @property
    def is_fixture(self) -> bool:
        return True

    def retrieve(self, request: ProviderRequest) -> ProviderResult:
        import veda.providers.fixtures as fixtures

        key = _fixture_key(request)
        fiscal_year = request.requested_period.fiscal_year

        if key is None:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message=(
                    "FixtureUSAspendingProvider requires company_name "
                    "or a supported entity_id"
                ),
            )

        awards = fixtures.USASPENDING_AWARDS_BY_NAME.get(key, [])
        filtered = [
            record
            for record in awards
            if record.get("fiscal_year") == fiscal_year
        ]

        if not filtered:
            return _result(
                self,
                ProviderStatus.NOT_FOUND,
                error_message=(
                    f"No fixture awards for {key!r} "
                    f"in fiscal year {fiscal_year}"
                ),
                metadata={"fiscal_year": fiscal_year},
            )

        return _result(
            self,
            ProviderStatus.FOUND,
            raw_records=filtered,
            metadata={"fiscal_year": fiscal_year},
        )
