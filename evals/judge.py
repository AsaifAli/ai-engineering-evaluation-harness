from __future__ import annotations

import json
from typing import Any

from app import gateway
from app.db import insert_judge_run

JUDGE_PROMPT_VERSION = "llm-judge-v1"
JUDGE_SYSTEM = """You are an LLM evaluation judge. Evaluate the candidate answer against the reference evidence.
Return ONLY valid JSON with keys: answer_relevance, groundedness, completeness, faithfulness, overall, rationale.
All scores must be integers from 1 to 5. Do not reward unsupported claims. Groundedness and faithfulness should reflect whether the answer is supported by the provided evidence.
Keep rationale concise and evidence-based."""


async def judge_response(*, target: str, case_id: str, answer: str, reference: str, context: list[str], quality_id: str | None = None) -> dict[str, Any]:
    if not gateway.configured():
        result = {
            "target": target,
            "case_id": case_id,
            "quality_id": quality_id,
            "status": "skipped",
            "provider": "gateway",
            "model": "session-selected",
            "reason": "LLM gateway session token is not configured",
            "prompt_version": JUDGE_PROMPT_VERSION,
        }
        insert_judge_run(**result, score=None, criteria={}, rationale="")
        return result

    response = await gateway.chat_json(
        system_prompt=JUDGE_SYSTEM,
        user_prompt=json.dumps({
            "candidate_answer": answer,
            "reference_answer": reference,
            "evidence_context": context,
        }, ensure_ascii=False),
        workflow="llm_judge",
        prompt_version=JUDGE_PROMPT_VERSION,
    )
    data = response.data
    criteria = {}
    for key in ("answer_relevance", "groundedness", "completeness", "faithfulness", "overall"):
        value = int(max(1, min(5, int(data.get(key, 1)))))
        criteria[key] = value
    score = round(sum(criteria.values()) / (5 * len(criteria)), 6)
    result = {
        "target": target,
        "case_id": case_id,
        "quality_id": quality_id,
        "status": "completed",
        "provider": response.provider,
        "model": response.model,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "score": score,
        "criteria": criteria,
        "rationale": str(data.get("rationale", ""))[:2000],
        "latency_ms": response.latency_ms,
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "estimated_cost_usd": response.estimated_cost_usd,
        },
    }
    insert_judge_run(target=target, case_id=case_id, quality_id=quality_id, status="completed", provider=response.provider, model=response.model, prompt_version=JUDGE_PROMPT_VERSION, score=score, criteria=criteria, rationale=result["rationale"], metadata={"latency_ms": response.latency_ms, "usage": result["usage"]})
    return result
