import uuid

from app.services.llamaindex_knowledge_service import build_document_metadata


def test_build_document_metadata():
    owner_id = uuid.uuid4()
    metadata = build_document_metadata(
        doc_id=uuid.uuid4(),
        title="Test Doc",
        doc_type="other",
        scope="user",
        owner_id=owner_id,
        tags=["a", "b"],
        category="demo",
    )
    assert metadata["title"] == "Test Doc"
    assert metadata["scope"] == "user"
    assert metadata["owner_id"] == str(owner_id)
    assert metadata["tags"] == ["a", "b"]
