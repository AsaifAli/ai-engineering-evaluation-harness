# LLM evaluation

## Golden sets

`evals/datasets/` contains small representative datasets for issue triage, PR review and experiment summaries.

## Scoring

The evaluator checks expected structured fields and produces a per-case score plus suite-level pass rate. Results are persisted to `evaluation_runs`.

## Regression workflow

The same suites can be run in CI and against the gateway-backed runtime. A real deployment should compare the new run to a stored baseline and fail deployment if critical fields or safety cases regress.

## Important limitation

This project does not claim a statistically complete benchmark. The datasets are deliberately small and transparent so the evaluation design can be demonstrated and extended.
