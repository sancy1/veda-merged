# filename: tests/normalization/__init__.py
# title: Normalization Layer Test Package Marker
# layer: Test suite - normalization
# status: Phase 1-6 test recovery
# description:
#     Marks tests/normalization/ as a Python package. Tests here verify
#     conversion of provider records into canonical Evidence objects,
#     including the fy/fp hardening and duplicate-filing tiebreak.
# source:
#     AUTHORED - no test package existed before test recovery began.
# notes:
#     - test_sec.py is the single most valuable test file in the entire
#       suite. It guards the live-SEC correctness rules discovered by
#       the personal prototype.