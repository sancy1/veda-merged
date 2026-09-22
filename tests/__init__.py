# filename: tests/__init__.py
# title: Tests Package Marker
# layer: Test suite
# status: Phase 1-6 test recovery
# description:
#     Marks the tests/ directory as an importable Python package so
#     pytest can resolve relative imports across the test tree.
#     Contains no test logic.
# source:
#     AUTHORED - no test package existed before test recovery began.
# notes:
#     - This marker is required for the tests/unit, tests/integration,
#       and tests/smoke subpackages to be discoverable by pytest when
#       running from the repository root.