"""OperationLog 模型和 Schema 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.operation_log import OperationLog, ActionType
from app.schemas.operation_log import (
    OperationLogBase,
    OperationLogCreate,
    OperationLogResponse,
    OperationLogSummary,
    OperationLogList,
    OperationLogFilter,
)


class TestActionType:
    """操作类型枚举测试"""

    def test_action_type_values(self):
        """测试枚举值"""
        assert ActionType.LOGIN == "login"
        assert ActionType.LOGOUT == "logout"
        assert ActionType.REGISTER == "register"
        assert ActionType.PROJECT_CREATE == "project_create"
        assert ActionType.PROJECT_UPDATE == "project_update"
        assert ActionType.PROJECT_DELETE == "project_delete"
        assert ActionType.PROJECT_VIEW == "project_view"
        assert ActionType.CHAPTER_CREATE == "chapter_create"
        assert ActionType.CHAPTER_UPDATE == "chapter_update"
        assert ActionType.CHAPTER_DELETE == "chapter_delete"
        assert ActionType.VERSION_CREATE == "version_create"
        assert ActionType.VERSION_ROLLBACK == "version_rollback"
        assert ActionType.AI_GENERATE == "ai_generate"
        assert ActionType.AI_PROOFREAD == "ai_proofread"
        assert ActionType.EXPORT_DOCX == "export_docx"
        assert ActionType.EXPORT_PDF == "export_pdf"
        assert ActionType.SETTINGS_CHANGE == "settings_change"

    def test_action_type_is_string(self):
        """测试枚举继承自 str"""
        assert isinstance(ActionType.LOGIN, str)
        assert ActionType.LOGIN.upper() == "LOGIN"


class TestOperationLogModel:
    """操作日志 ORM 模型测试"""

    def test_table_name(self):
        """测试表名"""
        assert OperationLog.__tablename__ == "operation_logs"

    def test_model_columns(self):
        """测试模型列定义"""
        columns = {c.name: c for c in OperationLog.__table__.columns}

        # 主键
        assert "id" in columns
        assert columns["id"].primary_key

        # 外键
        assert "user_id" in columns
        assert columns["user_id"].nullable  # 可为空（系统操作）
        assert len(list(columns["user_id"].foreign_keys)) > 0

        assert "project_id" in columns
        assert columns["project_id"].nullable  # 可为空（非项目操作）
        assert len(list(columns["project_id"].foreign_keys)) > 0

        # 核心字段
        assert "action" in columns
        assert columns["action"].nullable is False

        assert "detail" in columns
        assert columns["detail"].nullable is False

        assert "ip_address" in columns
        assert columns["ip_address"].nullable

        # 时间戳
        assert "created_at" in columns
        assert columns["created_at"].nullable is False

    def test_primary_key_type(self):
        """测试主键为 UUID"""
        id_col = OperationLog.__table__.columns["id"]
        assert id_col.type.__class__.__name__ == "UUID"

    def test_detail_type(self):
        """测试详情为 JSONB"""
        detail_col = OperationLog.__table__.columns["detail"]
        assert detail_col.type.__class__.__name__ == "JSONB"

    def test_ip_address_length(self):
        """测试 IP 地址最大长度"""
        ip_col = OperationLog.__table__.columns["ip_address"]
        assert ip_col.type.length == 45


class TestOperationLogSchemas:
    """操作日志 Pydantic Schema 测试"""

    def test_operation_log_base_required_fields(self):
        """测试基础 schema 必填字段"""
        data = {"action": ActionType.LOGIN}
        log = OperationLogBase(**data)
        assert log.action == ActionType.LOGIN
        assert log.detail == {}
        assert log.ip_address is None

    def test_operation_log_base_with_all_fields(self):
        """测试完整基础 schema"""
        data = {
            "action": ActionType.PROJECT_CREATE,
            "detail": {"project_name": "测试项目"},
            "ip_address": "192.168.1.1"
        }
        log = OperationLogBase(**data)
        assert log.action == ActionType.PROJECT_CREATE
        assert log.detail["project_name"] == "测试项目"
        assert log.ip_address == "192.168.1.1"

    def test_operation_log_base_ip_max_length(self):
        """测试 IP 地址最大长度验证"""
        long_ip = "a" * 46
        with pytest.raises(ValidationError) as exc_info:
            OperationLogBase(action=ActionType.LOGIN, ip_address=long_ip)
        assert "ip_address" in str(exc_info.value)

    def test_operation_log_create(self):
        """测试创建请求 schema"""
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()
        data = {
            "user_id": user_id,
            "project_id": project_id,
            "action": ActionType.CHAPTER_UPDATE,
            "detail": {"chapter_id": "ch1", "changes": ["title", "content"]},
            "ip_address": "10.0.0.1"
        }
        log = OperationLogCreate(**data)
        assert log.user_id == user_id
        assert log.project_id == project_id
        assert log.action == ActionType.CHAPTER_UPDATE
        assert log.detail["chapter_id"] == "ch1"

    def test_operation_log_create_minimal(self):
        """测试最小创建请求（仅 action）"""
        data = {"action": ActionType.LOGOUT}
        log = OperationLogCreate(**data)
        assert log.action == ActionType.LOGOUT
        assert log.user_id is None
        assert log.project_id is None
        assert log.detail == {}

    def test_operation_log_create_missing_action(self):
        """测试缺少 action 必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            OperationLogCreate(user_id=uuid.uuid4())
        assert "action" in str(exc_info.value)

    def test_operation_log_response_from_orm(self):
        """测试响应 schema 支持 ORM 模型"""
        class MockLog:
            id = uuid.uuid4()
            user_id = uuid.uuid4()
            project_id = uuid.uuid4()
            action = ActionType.AI_GENERATE
            detail = {"model": "gpt-4", "tokens": 1500}
            ip_address = "172.16.0.1"
            created_at = datetime.now()

        mock = MockLog()
        response = OperationLogResponse.model_validate(mock)
        assert response.action == ActionType.AI_GENERATE
        assert response.detail["model"] == "gpt-4"
        assert response.ip_address == "172.16.0.1"

    def test_operation_log_summary(self):
        """测试摘要 schema（不含详情）"""
        class MockLog:
            id = uuid.uuid4()
            user_id = uuid.uuid4()
            project_id = None
            action = ActionType.SETTINGS_CHANGE
            ip_address = "127.0.0.1"
            created_at = datetime.now()

        mock = MockLog()
        summary = OperationLogSummary.model_validate(mock)
        assert summary.action == ActionType.SETTINGS_CHANGE
        assert summary.project_id is None
        assert not hasattr(summary, "detail")

    def test_operation_log_list(self):
        """测试日志列表 schema"""
        class MockLog1:
            id = uuid.uuid4()
            user_id = uuid.uuid4()
            project_id = None
            action = ActionType.LOGIN
            ip_address = "192.168.1.1"
            created_at = datetime.now()

        class MockLog2:
            id = uuid.uuid4()
            user_id = uuid.uuid4()
            project_id = uuid.uuid4()
            action = ActionType.PROJECT_VIEW
            ip_address = "192.168.1.2"
            created_at = datetime.now()

        items = [
            OperationLogSummary.model_validate(MockLog1()),
            OperationLogSummary.model_validate(MockLog2()),
        ]
        log_list = OperationLogList(items=items, total=2, page=1, page_size=20)
        assert len(log_list.items) == 2
        assert log_list.total == 2
        assert log_list.page == 1
        assert log_list.page_size == 20

    def test_operation_log_filter(self):
        """测试筛选条件 schema"""
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()
        start = datetime(2026, 1, 1)
        end = datetime(2026, 2, 1)

        filter_obj = OperationLogFilter(
            user_id=user_id,
            project_id=project_id,
            action=ActionType.AI_GENERATE,
            start_time=start,
            end_time=end,
        )
        assert filter_obj.user_id == user_id
        assert filter_obj.project_id == project_id
        assert filter_obj.action == ActionType.AI_GENERATE
        assert filter_obj.start_time == start
        assert filter_obj.end_time == end

    def test_operation_log_filter_empty(self):
        """测试空筛选条件"""
        filter_obj = OperationLogFilter()
        assert filter_obj.user_id is None
        assert filter_obj.project_id is None
        assert filter_obj.action is None

    def test_invalid_action_type_value(self):
        """测试无效操作类型值"""
        with pytest.raises(ValidationError) as exc_info:
            OperationLogBase(action="invalid_action")
        assert "action" in str(exc_info.value)

    def test_action_type_enum_in_schema(self):
        """测试 schema 中使用操作类型枚举"""
        data = {
            "action": "ai_generate",
        }
        log = OperationLogBase(**data)
        assert log.action == ActionType.AI_GENERATE

    def test_complex_detail_data(self):
        """测试复杂详情数据结构"""
        data = {
            "action": ActionType.VERSION_ROLLBACK,
            "detail": {
                "target_version": "v1.2.3",
                "previous_version": "v1.2.4",
                "reason": "发现重大 bug",
                "metadata": {
                    "rollback_by": "admin",
                    "approved": True
                }
            }
        }
        log = OperationLogBase(**data)
        assert log.detail["target_version"] == "v1.2.3"
        assert log.detail["metadata"]["approved"] is True

    def test_ipv6_address(self):
        """测试 IPv6 地址"""
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        data = {
            "action": ActionType.LOGIN,
            "ip_address": ipv6
        }
        log = OperationLogBase(**data)
        assert log.ip_address == ipv6
