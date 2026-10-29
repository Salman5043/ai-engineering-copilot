from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.agent import reasoner


def test_system_prompt_static_runtime_boundary():
    p = reasoner.SYSTEM_PROMPT.lower()
    assert "not proof" in p
    assert "compile-time" in p
    assert "constructor" in p
    assert "missing edge" in p
    assert "monkey-patching" in p


def test_prompt_retains_evidence_locations():
    p = reasoner.build_reasoning_prompt(
        query="Does A call B?", intent="architecture",
        evidence=[{"file": "pkg/a.py", "start_line": 12,
                   "end_line": 12, "symbol": "A",
                   "symbol_type": "static_call_relationship",
                   "content": "STATIC CALL EVIDENCE: A -> B"}],
    )
    assert "pkg/a.py:12-12" in p
    assert "STATIC CALL EVIDENCE: A -> B" in p
    assert "runtime execution" in p


def test_prompt_no_evidence_preserves_insufficiency():
    p = reasoner.build_reasoning_prompt(
        query="What calls x?", intent="general_search", evidence=[]
    )
    assert "No repository evidence was collected." in p
    assert "state when evidence is insufficient" in p


def test_generate_answer_api_unchanged():
    class FakeLLM:
        def invoke(self, messages):
            assert messages[0][0] == "system"
            assert "static-analysis edges" in messages[0][1]
            assert messages[1][0] == "human"
            return SimpleNamespace(content="  Answer  ")
    with patch.object(reasoner, "get_llm", return_value=FakeLLM()):
        assert reasoner.generate_reasoned_answer(
            query="Q", intent="architecture", evidence=[]
        ) == "Answer"


def test_non_string_llm_content_still_supported():
    class FakeLLM:
        def invoke(self, messages):
            return SimpleNamespace(content=["ok"])
    with patch.object(reasoner, "get_llm", return_value=FakeLLM()):
        assert reasoner.generate_reasoned_answer(
            query="Q", intent="architecture", evidence=[]
        ) == "['ok']"
