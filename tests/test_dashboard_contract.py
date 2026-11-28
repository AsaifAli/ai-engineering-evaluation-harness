from pathlib import Path


DASHBOARD = Path(__file__).parents[1] / "app" / "dashboard.html"


def test_dashboard_explains_supported_frameworks_without_claiming_all_are_live():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "Evaluation framework coverage" in html
    assert "RAGAS" in html
    assert "DeepEval" in html
    assert "TruLens" in html
    assert "Phoenix" in html
    assert "import adapter" in html.lower()
    assert "not currently emitted" in html.lower()


def test_dashboard_separates_external_framework_scores_from_runtime_metrics():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "Framework scores" in html
    assert "Runtime / domain checks" in html
    assert "external." in html
    assert "config_version" in html
    assert "dataset_version" in html
    assert "prompt_version" in html
    assert "model_version" in html


def test_dashboard_exposes_project_and_framework_filters():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert 'id="runtimeProjectFilter"' in html
    assert 'id="runtimeFrameworkFilter"' in html
    assert 'id="runtimeSearch"' in html
    assert "applyRuntimeFilters" in html


def test_dashboard_renders_experiment_lineage_and_metric_deltas():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "Experiment history &amp; comparisons" in html
    assert "/api/ai-quality/runtime-experiments" in html
    assert "baseline_experiment_id" in html
    assert "metric_deltas" in html
    assert "directional only" in html.lower()


def test_dashboard_keeps_count_metrics_as_counts_not_percentages():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert 'key.endsWith("_count")' in html
    assert "isCountMetric" in html


def test_dashboard_formats_completeness_and_percentage_deltas_as_percentages():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert '"completeness"' in html
    assert "function isRatioMetric(name)" in html
    assert 'isRatioMetric(name))return' in html


def test_dashboard_filters_mixed_framework_and_native_signals_independently():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert 'entries.filter(([key])=>!externalFramework(key))' in html
    assert 'entries.filter(([key])=>externalFramework(key)===framework)' in html
    assert 'Object.fromEntries(selectedEntries)' in html
