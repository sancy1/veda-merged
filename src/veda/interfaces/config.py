# filename: src/veda/interfaces/config.py
# title: Interface Configuration
# layer: Interface layer
# status: Phase 7 — Sub-phase 7B
# description:
#     Defines the InterfaceConfig model. It gathers every decision
#     the interface layer must make before calling the pipeline.
#
#     Every default is offline:
#
#         resolver_mode  = "fixture"
#         provider_mode  = "fixture"
#         extractor_mode = "rule_based"
#
#     Running the CLI with no arguments beyond vendor and year
#     produces a valid packet using only fixtures and rule-based
#     extraction. No network. No API key. No model call.
#
#     Provider mode is fixture-only in Phase 7. Live provider mode
#     is reserved for a later phase and is rejected at config
#     construction.
#
#     Extractor mode accepts "rule_based". "composite" is
#     syntactically valid but is rejected at bundle construction,
#     because a composite containing the disabled LLM stub cannot
#     produce a packet.
#
# source:
#     AUTHORED — Phase 7 introduces this configuration model.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InterfaceConfig(BaseModel):
    """
    Immutable configuration for one interface-layer invocation.

    Fields
    ------
    user_agent : str
        SEC User-Agent. Required for future live-provider
        construction. Not used by the fixture path.

    resolver_mode : Literal["fixture", "live"]
        Which entity-resolution source to use.
        Default "fixture" for reproducible offline operation.

    provider_mode : Literal["fixture"]
        Which provider set to construct.
        Phase 7 accepts only "fixture". Live provider mode is
        reserved for a later phase.

    extractor_mode : Literal["rule_based", "composite"]
        Which claim extractor to construct.
        "rule_based" is available.
        "composite" is syntactically valid but the bundle builder
        rejects it because the LLM stub is disabled.

    output_format : Literal["json", "human", "both"]
        What the CLI prints.
        Default "both".

    output_path : str | None
        When set, the CLI writes the JSON packet to this path.

    sec_filing_accession_number : str | None
        Optional SEC filing accession number for the fixture
        filing provider's passage lookup.

    sec_filing_form : str | None
        Optional SEC form (10-K, 10-Q, etc.).

    sec_filing_passage_hint : str | None
        Optional passage hint (e.g., "revenues").

    Frozen
    ------
    The model is immutable. Every field is read-only after
    construction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_agent: str = Field(
        default="",
        description=(
            "SEC User-Agent. Required for live provider construction. "
            "May be empty when provider_mode is 'fixture'."
        ),
    )

    resolver_mode: Literal["fixture", "live"] = Field(
        default="fixture",
        description="Entity-resolution source.",
    )

    provider_mode: Literal["fixture", "live"] = Field(
        default="fixture",
        description=(
            "Provider set. 'fixture' uses deterministic offline data. "
            "'live' fetches from real SEC and USAspending endpoints. "
            "Live mode requires a non-empty user_agent."
        ),
    )

    extractor_mode: Literal["rule_based", "composite"] = Field(
        default="rule_based",
        description="Claim extractor. 'composite' requires a live LLM adapter.",
    )

    output_format: Literal["json", "human", "both"] = Field(
        default="both",
        description="What the CLI prints.",
    )

    output_path: str | None = Field(
        default=None,
        description="Optional file path for the JSON packet.",
    )

    sec_filing_accession_number: str | None = Field(
        default=None,
        description="Optional SEC filing accession number.",
    )

    sec_filing_form: str | None = Field(
        default=None,
        description="Optional SEC form (10-K, 10-Q, ...).",
    )

    sec_filing_passage_hint: str | None = Field(
        default=None,
        description="Optional passage hint.",
    )


__all__ = ["InterfaceConfig"]