from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class IssueRequest(BaseModel):
    title: str
    body: str = ""
    labels: List[str] = Field(default_factory=list)
    repository: Optional[str] = None
    author: Optional[str] = None


class PRRequest(BaseModel):
    title: str
    body: str = ""
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    repository: Optional[str] = None
    author: Optional[str] = None
    diff: Optional[str] = None

    @field_validator("changed_files", "additions", "deletions")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("numeric change counts must be non-negative")
        return value


class ExperimentRequest(BaseModel):
    experiment: str
    metrics: Dict[str, Any]
    baseline: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    workflow: str
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]
    decided_by: str = "human"
    decision_note: str = ""


class IssueDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: Literal["security", "bug", "ai-ml", "engineering"]
    priority: Literal["critical", "high", "medium", "low"]
    labels: List[str]
    summary: str
    recommended_action: str
    confidence: float
    requires_human_approval: bool = True

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class PRDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    risk: Literal["high", "medium", "low"]
    risk_score: float = Field(ge=0, le=100)
    review_summary: str
    recommended_checks: List[str]
    requires_human_approval: bool = True


class ExperimentDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    next_action: str


class GatewayMetadata(BaseModel):
    provider: str = "gateway"
    model: str = "unknown"
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    latency_ms: float = 0
    request_id: Optional[str] = None
