# filename: tests/shared/__init__.py
# title: Shared Contract Test Package Marker
# layer: Test suite - shared contract
# status: Phase 1-6 test recovery
# description:
#     Marks tests/shared/ as a Python package. Tests here verify the
#     canonical data contract: enums, IDs, models, periods, validation.
# source:
#     AUTHORED - no test package existed before test recovery began.
# notes:
#     - These tests are the foundation. Every higher-layer test trusts
#       the shared contract is correct.