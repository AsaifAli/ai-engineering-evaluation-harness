

def test_ragas_agent_adapter_scores_structured_conversation_and_expected_tools(monkeypatch):
    import asyncio
    import sys
    import types

    from evals.frameworks import evaluate_agent_tools_with_ragas

    root = types.ModuleType("ragas")
    root.__path__ = []
    metrics_package = types.ModuleType("ragas.metrics")
    metrics_package.__path__ = []
    collections = types.ModuleType("ragas.metrics.collections")
    messages_module = types.ModuleType("ragas.messages")

    class FakeMessage:
        def __init__(self, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    class FakeToolCall:
        def __init__(self, name, args=None):
            self.name = name
            self.args = args or {}

    class FakeToolMetric:
        name = "ToolCallAccuracy"

        async def ascore(self, **kwargs):
            calls = kwargs["reference_tool_calls"]
            assert [call.name for call in calls] == ["search", "read"]
            assert calls[0].args == {"query": "retention policy"}
            assert [type(message).__name__ for message in kwargs["user_input"]] == [
                "FakeMessage", "FakeMessage", "FakeMessage", "FakeMessage"
            ]
            return SimpleNamespace(value=1.0, reason="all tool calls matched")

    messages_module.HumanMessage = FakeMessage
    messages_module.AIMessage = FakeMessage
    messages_module.ToolMessage = FakeMessage
    messages_module.ToolCall = FakeToolCall
    collections.ToolCallAccuracy = FakeToolMetric
    collections.ToolCallF1 = FakeToolMetric
    monkeypatch.setitem(sys.modules, "ragas", root)
    monkeypatch.setitem(sys.modules, "ragas.metrics", metrics_package)
    monkeypatch.setitem(sys.modules, "ragas.metrics.collections", collections)
    monkeypatch.setitem(sys.modules, "ragas.messages", messages_module)

    result = asyncio.run(evaluate_agent_tools_with_ragas({
        "user_input": [
            {"role": "user", "content": "Find the retention policy."},
            {"role": "assistant", "content": "Searching.", "tool_calls": [
                {"name": "search", "args": {"query": "retention policy"}}
            ]},
            {"role": "tool", "content": "Found policy-v3."},
            {"role": "assistant", "content": "The policy is seven years."},
        ],
        "reference_tool_calls": [
            {"name": "search", "args": {"query": "retention policy"}},
            {"tool": "read", "arguments": {"document_id": "policy-v3"}},
        ],
    }))
    assert result["framework"] == "ragas"
    assert result["metrics"]["ToolCallAccuracy"]["score"] == 1.0


def test_ragas_agent_adapter_requires_structured_message_trace(monkeypatch):
    import asyncio
    import sys
    import types

    import pytest
    from evals.frameworks import evaluate_agent_tools_with_ragas

    root = types.ModuleType("ragas")
    root.__path__ = []
    metrics_package = types.ModuleType("ragas.metrics")
    metrics_package.__path__ = []
    collections = types.ModuleType("ragas.metrics.collections")
    messages_module = types.ModuleType("ragas.messages")
    class FakeMessage:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    class FakeToolCall:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    class FakeMetric:
        def __init__(self):
            pass
    messages_module.HumanMessage = FakeMessage
    messages_module.AIMessage = FakeMessage
    messages_module.ToolMessage = FakeMessage
    messages_module.ToolCall = FakeToolCall
    collections.ToolCallAccuracy = FakeMetric
    collections.ToolCallF1 = FakeMetric
    monkeypatch.setitem(sys.modules, "ragas", root)
    monkeypatch.setitem(sys.modules, "ragas.metrics", metrics_package)
    monkeypatch.setitem(sys.modules, "ragas.metrics.collections", collections)
    monkeypatch.setitem(sys.modules, "ragas.messages", messages_module)

    with pytest.raises(ValueError, match="non-empty RAGAS message list"):
        asyncio.run(evaluate_agent_tools_with_ragas({
            "user_input": [],
            "reference_tool_calls": [],
        }))
