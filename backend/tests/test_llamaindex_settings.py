from app.config import Settings


def test_llamaindex_defaults_present():
    settings = Settings()
    assert settings.knowledge_vector_backend == "llamaindex"
    assert settings.embedding_model
    assert settings.embedding_dimension > 0
    assert settings.knowledge_chunk_size > 0
    assert settings.knowledge_chunk_overlap >= 0
