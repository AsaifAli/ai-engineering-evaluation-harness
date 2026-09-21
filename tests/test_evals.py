import json
from pathlib import Path
from evals.scoring import score_case


def test_issue_eval_dataset_has_cases():
    data = json.loads((Path("evals/datasets/issue_triage.json")).read_text())
    assert len(data) >= 3


def test_scoring_requires_expected_fields():
    passed, score, checks = score_case({"category":"bug","priority":"high"}, {"category":"bug","priority":"high"})
    assert passed is True
    assert score == 100.0
    assert all(checks.values())
