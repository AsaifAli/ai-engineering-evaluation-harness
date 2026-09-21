from __future__ import annotations

from typing import Any

from ..harness import AgentRun, HttpAIProjectAdapter


class GenericHTTPAdapter(HttpAIProjectAdapter):
    """Configurable adapter for services exposing a simple JSON run endpoint."""

    name = "generic-http"

    def __init__(
        self,
        base_url: str,
        *,
        run_path: str = "/run",
        timeout: float = 60.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(base_url, timeout=timeout)
        self.run_path = run_path if run_path.startswith("/") else f"/{run_path}"
        self._headers = headers or {}

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", **self._headers}

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        body = {"workflow": workflow, "payload": payload}
        response = await self.request("POST", self.run_path, headers=self.headers, json=body)
        return self.normalize_response(response, workflow)

    def normalize_response(self, response: dict[str, Any], workflow: str) -> AgentRun:
        return AgentRun(
            run_id=str(response.get("run_id") or response.get("id") or ""),
            workflow=workflow,
            status=str(response.get("status") or "unknown"),
            output=response.get("output") if isinstance(response.get("output"), dict) else response,
            duration_ms=int(response.get("duration_ms") or response.get("latency_ms") or 0),
            usage=response.get("usage") if isinstance(response.get("usage"), dict) else None,
            warnings=response.get("warnings") if isinstance(response.get("warnings"), list) else [],
            trace=response.get("trace") if isinstance(response.get("trace"), list) else response.get("steps") if isinstance(response.get("steps"), list) else [],
            metadata={k: response.get(k) for k in ("prompt_version", "model_version", "config_version", "dataset_version") if response.get(k) not in (None, "")},
        )
