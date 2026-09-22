# filename: src/veda/pipeline/llm_extraction.py
# title: LLM Claim Extractor — Disabled Contract Stub
# layer: Pipeline layer
# status: Phase 7 — Sub-phase 7A
# description:
#     Disabled contract stub. This class exists to prove the
#     ClaimExtractor seam. It satisfies the ABC's three members. Its
#     extract() method raises NotImplementedError because no live LLM
#     adapter exists in Phase 7.
#
#     This module imports no model SDK. It reads no API key. It makes
#     no network call. It is never constructed by the default
#     configuration.
#
#     The class is intentionally strict: construction without
#     enabled=True raises RuntimeError, so a caller cannot enable the
#     stub by accident. Even with enabled=True, extract() raises
#     NotImplementedError. There is no code path in Phase 7 where
#     this class produces a claim.
#
#     The employer's AI directive (A-006, A-007) requires narrative
#     extraction from unstructured text. That capability is reserved
#     for a later phase. This stub defines the interface a real
#     adapter will implement. It does not implement the adapter.
#
# source:
#     AUTHORED — Phase 7 introduces this disabled stub. The real
#     adapter is deferred until the deterministic pipeline is frozen
#     and the interface layer is stable.
#
# notes:
#     - No model SDK is imported. A real adapter will import one; this
#       stub does not.
#     - The error messages name the employer's constraint: LLM
#       extraction is opt-in only, and the live adapter is not
#       implemented yet.
#     - The stub is tested in tests/pipeline/test_llm_extraction.py.
#     - The default configuration never constructs or calls this
#       class. Two dedicated tests in test_llm_extraction.py prove
#       that guarantee.

from __future__ import annotations

from veda.pipeline.extraction_protocol import ClaimExtractor
from veda.shared.models import Claim, Evidence


class LLMClaimExtractor(ClaimExtractor):
    """
    Disabled contract stub for LLM-backed claim extraction.

    Satisfies the ClaimExtractor ABC. Does not implement live
    extraction.

    Construction
    ------------
    LLMClaimExtractor()                  -> RuntimeError
    LLMClaimExtractor(enabled=True)      -> constructs successfully

    Methods
    -------
    extract()                            -> NotImplementedError

    Rationale
    ---------
    The employer's AI directive requires narrative extraction. That
    capability is a later phase. This stub exists so the seam is
    present, tested, and reserved. No code path in Phase 7 uses it.
    """

    def __init__(self, *, enabled: bool = False) -> None:
        """
        Construct a disabled stub, or an enabled-but-unimplemented
        stub.

        Parameters
        ----------
        enabled : bool, default False
            When False (default), construction raises RuntimeError.
            The caller must opt in explicitly.
            When True, construction succeeds, but extract() still
            raises NotImplementedError because no live adapter exists
            in Phase 7.
        """
        if not enabled:
            raise RuntimeError(
                "LLMClaimExtractor is a disabled contract stub. "
                "Pass enabled=True to construct it, but note that "
                "extract() is not implemented in this phase. "
                "Live LLM extraction is reserved for a later phase "
                "and is not the default pipeline behavior."
            )
        self._enabled = True

    @property
    def extraction_method_name(self) -> str:
        return "llm"

    @property
    def is_llm_backed(self) -> bool:
        return True

    def extract(self, evidence: list[Evidence]) -> list[Claim]:
        """
        Not implemented in Phase 7.

        Raises NotImplementedError. Does not return an empty list.
        Does not return fake claims. The absence of a live adapter
        must be visible to the caller, not hidden.
        """
        raise NotImplementedError(
            "LLMClaimExtractor.extract() is not implemented in Phase 7. "
            "Live LLM extraction is reserved for a later phase. "
            "The default configuration uses RuleBasedClaimExtractor. "
            "A composite configuration requires a live LLM adapter, "
            "which does not exist yet."
        )


__all__ = ["LLMClaimExtractor"]