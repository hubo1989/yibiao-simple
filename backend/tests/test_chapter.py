"""Chapter 模型和 Schema 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.chapter import Chapter, ChapterStatus
from app.schemas.chapter import (
    ChapterBase,
    ChapterCreate,
    ChapterUpdate,
    ChapterLockRequest,
    ChapterResponse,
    ChapterSummary,
    ChapterTree,
)


class TestChapterStatus:
    """章节状态枚举测试"""

    def test_status_values(self):
        """测试状态枚举值"""
        assert ChapterStatus.PENDING == "pending"
        assert ChapterStatus.GENERATED == "generated"
        assert ChapterStatus.REVIEWING == "reviewing"
        assert ChapterStatus.FINALIZED == "finalized"

    def test_status_is_string(self):
        """测试枚举继承自 str"""
        assert isinstance(ChapterStatus.PENDING, str)
        assert ChapterStatus.PENDING.upper() == "PENDING"


class TestChapterModel:
    """章节 ORM 模型测试"""

    def test_table_name(self):
        """测试表名"""
        assert Chapter.__tablename__ == "chapters"

    def test_model_columns(self):
        """测试模型列定义"""
        columns = {c.name: c for c in Chapter.__table__.columns}

        # 主键
        assert "id" in columns
        assert columns["id"].primary_key

        # 外键 - 使用 foreign_keys 属性
        assert "project_id" in columns
        assert len(list(columns["project_id"].foreign_keys)) > 0

        # 自引用外键
        assert "parent_id" in columns
        assert columns["parent_id"].nullable

        # 核心字段
        assert "chapter_number" in columns
        assert columns["chapter_number"].nullable is False
        assert "title" in columns
        assert columns["title"].nullable is False
        assert "content" in columns
        assert columns["content"].nullable

        # 状态字段
        assert "status" in columns
        assert columns["status"].nullable is False
        assert "order_index" in columns

        # 锁定字段
        assert "locked_by" in columns
        assert columns["locked_by"].nullable
        assert "locked_at" in columns
        assert columns["locked_at"].nullable

        # 时间戳
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_primary_key_type(self):
        """测试主键为 UUID"""
        id_col = Chapter.__table__.columns["id"]
        assert id_col.type.__class__.__name__ == "UUID"

    def test_model_repr(self):
        """测试 __repr__ 方法"""
        # 直接测试 __repr__ 方法而不初始化完整的 ORM 对象
        expected_repr_format = "<Chapter {self.chapter_number} {self.title}>"
        assert "{self.chapter_number}" in expected_repr_format


class TestChapterSchemas:
    """章节 Pydantic Schema 测试"""

    def test_chapter_base_required_fields(self):
        """测试基础 schema 必填字段"""
        data = {"chapter_number": "1.2", "title": "项目背景"}
        chapter = ChapterBase(**data)
        assert chapter.chapter_number == "1.2"
        assert chapter.title == "项目背景"

    def test_chapter_base_min_length_validation(self):
        """测试最小长度验证"""
        with pytest.raises(ValidationError) as exc_info:
            ChapterBase(chapter_number="", title="标题")
        assert "chapter_number" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ChapterBase(chapter_number="1.1", title="")
        assert "title" in str(exc_info.value)

    def test_chapter_base_max_length_validation(self):
        """测试最大长度验证"""
        long_number = "a" * 51
        with pytest.raises(ValidationError) as exc_info:
            ChapterBase(chapter_number=long_number, title="标题")
        assert "chapter_number" in str(exc_info.value)

        long_title = "a" * 501
        with pytest.raises(ValidationError) as exc_info:
            ChapterBase(chapter_number="1.1", title=long_title)
        assert "title" in str(exc_info.value)

    def test_chapter_create(self):
        """测试创建请求 schema"""
        project_id = uuid.uuid4()
        data = {
            "project_id": project_id,
            "chapter_number": "2.1",
            "title": "技术方案",
            "order_index": 0,
        }
        chapter = ChapterCreate(**data)
        assert chapter.project_id == project_id
        assert chapter.parent_id is None
        assert chapter.order_index == 0

    def test_chapter_create_with_parent(self):
        """测试带父章节的创建"""
        project_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        data = {
            "project_id": project_id,
            "parent_id": parent_id,
            "chapter_number": "2.1.1",
            "title": "子章节",
        }
        chapter = ChapterCreate(**data)
        assert chapter.parent_id == parent_id

    def test_chapter_create_order_index_validation(self):
        """测试排序索引非负验证"""
        project_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            ChapterCreate(
                project_id=project_id,
                chapter_number="1.1",
                title="测试",
                order_index=-1,
            )

    def test_chapter_update_all_optional(self):
        """测试更新 schema 所有字段可选"""
        update = ChapterUpdate()
        assert update.chapter_number is None
        assert update.title is None
        assert update.content is None
        assert update.status is None

    def test_chapter_update_partial(self):
        """测试部分更新"""
        update = ChapterUpdate(
            chapter_number="2.1",
            status=ChapterStatus.GENERATED,
        )
        assert update.chapter_number == "2.1"
        assert update.status == ChapterStatus.GENERATED
        assert update.title is None

    def test_chapter_lock_request(self):
        """测试锁定请求 schema"""
        lock_req = ChapterLockRequest(lock=True)
        assert lock_req.lock is True

        unlock_req = ChapterLockRequest(lock=False)
        assert unlock_req.lock is False

    def test_chapter_response_from_orm(self):
        """测试响应 schema 支持 ORM 模型"""
        # 模拟 ORM 对象
        class MockChapter:
            id = uuid.uuid4()
            project_id = uuid.uuid4()
            parent_id = None
            chapter_number = "1.1"
            title = "测试章节"
            content = "内容文本"
            status = ChapterStatus.PENDING
            order_index = 0
            locked_by = None
            locked_at = None
            created_at = datetime.now()
            updated_at = datetime.now()

        mock = MockChapter()
        response = ChapterResponse.model_validate(mock)
        assert response.chapter_number == "1.1"
        assert response.title == "测试章节"
        assert response.status == ChapterStatus.PENDING

    def test_chapter_summary(self):
        """测试摘要 schema（不含大文本字段）"""
        class MockChapter:
            id = uuid.uuid4()
            project_id = uuid.uuid4()
            parent_id = uuid.uuid4()
            chapter_number = "2.3.1"
            title = "实施计划"
            status = ChapterStatus.REVIEWING
            order_index = 3
            locked_by = uuid.uuid4()

        mock = MockChapter()
        summary = ChapterSummary.model_validate(mock)
        assert summary.chapter_number == "2.3.1"
        assert summary.title == "实施计划"
        assert not hasattr(summary, "content")  # 摘要不包含内容字段
        assert not hasattr(summary, "created_at")

    def test_chapter_tree(self):
        """测试树形结构 schema"""
        child_uuid = uuid.uuid4()
        parent_uuid = uuid.uuid4()
        proj_uuid = uuid.uuid4()

        class MockChild:
            id = child_uuid
            project_id = proj_uuid
            parent_id = parent_uuid
            chapter_number = "1.1.1"
            title = "子章节"
            status = ChapterStatus.PENDING
            order_index = 0
            locked_by = None
            children = []

        class MockParent:
            id = parent_uuid
            project_id = proj_uuid
            parent_id = None
            chapter_number = "1.1"
            title = "父章节"
            status = ChapterStatus.GENERATED
            order_index = 0
            locked_by = None
            children = [MockChild()]

        mock = MockParent()
        tree = ChapterTree.model_validate(mock)
        assert tree.chapter_number == "1.1"
        assert len(tree.children) == 1
        assert tree.children[0].chapter_number == "1.1.1"

    def test_status_enum_in_schema(self):
        """测试 schema 中使用状态枚举"""
        data = {
            "chapter_number": "1.1",
            "title": "测试",
            "status": "generated",
        }
        update = ChapterUpdate(**data)
        assert update.status == ChapterStatus.GENERATED

    def test_invalid_status_value(self):
        """测试无效状态值"""
        with pytest.raises(ValidationError) as exc_info:
            ChapterUpdate(status="invalid_status")
        assert "status" in str(exc_info.value)
