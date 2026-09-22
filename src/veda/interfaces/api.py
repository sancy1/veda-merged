# filename: src/veda/interfaces/api.py
# title: HTTP API Surface
# layer: Interface layer
# status: Phase 7 — Sub-phase 7C
# description:
#     The VEDA FastAPI surface. Exposes the pipeline over HTTP.

#     Routes:
#
#         GET  /health          -> {"status": "ok"}
#         POST /assess          -> full assessment packet as JSON
#         GET  /                -> serves static/dashboard.html
#         GET  /static/*        -> static assets
#         GET  /openapi.json    -> automatic OpenAPI schema
#
#     The /assess endpoint accepts a request body with the vendor
#     name and fiscal year, plus optional mode overrides. Every
#     assessment outcome returns HTTP 200. The packet itself carries
#     the status. An abstention is a valid answer, not an HTTP
#     error. HTTP status codes reflect transport and configuration
#     errors only.
#
#     Provider mode is fixture-only in Phase 7. Requesting
#     provider_mode="live" returns HTTP 500 with a config error
#     message. Requesting extractor_mode="composite" returns HTTP 500
#     with a config error message.
#
#     Startup:
#         uvicorn veda.interfaces.api:app --reload
#
# source:
#     MERGED — the API shape comes from veda's app/api.py. That
#     prototype exposed /assess, /assess/supported, /assess/conflict,
#     /assess/insufficient, /assess/subsidiary. The merged version
#     exposes one /assess endpoint that accepts mode overrides in the
#     body, plus the health and dashboard routes. The pinned routes
#     are not needed because the request body already selects the
#     case.
#
# notes:
#     - No business logic. The API constructs an InterfaceConfig,
#       calls the same build_bundle / build_resolver / build_extractor
#       the CLI calls, calls run_assessment, and returns the packet.
#     - The API never imports a provider directly. It goes through
#       the interface layer.
#     - The API never constructs a model SDK. It never reads an API
#       key. The default path is entirely offline.

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from veda.interfaces.bundle_builder import (
    build_bundle,
    build_extractor,
    build_resolver,
)
from veda.interfaces.config import InterfaceConfig
from veda.interfaces.errors import (
    BundleBuildError,
    InterfaceConfigError,
    PipelineError,
)
from veda.pipeline.orchestrator import run_assessment
from veda.shared.models import Assessment
from veda.shared.periods import RequestedPeriod


# --------------------------------------------------------------------
# Static file paths
# --------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
STATIC_DIR = _HERE / "static"
DASHBOARD_PATH = STATIC_DIR / "dashboard.html"


# --------------------------------------------------------------------
# The FastAPI application
# --------------------------------------------------------------------
app = FastAPI(
    title="VEDA",
    description=(
        "Vendor Economic Dependency Assessment. "
        "A provenance-aware evidence pipeline."
    ),
    version="0.1.0",
)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------
# Request body
# --------------------------------------------------------------------
class AssessRequest(BaseModel):
    """
    Request body for POST /assess.

    The two required fields mirror the CLI's two arguments. The
    optional mode fields default to the same offline-safe values the
    CLI uses.
    """

    company_name: str = Field(..., min_length=1)
    fiscal_year: int
    resolver_mode: Literal["fixture", "live"] = "fixture"
    provider_mode: Literal["fixture", "live"] = "fixture"
    extractor_mode: Literal["rule_based", "composite"] = "rule_based"
    sec_filing_accession_number: Optional[str] = None
    sec_filing_form: Optional[str] = None
    sec_filing_passage_hint: Optional[str] = None


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    """Liveness check."""
    return {"status": "ok"}


@app.post("/assess", response_model=None)
def assess(body: AssessRequest, request: Request) -> JSONResponse:
    """
    Run the pipeline for one vendor and one fiscal year.

    Returns the full assessment packet as JSON.

    Every assessment outcome (SUPPORTED, SUPPORTED_WITH_LIMITATIONS,
    CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, REQUIRES_HUMAN_REVIEW)
    returns HTTP 200. The packet carries the status.

    Configuration errors return HTTP 500 with a clear message.
    """
    # 1. Resolve the user agent. Priority order:
    #    a. The X-SEC-User-Agent header sent by the dashboard.
    #    b. The SEC_API_USER_AGENT environment variable.
    #    c. An empty string, which the pipeline treats as "not provided".
    # The pipeline validates the value only when live mode is requested.
    header_ua = request.headers.get("X-SEC-User-Agent", "").strip()
    env_ua = os.environ.get("SEC_API_USER_AGENT", "").strip()
    user_agent = header_ua or env_ua or ""

    # 2. Build the configuration.
    try:
        config = InterfaceConfig(
            user_agent=user_agent,
            resolver_mode=body.resolver_mode,
            provider_mode=body.provider_mode,
            extractor_mode=body.extractor_mode,
            sec_filing_accession_number=body.sec_filing_accession_number,
            sec_filing_form=body.sec_filing_form,
            sec_filing_passage_hint=body.sec_filing_passage_hint,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid configuration: {exc}",
        )

    # 3. Build the bundle, resolver, and extractor.
    try:
        bundle = build_bundle(config)
        resolver_source = build_resolver(config)
        claim_extractor = build_extractor(config)
    except InterfaceConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except BundleBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 4. Run the pipeline.
    try:
        requested = RequestedPeriod(
            fiscal_year=body.fiscal_year,
            raw=str(body.fiscal_year),
        )
        packet = run_assessment(
            vendor_name=body.company_name,
            requested_period=requested,
            bundle=bundle,
            resolver_source=resolver_source,
            user_agent=config.user_agent,
            extractor=claim_extractor,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {type(exc).__name__}: {exc}",
        )

    # 5. Return the packet. Any assessment status is 200.
    return JSONResponse(
        content=packet.model_dump(mode="json"),
        status_code=200,
    )


@app.get("/")
def dashboard() -> FileResponse:
    """Serve the static dashboard if it exists."""
    if not DASHBOARD_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Dashboard is not available.",
        )
    return FileResponse(str(DASHBOARD_PATH))


__all__ = ["app", "AssessRequest"]