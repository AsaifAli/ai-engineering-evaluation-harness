from evals.project_runner import load_cases
from evals.scoring import score_case


def test_only_retained_application_fixtures_are_registered():
    assert len(load_cases("evidenceflow")) >= 1
    assert len(load_cases("quotesense")) >= 1
    assert len(load_cases("flowpilot")) >= 4


def test_scoring_requires_expected_fields():
    passed, score, checks = score_case(
        {"category": "document", "priority": "high"},
        {"category": "document", "priority": "high"},
    )
    assert passed is True
    assert score == 100.0
    assert all(checks.values())
