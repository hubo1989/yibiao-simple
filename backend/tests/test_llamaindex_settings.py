from app.config import Settings


def test_llamaindex_defaults_present():
    settings = Settings()
    assert settings.knowledge_vector_backend == "llamaindex"
    assert settings.embedding_model
    assert settings.embedding_dimension > 0
    assert settings.knowledge_chunk_size > 0
    assert settings.knowledge_chunk_overlap >= 0


def test_env_llm_and_embedding_settings(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8001/v1")
    monkeypatch.setenv("LLM_API_KEY", "local-key")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:14b")
    monkeypatch.setenv("LLM_MODELS", "qwen2.5:14b,deepseek-r1:14b")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://localhost:8002/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "bge-m3")
    monkeypatch.setenv("EMBEDDING_MODELS", "bge-m3,text-embedding-3-large")

    settings = Settings()

    assert settings.llm_provider == "openai-compatible"
    assert settings.llm_base_url == "http://localhost:8001/v1"
    assert settings.llm_api_key == "local-key"
    assert settings.generation_model == "qwen2.5:14b"
    assert settings.generation_models == ["qwen2.5:14b", "deepseek-r1:14b"]
    assert settings.embedding_provider == "openai-compatible"
    assert settings.effective_embedding_base_url == "http://localhost:8002/v1"
    assert settings.effective_embedding_api_key == "embed-key"
    assert settings.index_models == ["bge-m3", "text-embedding-3-large"]


def test_embedding_api_key_falls_back_to_llm_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "shared-key")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    settings = Settings()

    assert settings.effective_embedding_api_key == "shared-key"
