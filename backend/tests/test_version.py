"""Version 模型和 Schema 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.version import ProjectVersion, ChangeType
from app.schemas.version import (
    VersionBase,
    VersionCreate,
    VersionResponse,
    VersionSummary,
    VersionList,
    VersionRollbackRequest,
)


class TestChangeType:
    """变更类型枚举测试"""

    def test_change_type_values(self):
        """测试枚举值"""
        assert ChangeType.AI_GENERATE == "ai_generate"
        assert ChangeType.MANUAL_EDIT == "manual_edit"
        assert ChangeType.PROOFREAD == "proofread"
        assert ChangeType.ROLLBACK == "rollback"

    def test_change_type_is_string(self):
        """测试枚举继承自 str"""
        assert isinstance(ChangeType.AI_GENERATE, str)
        assert ChangeType.AI_GENERATE.upper() == "AI_GENERATE"


class TestProjectVersionModel:
    """版本快照 ORM 模型测试"""

    def test_table_name(self):
        """测试表名"""
        assert ProjectVersion.__tablename__ == "project_versions"

    def test_model_columns(self):
        """测试模型列定义"""
        columns = {c.name: c for c in ProjectVersion.__table__.columns}

        # 主键
        assert "id" in columns
        assert columns["id"].primary_key

        # 外键
        assert "project_id" in columns
        assert len(list(columns["project_id"].foreign_keys)) > 0

        assert "chapter_id" in columns
        assert columns["chapter_id"].nullable  # 可为空（全量快照）

        assert "created_by" in columns
        assert columns["created_by"].nullable

        # 核心字段
        assert "version_number" in columns
        assert columns["version_number"].nullable is False

        assert "snapshot_data" in columns
        assert columns["snapshot_data"].nullable is False

        assert "change_type" in columns
        assert columns["change_type"].nullable is False

        assert "change_summary" in columns
        assert columns["change_summary"].nullable

        # 时间戳
        assert "created_at" in columns
        # 注意：版本表没有 updated_at，因为版本是不可变的

    def test_primary_key_type(self):
        """测试主键为 UUID"""
        id_col = ProjectVersion.__table__.columns["id"]
        assert id_col.type.__class__.__name__ == "UUID"

    def test_snapshot_data_type(self):
        """测试快照数据为 JSONB"""
        snapshot_col = ProjectVersion.__table__.columns["snapshot_data"]
        assert snapshot_col.type.__class__.__name__ == "JSONB"


class TestVersionSchemas:
    """版本 Pydantic Schema 测试"""

    def test_version_base_required_fields(self):
        """测试基础 schema 必填字段"""
        data = {"change_type": ChangeType.MANUAL_EDIT}
        version = VersionBase(**data)
        assert version.change_type == ChangeType.MANUAL_EDIT
        assert version.change_summary is None

    def test_version_base_with_summary(self):
        """测试带摘要的基础 schema"""
        data = {
            "change_type": ChangeType.AI_GENERATE,
            "change_summary": "AI 生成项目背景章节"
        }
        version = VersionBase(**data)
        assert version.change_type == ChangeType.AI_GENERATE
        assert version.change_summary == "AI 生成项目背景章节"

    def test_version_base_summary_max_length(self):
        """测试摘要最大长度验证"""
        long_summary = "a" * 2001
        with pytest.raises(ValidationError) as exc_info:
            VersionBase(change_type=ChangeType.MANUAL_EDIT, change_summary=long_summary)
        assert "change_summary" in str(exc_info.value)

    def test_version_create(self):
        """测试创建请求 schema"""
        project_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        snapshot_data = {
            "title": "项目背景",
            "content": "这是项目背景内容...",
            "chapter_number": "1.1"
        }
        data = {
            "project_id": project_id,
            "chapter_id": chapter_id,
            "snapshot_data": snapshot_data,
            "change_type": ChangeType.AI_GENERATE,
            "change_summary": "AI 生成章节内容"
        }
        version = VersionCreate(**data)
        assert version.project_id == project_id
        assert version.chapter_id == chapter_id
        assert version.snapshot_data == snapshot_data
        assert version.change_type == ChangeType.AI_GENERATE

    def test_version_create_without_chapter(self):
        """测试全量快照创建（无章节 ID）"""
        project_id = uuid.uuid4()
        snapshot_data = {
            "chapters": [
                {"id": "1", "title": "章节1", "content": "内容1"},
                {"id": "2", "title": "章节2", "content": "内容2"},
            ]
        }
        data = {
            "project_id": project_id,
            "snapshot_data": snapshot_data,
            "change_type": ChangeType.MANUAL_EDIT,
        }
        version = VersionCreate(**data)
        assert version.project_id == project_id
        assert version.chapter_id is None
        assert len(version.snapshot_data["chapters"]) == 2

    def test_version_create_missing_project_id(self):
        """测试缺少 project_id 必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            VersionCreate(
                snapshot_data={},
                change_type=ChangeType.MANUAL_EDIT,
            )
        assert "project_id" in str(exc_info.value)

    def test_version_create_missing_snapshot_data(self):
        """测试缺少 snapshot_data 必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            VersionCreate(
                project_id=uuid.uuid4(),
                change_type=ChangeType.MANUAL_EDIT,
            )
        assert "snapshot_data" in str(exc_info.value)

    def test_version_response_from_orm(self):
        """测试响应 schema 支持 ORM 模型"""
        class MockVersion:
            id = uuid.uuid4()
            project_id = uuid.uuid4()
            chapter_id = uuid.uuid4()
            version_number = 5
            snapshot_data = {"content": "测试内容"}
            change_type = ChangeType.PROOFREAD
            change_summary = "校对了错别字"
            created_by = uuid.uuid4()
            created_at = datetime.now()

        mock = MockVersion()
        response = VersionResponse.model_validate(mock)
        assert response.version_number == 5
        assert response.change_type == ChangeType.PROOFREAD
        assert response.change_summary == "校对了错别字"

    def test_version_summary(self):
        """测试摘要 schema（不含大快照数据）"""
        class MockVersion:
            id = uuid.uuid4()
            project_id = uuid.uuid4()
            chapter_id = None
            version_number = 10
            change_type = ChangeType.ROLLBACK
            change_summary = "回滚到版本 8"
            created_by = uuid.uuid4()
            created_at = datetime.now()

        mock = MockVersion()
        summary = VersionSummary.model_validate(mock)
        assert summary.version_number == 10
        assert summary.change_type == ChangeType.ROLLBACK
        assert not hasattr(summary, "snapshot_data")  # 摘要不包含快照数据

    def test_version_list(self):
        """测试版本列表 schema"""
        proj_id = uuid.uuid4()
        user_id1 = uuid.uuid4()
        user_id2 = uuid.uuid4()

        class MockVersion1:
            id = uuid.uuid4()
            project_id = proj_id
            chapter_id = None
            version_number = 1
            change_type = ChangeType.MANUAL_EDIT
            change_summary = "初始版本"
            created_by = user_id1
            created_at = datetime.now()

        class MockVersion2:
            id = uuid.uuid4()
            project_id = proj_id
            chapter_id = None
            version_number = 2
            change_type = ChangeType.AI_GENERATE
            change_summary = "AI 优化内容"
            created_by = user_id2
            created_at = datetime.now()

        items = [
            VersionSummary.model_validate(MockVersion1()),
            VersionSummary.model_validate(MockVersion2()),
        ]
        version_list = VersionList(items=items, total=2, project_id=proj_id)
        assert len(version_list.items) == 2
        assert version_list.total == 2
        assert version_list.project_id == proj_id

    def test_version_rollback_request(self):
        """测试回滚请求 schema"""
        target_id = uuid.uuid4()
        request = VersionRollbackRequest(target_version_id=target_id)
        assert request.target_version_id == target_id
        assert request.create_snapshot is True  # 默认创建快照

    def test_version_rollback_request_no_snapshot(self):
        """测试回滚请求不创建快照"""
        target_id = uuid.uuid4()
        request = VersionRollbackRequest(target_version_id=target_id, create_snapshot=False)
        assert request.create_snapshot is False

    def test_invalid_change_type_value(self):
        """测试无效变更类型值"""
        with pytest.raises(ValidationError) as exc_info:
            VersionBase(change_type="invalid_type")
        assert "change_type" in str(exc_info.value)

    def test_change_type_enum_in_schema(self):
        """测试 schema 中使用变更类型枚举"""
        data = {
            "change_type": "ai_generate",
            "change_summary": "测试"
        }
        version = VersionBase(**data)
        assert version.change_type == ChangeType.AI_GENERATE

    def test_complex_snapshot_data(self):
        """测试复杂快照数据结构"""
        project_id = uuid.uuid4()
        snapshot_data = {
            "metadata": {
                "generated_at": "2026-02-12T10:00:00Z",
                "model": "gpt-4"
            },
            "chapters": [
                {
                    "id": "ch1",
                    "title": "第一章",
                    "content": "内容...",
                    "children": [
                        {"id": "ch1.1", "title": "1.1 子章节", "content": "子内容..."}
                    ]
                }
            ],
            "statistics": {
                "total_words": 5000,
                "total_chapters": 10
            }
        }
        data = {
            "project_id": project_id,
            "snapshot_data": snapshot_data,
            "change_type": ChangeType.AI_GENERATE,
        }
        version = VersionCreate(**data)
        assert version.snapshot_data["metadata"]["model"] == "gpt-4"
        assert len(version.snapshot_data["chapters"]) == 1
        assert version.snapshot_data["statistics"]["total_words"] == 5000
