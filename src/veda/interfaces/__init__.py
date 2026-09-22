# filename: src/veda/interfaces/__init__.py
# title: Interfaces Package Marker
# layer: Interface layer
# status: Phase 7 — Sub-phase 7B
# description:
#     Marks src/veda/interfaces/ as an importable Python package.
#     Contains no business logic.
#
#     The interface layer is the only layer that knows about the
#     CLI, the HTTP API, and the dashboard. It constructs a
#     configuration, builds a provider bundle, calls
#     run_assessment(), and renders the result. It never
#     recomputes the pipeline's decisions.
#
# source:
#     AUTHORED — Phase 7 introduces the interface layer.

from __future__ import annotations

__all__: list[str] = []