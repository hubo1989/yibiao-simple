"""Project 模型和 Schema 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.project import Project, ProjectStatus, ProjectMemberRole
from app.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummary,
    ProjectMemberAdd,
    ProjectMemberResponse,
)


class TestProjectStatusEnum:
    """测试 ProjectStatus 枚举"""

    def test_status_is_string_enum(self):
        """枚举应继承自 str"""
        assert issubclass(ProjectStatus, str)

    def test_status_values(self):
        """验证状态值"""
        assert ProjectStatus.DRAFT == "draft"
        assert ProjectStatus.IN_PROGRESS == "in_progress"
        assert ProjectStatus.REVIEWING == "reviewing"
        assert ProjectStatus.COMPLETED == "completed"


class TestProjectMemberRoleEnum:
    """测试 ProjectMemberRole 枚举"""

    def test_role_is_string_enum(self):
        """枚举应继承自 str"""
        assert issubclass(ProjectMemberRole, str)

    def test_role_values(self):
        """验证角色值"""
        assert ProjectMemberRole.OWNER == "owner"
        assert ProjectMemberRole.EDITOR == "editor"
        assert ProjectMemberRole.REVIEWER == "reviewer"


class TestProjectModel:
    """测试 Project ORM 模型"""

    def test_table_name(self):
        """验证表名"""
        assert Project.__tablename__ == "projects"

    def test_columns_exist(self):
        """验证所有列存在"""
        columns = {c.name for c in Project.__table__.columns}
        expected = {
            "id",
            "name",
            "description",
            "creator_id",
            "status",
            "file_content",
            "project_overview",
            "tech_requirements",
            "created_at",
            "updated_at",
        }
        assert columns == expected

    def test_primary_key_is_uuid(self):
        """验证主键是 UUID 类型"""
        pk = Project.__table__.primary_key.columns.values()[0]
        assert pk.name == "id"


class TestProjectBase:
    """测试 ProjectBase Schema"""

    def test_valid_data(self):
        """验证有效数据"""
        project = ProjectBase(name="Test Project", description="A test")
        assert project.name == "Test Project"
        assert project.description == "A test"

    def test_name_required(self):
        """name 为必填"""
        with pytest.raises(ValidationError):
            ProjectBase()

    def test_name_min_length(self):
        """name 最小长度为 1"""
        with pytest.raises(ValidationError):
            ProjectBase(name="")

    def test_name_max_length(self):
        """name 最大长度为 255"""
        long_name = "x" * 256
        with pytest.raises(ValidationError):
            ProjectBase(name=long_name)

    def test_description_optional(self):
        """description 可选"""
        project = ProjectBase(name="Test")
        assert project.description is None


class TestProjectCreate:
    """测试 ProjectCreate Schema"""

    def test_inherits_from_base(self):
        """继承自 ProjectBase"""
        project = ProjectCreate(name="New Project", description="Desc")
        assert project.name == "New Project"
        assert project.description == "Desc"

    def test_minimal_data(self):
        """最小数据"""
        project = ProjectCreate(name="Minimal")
        assert project.name == "Minimal"
        assert project.description is None


class TestProjectUpdate:
    """测试 ProjectUpdate Schema"""

    def test_all_fields_optional(self):
        """所有字段可选"""
        update = ProjectUpdate()
        assert update.name is None
        assert update.description is None
        assert update.status is None
        assert update.file_content is None
        assert update.project_overview is None
        assert update.tech_requirements is None

    def test_partial_update(self):
        """部分更新"""
        update = ProjectUpdate(name="Updated", status=ProjectStatus.IN_PROGRESS)
        assert update.name == "Updated"
        assert update.status == ProjectStatus.IN_PROGRESS

    def test_name_validation_on_provided(self):
        """提供的 name 需验证"""
        with pytest.raises(ValidationError):
            ProjectUpdate(name="")


class TestProjectResponse:
    """测试 ProjectResponse Schema"""

    def test_from_attributes(self):
        """支持 ORM 模型转换"""
        class MockProject:
            id = uuid.uuid4()
            name = "Test"
            description = "Desc"
            creator_id = uuid.uuid4()
            status = ProjectStatus.DRAFT
            file_content = None
            project_overview = None
            tech_requirements = None
            created_at = datetime.utcnow()
            updated_at = datetime.utcnow()

        response = ProjectResponse.model_validate(MockProject())
        assert response.name == "Test"
        assert response.status == ProjectStatus.DRAFT


class TestProjectSummary:
    """测试 ProjectSummary Schema"""

    def test_excludes_large_fields(self):
        """不包含大文本字段"""
        summary_fields = ProjectSummary.model_fields.keys()
        assert "file_content" not in summary_fields
        assert "project_overview" not in summary_fields
        assert "tech_requirements" not in summary_fields

    def test_includes_required_fields(self):
        """包含必要字段"""
        summary_fields = ProjectSummary.model_fields.keys()
        assert "id" in summary_fields
        assert "name" in summary_fields
        assert "status" in summary_fields


class TestProjectMemberAdd:
    """测试 ProjectMemberAdd Schema"""

    def test_valid_data(self):
        """验证有效数据"""
        user_id = uuid.uuid4()
        member = ProjectMemberAdd(user_id=user_id, role=ProjectMemberRole.EDITOR)
        assert member.user_id == user_id
        assert member.role == ProjectMemberRole.EDITOR

    def test_default_role(self):
        """默认角色为 editor"""
        user_id = uuid.uuid4()
        member = ProjectMemberAdd(user_id=user_id)
        assert member.role == ProjectMemberRole.EDITOR


class TestProjectMemberResponse:
    """测试 ProjectMemberResponse Schema"""

    def test_from_attributes(self):
        """支持 ORM 模型转换"""
        class MockMember:
            user_id = uuid.uuid4()
            project_id = uuid.uuid4()
            role = ProjectMemberRole.OWNER
            joined_at = datetime.utcnow()

        response = ProjectMemberResponse.model_validate(MockMember())
        assert response.role == ProjectMemberRole.OWNER
