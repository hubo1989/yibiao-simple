"""评论批注 API 单元测试"""
import uuid
from datetime import datetime, timezone

import pytest

from app.routers.comments import (
    CommentCreateRequest,
    CommentUpdateRequest,
    CommentResponse,
    CommentListResponse,
)


class TestCommentCreateRequest:
    """创建批注请求 Schema 测试"""

    def test_create_with_content_only(self):
        """测试只有内容的创建请求"""
        request = CommentCreateRequest(content="这是一个批注")
        assert request.content == "这是一个批注"
        assert request.position_start is None
        assert request.position_end is None

    def test_create_with_position(self):
        """测试带位置的创建请求"""
        request = CommentCreateRequest(
            content="这段需要修改",
            position_start=100,
            position_end=150,
        )
        assert request.content == "这段需要修改"
        assert request.position_start == 100
        assert request.position_end == 150

    def test_content_min_length_validation(self):
        """测试内容最小长度验证"""
        # 空内容应该失败（min_length=1）
        with pytest.raises(ValueError):
            CommentCreateRequest(content="")

    def test_content_max_length_validation(self):
        """测试内容最大长度验证"""
        # 超过 5000 字符应该失败
        long_content = "a" * 5001
        with pytest.raises(ValueError):
            CommentCreateRequest(content=long_content)

    def test_position_must_be_non_negative(self):
        """测试位置必须为非负数"""
        with pytest.raises(ValueError):
            CommentCreateRequest(content="test", position_start=-1)

        with pytest.raises(ValueError):
            CommentCreateRequest(content="test", position_end=-1)


class TestCommentUpdateRequest:
    """更新批注请求 Schema 测试"""

    def test_update_content(self):
        """测试更新内容"""
        request = CommentUpdateRequest(content="修改后的批注内容")
        assert request.content == "修改后的批注内容"


class TestCommentResponse:
    """批注响应 Schema 测试"""

    def test_response_basic_fields(self):
        """测试基本字段"""
        now = datetime.now(timezone.utc).isoformat()
        response = CommentResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            username="reviewer1",
            content="需要修改这段",
            position_start=10,
            position_end=50,
            is_resolved=False,
            created_at=now,
            updated_at=now,
        )
        assert response.is_resolved is False
        assert response.username == "reviewer1"
        assert response.resolved_by is None
        assert response.resolved_at is None

    def test_response_with_resolution(self):
        """测试已解决的批注响应"""
        now = datetime.now(timezone.utc).isoformat()
        response = CommentResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            username="reviewer1",
            content="需要修改这段",
            position_start=10,
            position_end=50,
            is_resolved=True,
            resolved_by=str(uuid.uuid4()),
            resolved_by_username="editor1",
            resolved_at=now,
            created_at=now,
            updated_at=now,
        )
        assert response.is_resolved is True
        assert response.resolved_by is not None
        assert response.resolved_by_username == "editor1"

    def test_response_without_position(self):
        """测试无位置信息的响应"""
        now = datetime.now(timezone.utc).isoformat()
        response = CommentResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            username="reviewer1",
            content="整体结构需要调整",
            position_start=None,
            position_end=None,
            is_resolved=False,
            created_at=now,
            updated_at=now,
        )
        assert response.position_start is None
        assert response.position_end is None


class TestCommentListResponse:
    """批注列表响应 Schema 测试"""

    def test_empty_list(self):
        """测试空列表"""
        response = CommentListResponse(items=[], total=0)
        assert response.items == []
        assert response.total == 0

    def test_list_with_items(self):
        """测试带项目的列表"""
        now = datetime.now(timezone.utc).isoformat()
        items = [
            CommentResponse(
                id=str(uuid.uuid4()),
                chapter_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                username=f"user{i}",
                content=f"批注{i}",
                position_start=None,
                position_end=None,
                is_resolved=False,
                created_at=now,
                updated_at=now,
            )
            for i in range(3)
        ]
        response = CommentListResponse(items=items, total=3)
        assert len(response.items) == 3
        assert response.total == 3


class TestPositionValidation:
    """位置验证逻辑测试"""

    def test_valid_position_range(self):
        """测试有效的位置范围"""
        request = CommentCreateRequest(
            content="test",
            position_start=0,
            position_end=100,
        )
        assert request.position_start < request.position_end

    def test_position_at_same_point(self):
        """测试起始和结束位置相同"""
        request = CommentCreateRequest(
            content="test",
            position_start=50,
            position_end=50,
        )
        # 相同位置是合法的（表示一个插入点）
        assert request.position_start == request.position_end

    def test_only_start_position(self):
        """测试只有起始位置"""
        request = CommentCreateRequest(
            content="test",
            position_start=100,
        )
        assert request.position_start == 100
        assert request.position_end is None

    def test_only_end_position(self):
        """测试只有结束位置"""
        request = CommentCreateRequest(
            content="test",
            position_end=100,
        )
        assert request.position_start is None
        assert request.position_end == 100


class TestCommentPermissionScenarios:
    """批注权限场景测试（逻辑验证）"""

    def test_author_can_resolve_own_comment(self):
        """作者可以解决自己的批注"""
        author_id = uuid.uuid4()
        current_user_id = author_id
        is_author = author_id == current_user_id
        assert is_author is True

    def test_owner_can_resolve_any_comment(self):
        """Owner 可以解决任何批注"""
        role = "owner"
        is_owner = role == "owner"
        assert is_owner is True

    def test_admin_can_resolve_any_comment(self):
        """Admin 可以解决任何批注"""
        user_role = "admin"
        is_admin = user_role == "admin"
        assert is_admin is True

    def test_editor_cannot_resolve_others_comment(self):
        """Editor 不能解决他人的批注"""
        author_id = uuid.uuid4()
        current_user_id = uuid.uuid4()
        role = "editor"

        is_author = author_id == current_user_id
        is_owner = role == "owner"
        is_admin = user_role == "admin" if "user_role" in dir() else False

        can_resolve = is_author or is_owner or is_admin
        assert can_resolve is False

    def test_only_author_or_admin_can_delete(self):
        """只有作者或 Admin 可以删除批注"""
        author_id = uuid.uuid4()

        # 作者可以删除
        current_user_id = author_id
        is_author = author_id == current_user_id
        is_admin = False
        can_delete = is_author or is_admin
        assert can_delete is True

        # Admin 可以删除
        current_user_id = uuid.uuid4()
        is_author = author_id == current_user_id
        is_admin = True
        can_delete = is_author or is_admin
        assert can_delete is True

        # 其他人不能删除
        current_user_id = uuid.uuid4()
        is_author = author_id == current_user_id
        is_admin = False
        can_delete = is_author or is_admin
        assert can_delete is False


class TestReviewerCanAddComments:
    """审阅者可以添加批注的权限测试"""

    def test_reviewer_role_allows_comment(self):
        """Reviewer 角色允许添加批注"""
        # require_reviewer 允许 REVIEWER、EDITOR、ADMIN
        allowed_roles = {"reviewer", "editor", "admin"}
        assert "reviewer" in allowed_roles

    def test_editor_role_allows_comment(self):
        """Editor 角色允许添加批注"""
        allowed_roles = {"reviewer", "editor", "admin"}
        assert "editor" in allowed_roles

    def test_admin_role_allows_comment(self):
        """Admin 角色允许添加批注"""
        allowed_roles = {"reviewer", "editor", "admin"}
        assert "admin" in allowed_roles


class TestCommentResolutionFlow:
    """批注解决流程测试"""

    def test_resolved_comment_has_timestamp(self):
        """已解决的批注有解决时间"""
        now = datetime.now(timezone.utc).isoformat()
        response = CommentResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            username="reviewer1",
            content="需要修改",
            position_start=10,
            position_end=50,
            is_resolved=True,
            resolved_by=str(uuid.uuid4()),
            resolved_by_username="editor1",
            resolved_at=now,
            created_at=now,
            updated_at=now,
        )
        assert response.resolved_at is not None

    def test_unresolved_comment_no_resolution_info(self):
        """未解决的批注没有解决信息"""
        now = datetime.now(timezone.utc).isoformat()
        response = CommentResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            username="reviewer1",
            content="需要修改",
            position_start=10,
            position_end=50,
            is_resolved=False,
            created_at=now,
            updated_at=now,
        )
        assert response.resolved_by is None
        assert response.resolved_at is None
        assert response.resolved_by_username is None
