# filename: tests/smoke/__init__.py
# title: Smoke Test Package Marker
# layer: Test suite - smoke
# status: Phase 1-6 test recovery
# description:
#     Marks tests/smoke/ as a Python package. Smoke tests are the
#     end-to-end acceptance checks that convert the inline Phase 6
#     validation transcript into saved, reproducible artifacts.
# source:
#     AUTHORED - no test package existed before test recovery began.
# notes:
#     - The smoke tests are the frozen Phase 6 baseline. Every future
#       change must keep them passing.