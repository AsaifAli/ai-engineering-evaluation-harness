from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.config import HARNESS_CONFIG_VERSION
from app.db import insert_audit, insert_ai_quality
from app.targets import TARGETS as TARGET_SPECS
from evals.project_evals import evaluate_case

DATA = Path(__file__).parent / "datasets"
# Any registered target with a dataset becomes evaluable; new plugins do not
# require changes to this runner.
TARGETS = tuple(spec.slug for spec in TARGET_SPECS if (DATA / f"{spec.slug}.json").exists())


def load_cases(target: str) -> list[dict[str, Any]]:
    path = DATA / f"{target}.json"
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"Dataset {path} must contain a list")
    return data


def run_target(target: str, *, mode: str = "replay", dataset_version: str = "v1", prompt_version: str = "not-applicable", model_version: str = "replay-fixture-v1", config_version: str = HARNESS_CONFIG_VERSION, experiment_id: str | None = None) -> dict[str, Any]:
    import uuid
    cases = load_cases(target)
    batch_id = str(uuid.uuid4())
    results = []
    for case in cases:
        if case.get("mode", mode) != mode and mode != "all":
            continue
        result = evaluate_case(
            target,
            str(case["id"]),
            case.get("expected", {}),
            case.get("actual", {}),
            mode=case.get("mode", mode),
        )
        quality_id = insert_ai_quality(
            batch_id=batch_id,
            target=result.target,
            case_id=result.case_id,
            mode=result.mode,
            score=result.score,
            passed=result.passed,
            metrics=result.metrics,
            gate_failures=result.gate_failures,
            notes=result.notes,
            dataset_version=dataset_version,
            prompt_version=prompt_version,
            model_version=model_version,
            config_version=config_version,
            experiment_id=experiment_id,
        )
        results.append({
            "quality_id": quality_id,
            "target": result.target,
            "case_id": result.case_id,
            "mode": result.mode,
            "score": result.score,
            "passed": result.passed,
            "metrics": result.metrics,
            "gate_failures": result.gate_failures,
            "notes": result.notes,
        })
    summary = {
        "target": target,
        "mode": mode,
        "batch_id": batch_id,
        "cases": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "avg_score": round(sum(result["score"] for result in results) / len(results), 6) if results else 0.0,
        "results": results,
    }
    insert_audit("ai_quality_evaluation", "passed" if summary["passed"] == summary["cases"] else "attention", summary, actor="evaluation-runner")
    return summary


def run_all(mode: str = "replay", **kwargs: Any) -> dict[str, Any]:
    outputs = [run_target(target, mode=mode, **kwargs) for target in TARGETS]
    return {
        "mode": mode,
        "targets": outputs,
        "platform_score": round(sum(x["avg_score"] for x in outputs) / len(outputs), 6) if outputs else 0.0,
        "target_gate_passes": sum(x["passed"] == x["cases"] for x in outputs),
        "target_count": len(outputs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project-specific AI quality evaluations")
    parser.add_argument("--target", choices=["all", *TARGETS], default="all")
    parser.add_argument("--mode", choices=["replay"], default="replay")
    parser.add_argument("--dataset-version", default="v1")
    parser.add_argument("--prompt-version", default="not-applicable")
    parser.add_argument("--model-version", default="replay-fixture-v1")
    parser.add_argument("--config-version", default="v1")
    parser.add_argument("--experiment-id", default=None)
    args = parser.parse_args()
    kwargs = {"dataset_version": args.dataset_version, "prompt_version": args.prompt_version, "model_version": args.model_version, "config_version": args.config_version, "experiment_id": args.experiment_id}
    output = run_all(args.mode, **kwargs) if args.target == "all" else run_target(args.target, mode=args.mode, **kwargs)
    print(json.dumps(output, indent=2))
    target_results = output["targets"] if args.target == "all" else [output]
    if any(item["passed"] != item["cases"] for item in target_results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
