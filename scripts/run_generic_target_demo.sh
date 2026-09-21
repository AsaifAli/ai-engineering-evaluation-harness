#!/usr/bin/env sh
set -eu

echo "== customer-rag health =="
curl -fsS http://localhost:9001/health
echo

echo "== harness target health =="
curl -fsS http://localhost:8000/api/targets/health
echo

echo "== generic adapter execution =="
curl -fsS -X POST 'http://localhost:8000/api/targets/customer-rag/run?mode=live' \
  -H 'Content-Type: application/json' \
  -d '{"workflow":"query","query":"What is the enterprise refund policy?"}'
echo
