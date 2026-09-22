# Lightweight MLOps Lifecycle

The harness deliberately implements the **smallest useful MLOps layer for an AI engineering portfolio system** rather than introducing MLflow or a full training platform.

## Model registry

`model_registry` tracks:

- provider and logical model name
- version
- lifecycle status (`observed`, `candidate`, `production`, `retired`)
- evaluation score and evaluation-set version
- config version
- promotion and retirement timestamps

A model can only be promoted through `POST /api/mlops/models/{id}/promote` when its evaluation score meets `MODEL_PROMOTION_MIN_SCORE` (default `0.90`). Promotion retires the previous production model for the same provider/name.

## Dataset registry

Every built-in replay evaluation dataset is registered by:

- dataset name
- version
- content SHA-256
- schema signature SHA-256
- sample count

This makes evaluation inputs reproducible without copying the dataset into a second storage system.

## Experiment tracking

Each evaluation batch creates an `experiment_runs` record linking:

`model version + dataset version + prompt version + config version + target + metrics`

The existing `experiment_comparisons` table remains the regression-comparison layer; `experiment_runs` is the lifecycle/run layer.

## API surface

Read-only endpoints:

- `GET /api/mlops/overview`
- `GET /api/mlops/models`
- `GET /api/mlops/datasets`
- `GET /api/mlops/experiments`

Controlled mutation endpoints:

- `POST /api/mlops/models`
- `POST /api/mlops/models/{id}/promote`
- `POST /api/mlops/datasets/sync`

When `HUB_API_KEY` is configured, mutation endpoints require `Authorization: Bearer <HUB_API_KEY>`.

## Why this is intentionally small

The system is not a conventional tabular ML training/serving platform. It is primarily an LLMOps and AI engineering control plane. Therefore it intentionally does **not** add feature stores, classic feature-drift detection, MLflow, Kubernetes, Redis, automated retraining, or full canary infrastructure.
