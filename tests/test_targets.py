from app.targets import TARGETS, target_catalog, target_registry


def test_five_portfolio_targets_registered():
    slugs = {target.slug for target in TARGETS}
    assert {"flowpilot", "legacylens", "evidenceflow", "quotesense", "webqa"}.issubset(slugs)


def test_target_registry_keeps_targets_unconfigured_without_runtime_env(monkeypatch):
    for target in TARGETS:
        monkeypatch.delenv(target.configured_env, raising=False)
    registry = target_registry()
    assert all(item["configured"] is False for item in registry.values())
    assert len(target_catalog()) >= 5


def test_targets_declare_modular_adapter_and_evaluation_pack():
    expected = {
        "flowpilot": ("flowpilot", "agent_workflow"),
        "legacylens": ("legacylens", "code_modernization"),
        "evidenceflow": ("generic_http", "rag"),
        "quotesense": ("generic_http", "document_intelligence"),
        "webqa": ("generic_http", "browser_qa"),
    }
    # Validate the five built-in portfolio targets explicitly.
    # Extra/plugin targets are intentionally allowed through the modular registry.
    by_slug = {target.slug: target for target in TARGETS}
    for slug, contract in expected.items():
        assert slug in by_slug
        target = by_slug[slug]
        assert (target.adapter, target.evaluation_pack) == contract

    # Target slugs must remain unique even when external/plugin targets are loaded.
    assert len(by_slug) == len(TARGETS)


def test_live_smoke_contracts_for_three_ui_projects():
    by_slug = {target.slug: target for target in TARGETS}
    for slug in ("evidenceflow", "quotesense", "webqa"):
        target = by_slug[slug]
        assert target.mode == "live_smoke"
        assert target.adapter == "generic_http"
        assert target.run_path == "/harness/smoke"
        assert target.health_path == "/health"
