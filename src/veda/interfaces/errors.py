# filename: src/veda/interfaces/errors.py
# title: Interface Error Taxonomy
# layer: Interface layer
# status: Phase 7 — Sub-phase 7B
# description:
#     Defines the typed errors raised by the interface layer.
#
#     The interface layer distinguishes two kinds of outcomes:
#
#         Failures    — the pipeline could not run. Config error,
#                       bundle build error, unexpected pipeline
#                       exception.
#
#         Outcomes    — the pipeline ran and produced a packet.
#                       Every one of the five assessment states
#                       (SUPPORTED, SUPPORTED_WITH_LIMITATIONS,
#                       CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE,
#                       REQUIRES_HUMAN_REVIEW) is an outcome.
#
#     An outcome is not an error. An abstention is a valid answer.
#     The CLI renders it and exits 0. The API returns HTTP 200.
#
#     Errors exist for the failure cases only.
#
# source:
#     AUTHORED — Phase 7 introduces this taxonomy.

from __future__ import annotations


class InterfaceError(Exception):
    """Base class for every interface-layer error."""


class InterfaceConfigError(InterfaceError):
    """
    Raised when the caller's configuration is invalid or requests a
    capability that is not available in the current phase.

    Examples:
        - extractor_mode="composite" (requires a live LLM adapter
          that is reserved for a later phase)
        - provider_mode="live" (reserved; Phase 7 accepts only
          "fixture")
        - invalid literal value for any mode field
    """


class BundleBuildError(InterfaceError):
    """
    Raised when the bundle builder cannot construct a valid
    ProviderBundle from the supplied configuration.

    Examples:
        - a required provider instance is missing
        - a live provider is requested but no user agent is available
    """


class PipelineError(InterfaceError):
    """
    Raised when run_assessment() raises an exception the interface
    layer cannot recover from.

    A PipelineError is distinct from an assessment outcome. An
    assessment outcome is a packet with an assessment_status. A
    PipelineError means no packet was produced at all.
    """


__all__ = [
    "InterfaceError",
    "InterfaceConfigError",
    "BundleBuildError",
    "PipelineError",
]