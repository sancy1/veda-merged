# filename: tests/interfaces/test_config.py
# title: Interface Layer - Configuration Tests
# layer: Test suite - interfaces
# status: Phase 7 — Sub-phase 7B
# description:
#     Verifies InterfaceConfig: defaults are offline, user_agent is
#     required, literals validate, the model is frozen.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from veda.interfaces.config import InterfaceConfig


def test_default_resolver_mode_is_fixture() -> None:
    c = InterfaceConfig(user_agent="Test test@example.com")
    assert c.resolver_mode == "fixture"


def test_default_provider_mode_is_fixture() -> None:
    c = InterfaceConfig(user_agent="Test test@example.com")
    assert c.provider_mode == "fixture"


def test_default_extractor_mode_is_rule_based() -> None:
    c = InterfaceConfig(user_agent="Test test@example.com")
    assert c.extractor_mode == "rule_based"


def test_default_output_format_is_both() -> None:
    c = InterfaceConfig(user_agent="Test test@example.com")
    assert c.output_format == "both"


def test_default_output_path_is_none() -> None:
    c = InterfaceConfig(user_agent="Test test@example.com")
    assert c.output_path is None


def test_user_agent_defaults_to_empty() -> None:
    """
    InterfaceConfig accepts a missing user_agent and defaults to
    an empty string. The value is validated at bundle-build time
    only when provider_mode='live'.
    """
    c = InterfaceConfig()
    assert c.user_agent == ""


def test_user_agent_can_be_empty_for_fixture_mode() -> None:
    """
    An empty User-Agent is valid when provider_mode='fixture'.
    The fixture path never makes a network request.
    """
    c = InterfaceConfig(user_agent="", provider_mode="fixture")
    assert c.user_agent == ""


def test_resolver_mode_accepts_live() -> None:
    c = InterfaceConfig(user_agent="x", resolver_mode="live")
    assert c.resolver_mode == "live"


def test_resolver_mode_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        InterfaceConfig(user_agent="x", resolver_mode="unknown")   # type: ignore[arg-type]


def test_provider_mode_defaults_to_fixture() -> None:
    c = InterfaceConfig(user_agent="x")
    assert c.provider_mode == "fixture"


def test_provider_mode_accepts_live() -> None:
    c = InterfaceConfig(user_agent="x", provider_mode="live")
    assert c.provider_mode == "live"


def test_provider_mode_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        InterfaceConfig(user_agent="x", provider_mode="other")   # type: ignore[arg-type]


def test_extractor_mode_accepts_rule_based() -> None:
    c = InterfaceConfig(user_agent="x", extractor_mode="rule_based")
    assert c.extractor_mode == "rule_based"


def test_extractor_mode_accepts_composite_syntactically() -> None:
    c = InterfaceConfig(user_agent="x", extractor_mode="composite")
    assert c.extractor_mode == "composite"


def test_extractor_mode_rejects_llm() -> None:
    with pytest.raises(ValidationError):
        InterfaceConfig(user_agent="x", extractor_mode="llm")   # type: ignore[arg-type]


def test_output_format_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        InterfaceConfig(user_agent="x", output_format="xml")   # type: ignore[arg-type]


def test_config_is_frozen() -> None:
    c = InterfaceConfig(user_agent="x")
    with pytest.raises(ValidationError):
        c.user_agent = "y"   # type: ignore[misc]


def test_config_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        InterfaceConfig(user_agent="x", unknown_field="value")   # type: ignore[call-arg]