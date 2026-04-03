from app.services.llamaindex_knowledge_service import split_knowledge_text


def test_split_knowledge_text_returns_chunks():
    text = "第一段。\n\n第二段。\n\n第三段。"
    chunks = split_knowledge_text(text, chunk_size=20, chunk_overlap=5)
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_split_knowledge_text_empty():
    assert split_knowledge_text("") == []
    assert split_knowledge_text(None) == []


def test_split_knowledge_text_single_short():
    text = "短文本"
    chunks = split_knowledge_text(text, chunk_size=512, chunk_overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "短文本"
