from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any
import json

import httpx

from .config import EXTRA_TARGETS_JSON


@dataclass(frozen=True)
class TargetSpec:
    slug: str
    name: str
    role: str
    repository: str
    expected_url: str
    health_path: str
    mode: str = "health_only"
    adapter: str = "health_only"
    evaluation_pack: str = ""
    run_path: str = "/run"
    configured_env: str = ""
    capabilities: tuple[str, ...] = ()


BUILTIN_TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec(
        slug="flowpilot",
        name="FlowPilot — AI Automation Command Center",
        role="Agentic automation control plane",
        repository="https://github.com/AsaifAli/AI-Automation-Command-Center",
        expected_url="https://ai-automation-api.onrender.com",
        health_path="/health",
        mode="live_run",
        adapter="flowpilot",
        evaluation_pack="agent_workflow",
        configured_env="COMMAND_CENTER_BASE_URL",
        capabilities=("live_runs", "workflow_evaluation", "approval", "audit"),
    ),
    TargetSpec(
        slug="legacylens",
        name="LegacyLens — Agentic Software Modernization",
        role="Agentic code modernization",
        repository="https://github.com/AsaifAli/AI-Code-Modernization-Platform",
        expected_url="https://ai-code-modernization-api.onrender.com",
        health_path="/healthz",
        mode="live_task",
        adapter="legacylens",
        evaluation_pack="code_modernization",
        configured_env="LEGACY_LENS_BASE_URL",
        capabilities=("health", "migration_tasks", "quality_gates", "semantic_verification"),
    ),
    TargetSpec(
        slug="evidenceflow",
        name="EvidenceFlow — Verified Sparse-First RAG",
        role="Agentic RAG and research",
        repository="https://github.com/AsaifAli/LangGraph-RAG",
        expected_url="https://evidenceflow-langgraph.onrender.com",
        health_path="/_stcore/health",
        mode="replay_ready",
        adapter="health_only",
        evaluation_pack="rag",
        configured_env="EVIDENCEFLOW_BASE_URL",
        capabilities=("health", "rag_evaluation", "grounding", "citation_verification"),
    ),
    TargetSpec(
        slug="quotesense",
        name="QuoteSense — Procurement Intelligence",
        role="Document intelligence and procurement",
        repository="https://github.com/AsaifAli/quotation-analyzer",
        expected_url="https://quotation-analyzer.onrender.com",
        health_path="/_stcore/health",
        mode="replay_ready",
        adapter="health_only",
        evaluation_pack="document_intelligence",
        configured_env="QUOTESENSE_BASE_URL",
        capabilities=("health", "document_extraction", "deterministic_scoring", "risk_analysis"),
    ),
    TargetSpec(
        slug="webqa",
        name="WebQA Intelligence — AI-Assisted Testing",
        role="Browser QA and regression intelligence",
        repository="https://github.com/AsaifAli/web-crawler-agent",
        expected_url="https://web-crawler-agent.onrender.com",
        health_path="/_stcore/health",
        mode="replay_ready",
        adapter="health_only",
        evaluation_pack="browser_qa",
        configured_env="WEBQA_BASE_URL",
        capabilities=("health", "qa_generation", "safe_execution", "regression"),
    ),
)


def _load_extra_targets() -> tuple[TargetSpec, ...]:
    if not EXTRA_TARGETS_JSON:
        return ()
    try:
        raw = json.loads(EXTRA_TARGETS_JSON)
    except json.JSONDecodeError as exc:
        raise ValueError("EXTRA_TARGETS_JSON must be valid JSON") from exc
    if not isinstance(raw, list):
        raise ValueError("EXTRA_TARGETS_JSON must be a JSON list")
    extras: list[TargetSpec] = []
    builtin_slugs = {item.slug for item in BUILTIN_TARGETS}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each extra target must be a JSON object")
        required = {"slug", "name", "role", "expected_url", "health_path", "adapter", "evaluation_pack", "configured_env"}
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(f"Extra target missing fields: {', '.join(missing)}")
        slug = str(item["slug"]).strip().lower()
        if slug in builtin_slugs or any(existing.slug == slug for existing in extras):
            raise ValueError(f"Duplicate target slug: {slug}")
        capabilities = tuple(str(value) for value in item.get("capabilities", []))
        extras.append(
            TargetSpec(
                slug=slug,
                name=str(item["name"]),
                role=str(item["role"]),
                repository=str(item.get("repository", "")),
                expected_url=str(item["expected_url"]).rstrip("/"),
                health_path=str(item["health_path"]),
                mode=str(item.get("mode", "live_run")),
                adapter=str(item["adapter"]),
                evaluation_pack=str(item["evaluation_pack"]),
                run_path=str(item.get("run_path", "/run")),
                configured_env=str(item["configured_env"]),
                capabilities=capabilities,
            )
        )
    return tuple(extras)


TARGETS: tuple[TargetSpec, ...] = BUILTIN_TARGETS + _load_extra_targets()


def target_catalog() -> list[dict[str, Any]]:
    return [asdict(t) for t in TARGETS]


def configured_target_url(spec: TargetSpec) -> str:
    import os

    return os.getenv(spec.configured_env, "").strip().rstrip("/")


def target_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for spec in TARGETS:
        base_url = configured_target_url(spec)
        registry[spec.slug] = {
            **asdict(spec),
            "configured": bool(base_url),
            "base_url": base_url,
        }
    return registry


async def check_target_health(spec: TargetSpec, *, timeout: float = 8.0) -> dict[str, Any]:
    base_url = configured_target_url(spec)
    if not base_url:
        return {
            "slug": spec.slug,
            "name": spec.name,
            "status": "not_configured",
            "configured": False,
            "expected_url": spec.expected_url,
            "health_url": f"{spec.expected_url}{spec.health_path}",
            "mode": spec.mode,
        }

    url = f"{base_url}{spec.health_path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
        ok = response.status_code < 400
        return {
            "slug": spec.slug,
            "name": spec.name,
            "status": "healthy" if ok else "unhealthy",
            "configured": True,
            "http_status": response.status_code,
            "base_url": base_url,
            "health_url": url,
            "mode": spec.mode,
        }
    except httpx.HTTPError as exc:
        return {
            "slug": spec.slug,
            "name": spec.name,
            "status": "unreachable",
            "configured": True,
            "base_url": base_url,
            "health_url": url,
            "mode": spec.mode,
            "error": str(exc),
        }


async def check_all_target_health() -> list[dict[str, Any]]:
    return await asyncio.gather(*(check_target_health(spec) for spec in TARGETS))
