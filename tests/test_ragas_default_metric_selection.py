eval({})



def _fake_ragas_collections(monkeypatch):
    import sys
    import types

    root = types.ModuleType("ragas")
    root.__path__ = []
    metrics_package = types.ModuleType("ragas.metrics")
    metrics_package.__path__ = []
    collections = types.ModuleType("ragas.metrics.collections")
    constructed = []

    class FakeMetric:
        def __init__(self, llm=None, embeddings=None):
            self.llm = llm
            self.embeddings = embeddings
            constructed.append(self.__class__.__name__)

        async def ascore(self, **kwargs):
            return SimpleNamespace(value=0.8)

    for name in (
        "Faithfulness",
        "AnswerRelevancy",
        "AnswerCorrectness",
        "ContextRecall",
        "ContextPrecisionWithReference",
        "ContextPrecisionWithoutReference",
    ):
        setattr(collections, name, type(name, (FakeMetric,), {}))

    monkeypatch.setitem(sys.modules, "ragas", root)
    monkeypatch.setitem(sys.modules, "ragas.metrics", metrics_package)
    monkeypatch.setitem(sys.modules, "ragas.metrics.collections", collections)
    return constructed


def test_default_ragas_metrics_use_reference_aware_context_precision(monkeypatch):
    from evals.frameworks import _ragas_metrics

    constructed = _fake_ragas_collections(monkeypatch)
    metrics = _ragas_metrics(
        {
            "user_input": "question",
            "response": "answer",
            "retrieved_contexts": ["context"],
            "reference": "expected answer",
        },
        llm=object(),
        embeddings=None,
        metrics=None,
    )
    names = [metric.__class__.__name__ for metric in metrics]
    assert "ContextPrecisionWithReference" in names
    assert "ContextRecall" in names
    assert "AnswerCorrectness" in names
    assert "ContextPrecisionWithoutReference" not in names


def test_default_ragas_metrics_work_without_reference(monkeypatch):
    from evals.frameworks import _ragas_metrics

    _fake_ragas_collections(monkeypatch)
    metrics = _ragas_metrics(
        {
            "user_input": "question",
            "response": "answer",
            "retrieved_contexts": ["context"],
        },
        llm=object(),
        embeddings=None,
        metrics=None,
    )
    names = [metric.__class__.__name__ for metric in metrics]
    assert "ContextPrecisionWithoutReference" in names
    assert "ContextRecall" not in names
    assert "AnswerCorrectness" not in names


def test_ragas_dataset_runner_rejects_mixed_reference_presence():
    import pytest

    with pytest.raises(ValueError, match="consistently include reference"):
        asyncio.run(evaluate_ragas_dataset(
            [
                {"id": "a", "user_input": "q", "response": "a", "retrieved_contexts": [], "reference": "a"},
                {"id": "b", "user_input": "q", "response": "b", "retrieved_contexts": []},
            ],
            metrics=[FakeRagasMetric()],
        ))
