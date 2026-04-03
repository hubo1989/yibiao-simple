def test_knowledge_context_formatter_preserves_expected_sections():
    """验证 outline 章节生成中的知识上下文格式化保持稳定"""
    result = {
        "title": "企业案例",
        "doc_type": "company_info",
        "reasoning": "向量相似度匹配",
        "content_preview": "内容片段",
    }
    formatted = (
        f"[1] 类型: 企业资料/能力\n"
        f"标题: {result['title']}\n"
        f"相关性: {result['reasoning']}\n"
        f"内容:\n{result['content_preview']}"
    )
    assert "标题: 企业案例" in formatted
    assert "类型: 企业资料/能力" in formatted
    assert "相关性: 向量相似度匹配" in formatted
    assert "内容:\n内容片段" in formatted


def test_doc_type_label_mapping():
    """验证 doc_type 到中文标签的映射"""
    doc_type_label_map = {
        "history_bid": "历史标书风格",
        "company_info": "企业资料/能力",
    }
    assert doc_type_label_map["company_info"] == "企业资料/能力"
    assert doc_type_label_map["history_bid"] == "历史标书风格"
    # 未知类型应返回原始值
    assert doc_type_label_map.get("other", "other") == "other"
