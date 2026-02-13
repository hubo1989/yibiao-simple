"""章节状态流转 API 单元测试"""
import uuid

import pytest

from app.routers.chapters import (
    STATUS_TRANSITIONS,
    _validate_status_transition,
    StatusUpdateRequest,
    StatusUpdateResponse,
)
from app.models.chapter import ChapterStatus
from app.models.project import ProjectMemberRole
from app.models.user import UserRole


class TestStatusTransitionsDefinition:
    """状态转换规则定义测试"""

    def test_pending_can_transition_to_generated(self):
        """pending 状态可以转换到 generated"""
        assert ChapterStatus.GENERATED in STATUS_TRANSITIONS[ChapterStatus.PENDING]

    def test_generated_can_transition_to_reviewing(self):
        """generated 状态可以转换到 reviewing"""
        assert ChapterStatus.REVIEWING in STATUS_TRANSITIONS[ChapterStatus.GENERATED]

    def test_reviewing_can_transition_to_finalized(self):
        """reviewing 状态可以转换到 finalized"""
        assert ChapterStatus.FINALIZED in STATUS_TRANSITIONS[ChapterStatus.REVIEWING]

    def test_reviewing_can_transition_to_generated(self):
        """reviewing 状态可以打回到 generated"""
        assert ChapterStatus.GENERATED in STATUS_TRANSITIONS[ChapterStatus.REVIEWING]

    def test_finalized_has_no_transitions(self):
        """finalized 状态没有允许的转换"""
        assert len(STATUS_TRANSITIONS[ChapterStatus.FINALIZED]) == 0

    def test_invalid_transition_not_in_rules(self):
        """不允许的状态转换不在规则中"""
        # pending 不能直接到 reviewing
        assert ChapterStatus.REVIEWING not in STATUS_TRANSITIONS[ChapterStatus.PENDING]
        # pending 不能直接到 finalized
        assert ChapterStatus.FINALIZED not in STATUS_TRANSITIONS[ChapterStatus.PENDING]
        # generated 不能直接到 finalized
        assert ChapterStatus.FINALIZED not in STATUS_TRANSITIONS[ChapterStatus.GENERATED]


class TestStatusTransitionEditorPermissions:
    """Editor 状态转换权限测试"""

    def test_editor_can_pending_to_generated(self):
        """Editor 可以将 pending 转换为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.PENDING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is True
        assert error == ""

    def test_editor_can_generated_to_reviewing(self):
        """Editor 可以将 generated 转换为 reviewing"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.GENERATED,
            ChapterStatus.REVIEWING,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is True
        assert error == ""

    def test_editor_cannot_reviewing_to_finalized(self):
        """Editor 不能将 reviewing 转换为 finalized"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.FINALIZED,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is False
        assert "无权" in error

    def test_editor_cannot_reviewing_to_generated(self):
        """Editor 不能将 reviewing 打回为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is False
        assert "无权" in error

    def test_editor_cannot_transition_from_finalized(self):
        """Editor 不能从 finalized 转换状态"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.FINALIZED,
            ChapterStatus.REVIEWING,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is False


class TestStatusTransitionReviewerPermissions:
    """Reviewer 状态转换权限测试"""

    def test_reviewer_cannot_pending_to_generated(self):
        """Reviewer 不能将 pending 转换为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.PENDING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.REVIEWER,
            UserRole.REVIEWER,
        )
        assert is_valid is False

    def test_reviewer_can_reviewing_to_finalized(self):
        """Reviewer 可以将 reviewing 转换为 finalized"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.FINALIZED,
            ProjectMemberRole.REVIEWER,
            UserRole.REVIEWER,
        )
        assert is_valid is True
        assert error == ""

    def test_reviewer_can_reviewing_to_generated(self):
        """Reviewer 可以将 reviewing 打回为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.REVIEWER,
            UserRole.REVIEWER,
        )
        assert is_valid is True
        assert error == ""


class TestStatusTransitionOwnerPermissions:
    """Owner 状态转换权限测试"""

    def test_owner_can_pending_to_generated(self):
        """Owner 可以将 pending 转换为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.PENDING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.OWNER,
            UserRole.EDITOR,
        )
        assert is_valid is True

    def test_owner_can_generated_to_reviewing(self):
        """Owner 可以将 generated 转换为 reviewing"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.GENERATED,
            ChapterStatus.REVIEWING,
            ProjectMemberRole.OWNER,
            UserRole.EDITOR,
        )
        assert is_valid is True

    def test_owner_can_reviewing_to_finalized(self):
        """Owner 可以将 reviewing 转换为 finalized"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.FINALIZED,
            ProjectMemberRole.OWNER,
            UserRole.EDITOR,
        )
        assert is_valid is True

    def test_owner_can_reviewing_to_generated(self):
        """Owner 可以将 reviewing 打回为 generated"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.OWNER,
            UserRole.EDITOR,
        )
        assert is_valid is True


class TestStatusTransitionAdminPermissions:
    """全局 Admin 状态转换权限测试"""

    def test_admin_can_any_transition(self):
        """全局 Admin 可以执行任意状态转换"""
        # Admin 可以从 pending 直接到 finalized
        is_valid, error = _validate_status_transition(
            ChapterStatus.PENDING,
            ChapterStatus.FINALIZED,
            ProjectMemberRole.REVIEWER,  # 即使项目角色很低
            UserRole.ADMIN,
        )
        assert is_valid is True
        assert error == ""

    def test_admin_can_transition_from_finalized(self):
        """全局 Admin 可以从 finalized 转换状态"""
        is_valid, error = _validate_status_transition(
            ChapterStatus.FINALIZED,
            ChapterStatus.REVIEWING,
            ProjectMemberRole.EDITOR,
            UserRole.ADMIN,
        )
        assert is_valid is True
        assert error == ""


class TestStatusUpdateSchemas:
    """状态更新 Schema 测试"""

    def test_status_update_request_valid(self):
        """有效的状态更新请求"""
        request = StatusUpdateRequest(status=ChapterStatus.GENERATED)
        assert request.status == ChapterStatus.GENERATED

    def test_status_update_request_all_statuses(self):
        """所有状态值都有效"""
        for status in ChapterStatus:
            request = StatusUpdateRequest(status=status)
            assert request.status == status

    def test_status_update_response(self):
        """状态更新响应"""
        response = StatusUpdateResponse(
            id=str(uuid.uuid4()),
            chapter_number="1.2.3",
            title="测试章节",
            old_status="pending",
            new_status="generated",
            message="章节状态已从 pending 更新为 generated",
        )
        assert response.old_status == "pending"
        assert response.new_status == "generated"
        assert "pending" in response.message
        assert "generated" in response.message


class TestInvalidTransitions:
    """无效状态转换测试"""

    def test_same_status_not_in_rules(self):
        """相同状态不在转换规则中"""
        # pending -> pending 不在规则中
        assert ChapterStatus.PENDING not in STATUS_TRANSITIONS[ChapterStatus.PENDING]

    def test_backward_transition_not_allowed_for_editor(self):
        """Editor 不能进行逆向转换（除了由内容编辑触发的 pending->generated）"""
        # Editor 不能从 reviewing 打回
        is_valid, _ = _validate_status_transition(
            ChapterStatus.REVIEWING,
            ChapterStatus.GENERATED,
            ProjectMemberRole.EDITOR,
            UserRole.EDITOR,
        )
        assert is_valid is False

    def test_skip_status_transition_not_allowed(self):
        """不能跳过中间状态"""
        # pending 不能直接到 reviewing
        is_valid, error = _validate_status_transition(
            ChapterStatus.PENDING,
            ChapterStatus.REVIEWING,
            ProjectMemberRole.OWNER,
            UserRole.EDITOR,
        )
        assert is_valid is False
        assert "不允许" in error
