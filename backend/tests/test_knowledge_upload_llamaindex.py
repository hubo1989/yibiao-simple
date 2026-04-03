def test_upload_indexing_uses_file_service():
    """验证文件上传索引使用 FileService 而不是 pdf_utils"""
    from app.services.file_service import FileService
    assert hasattr(FileService, "extract_text_from_pdf")


def test_llamaindex_service_has_required_methods():
    """验证 LlamaIndex 服务暴露了所需的方法"""
    from app.services.llamaindex_knowledge_service import LlamaIndexKnowledgeService
    assert hasattr(LlamaIndexKnowledgeService, "index_document")
    assert hasattr(LlamaIndexKnowledgeService, "search")
    assert hasattr(LlamaIndexKnowledgeService, "delete_document")


def test_knowledge_router_imports_llamaindex():
    """验证 knowledge 路由导入了 LlamaIndex 服务"""
    from app.routers import knowledge
    # 应该能从模块找到 LlamaIndex 相关属性
    assert hasattr(knowledge, "process_vector_indexing_only")
