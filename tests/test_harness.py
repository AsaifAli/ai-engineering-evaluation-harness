from app.harness import AgentRun, timed_run


class DemoAdapter:
    async def run(self, workflow, payload):
        return AgentRun(run_id="demo", workflow=workflow, status="completed", output={"ok": True})


def test_harness_timed_run():
    import asyncio
    result = asyncio.run(timed_run(DemoAdapter(), "demo", {}))
    assert result.status == "completed"
    assert result.run_id == "demo"
    assert result.output["ok"] is True
