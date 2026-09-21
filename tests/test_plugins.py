from app.adapters.generic_http import GenericHTTPAdapter
from evals.registry import get_pack


def test_generic_http_adapter_normalizes_common_response_fields():
    adapter = GenericHTTPAdapter("https://example.com", run_path="/v1/run")
    result = adapter.normalize_response({
        "id": "abc",
        "status": "completed",
        "output": {"answer": "ok"},
        "latency_ms": 12,
        "usage": {"total_tokens": 9},
    }, "demo")
    assert result.run_id == "abc"
    assert result.workflow == "demo"
    assert result.status == "completed"
    assert result.output == {"answer": "ok"}
    assert result.duration_ms == 12


def test_evaluation_pack_registry_is_reusable():
    pack = get_pack("rag")
    assert pack.name == "rag"
    assert "recall@5" in pack.gates
    assert "ndcg@5" in pack.weights


def test_llm_judge_prompt_is_versioned():
    from evals.judge import JUDGE_PROMPT_VERSION
    assert JUDGE_PROMPT_VERSION == "llm-judge-v1"
