"""
File: src/veda/pipeline/__init__.py
Title: Pipeline Package
Layer: Pipeline layer
Status: Merged prototype foundation — Phase 6

Purpose
-------
Exposes the pipeline's public entry points. Downstream phases
(interfaces, adapters) import from veda.pipeline rather than the
individual implementation modules.

Public API
----------
run_assessment       Run the full pipeline, return an Assessment
ProviderBundle       Container for the four provider instances
extract_claims       Evidence list -> Claim list
detect_conflicts     Claim list -> Conflict list
build_assessment     Assessment state engine entry point

Does not
--------
Does not make network calls.
Does not import veda.providers.fixtures.
Does not retrieve, normalize, or persist.

Design notes
------------
The package marker is written last so all sibling modules exist
before the public imports are evaluated.
"""

from veda.pipeline.assessment import build_assessment_status as build_assessment
from veda.pipeline.claim_extraction import extract_claims
from veda.pipeline.conflict_detector import detect_conflicts
from veda.pipeline.orchestrator import ProviderBundle, run_assessment

__all__ = [
    "run_assessment",
    "ProviderBundle",
    "extract_claims",
    "detect_conflicts",
    "build_assessment",
]