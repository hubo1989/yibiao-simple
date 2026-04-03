def test_metadata_contract_contains_all_filterable_fields():
    import uuid
    from app.services.llamaindex_knowledge_service import build_document_metadata

    metadata = build_document_metadata(
        doc_id=uuid.uuid4(),
        title="Demo",
        doc_type="history_bid",
        scope="user",
        owner_id=uuid.uuid4(),
        category="cases",
        tags=["x"],
    )
    assert sorted(metadata.keys()) == [
        "category",
        "doc_id",
        "doc_type",
        "owner_id",
        "scope",
        "tags",
        "title",
    ]
