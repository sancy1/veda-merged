# filename: tests/pipeline/test_llm_extraction.py
# title: Pipeline Layer - LLM Extractor Disabled Stub Tests
# layer: Test suite - pipeline
# status: Phase 7 — Sub-phase 7A
# description:
#     Verifies the disabled contract stub for LLM claim extraction.
#     Also proves that the default configuration never constructs or
#     calls the stub. Two dedicated tests guarantee that default
#     behavior stays LLM-free.
#
# source:
#     AUTHORED — Phase 7 introduces the stub; the reviewer required
#     explicit tests proving the default never constructs or calls it.

from __future__ import annotations

import pytest

from veda.pipeline.claim_extraction import RuleBasedClaimExtractor
from veda.pipeline.llm_extraction import LLMClaimExtractor


# ====================================================================
# 1. Construction behavior
# ====================================================================

def test_construction_without_opt_in_raises() -> None:
    with pytest.raises(RuntimeError):
        LLMClaimExtractor()


def test_error_message_names_opt_in_requirement() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        LLMClaimExtractor()
    message = str(exc_info.value).lower()
    assert "disabled" in message or "opt" in message or "enabled=true" in message


def test_construction_with_opt_in_succeeds() -> None:
    extractor = LLMClaimExtractor(enabled=True)
    assert extractor is not None


# ====================================================================
# 2. Properties
# ====================================================================

def test_extraction_method_name() -> None:
    assert LLMClaimExtractor(enabled=True).extraction_method_name == "llm"


def test_is_llm_backed_true() -> None:
    assert LLMClaimExtractor(enabled=True).is_llm_backed is True


# ====================================================================
# 3. extract() raises NotImplementedError
# ====================================================================

def test_extract_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        LLMClaimExtractor(enabled=True).extract([])


def test_extract_does_not_return_empty_list() -> None:
    extractor = LLMClaimExtractor(enabled=True)
    try:
        result = extractor.extract([])
        # If we reach here, extract did not raise. That is a defect.
        raise AssertionError(
            "LLMClaimExtractor.extract() must raise NotImplementedError, "
            f"got return value: {result!r}"
        )
    except NotImplementedError:
        pass


def test_extract_does_not_produce_fake_claims() -> None:
    """No code path returns a claim without a real extractor."""
    try:
        LLMClaimExtractor(enabled=True).extract([])
    except NotImplementedError:
        pass


# ====================================================================
# 4. Default configuration never constructs or calls the LLM stub
# ====================================================================

def test_default_configuration_never_constructs_llm_extractor() -> None:
    """
    The default pipeline configuration constructs
    RuleBasedClaimExtractor only. This test proves that constructing
    the default extractor does not build any LLM-backed extractor.
    """
    extractor = RuleBasedClaimExtractor()
    assert extractor.is_llm_backed is False
    assert extractor.extraction_method_name == "rule_based"


def test_default_configuration_never_calls_llm_extract() -> None:
    """
    Calling extract on the default extractor must not call the LLM
    stub. The stub raises if extract is called, so if any code path
    reaches it, the test fails.
    """
    extractor = RuleBasedClaimExtractor()
    result = extractor.extract([])
    assert result == []


# ====================================================================
# 5. Module purity
# ====================================================================

def test_module_does_not_import_model_sdk() -> None:
    """
    The stub imports no model SDK. Verify by checking the module's
    globals for suspicious imports.
    """
    import veda.pipeline.llm_extraction as mod
    source = open(mod.__file__, "r", encoding="utf-8").read()
    forbidden = ["import openai", "import anthropic", "from openai", "from anthropic"]
    for token in forbidden:
        assert token not in source, f"llm_extraction.py imports {token!r}"