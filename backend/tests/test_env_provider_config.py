def test_build_env_provider_option_from_settings(monkeypatch):
    from app.routers import config as config_router

    monkeypatch.setattr(config_router.settings, "llm_provider", "openai-compatible")
    monkeypatch.setattr(config_router.settings, "llm_base_url", "http://localhost:8001/v1")
    monkeypatch.setattr(config_router.settings, "llm_api_key", "local-key")
    monkeypatch.setattr(config_router.settings, "llm_model", "qwen2.5:14b")
    monkeypatch.setattr(config_router.settings, "llm_models", "qwen2.5:14b,deepseek-r1:14b")
    monkeypatch.setattr(config_router.settings, "embedding_provider", "openai-compatible")
    monkeypatch.setattr(config_router.settings, "embedding_base_url", "http://localhost:8002/v1")
    monkeypatch.setattr(config_router.settings, "embedding_model", "bge-m3")

    provider = config_router.build_env_provider_option(is_default=True)

    assert provider is not None
    assert provider.config_id == "env"
    assert provider.provider == "openai-compatible"
    assert provider.models == ["qwen2.5:14b", "deepseek-r1:14b"]
    assert provider.default_model == "qwen2.5:14b"
    assert provider.index_model == "bge-m3"
    assert provider.embedding_base_url == "http://localhost:8002/v1"
    assert provider.embedding_provider == "openai-compatible"
    assert provider.source == "environment"
    assert provider.is_default is True
