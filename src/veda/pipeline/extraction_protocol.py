# filename: src/veda/pipeline/extraction_protocol.py
# title: Claim Extraction Protocol
# layer: Pipeline layer
# status: Phase 7 — Sub-phase 7A
# description:
#     Defines the ClaimExtractor abstract base class. This is the
#     single contract the orchestrator depends on when converting
#     Evidence into Claim objects.
#
#     Three concrete implementations satisfy this contract:
#
#         RuleBasedClaimExtractor  — wraps the deterministic
#                                     extract_claims() function.
#         LLMClaimExtractor        — disabled contract stub, reserved
#                                     for a later phase. Never
#                                     constructed by the default
#                                     configuration.
#         CompositeClaimExtractor  — combines two extractors into one,
#                                     deduplicating by claim_id.
#
#     The orchestrator receives exactly one ClaimExtractor and calls
#     extract(evidence). It does not know which implementation is
#     active. This is what makes the LLM an opt-in addition rather
#     than a rewrite of the pipeline.
#
#     The pipeline's default configuration constructs
#     RuleBasedClaimExtractor only. No LLM is constructed. No model
#     SDK is imported. No API key is read. No model call is made.
#     The deterministic Phase 6 behavior is unchanged.
#
# source:
#     AUTHORED — Phase 7 introduces this seam. Neither the personal
#     prototype nor the original veda prototype had a pluggable claim
#     extractor. Both called extract_claims() directly. The seam
#     exists so a future LLM adapter can be added without touching
#     the orchestrator or the frozen deterministic stages.
#
# notes:
#     - Three abstract members, mirroring EvidenceProvider's shape:
#         extraction_method_name   str
#         is_llm_backed            bool
#         extract                  Evidence list -> Claim list
#     - The ABC is not instantiable. A subclass missing any member
#       fails at construction.
#     - The ABC imports no model SDK. It imports only the shared
#       contract types.

from __future__ import annotations

from abc import ABC, abstractmethod

from veda.shared.models import Claim, Evidence


class ClaimExtractor(ABC):
    """
    Convert Evidence objects into Claim objects.

    Contract
    --------
    Every extractor must:

      - Return a list of Claim objects.
      - Reference at least one evidence_id on each SUPPORTED claim
        (the Claim model enforces this on construction).
      - Not mutate the input Evidence list.
      - Not raise for ordinary evidence that produces no claim; skip
        it and continue.

    The orchestrator calls extract(evidence) once. It does not
    inspect the concrete class, and it does not combine multiple
    extractors itself. Combination is the CompositeClaimExtractor's
    responsibility.
    """

    @property
    @abstractmethod
    def extraction_method_name(self) -> str:
        """
        Human-readable name for the extraction method.

        Used in run metadata and in claim-level provenance. Examples:
            "rule_based"
            "llm"
            "composite(rule_based+llm)"
        """

    @property
    @abstractmethod
    def is_llm_backed(self) -> bool:
        """
        Whether this extractor uses a large language model.

        False for RuleBasedClaimExtractor. True for LLMClaimExtractor.
        True for any CompositeClaimExtractor containing an
        LLM-backed side.

        The pipeline uses this flag for provenance labeling only. It
        never changes the deterministic validation, conflict
        detection, or assessment.
        """

    @abstractmethod
    def extract(self, evidence: list[Evidence]) -> list[Claim]:
        """
        Convert Evidence objects into Claim objects.

        Inputs
        ------
        evidence : list[Evidence]
            Evidence already normalized by the normalization layer.
            May be empty.

        Outputs
        -------
        list[Claim]
            Claims derived from the evidence. May be empty. Sorted
            deterministically by the implementation.

        Error behavior
        --------------
        Individual evidence that cannot produce a claim is skipped,
        not raised. The method never raises for ordinary evidence.

        The implementation must not mutate the input list or its
        elements.
        """


__all__ = ["ClaimExtractor"]