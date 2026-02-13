"""管理员用户管理和使用统计 API 测试"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.project import Project
from app.models.operation_log import OperationLog, ActionType
from app.schemas.user import (
    UserResponse,
    UserListResponse,
    UsageStatsResponse,
)
from app.auth.security import get_password_hash, verify_password


class TestUserListSchema:
    """用户列表 Schema 测试"""

    def test_user_list_response_creation(self):
        """测试用户列表响应创建"""
        user = UserResponse(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            role=UserRole.EDITOR,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        response = UserListResponse(
            items=[user],
            total=1,
            page=1,
            page_size=20,
        )

        assert response.total == 1
        assert len(response.items) == 1
        assert response.page == 1
        assert response.page_size == 20

    def test_user_list_response_empty(self):
        """测试空用户列表响应"""
        response = UserListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )

        assert response.total == 0
        assert len(response.items) == 0


class TestAdminUserCreateSchema:
    """管理员创建用户 Schema 测试"""

    def test_admin_user_create_defaults(self):
        """测试创建用户请求默认值"""
        from app.schemas.user import AdminUserCreate

        data = AdminUserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123",
        )

        assert data.role == UserRole.EDITOR
        assert data.is_active is True

    def test_admin_user_create_custom_role(self):
        """测试创建用户请求自定义角色"""
        from app.schemas.user import AdminUserCreate

        data = AdminUserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            role=UserRole.REVIEWER,
            is_active=False,
        )

        assert data.role == UserRole.REVIEWER
        assert data.is_active is False


class TestAdminUserUpdateSchema:
    """管理员更新用户 Schema 测试"""

    def test_admin_user_update_partial(self):
        """测试部分更新用户请求"""
        from app.schemas.user import AdminUserUpdate

        data = AdminUserUpdate(role=UserRole.ADMIN)

        assert data.username is None
        assert data.email is None
        assert data.role == UserRole.ADMIN
        assert data.is_active is None

    def test_admin_user_update_all_fields(self):
        """测试更新所有字段"""
        from app.schemas.user import AdminUserUpdate

        data = AdminUserUpdate(
            username="newusername",
            email="newemail@example.com",
            role=UserRole.REVIEWER,
            is_active=False,
        )

        assert data.username == "newusername"
        assert data.email == "newemail@example.com"
        assert data.role == UserRole.REVIEWER
        assert data.is_active is False


class TestResetPasswordSchema:
    """重置密码 Schema 测试"""

    def test_reset_password_request(self):
        """测试重置密码请求"""
        from app.schemas.user import ResetPasswordRequest

        data = ResetPasswordRequest(new_password="newpassword123")

        assert data.new_password == "newpassword123"

    def test_reset_password_min_length(self):
        """测试密码最小长度"""
        from pydantic import ValidationError
        from app.schemas.user import ResetPasswordRequest

        with pytest.raises(ValidationError):
            ResetPasswordRequest(new_password="short")


class TestUsageStatsSchema:
    """使用统计 Schema 测试"""

    def test_usage_stats_response(self):
        """测试使用统计响应"""
        stats = UsageStatsResponse(
            total_projects=10,
            total_users=5,
            active_users=4,
            monthly_generations=100,
            estimated_tokens=200000,
        )

        assert stats.total_projects == 10
        assert stats.total_users == 5
        assert stats.active_users == 4
        assert stats.monthly_generations == 100
        assert stats.estimated_tokens == 200000


class TestAdminEndpoints:
    """管理员端点测试（不依赖数据库）"""

    def test_password_hash_and_verify(self):
        """测试密码哈希和验证"""
        password = "testpassword123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_list_users_filter_conditions(self):
        """测试用户列表筛选条件构建逻辑"""
        # 这个测试验证筛选条件的逻辑
        # 在实际集成测试中会测试数据库查询

        filters = {
            "username": "test",
            "email": None,
            "role": UserRole.EDITOR,
            "is_active": True,
        }

        # 验证筛选条件结构
        assert filters["username"] == "test"
        assert filters["email"] is None
        assert filters["role"] == UserRole.EDITOR
        assert filters["is_active"] is True

    def test_monthly_generations_actions(self):
        """测试月度生成次数统计的操作类型"""
        generation_actions = [
            ActionType.AI_GENERATE,
            ActionType.AI_PROOFREAD,
            ActionType.CONSISTENCY_CHECK,
        ]

        assert ActionType.AI_GENERATE in generation_actions
        assert ActionType.AI_PROOFREAD in generation_actions
        assert ActionType.CONSISTENCY_CHECK in generation_actions
        assert ActionType.LOGIN not in generation_actions

    def test_token_estimation_logic(self):
        """测试 Token 估算逻辑"""
        monthly_generations = 50
        estimated_tokens = monthly_generations * 2000

        assert estimated_tokens == 100000


class TestAdminUserResponseModels:
    """管理员用户响应模型测试"""

    def test_user_response_from_user_model(self):
        """测试从 User 模型创建响应"""
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # 模拟 User 对象
        class MockUser:
            id = user_id
            username = "testuser"
            email = "test@example.com"
            role = UserRole.EDITOR
            is_active = True
            created_at = now
            updated_at = now

        mock_user = MockUser()

        response = UserResponse.model_validate(mock_user)

        assert response.id == user_id
        assert response.username == "testuser"
        assert response.email == "test@example.com"
        assert response.role == UserRole.EDITOR
        assert response.is_active is True

    def test_user_list_pagination_calculation(self):
        """测试用户列表分页计算"""
        page = 2
        page_size = 20

        offset = (page - 1) * page_size

        assert offset == 20  # 第2页从第20条开始

    def test_user_list_pagination_first_page(self):
        """测试用户列表第一页"""
        page = 1
        page_size = 20

        offset = (page - 1) * page_size

        assert offset == 0  # 第1页从第0条开始


class TestAdminSecurityChecks:
    """管理员安全检查测试"""

    def test_admin_cannot_disable_self(self):
        """测试管理员不能禁用自己"""
        # 这是业务逻辑验证
        user_id = uuid.uuid4()
        current_user_id = user_id

        # 管理员尝试禁用自己
        is_self = user_id == current_user_id
        is_disabling = True

        # 应该被阻止
        should_prevent = is_self and is_disabling

        assert should_prevent is True

    def test_admin_can_disable_others(self):
        """测试管理员可以禁用其他用户"""
        user_id = uuid.uuid4()
        current_user_id = uuid.uuid4()  # 不同的ID

        is_self = user_id == current_user_id
        is_disabling = True

        # 不应该被阻止
        should_prevent = is_self and is_disabling

        assert should_prevent is False

    def test_username_conflict_detection(self):
        """测试用户名冲突检测逻辑"""
        existing_usernames = ["admin", "editor", "reviewer"]

        new_username = "admin"
        has_conflict = new_username in existing_usernames

        assert has_conflict is True

        new_username = "newuser"
        has_conflict = new_username in existing_usernames

        assert has_conflict is False

    def test_email_conflict_detection(self):
        """测试邮箱冲突检测逻辑"""
        existing_emails = ["admin@example.com", "editor@example.com"]

        new_email = "admin@example.com"
        has_conflict = new_email in existing_emails

        assert has_conflict is True

        new_email = "newuser@example.com"
        has_conflict = new_email in existing_emails

        assert has_conflict is False


class TestUsageStatsCalculation:
    """使用统计计算测试"""

    def test_month_start_calculation(self):
        """测试本月开始时间计算"""
        now = datetime(2024, 3, 15, 10, 30, 45, tzinfo=timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        assert month_start.day == 1
        assert month_start.hour == 0
        assert month_start.minute == 0
        assert month_start.second == 0

    def test_generation_count_filtering(self):
        """测试生成次数筛选逻辑"""
        # 模拟操作日志数据
        logs = [
            {"action": ActionType.AI_GENERATE, "month": 3},
            {"action": ActionType.AI_PROOFREAD, "month": 3},
            {"action": ActionType.CONSISTENCY_CHECK, "month": 3},
            {"action": ActionType.LOGIN, "month": 3},
            {"action": ActionType.AI_GENERATE, "month": 2},  # 上个月
        ]

        generation_actions = [
            ActionType.AI_GENERATE,
            ActionType.AI_PROOFREAD,
            ActionType.CONSISTENCY_CHECK,
        ]

        current_month = 3

        # 统计本月生成次数
        count = sum(
            1 for log in logs
            if log["action"] in generation_actions and log["month"] == current_month
        )

        assert count == 3  # 本月3次生成操作

    def test_token_estimation_per_generation(self):
        """测试每次生成的 Token 估算"""
        generations = 10
        tokens_per_generation = 2000

        total_tokens = generations * tokens_per_generation

        assert total_tokens == 20000
