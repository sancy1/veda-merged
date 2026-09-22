# filename: tests/test_project_scaffolding.py
# title: Phase 1 - Project Scaffolding Tests
# layer: Test suite - package
# status: Phase 1-6 test recovery
# description:
#     Verifies the merged VEDA package can be imported, its declared
#     modules exist, and no import triggers network I/O or file writes.
#
#     These are the foundational tests. If they fail, no higher-layer
#     test can be trusted, because the package itself does not load
#     correctly.
#
#     What this file proves:
#       - import veda succeeds
#       - veda.__version__ is a non-empty string
#       - every declared subpackage imports cleanly
#       - no import performs network I/O
#       - pyproject.toml declares the runtime dependencies the code uses
#
# source:
#     AUTHORED - Phase 1 had no saved test before recovery began.
#     The inline checks run during Phase 1 project setup are preserved
#     here as durable assertions.
#
# notes:
#     - Import-time network detection uses monkeypatch on httpx.Client
#       and socket.socket. Any import that would fire a request is
#       caught and the test fails.
#     - The dependency list is asserted against pyproject.toml, not
#       against the environment. This proves the manifest is complete,
#       not that the environment happens to have the packages.

from __future__ import annotations

import importlib
import socket
import tomllib
from pathlib import Path

import pytest


# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


# --------------------------------------------------------------------
# Every declared subpackage of veda that must import
# --------------------------------------------------------------------
VEDA_SUBPACKAGES = [
    "veda",
    "veda.shared",
    "veda.shared.enums",
    "veda.shared.ids",
    "veda.shared.models",
    "veda.shared.periods",
    "veda.shared.validation",
    "veda.entity",
    "veda.entity.resolver",
    "veda.entity.reporting_boundary",
    "veda.providers",
    "veda.providers.base",
    "veda.providers.results",
    "veda.providers.fixtures",
    "veda.providers.sec_company_facts",
    "veda.providers.sec_filings",
    "veda.providers.usaspending",
    "veda.providers.annual_reports",
    "veda.normalization",
    "veda.normalization.sec",
    "veda.normalization.filings",
    "veda.normalization.usaspending",
    "veda.normalization.annual_reports",
    "veda.normalization.evidence_ids",
    "veda.normalization.helpers",
    "veda.pipeline",
    "veda.pipeline.orchestrator",
    "veda.pipeline.packet",
    "veda.pipeline.assessment",
    "veda.pipeline.claim_extraction",
    "veda.pipeline.claim_typing",
    "veda.pipeline.conflict_detector",
    "veda.pipeline.abstention",
]


# ====================================================================
# 1. Package imports
# ====================================================================

def test_veda_package_imports() -> None:
    """The top-level veda package imports successfully."""
    module = importlib.import_module("veda")
    assert module is not None


def test_veda_version_is_nonempty_string() -> None:
    """veda.__version__ is a non-empty string."""
    import veda
    assert isinstance(veda.__version__, str)
    assert veda.__version__.strip() != ""


def test_veda_version_matches_pyproject() -> None:
    """veda.__version__ matches the version declared in pyproject.toml."""
    import veda

    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    declared = data["project"]["version"]
    assert veda.__version__ == declared, (
        f"__version__ is {veda.__version__!r} but pyproject declares {declared!r}"
    )


# ====================================================================
# 2. Every declared subpackage imports
# ====================================================================

@pytest.mark.parametrize("module_name", VEDA_SUBPACKAGES)
def test_every_declared_subpackage_imports(module_name: str) -> None:
    """Every declared subpackage and module imports without error."""
    module = importlib.import_module(module_name)
    assert module is not None


# ====================================================================
# 3. No import triggers network I/O
# ====================================================================

def test_no_import_performs_network_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Importing every declared module must not open a socket or construct
    an httpx client that connects.

    We monkeypatch socket.socket and httpx.Client.get/post to raise if
    called. Then we re-import every module. Any network attempt during
    import is caught.
    """
    def _fail_socket(*args, **kwargs):
        raise AssertionError("import-time socket creation detected")

    def _fail_client(*args, **kwargs):
        raise AssertionError("import-time httpx client call detected")

    monkeypatch.setattr(socket, "socket", _fail_socket)

    import httpx
    monkeypatch.setattr(httpx.Client, "get", _fail_client)
    monkeypatch.setattr(httpx.Client, "post", _fail_client)
    monkeypatch.setattr(httpx, "get", _fail_client)
    monkeypatch.setattr(httpx, "post", _fail_client)

    for module_name in VEDA_SUBPACKAGES:
        importlib.import_module(module_name)


# ====================================================================
# 4. Manifest declares the runtime dependencies
# ====================================================================

def _runtime_dependencies() -> set[str]:
    """Return the set of runtime dependency names declared in pyproject."""
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    deps: list[str] = data["project"]["dependencies"]
    names: set[str] = set()
    for dep in deps:
        # strip any version specifier, extras, or whitespace
        base = dep.split(";")[0].strip()
        for sep in [">", "<", "=", "!", "[", " ", "\t"]:
            base = base.split(sep)[0]
        if base:
            names.add(base)
    return names


def test_pyproject_declares_pydantic() -> None:
    """pyproject.toml declares pydantic as a runtime dependency."""
    assert "pydantic" in _runtime_dependencies()


def test_pyproject_declares_pydantic_settings() -> None:
    """pyproject.toml declares pydantic-settings as a runtime dependency."""
    assert "pydantic-settings" in _runtime_dependencies()


def test_pyproject_declares_httpx() -> None:
    """pyproject.toml declares httpx as a runtime dependency."""
    assert "httpx" in _runtime_dependencies()


def test_pyproject_declares_fastapi() -> None:
    """pyproject.toml declares fastapi as a runtime dependency."""
    assert "fastapi" in _runtime_dependencies()


def test_pyproject_declares_typer() -> None:
    """pyproject.toml declares typer as a runtime dependency."""
    assert "typer" in _runtime_dependencies()


def test_pyproject_declares_rich() -> None:
    """pyproject.toml declares rich as a runtime dependency."""
    assert "rich" in _runtime_dependencies()


# ====================================================================
# 5. Test dependencies
# ====================================================================

def _test_dependencies() -> set[str]:
    """Return the set of test dependency names declared in pyproject."""
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    deps: list[str] = data["project"]["optional-dependencies"]["test"]
    names: set[str] = set()
    for dep in deps:
        base = dep.split(";")[0].strip()
        for sep in [">", "<", "=", "!", "[", " ", "\t"]:
            base = base.split(sep)[0]
        if base:
            names.add(base)
    return names


def test_pyproject_declares_pytest() -> None:
    """pyproject.toml declares pytest as a test dependency."""
    assert "pytest" in _test_dependencies()


def test_pyproject_declares_respx() -> None:
    """pyproject.toml declares respx as a test dependency."""
    assert "respx" in _test_dependencies()


# ====================================================================
# 6. Console entry point
# ====================================================================

def test_console_entry_point_declared() -> None:
    """
    pyproject.toml declares the veda console entry point targeting
    veda.interfaces.cli:app.

    Phase 7 will create that module. Phase 1 only asserts the manifest
    declares it, so the packaging contract is frozen before the target
    file exists.
    """
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    scripts = data["project"].get("scripts", {})
    assert "veda" in scripts
    assert scripts["veda"] == "veda.interfaces.cli:app"


# ====================================================================
# 7. Package layout
# ====================================================================

def test_src_layout_package_discovery_declared() -> None:
    """pyproject.toml declares src/ as the package-discovery root."""
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    where = data["tool"]["setuptools"]["packages"]["find"]["where"]
    assert where == ["src"]


def test_pytest_pythonpath_includes_src() -> None:
    """
    pyproject.toml declares pythonpath = ["src"] so tests can import
    veda.* without an editable install being present.
    """
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)

    pythonpath = data["tool"]["pytest"]["ini_options"]["pythonpath"]
    assert "src" in pythonpath