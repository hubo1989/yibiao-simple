def test_knowledge_doc_has_backend_marker():
    from app.models.knowledge import KnowledgeDoc

    assert hasattr(KnowledgeDoc, "index_backend")
    assert hasattr(KnowledgeDoc, "index_version")
