# filename: tests/providers/__init__.py
# title: Provider Layer Test Package Marker
# layer: Test suite - providers
# status: Phase 1-6 test recovery
# description:
#     Marks tests/providers/ as a Python package. Tests here verify the
#     provider ABC, request/result models, and each provider's
#     retrieval behavior (fixture and live with mocked httpx).
# source:
#     AUTHORED - no test package existed before test recovery began.
# notes:
#     - Live provider tests must use respx to intercept every httpx
#       call. No test reaches the network.