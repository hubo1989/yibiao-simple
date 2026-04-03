from app.services.llamaindex_knowledge_service import build_access_filters


def test_build_filters_for_user_scope():
    filters = build_access_filters(user_id="u1", enterprise_id=None)
    assert filters
    # 应该有 global 过滤
    assert {"key": "scope", "value": "global"} in filters
    # 应该有 user 过滤
    assert {"key": "owner_id", "value": "u1"} in filters


def test_build_filters_with_enterprise():
    filters = build_access_filters(user_id="u1", enterprise_id="e1")
    # 应该同时包含 user 和 enterprise
    owner_values = [f["value"] for f in filters if f["key"] == "owner_id"]
    assert "u1" in owner_values
    assert "e1" in owner_values


def test_build_filters_no_user():
    filters = build_access_filters(user_id=None, enterprise_id=None)
    assert len(filters) == 1
    assert filters[0] == {"key": "scope", "value": "global"}
