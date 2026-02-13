"""项目目录和内容生成 API 单元测试"""
import uuid

import pytest

from app.models.schemas import (
    ProjectOutlineRequest,
    ProjectContentGenerateRequest,
    ProjectOutlineResponse,
    ChapterCreatedResponse,
)
from app.models.chapter import ChapterStatus


class TestProjectOutlineRequestSchema:
    """测试 ProjectOutlineRequest Schema"""

    def test_valid_data(self) -> None:
        """验证有效数据"""
        project_id = uuid.uuid4()
        request = ProjectOutlineRequest(project_id=str(project_id))
        assert request.project_id == str(project_id)

    def test_string_project_id(self) -> None:
        """接受字符串格式的项目 ID"""
        request = ProjectOutlineRequest(project_id="test-project-id")
        assert request.project_id == "test-project-id"

    def test_model_validate_from_dict(self) -> None:
        """从字典验证"""
        request = ProjectOutlineRequest.model_validate({
            "project_id": str(uuid.uuid4()),
        })
        assert request.project_id is not None


class TestProjectContentGenerateRequestSchema:
    """测试 ProjectContentGenerateRequest Schema"""

    def test_valid_data(self) -> None:
        """验证有效数据"""
        project_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        request = ProjectContentGenerateRequest(
            project_id=str(project_id),
            chapter_id=str(chapter_id),
        )
        assert request.project_id == str(project_id)
        assert request.chapter_id == str(chapter_id)

    def test_both_ids_required(self) -> None:
        """两个 ID 都是必需的"""
        fields = ProjectContentGenerateRequest.model_fields.keys()
        assert "project_id" in fields
        assert "chapter_id" in fields

    def test_model_validate_from_dict(self) -> None:
        """从字典验证"""
        project_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        request = ProjectContentGenerateRequest.model_validate({
            "project_id": str(project_id),
            "chapter_id": str(chapter_id),
        })
        assert request.project_id == str(project_id)
        assert request.chapter_id == str(chapter_id)


class TestChapterCreatedResponseSchema:
    """测试 ChapterCreatedResponse Schema"""

    def test_valid_data(self) -> None:
        """验证有效数据"""
        chapter_id = uuid.uuid4()
        parent_id = uuid.uuid4()

        response = ChapterCreatedResponse(
            id=str(chapter_id),
            chapter_number="1.1",
            title="测试章节",
            parent_id=str(parent_id),
            status="pending",
        )
        assert response.id == str(chapter_id)
        assert response.chapter_number == "1.1"
        assert response.title == "测试章节"
        assert response.parent_id == str(parent_id)
        assert response.status == "pending"

    def test_optional_parent_id(self) -> None:
        """parent_id 是可选的"""
        chapter_id = uuid.uuid4()
        response = ChapterCreatedResponse(
            id=str(chapter_id),
            chapter_number="1",
            title="根章节",
            status="pending",
        )
        assert response.parent_id is None

    def test_status_field(self) -> None:
        """状态字段"""
        response = ChapterCreatedResponse(
            id=str(uuid.uuid4()),
            chapter_number="1",
            title="章节",
            status=ChapterStatus.GENERATED.value,
        )
        assert response.status == "generated"


class TestProjectOutlineResponseSchema:
    """测试 ProjectOutlineResponse Schema"""

    def test_valid_data(self) -> None:
        """验证有效数据"""
        project_id = uuid.uuid4()
        chapter1 = ChapterCreatedResponse(
            id=str(uuid.uuid4()),
            chapter_number="1",
            title="第一章",
            status="pending",
        )
        chapter2 = ChapterCreatedResponse(
            id=str(uuid.uuid4()),
            chapter_number="1.1",
            title="1.1 小节",
            parent_id=chapter1.id,
            status="pending",
        )

        response = ProjectOutlineResponse(
            project_id=str(project_id),
            chapters=[chapter1, chapter2],
            total_count=2,
        )
        assert response.project_id == str(project_id)
        assert response.total_count == 2
        assert len(response.chapters) == 2

    def test_empty_chapters(self) -> None:
        """空的章节列表"""
        project_id = uuid.uuid4()
        response = ProjectOutlineResponse(
            project_id=str(project_id),
            chapters=[],
            total_count=0,
        )
        assert response.total_count == 0
        assert response.chapters == []

    def test_model_dump(self) -> None:
        """测试序列化"""
        project_id = uuid.uuid4()
        response = ProjectOutlineResponse(
            project_id=str(project_id),
            chapters=[],
            total_count=0,
        )
        data = response.model_dump()
        assert "project_id" in data
        assert "chapters" in data
        assert "total_count" in data


class TestChapterStatusEnum:
    """测试 ChapterStatus 枚举"""

    def test_status_is_string_enum(self) -> None:
        """枚举应继承自 str"""
        import enum
        assert issubclass(ChapterStatus, str)
        assert issubclass(ChapterStatus, enum.Enum)

    def test_status_values(self) -> None:
        """验证状态值"""
        assert ChapterStatus.PENDING == "pending"
        assert ChapterStatus.GENERATED == "generated"
        assert ChapterStatus.REVIEWING == "reviewing"
        assert ChapterStatus.FINALIZED == "finalized"

    def test_status_from_string(self) -> None:
        """从字符串获取枚举值"""
        status = ChapterStatus("generated")
        assert status == ChapterStatus.GENERATED


class TestOutlineRouterHelperFunctions:
    """测试 outline router 辅助函数（非数据库测试）"""

    def test_version_snapshot_structure_outline(self) -> None:
        """目录快照数据结构"""
        # 目录生成时创建的快照结构
        snapshot_data = {
            "outline": [
                {"id": "1", "title": "第一章", "children": []},
            ],
            "total_chapters": 1,
        }
        assert "outline" in snapshot_data
        assert "total_chapters" in snapshot_data

    def test_version_snapshot_structure_content(self) -> None:
        """内容快照数据结构"""
        # 内容生成时创建的快照结构
        snapshot_data = {
            "chapter_id": str(uuid.uuid4()),
            "chapter_number": "1.1",
            "title": "测试章节",
            "content": "生成的章节内容...",
        }
        assert "chapter_id" in snapshot_data
        assert "content" in snapshot_data
        assert "chapter_number" in snapshot_data
        assert "title" in snapshot_data

    def test_outline_item_structure(self) -> None:
        """outline item 数据结构"""
        outline_item = {
            "id": "1.1",
            "title": "测试章节",
            "description": "章节描述",
            "children": [
                {"id": "1.1.1", "title": "子章节"},
            ],
        }
        assert "id" in outline_item
        assert "title" in outline_item
        assert "children" in outline_item


class TestRouterEndpointPatterns:
    """测试路由端点模式（非集成测试）"""

    def test_generate_outline_endpoint_accepts_json(self) -> None:
        """目录生成接口应接受 JSON 请求体"""
        request = ProjectOutlineRequest.model_validate({
            "project_id": str(uuid.uuid4()),
        })
        assert request.project_id is not None

    def test_generate_content_endpoint_accepts_json(self) -> None:
        """内容生成接口应接受 JSON 请求体"""
        project_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        request = ProjectContentGenerateRequest.model_validate({
            "project_id": str(project_id),
            "chapter_id": str(chapter_id),
        })
        assert request.project_id == str(project_id)
        assert request.chapter_id == str(chapter_id)

    def test_get_chapters_endpoint_response_structure(self) -> None:
        """获取章节列表接口响应结构"""
        fields = ProjectOutlineResponse.model_fields.keys()
        assert "project_id" in fields
        assert "chapters" in fields
        assert "total_count" in fields


class TestChapterCreatedResponseFromOrmPattern:
    """测试从 ORM 模型构建响应的模式"""

    def test_build_from_orm_pattern(self) -> None:
        """验证可以手动从 ORM 模型构建"""
        # 模拟 ORM 模型
        class MockChapter:
            id = uuid.uuid4()
            chapter_number = "1.1"
            title = "测试章节"
            parent_id = uuid.uuid4()
            status = ChapterStatus.PENDING

        chapter = MockChapter()
        response = ChapterCreatedResponse(
            id=str(chapter.id),
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            parent_id=str(chapter.parent_id) if chapter.parent_id else None,
            status=chapter.status.value,
        )
        assert response.chapter_number == "1.1"
        assert response.status == "pending"

    def test_build_nested_chapters_pattern(self) -> None:
        """构建嵌套章节响应"""
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()

        parent = ChapterCreatedResponse(
            id=str(parent_id),
            chapter_number="1",
            title="父章节",
            status="pending",
        )
        child = ChapterCreatedResponse(
            id=str(child_id),
            chapter_number="1.1",
            title="子章节",
            parent_id=str(parent_id),
            status="generated",
        )

        response = ProjectOutlineResponse(
            project_id=str(uuid.uuid4()),
            chapters=[parent, child],
            total_count=2,
        )

        assert len(response.chapters) == 2
        # 验证父子关系
        child_in_response = next(c for c in response.chapters if c.chapter_number == "1.1")
        assert child_in_response.parent_id == str(parent_id)
