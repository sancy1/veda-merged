# filename: src/veda/pipeline/composite_extraction.py
# title: Composite Claim Extractor
# layer: Pipeline layer
# status: Phase 7 — Sub-phase 7A
# description:
#     Combines two ClaimExtractor instances into one.

#     The orchestrator receives exactly one ClaimExtractor. When the
#     caller wants to combine a rule-based extractor with an
#     LLM-backed one, the combination is achieved by constructing a
#     CompositeClaimExtractor, not by the orchestrator knowing about
#     two extractors.
#
#     Determinism rules, frozen:
#
#       1. Both extractors receive the same evidence list.
#       2. Both return lists of claims.
#       3. Claims are deduplicated by claim_id.
#       4. On duplicate claim_id, the PRIMARY extractor's claim wins.
#       5. The output is sorted by claim_id ascending.
#       6. Neither input list is mutated.
#
#     The composite is available in Phase 7 but not enabled by
#     default. A composite containing the disabled LLM stub raises
#     NotImplementedError when extract() is called, because the
#     secondary extractor raises. The default configuration does not
#     construct a composite.
#
# source:
#     AUTHORED — Phase 7 introduces this class. The reviewer required
#     a composite rather than an orchestrator-level combination, so
#     the pipeline has exactly one extractor at all times.
#
# notes:
#     - The primary-wins-on-duplicate rule is documented in the class
#       docstring and locked by a dedicated test
#       (test_composite_primary_wins_on_duplicate_claim_id).
#     - is_llm_backed is True if either side is LLM-backed.
#     - extraction_method_name composes both side names.

from __future__ import annotations

from veda.pipeline.extraction_protocol import ClaimExtractor
from veda.shared.models import Claim, Evidence


class CompositeClaimExtractor(ClaimExtractor):
    """
    Combine two ClaimExtractor instances.

    Determinism
    -----------
    - Both extractors receive the same evidence list unchanged.
    - Claims are deduplicated by claim_id.
    - On duplicate claim_id, the PRIMARY extractor's claim is
      preserved. The SECONDARY extractor's claim is discarded.
    - Output is sorted by claim_id ascending.
    - Inputs are not mutated.
    """

    def __init__(
        self,
        *,
        primary: ClaimExtractor,
        secondary: ClaimExtractor,
    ) -> None:
        if not isinstance(primary, ClaimExtractor):
            raise TypeError(
                "CompositeClaimExtractor primary must be a ClaimExtractor "
                f"(got {type(primary).__name__})"
            )
        if not isinstance(secondary, ClaimExtractor):
            raise TypeError(
                "CompositeClaimExtractor secondary must be a ClaimExtractor "
                f"(got {type(secondary).__name__})"
            )
        self._primary = primary
        self._secondary = secondary

    @property
    def extraction_method_name(self) -> str:
        return (
            f"composite({self._primary.extraction_method_name}"
            f"+{self._secondary.extraction_method_name})"
        )

    @property
    def is_llm_backed(self) -> bool:
        return self._primary.is_llm_backed or self._secondary.is_llm_backed

    def extract(self, evidence: list[Evidence]) -> list[Claim]:
        """
        Run both extractors and merge their outputs.

        Returns a new list, sorted by claim_id, with duplicate claim
        IDs collapsed to the primary extractor's claim.
        """
        primary_claims = self._primary.extract(evidence)
        secondary_claims = self._secondary.extract(evidence)

        by_id: dict[str, Claim] = {}

        # Primary wins: insert first, then skip duplicates.
        for claim in primary_claims:
            by_id.setdefault(claim.claim_id, claim)

        for claim in secondary_claims:
            by_id.setdefault(claim.claim_id, claim)

        return sorted(by_id.values(), key=lambda c: c.claim_id)


__all__ = ["CompositeClaimExtractor"]