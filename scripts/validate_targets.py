from __future__ import annotations

import asyncio
import json

from app.targets import check_all_target_health


async def main() -> int:
    results = await check_all_target_health()
    print(json.dumps({"targets": results}, indent=2))
    configured = [x for x in results if x.get("configured")]
    failures = [x for x in configured if x.get("status") != "healthy"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
