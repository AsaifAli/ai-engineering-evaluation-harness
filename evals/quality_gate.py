from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .project_runner import run_all, run_target

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "evals" / "baselines"


def _baseline_path(name: str) -> Path:
    return BASELINES / f"{name}.json"


def current_summary(target: str = "all", baseline_targets: list[str] | None = None) -> dict[str, Any]:
    if target != "all":
        return run_target(target, mode="replay")
    targets = baseline_targets or []
    if targets:
        outputs = [run_target(item, mode="replay") for item in targets]
        return {
            "mode": "replay",
            "targets": outputs,
            "platform_score": round(sum(x["avg_score"] for x in outputs) / len(outputs), 6) if outputs else 0.0,
            "target_gate_passes": sum(x["passed"] == x["cases"] for x in outputs),
            "target_count": len(outputs),
        }
    return run_all("replay")


def check_gate(current: dict[str, Any], baseline: dict[str, Any], *, max_regression: float = 0.02) -> dict[str, Any]:
    current_targets = {x["target"]: x for x in current.get("targets", [])}
    baseline_targets = baseline.get("targets", {})
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for target, item in current_targets.items():
        b = baseline_targets.get(target)
        if not b:
            failures.append(f"{target}: missing baseline")
            continue
        score_delta = round(float(item["avg_score"]) - float(b["score"]), 6)
        gate_pass = item["passed"] == item["cases"]
        regression = score_delta < -abs(max_regression)
        if not gate_pass:
            failures.append(f"{target}: project quality gate failed")
        if regression:
            failures.append(f"{target}: score regression {score_delta:.4f} < -{max_regression:.4f}")
        results.append({"target": target, "baseline_score": b["score"], "current_score": item["avg_score"], "delta": score_delta, "gate_passed": gate_pass, "regression": regression})
    return {"passed": not failures, "failures": failures, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI quality CI gate against committed replay baselines")
    parser.add_argument("--target", default="all")
    parser.add_argument("--baseline", default="replay_v1")
    parser.add_argument("--max-regression", type=float, default=0.02)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    path = _baseline_path(args.baseline)
    path.parent.mkdir(parents=True, exist_ok=True)
    if args.write_baseline:
        current = current_summary(args.target)
        targets = current.get("targets", [])
        payload = {"name": args.baseline, "targets": {x["target"]: {"score": x["avg_score"], "cases": x["cases"]} for x in targets}}
        path.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"baseline_written": str(path), "targets": len(targets)}, indent=2))
        return
    if not path.exists():
        raise SystemExit(f"baseline not found: {path}. Create it with --write-baseline once the fixture suite is trusted.")
    baseline = json.loads(path.read_text())
    current = current_summary(args.target, baseline_targets=list(baseline.get("targets", {}).keys()) if args.target == "all" else None)
    result = check_gate(current, baseline, max_regression=args.max_regression)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
