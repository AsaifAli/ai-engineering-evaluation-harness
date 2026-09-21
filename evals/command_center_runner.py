from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.adapters.command_center import CommandCenterAdapter

DATA = Path(__file__).parent / "datasets" / "command_center.json"


async def main_async(min_score: float) -> int:
    cases = json.loads(DATA.read_text())
    adapter = CommandCenterAdapter()
    passed = 0
    scores = []
    details = []
    for case in cases:
        run = await adapter.run(case["workflow"], case["payload"])
        actual = run.output
        assertions = case["assertions"]
        checks: dict[str, bool] = {}
        if "count" in assertions:
            checks["count"] = actual.get("count") == assertions["count"]
        if "has_actions" in assertions:
            checks["has_actions"] = bool(actual.get("recommended_actions")) == assertions["has_actions"]
        if "approval_required" in assertions:
            candidates = actual.get("candidates", [])
            checks["approval_required"] = all(c.get("approval_required") is assertions["approval_required"] for c in candidates)
        if "risk_count" in assertions:
            checks["risk_count"] = actual.get("risk_count") == assertions["risk_count"]
        ok = all(checks.values()) if checks else False
        score = round(sum(bool(v) for v in checks.values()) / len(checks) * 100, 2) if checks else 0.0
        passed += int(ok)
        scores.append(score)
        details.append({"id": case["id"], "run_id": run.run_id, "status": run.status, "score": score, "checks": checks})
    score = round(sum(scores) / len(scores), 2) if scores else 0.0
    print(json.dumps({"target": adapter.name, "passed": passed, "total": len(cases), "score": score, "details": details}, indent=2, default=str))
    return 0 if score >= min_score else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the harness evaluation suite against the AI Automation Command Center")
    parser.add_argument("--min-score", type=float, default=90.0)
    args = parser.parse_args()
    return asyncio.run(main_async(args.min_score))


if __name__ == "__main__":
    raise SystemExit(main())
