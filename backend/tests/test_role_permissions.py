"""角色权限测试"""
import uuid
from typing import Callable

import pytest
from fastapi import HTTPException

from app.auth.dependencies import require_role, require_admin, require_editor, require_reviewer
from app.auth.security import get_password_hash
from app.models.user import User, UserRole


def create_test_user(
    username: str,
    role: UserRole,
    is_active: bool = True,
) -> User:
    """创建测试用户的辅助函数"""
    return User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("password"),
        role=role,
        is_active=is_active,
    )


class TestRequireRole:
    """require_role 依赖测试"""

    def test_require_role_admin_passes_any_check(self) -> None:
        """管理员可以通过任何角色检查"""
        admin_user = create_test_user("admin", UserRole.ADMIN)
        checker = require_role(UserRole.EDITOR, UserRole.REVIEWER)

        # 同步调用异步函数
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(admin_user))
        assert result == admin_user

    def test_require_role_editor_with_editor_permission(self) -> None:
        """编辑者可以通过编辑者权限检查"""
        editor_user = create_test_user("editor", UserRole.EDITOR)
        checker = require_role(UserRole.EDITOR)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(editor_user))
        assert result == editor_user

    def test_require_role_editor_with_admin_permission_fails(self) -> None:
        """编辑者不能通过管理员权限检查"""
        editor_user = create_test_user("editor", UserRole.EDITOR)
        checker = require_role(UserRole.ADMIN)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(checker(editor_user))

        assert exc_info.value.status_code == 403
        assert "权限不足" in exc_info.value.detail

    def test_require_role_reviewer_with_editor_permission_fails(self) -> None:
        """审阅者不能通过编辑者权限检查"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)
        checker = require_role(UserRole.EDITOR)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(checker(reviewer_user))

        assert exc_info.value.status_code == 403
        assert "权限不足" in exc_info.value.detail

    def test_require_role_reviewer_with_reviewer_permission(self) -> None:
        """审阅者可以通过审阅者权限检查"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)
        checker = require_role(UserRole.REVIEWER)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(reviewer_user))
        assert result == reviewer_user

    def test_require_role_multiple_roles_in_error_message(self) -> None:
        """权限拒绝时错误信息包含所有允许的角色"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)
        checker = require_role(UserRole.ADMIN, UserRole.EDITOR)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(checker(reviewer_user))

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail
        assert "editor" in exc_info.value.detail


class TestPredefinedRoleDependencies:
    """预定义角色依赖测试"""

    def test_require_admin_with_admin(self) -> None:
        """管理员可以通过 require_admin"""
        admin_user = create_test_user("admin", UserRole.ADMIN)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_admin(admin_user))
        assert result == admin_user

    def test_require_admin_with_editor_fails(self) -> None:
        """编辑者不能通过 require_admin"""
        editor_user = create_test_user("editor", UserRole.EDITOR)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(require_admin(editor_user))

        assert exc_info.value.status_code == 403

    def test_require_admin_with_reviewer_fails(self) -> None:
        """审阅者不能通过 require_admin"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(require_admin(reviewer_user))

        assert exc_info.value.status_code == 403

    def test_require_editor_with_admin(self) -> None:
        """管理员可以通过 require_editor"""
        admin_user = create_test_user("admin", UserRole.ADMIN)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_editor(admin_user))
        assert result == admin_user

    def test_require_editor_with_editor(self) -> None:
        """编辑者可以通过 require_editor"""
        editor_user = create_test_user("editor", UserRole.EDITOR)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_editor(editor_user))
        assert result == editor_user

    def test_require_editor_with_reviewer_fails(self) -> None:
        """审阅者不能通过 require_editor"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(require_editor(reviewer_user))

        assert exc_info.value.status_code == 403

    def test_require_reviewer_with_admin(self) -> None:
        """管理员可以通过 require_reviewer"""
        admin_user = create_test_user("admin", UserRole.ADMIN)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_reviewer(admin_user))
        assert result == admin_user

    def test_require_reviewer_with_editor(self) -> None:
        """编辑者可以通过 require_reviewer"""
        editor_user = create_test_user("editor", UserRole.EDITOR)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_reviewer(editor_user))
        assert result == editor_user

    def test_require_reviewer_with_reviewer(self) -> None:
        """审阅者可以通过 require_reviewer"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(require_reviewer(reviewer_user))
        assert result == reviewer_user


class TestErrorMessageInChinese:
    """中文错误信息测试"""

    def test_permission_denied_message_in_chinese(self) -> None:
        """权限拒绝时返回中文错误信息"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)
        checker = require_role(UserRole.ADMIN)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(checker(reviewer_user))

        assert exc_info.value.status_code == 403
        # 检查包含中文
        assert "权限不足" in exc_info.value.detail
        assert "admin" in exc_info.value.detail

    def test_403_status_code_on_permission_denied(self) -> None:
        """权限拒绝返回 403 状态码"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)
        checker = require_role(UserRole.EDITOR)

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(checker(reviewer_user))

        assert exc_info.value.status_code == 403


class TestRoleHierarchy:
    """角色层级测试"""

    def test_admin_has_all_permissions(self) -> None:
        """管理员拥有所有权限"""
        admin_user = create_test_user("admin", UserRole.ADMIN)

        import asyncio
        loop = asyncio.get_event_loop()

        # 测试管理员可以通过所有角色检查
        for role in [UserRole.ADMIN, UserRole.EDITOR, UserRole.REVIEWER]:
            checker = require_role(role)
            result = loop.run_until_complete(checker(admin_user))
            assert result == admin_user

    def test_editor_has_editor_permission_only(self) -> None:
        """编辑者只有编辑者权限，没有管理员或审阅者权限"""
        editor_user = create_test_user("editor", UserRole.EDITOR)

        import asyncio
        loop = asyncio.get_event_loop()

        # 编辑者可以通过编辑者检查
        checker = require_role(UserRole.EDITOR)
        result = loop.run_until_complete(checker(editor_user))
        assert result == editor_user

        # 编辑者不能通过审阅者检查（角色是精确匹配的）
        checker = require_role(UserRole.REVIEWER)
        with pytest.raises(HTTPException):
            loop.run_until_complete(checker(editor_user))

        # 编辑者不能通过管理员检查
        checker = require_role(UserRole.ADMIN)
        with pytest.raises(HTTPException):
            loop.run_until_complete(checker(editor_user))

    def test_reviewer_only_has_reviewer_permission(self) -> None:
        """审阅者只有审阅者权限"""
        reviewer_user = create_test_user("reviewer", UserRole.REVIEWER)

        import asyncio
        loop = asyncio.get_event_loop()

        # 审阅者可以通过审阅者检查
        checker = require_role(UserRole.REVIEWER)
        result = loop.run_until_complete(checker(reviewer_user))
        assert result == reviewer_user

        # 审阅者不能通过编辑者检查
        checker = require_role(UserRole.EDITOR)
        with pytest.raises(HTTPException):
            loop.run_until_complete(checker(reviewer_user))

        # 审阅者不能通过管理员检查
        checker = require_role(UserRole.ADMIN)
        with pytest.raises(HTTPException):
            loop.run_until_complete(checker(reviewer_user))


class TestRequireRoleFactory:
    """require_role 工厂函数测试"""

    def test_require_role_returns_callable(self) -> None:
        """require_role 返回可调用函数"""
        checker = require_role(UserRole.ADMIN)
        assert callable(checker)

    def test_require_role_single_role(self) -> None:
        """require_role 支持单个角色"""
        admin_user = create_test_user("admin", UserRole.ADMIN)
        checker = require_role(UserRole.ADMIN)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(admin_user))
        assert result == admin_user

    def test_require_role_multiple_roles(self) -> None:
        """require_role 支持多个角色（满足其一即可）"""
        editor_user = create_test_user("editor", UserRole.EDITOR)
        checker = require_role(UserRole.ADMIN, UserRole.EDITOR)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(editor_user))
        assert result == editor_user

    def test_require_role_empty_roles_still_allows_admin(self) -> None:
        """即使没有指定角色，管理员仍然可以通过"""
        admin_user = create_test_user("admin", UserRole.ADMIN)
        checker = require_role()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(checker(admin_user))
        assert result == admin_user
