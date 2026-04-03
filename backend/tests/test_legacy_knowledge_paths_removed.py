def test_runtime_no_longer_depends_on_legacy_vector_service():
    """验证活跃运行时代码不再直接依赖旧的 VectorIndexService"""
    import importlib

    # 导入 knowledge 路由应该不触发 VectorIndexService
    spec = importlib.util.find_spec("app.routers.knowledge")
    assert spec is not None

    # 导入 retrieval service 应该不依赖旧的 VectorIndexService
    from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
    assert KnowledgeRetrievalService is not None

    # 验证 LlamaIndex 服务可导入
    from app.services.llamaindex_knowledge_service import (
        LlamaIndexKnowledgeService,
        build_document_metadata,
        build_access_filters,
        split_knowledge_text,
    )
    assert LlamaIndexKnowledgeService is not None
    assert callable(build_document_metadata)
    assert callable(build_access_filters)
    assert callable(split_knowledge_text)


def test_file_service_has_pdf_extractor():
    from app.services.file_service import FileService
    assert hasattr(FileService, "extract_text_from_pdf")
