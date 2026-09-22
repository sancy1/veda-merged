# filename: tests/interfaces/test_errors.py
# title: Interface Layer - Error Taxonomy Tests
# layer: Test suite - interfaces
# status: Phase 7 — Sub-phase 7B
# description:
#     Verifies the interface error taxonomy: the base class, the
#     three subclasses, and the inheritance relationships.

from __future__ import annotations

import pytest

from veda.interfaces.errors import (
    BundleBuildError,
    InterfaceConfigError,
    InterfaceError,
    PipelineError,
)


def test_interface_error_is_exception() -> None:
    assert issubclass(InterfaceError, Exception)


def test_interface_config_error_subclass() -> None:
    assert issubclass(InterfaceConfigError, InterfaceError)


def test_bundle_build_error_subclass() -> None:
    assert issubclass(BundleBuildError, InterfaceError)


def test_pipeline_error_subclass() -> None:
    assert issubclass(PipelineError, InterfaceError)


def test_interface_config_error_carries_message() -> None:
    err = InterfaceConfigError("custom message")
    assert "custom message" in str(err)


def test_bundle_build_error_carries_message() -> None:
    err = BundleBuildError("cannot build")
    assert "cannot build" in str(err)


def test_pipeline_error_carries_message() -> None:
    err = PipelineError("pipeline failed")
    assert "pipeline failed" in str(err)


def test_interface_error_can_be_raised_and_caught() -> None:
    with pytest.raises(InterfaceError):
        raise InterfaceConfigError("test")


def test_three_subclasses_are_distinct() -> None:
    assert InterfaceConfigError is not BundleBuildError
    assert InterfaceConfigError is not PipelineError
    assert BundleBuildError is not PipelineError