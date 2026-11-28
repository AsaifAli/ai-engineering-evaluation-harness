import asyncio
import sys
import types
from types import SimpleNamespace

from evals.frameworks import evaluate_ragas_dataset, evaluate_agent_tools_with_deepeval


class FakeRagasMetric:
    name = "Faithfulness"

    async def ascore(self, **sample):
        assert "sample_id" not in sample
        score = 0.9 if "supported" in sample["response"] else 0.5
        return SimpleNamespace(value=score, reason="fixture reason")


def test_ragas_dataset_runner_returns_per_case_and_aggregate_metrics():
    result = asyncio.run(
        evaluate_ragas_dataset(
            [
                {
                    "id": "case-1",
                    "user_input": "What is the retention policy?",
                    "response": "supported answer",
                    "retrieved_contexts": ["retention is 7 years"],
                    "reference": "7 years",
                },
                {
                    "id": "case-2",
                    "user_input": "What is the refund policy?",
                    "response": "unsupported answer",
                    "retrieved_contexts": ["refunds within 30 days"],
                    "reference": "30 days",
                },
            ],
            metrics=[FakeRagasMetric()],
        )
    )
    assert result["framework"] == "ragas"
    assert result["sample_count"] == 2
    assert result["results"][0]["case_id"] == "case-1"
    assert result["summary"]["metrics"]["Faithfulness"]["mean"] == 0.7
    assert result["summary"]["metrics"]["Faithfulness"]["min"] == 0.5


def test_ragas_dataset_runner_rejects_missing_rag_fields():
    import pytest

    with pytest.raises(ValueError, match="retrieved_contexts"):
        asyncio.run(evaluate_ragas_dataset([{
            "id": "bad",
            "user_input": "question",
            "response": "answer",
        }], metrics=[FakeRagasMetric()]))


def test_deepeval_agent_tool_adapter_builds_tool_calls_and_scores(monkeypatch):
    deepeval_package = types.ModuleType("deepeval")
    deepeval_package.__path__ = []
    test_case_module = types.ModuleType("deepeval.test_case")

    class FakeToolCall:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeLLMTestCase:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    test_case_module.ToolCall = FakeToolCall
    test_case_module.LLMTestCase = FakeLLMTestCase
    monkeypatch.setitem(sys.modules, "deepeval", deepeval_package)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case_module)

    class FakeMetric:
        score = 0.95
        reason = "Expected tools selected."
        success = True

        def measure(self, case):
            assert [tool.name for tool in case.tools_called] == ["search", "read"]
            assert case.tools_called[0].input == {"query": "retention policy"}
            assert case.expected_tools[1].name == "read"

    result = evaluate_agent_tools_with_deepeval(
        {
            "input": "Find the retention policy.",
            "actual_output": "The policy states seven years.",
            "tool_calls": [
                {"tool": "search", "arguments": {"query": "retention policy"}},
                {"tool": "read", "arguments": {"document_id": "policy-v3"}},
            ],
            "expected_tool_calls": [
                {"tool": "search", "arguments": {"query": "retention policy"}},
                {"tool": "read", "arguments": {"document_id": "policy-v3"}},
            ],
        },
        metrics=[FakeMetric()],
    )
    assert result["FakeMetric"]["score"] == 0.95
    assert result["FakeMetric"]["success"] is True


def test_deepeval_agent_tool_adapter_never_uses_an_implicit_judge():
    import pytest

    with pytest.raises(ValueError, match="explicitly configured"):
        evaluate_agent_tools_with_deepeval({})
