"""操作日志中间件和审计 API 测试"""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.operation_log import ActionType
from app.middleware.audit_middleware import (
    sanitize_dict,
    get_action_type,
    should_log_detail,
    SENSITIVE_FIELDS,
)


class TestSanitizeDict:
    """测试敏感信息过滤"""

    def test_filter_password(self):
        """测试密码字段被过滤"""
        data = {"username": "test", "password": "secret123"}
        result = sanitize_dict(data)
        assert result["username"] == "test"
        assert result["password"] == "***"

    def test_filter_api_key(self):
        """测试 API key 被过滤"""
        data = {"name": "config", "api_key": "sk-123456"}
        result = sanitize_dict(data)
        assert result["name"] == "config"
        assert result["api_key"] == "***"

    def test_filter_nested_dict(self):
        """测试嵌套字典中的敏感信息被过滤"""
        data = {
            "user": {
                "name": "test",
                "password": "secret",
                "profile": {"token": "abc123"},
            }
        }
        result = sanitize_dict(data)
        assert result["user"]["name"] == "test"
        assert result["user"]["password"] == "***"
        assert result["user"]["profile"]["token"] == "***"

    def test_filter_list_of_dicts(self):
        """测试列表中的字典敏感信息被过滤"""
        data = {
            "users": [
                {"name": "user1", "password": "pass1"},
                {"name": "user2", "password": "pass2"},
            ]
        }
        result = sanitize_dict(data)
        assert result["users"][0]["password"] == "***"
        assert result["users"][1]["password"] == "***"

    def test_preserve_normal_data(self):
        """测试正常数据不被过滤"""
        data = {
            "project_name": "Test Project",
            "description": "A test project",
            "count": 42,
        }
        result = sanitize_dict(data)
        assert result == data

    def test_filter_access_token(self):
        """测试 access_token 被过滤"""
        data = {"access_token": "eyJ...", "refresh_token": "eyJ..."}
        result = sanitize_dict(data)
        assert result["access_token"] == "***"
        assert result["refresh_token"] == "***"

    def test_filter_hashed_password(self):
        """测试 hashed_password 被过滤"""
        data = {"user": {"name": "test", "hashed_password": "$2b$12$..."}}
        result = sanitize_dict(data)
        assert result["user"]["hashed_password"] == "***"


class TestGetActionType:
    """测试操作类型判断"""

    def test_get_request_returns_none(self):
        """GET 请求不记录"""
        result = get_action_type("GET", "/api/projects")
        assert result is None

    def test_post_project_create(self):
        """POST /api/projects 返回 PROJECT_CREATE"""
        result = get_action_type("POST", "/api/projects")
        assert result == ActionType.PROJECT_CREATE

    def test_put_project_update(self):
        """PUT /api/projects/{uuid} 返回 PROJECT_UPDATE"""
        test_uuid = str(uuid.uuid4())
        result = get_action_type("PUT", f"/api/projects/{test_uuid}")
        assert result == ActionType.PROJECT_UPDATE

    def test_patch_project_update(self):
        """PATCH /api/projects/{uuid} 返回 PROJECT_UPDATE"""
        test_uuid = str(uuid.uuid4())
        result = get_action_type("PATCH", f"/api/projects/{test_uuid}")
        assert result == ActionType.PROJECT_UPDATE

    def test_delete_project(self):
        """DELETE /api/projects/{uuid} 返回 PROJECT_DELETE"""
        test_uuid = str(uuid.uuid4())
        result = get_action_type("DELETE", f"/api/projects/{test_uuid}")
        assert result == ActionType.PROJECT_DELETE

    def test_post_chapter_create(self):
        """POST /api/chapters 返回 CHAPTER_CREATE"""
        result = get_action_type("POST", "/api/chapters")
        assert result == ActionType.CHAPTER_CREATE

    def test_put_chapter_update(self):
        """PUT /api/chapters/{uuid} 返回 CHAPTER_UPDATE"""
        test_uuid = str(uuid.uuid4())
        result = get_action_type("PUT", f"/api/chapters/{test_uuid}")
        assert result == ActionType.CHAPTER_UPDATE

    def test_delete_chapter(self):
        """DELETE /api/chapters/{uuid} 返回 CHAPTER_DELETE"""
        test_uuid = str(uuid.uuid4())
        result = get_action_type("DELETE", f"/api/chapters/{test_uuid}")
        assert result == ActionType.CHAPTER_DELETE

    def test_ai_generate(self):
        """AI 生成路径返回 AI_GENERATE"""
        result = get_action_type("POST", "/api/outline/generate")
        assert result == ActionType.AI_GENERATE

    def test_export_docx(self):
        """导出 Word 返回 EXPORT_DOCX"""
        result = get_action_type("POST", "/api/export/docx")
        assert result == ActionType.EXPORT_DOCX

    def test_export_pdf(self):
        """导出 PDF 返回 EXPORT_PDF"""
        result = get_action_type("POST", "/api/export/pdf")
        assert result == ActionType.EXPORT_PDF

    def test_login(self):
        """登录返回 LOGIN"""
        result = get_action_type("POST", "/api/auth/login")
        assert result == ActionType.LOGIN

    def test_register(self):
        """注册返回 REGISTER"""
        result = get_action_type("POST", "/api/auth/register")
        assert result == ActionType.REGISTER

    def test_settings_change(self):
        """配置变更返回 SETTINGS_CHANGE"""
        result = get_action_type("POST", "/api/admin/api-keys")
        assert result == ActionType.SETTINGS_CHANGE

    def test_unknown_path_returns_none(self):
        """未知路径返回 None（跳过记录）"""
        result = get_action_type("POST", "/api/unknown/endpoint")
        assert result is None

    def test_ai_proofread(self):
        """AI 校对返回 AI_PROOFREAD"""
        result = get_action_type("POST", "/api/proofread")
        assert result == ActionType.AI_PROOFREAD

    def test_consistency_check(self):
        """一致性检查返回 CONSISTENCY_CHECK"""
        result = get_action_type("POST", "/api/consistency-check")
        assert result == ActionType.CONSISTENCY_CHECK


class TestShouldLogDetail:
    """测试详细日志记录判断"""

    def test_project_operations(self):
        """项目操作需要详细日志"""
        assert should_log_detail("/api/projects") is True
        assert should_log_detail("/api/projects/123") is True

    def test_ai_operations(self):
        """AI 操作需要详细日志"""
        assert should_log_detail("/api/outline/generate") is True
        assert should_log_detail("/api/proofread") is True
        assert should_log_detail("/api/consistency-check") is True

    def test_export_operations(self):
        """导出操作需要详细日志"""
        assert should_log_detail("/api/export/docx") is True

    def test_normal_operations(self):
        """普通操作不需要详细日志"""
        assert should_log_detail("/api/auth/login") is False
        assert should_log_detail("/api/health") is False


class TestSensitiveFieldList:
    """测试敏感字段列表"""

    def test_sensitive_fields_coverage(self):
        """确保敏感字段列表包含常见字段"""
        assert "password" in SENSITIVE_FIELDS
        assert "api_key" in SENSITIVE_FIELDS
        assert "token" in SENSITIVE_FIELDS
        assert "secret" in SENSITIVE_FIELDS

    def test_sensitive_fields_completeness(self):
        """确保敏感字段列表包含所有定义的字段"""
        expected_fields = {
            "password",
            "password_confirm",
            "hashed_password",
            "api_key",
            "api_key_encrypted",
            "token",
            "access_token",
            "refresh_token",
            "secret",
            "authorization",
        }
        assert SENSITIVE_FIELDS == expected_fields


class TestAuditLogQuerySchema:
    """测试审计日志查询 Schema"""

    def test_default_values(self):
        """测试默认值"""
        from app.schemas.operation_log import AuditLogQuery

        query = AuditLogQuery()
        assert query.page == 1
        assert query.page_size == 20
        assert query.user_id is None
        assert query.action is None

    def test_custom_values(self):
        """测试自定义值"""
        from app.schemas.operation_log import AuditLogQuery

        user_id = uuid.uuid4()
        query = AuditLogQuery(
            user_id=user_id,
            action=ActionType.LOGIN,
            page=2,
            page_size=50,
        )
        assert query.user_id == user_id
        assert query.action == ActionType.LOGIN
        assert query.page == 2
        assert query.page_size == 50

    def test_page_validation(self):
        """测试页码验证"""
        from pydantic import ValidationError
        from app.schemas.operation_log import AuditLogQuery

        # 页码必须 >= 1
        with pytest.raises(ValidationError):
            AuditLogQuery(page=0)

        with pytest.raises(ValidationError):
            AuditLogQuery(page=-1)

    def test_page_size_validation(self):
        """测试每页数量验证"""
        from pydantic import ValidationError
        from app.schemas.operation_log import AuditLogQuery

        # 每页数量必须在 1-100 之间
        with pytest.raises(ValidationError):
            AuditLogQuery(page_size=0)

        with pytest.raises(ValidationError):
            AuditLogQuery(page_size=101)
