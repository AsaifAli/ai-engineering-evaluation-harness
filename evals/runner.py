from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import LLM_PROVIDER, GATEWAY_MODEL
from app.db import insert_evaluation
from app.main import app
from evals.scoring import score_case

DATA = Path(__file__).parent / "datasets"

SUITES = {
    "issue_triage": ("issue_triage.json", "/ai/triage"),
    "pr_review": ("pr_review.json", "/ai/pr-review"),
    "experiment_summary": ("experiment_summary.json", "/ai/experiment-summary"),
    "guardrails": ("guardrails.json", "/ai/triage"),
}


def run_suite(name: str) -> dict:
    filename, endpoint = SUITES[name]
    cases = json.loads((DATA / filename).read_text())
    passed = 0
    scores = []
    details = []
    with TestClient(app) as client:
        for case in cases:
            response = client.post(endpoint, json=case["input"])
            response.raise_for_status()
            actual = response.json()
            case_passed, score, checks = score_case(actual, case["expected"])
            passed += int(case_passed)
            scores.append(score)
            details.append({"id": case["id"], "passed": case_passed, "score": score, "checks": checks})
    score = round(sum(scores) / len(scores), 2) if scores else 0.0
    provider = LLM_PROVIDER
    model = GATEWAY_MODEL or ("deterministic-fallback-v2" if provider != "gateway" else "session-selected")
    insert_evaluation(eval_suite=f"{name}-golden", workflow=name, provider=provider, model=model,
                      passed=passed, total=len(cases), score=score, details=details)
    return {"workflow": name, "passed": passed, "total": len(cases), "score": score, "details": details}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", choices=["all", *SUITES.keys()], default="all")
    parser.add_argument("--min-score", type=float, default=90.0)
    args = parser.parse_args()
    names = list(SUITES) if args.workflow == "all" else [args.workflow]
    results = [run_suite(name) for name in names]
    print(json.dumps({"results": results}, indent=2))
    failing = [r for r in results if r["score"] < args.min_score]
    if failing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
