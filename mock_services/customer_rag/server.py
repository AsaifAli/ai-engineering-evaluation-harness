from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DOCUMENTS = [
    {
        "id": "policy_v3.pdf#section_4",
        "text": "Enterprise refund requests must be submitted within 30 days of the invoice date.",
        "score": 0.94,
    },
    {
        "id": "enterprise_terms.pdf#section_2",
        "text": "Refunds are reviewed against the enterprise service agreement and invoice date.",
        "score": 0.87,
    },
    {
        "id": "billing_faq.md#refunds",
        "text": "Standard customer refunds are subject to the applicable service terms.",
        "score": 0.61,
    },
]


class Handler(BaseHTTPRequestHandler):
    server_version = "CustomerRAGDemo/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok", "service": "customer-rag-demo"})
            return
        self._json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/run":
            self._json(404, {"detail": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"detail": "invalid JSON"})
            return

        workflow = body.get("workflow", "query")
        payload = body.get("payload") or {}
        query = str(payload.get("query") or "")

        self._json(
            200,
            {
                "run_id": "customer-rag-demo-001",
                "status": "completed",
                "duration_ms": 18,
                "usage": {"prompt_tokens": 112, "completion_tokens": 38, "total_tokens": 150},
                "output": {
                    "query": query,
                    "answer": "Enterprise refund requests must be submitted within 30 days of the invoice date.",
                    "retrieved_documents": DOCUMENTS,
                    "citations": [
                        "policy_v3.pdf#section_4",
                        "enterprise_terms.pdf#section_2",
                    ],
                    "workflow": workflow,
                },
                "warnings": [],
            },
        )

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[customer-rag] {fmt % args}")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9001), Handler).serve_forever()
