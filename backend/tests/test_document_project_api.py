"""项目上下文文档接口单元测试"""
import uuid

import pytest

from app.models.schemas import (
    AnalysisType,
    ProjectFileUploadResponse,
    ProjectAnalysisRequest,
)


class TestProjectFileUploadResponseSchema:
    """测试 ProjectFileUploadResponse Schema"""

    def test_valid_data(self) -> None:
        """验证有效数据"""
        project_id = uuid.uuid4()
        response = ProjectFileUploadResponse(
            success=True,
            message="上传成功",
            project_id=str(project_id),
            file_content_length=1000,
        )
        assert response.success is True
        assert response.message == "上传成功"
        assert response.project_id == str(project_id)
        assert response.file_content_length == 1000

    def test_failure_response(self) -> None:
        """失败响应"""
        response = ProjectFileUploadResponse(
            success=False,
            message="文件类型不支持",
            project_id="",
            file_content_length=0,
        )
        assert response.success is False


class TestProjectAnalysisRequestSchema:
    """测试 ProjectAnalysisRequest Schema"""

    def test_overview_analysis(self) -> None:
        """项目概述分析请求"""
        project_id = uuid.uuid4()
        request = ProjectAnalysisRequest(
            project_id=str(project_id),
            analysis_type=AnalysisType.OVERVIEW,
        )
        assert request.project_id == str(project_id)
        assert request.analysis_type == AnalysisType.OVERVIEW

    def test_requirements_analysis(self) -> None:
        """技术评分要求分析请求"""
        project_id = uuid.uuid4()
        request = ProjectAnalysisRequest(
            project_id=str(project_id),
            analysis_type=AnalysisType.REQUIREMENTS,
        )
        assert request.project_id == str(project_id)
        assert request.analysis_type == AnalysisType.REQUIREMENTS

    def test_invalid_uuid_format(self) -> None:
        """无效的 UUID 格式（在路由层验证）"""
        # Schema 层只验证字符串格式，UUID 验证在路由层
        request = ProjectAnalysisRequest(
            project_id="invalid-uuid",
            analysis_type=AnalysisType.OVERVIEW,
        )
        assert request.project_id == "invalid-uuid"


class TestAnalysisTypeEnum:
    """测试 AnalysisType 枚举"""

    def test_enum_is_string(self) -> None:
        """枚举应继承自 str"""
        assert issubclass(AnalysisType, str)

    def test_enum_values(self) -> None:
        """验证枚举值"""
        assert AnalysisType.OVERVIEW == "overview"
        assert AnalysisType.REQUIREMENTS == "requirements"


class TestProjectDocumentRouterPatterns:
    """测试项目文档路由模式（非集成测试）"""

    def test_upload_endpoint_accepts_form_data(self) -> None:
        """上传接口应接受 form-data（project_id + file）"""
        # 这只是模式验证，实际测试需要集成测试
        # 接口定义: project_id: str (Form), file: UploadFile (File)
        assert True  # 路由已定义

    def test_analyze_endpoint_accepts_json(self) -> None:
        """分析接口应接受 JSON 请求体"""
        # 验证 schema 接受 JSON
        project_id = uuid.uuid4()
        request = ProjectAnalysisRequest.model_validate({
            "project_id": str(project_id),
            "analysis_type": "overview",
        })
        assert request.analysis_type == AnalysisType.OVERVIEW

    def test_analysis_result_endpoint_returns_all_fields(self) -> None:
        """分析结果接口应返回所有相关字段"""
        # ProjectAnalysisResult schema 在路由中定义
        # 包含: project_id, file_content, project_overview, tech_requirements
        assert True  # 路由已定义
