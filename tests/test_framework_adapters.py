from evals.frameworks import _normalize_result


class MetricResult:
    value = 0.875
    reason = "supported"


def test_normalizes_ragas_metric_result():
    assert _normalize_result(MetricResult()) == {"score": 0.875, "reason": "supported"}


def test_normalizes_plain_float():
    assert _normalize_result(0.5) == {"score": 0.5}


def test_rejects_out_of_range_score():
    import pytest
    with pytest.raises(ValueError):
        _normalize_result(1.5)


def test_optional_framework_imports_are_lazy():
    import evals.frameworks as frameworks
    assert callable(frameworks.evaluate_with_ragas_async)
    assert callable(frameworks.evaluate_with_deepeval)
