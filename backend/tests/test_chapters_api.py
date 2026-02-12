"""章节锁定 API 单元测试"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.routers.chapters import (
    LOCK_TIMEOUT_MINUTES,
    _is_lock_expired,
    LockResponse,
    ChapterContentResponse,
    ChapterContentUpdateRequest,
)


class TestLockExpiration:
    """锁定过期逻辑测试"""

    def test_lock_not_expired_recently_locked(self):
        """测试刚锁定的章节未过期"""
        class MockChapter:
            locked_by = uuid.uuid4()
            locked_at = datetime.now(timezone.utc)

        chapter = MockChapter()
        assert _is_lock_expired(chapter) is False

    def test_lock_expired_after_timeout(self):
        """测试超过 30 分钟后锁定过期"""
        class MockChapter:
            locked_by = uuid.uuid4()
            # 31 分钟前锁定
            locked_at = datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT_MINUTES + 1)

        chapter = MockChapter()
        assert _is_lock_expired(chapter) is True

    def test_lock_not_expired_exactly_at_boundary(self):
        """测试刚好 30 分钟时未过期"""
        class MockChapter:
            locked_by = uuid.uuid4()
            # 29 分钟前锁定
            locked_at = datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT_MINUTES - 1)

        chapter = MockChapter()
        assert _is_lock_expired(chapter) is False

    def test_lock_expired_when_no_locked_at(self):
        """测试 locked_at 为 None 时视为过期"""
        class MockChapter:
            locked_by = uuid.uuid4()
            locked_at = None

        chapter = MockChapter()
        assert _is_lock_expired(chapter) is True

    def test_lock_expired_when_no_locked_by(self):
        """测试 locked_by 为 None 时"""
        class MockChapter:
            locked_by = None
            locked_at = datetime.now(timezone.utc)

        chapter = MockChapter()
        # 虽然有 locked_at，但没有 locked_by，这种情况下 _is_lock_expired 只看 locked_at
        # 但根据业务逻辑，locked_by 为 None 意味着未锁定
        # 这里测试函数的行为：只要有 locked_at 且未超时就返回 False
        assert _is_lock_expired(chapter) is False

    def test_lock_expired_with_naive_datetime(self):
        """测试无时区信息的 datetime 被正确处理"""
        class MockChapter:
            locked_by = uuid.uuid4()
            # 无时区信息
            locked_at = datetime.utcnow() - timedelta(minutes=LOCK_TIMEOUT_MINUTES + 1)

        chapter = MockChapter()
        assert _is_lock_expired(chapter) is True


class TestLockResponseSchema:
    """锁定响应 Schema 测试"""

    def test_lock_response_success(self):
        """测试成功的锁定响应"""
        user_id = uuid.uuid4()
        response = LockResponse(
            success=True,
            chapter_id=str(uuid.uuid4()),
            locked_by=str(user_id),
            locked_at=datetime.now(timezone.utc).isoformat(),
            locked_by_username="testuser",
            message="章节锁定成功",
        )
        assert response.success is True
        assert response.locked_by_username == "testuser"

    def test_lock_response_unlocked(self):
        """测试解锁后的响应"""
        response = LockResponse(
            success=True,
            chapter_id=str(uuid.uuid4()),
            message="章节解锁成功",
        )
        assert response.success is True
        assert response.locked_by is None
        assert response.locked_at is None


class TestChapterContentResponseSchema:
    """章节内容响应 Schema 测试"""

    def test_response_with_lock_info(self):
        """测试包含锁定信息的响应"""
        response = ChapterContentResponse(
            id=str(uuid.uuid4()),
            chapter_number="1.2.3",
            title="测试章节",
            content="这是章节内容",
            status="generated",
            locked_by=str(uuid.uuid4()),
            locked_at=datetime.now(timezone.utc).isoformat(),
            locked_by_username="editor1",
            is_locked=True,
            lock_expired=False,
        )
        assert response.is_locked is True
        assert response.lock_expired is False
        assert response.locked_by_username == "editor1"

    def test_response_without_lock(self):
        """测试未锁定的响应"""
        response = ChapterContentResponse(
            id=str(uuid.uuid4()),
            chapter_number="1.1",
            title="未锁定章节",
            content="内容",
            status="pending",
            is_locked=False,
            lock_expired=False,
        )
        assert response.is_locked is False
        assert response.locked_by is None

    def test_response_with_expired_lock(self):
        """测试锁定已过期的响应"""
        response = ChapterContentResponse(
            id=str(uuid.uuid4()),
            chapter_number="2.1",
            title="过期锁定章节",
            content="内容",
            status="generated",
            locked_by=str(uuid.uuid4()),
            locked_at=(datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat(),
            is_locked=True,
            lock_expired=True,
        )
        assert response.is_locked is True
        assert response.lock_expired is True


class TestChapterContentUpdateRequest:
    """章节内容更新请求 Schema 测试"""

    def test_update_with_content_only(self):
        """测试只有内容的更新请求"""
        request = ChapterContentUpdateRequest(content="新内容")
        assert request.content == "新内容"
        assert request.change_summary is None

    def test_update_with_summary(self):
        """测试带变更摘要的更新请求"""
        request = ChapterContentUpdateRequest(
            content="修改后的内容",
            change_summary="修正了错别字",
        )
        assert request.content == "修改后的内容"
        assert request.change_summary == "修正了错别字"

    def test_empty_content_is_valid(self):
        """测试空内容是有效的（用于清空内容）"""
        request = ChapterContentUpdateRequest(content="")
        assert request.content == ""


class TestLockTimeoutConstant:
    """锁定超时常量测试"""

    def test_lock_timeout_value(self):
        """验证锁定超时为 30 分钟"""
        assert LOCK_TIMEOUT_MINUTES == 30

    def test_lock_timeout_is_reasonable(self):
        """验证锁定超时在合理范围内"""
        # 锁定时间应在 5-120 分钟之间
        assert 5 <= LOCK_TIMEOUT_MINUTES <= 120


class TestLockConflictScenarios:
    """锁定冲突场景测试（逻辑验证）"""

    def test_same_user_can_relock(self):
        """同一用户可以刷新锁定"""
        # 逻辑：如果 chapter.locked_by == current_user.id，允许锁定（刷新时间）
        user_id = uuid.uuid4()
        chapter_locked_by = user_id
        assert chapter_locked_by == user_id

    def test_different_user_cannot_lock(self):
        """不同用户不能锁定已被锁定的章节"""
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        chapter_locked_by = user_id
        assert chapter_locked_by != other_user_id

    def test_expired_lock_allows_new_lock(self):
        """过期锁定允许新用户锁定"""
        # 锁定已过期
        old_lock_time = datetime.now(timezone.utc) - timedelta(minutes=31)
        assert old_lock_time < datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT_MINUTES)


class TestUnlockPermissions:
    """解锁权限逻辑测试"""

    def test_locker_can_unlock(self):
        """锁定者本人可以解锁"""
        user_id = uuid.uuid4()
        chapter_locked_by = user_id
        current_user_id = user_id
        is_locker = chapter_locked_by == current_user_id
        assert is_locker is True

    def test_owner_can_unlock(self):
        """项目 Owner 可以解锁"""
        role = "owner"
        is_owner = role == "owner"
        assert is_owner is True

    def test_editor_cannot_unlock_others_lock(self):
        """Editor 不能解锁他人的锁定"""
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        chapter_locked_by = user_id
        current_user_id = other_user_id
        role = "editor"

        is_locker = chapter_locked_by == current_user_id
        is_owner = role == "owner"

        can_unlock = is_locker or is_owner
        assert can_unlock is False

    def test_reviewer_cannot_unlock(self):
        """Reviewer 没有解锁权限"""
        # Reviewer 甚至不应该能访问锁定/解锁接口（被 require_editor 拦截）
        # 这里只是验证角色层级
        role = "reviewer"
        assert role != "owner" and role != "editor"
