"""提示词服务与路由的单元测试"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.models.project import ProjectMemberRole
from app.routers import projects as projects_router
from app.schemas.prompt import ProjectPromptOverride
from app.services import openai_service as openai_service_module
from app.services.openai_service import OpenAIService
from app.services.prompt_service import PromptService
from app.utils.builtin_prompts import get_builtin_prompt


async def collect_chunks(generator) -> list[str]:
    """收集异步生成器的全部输出"""
    return [chunk async for chunk in generator]


class TestPromptParsing:
    """测试提示词解析与渲染"""

    def test_split_prompt_supports_windows_newlines_and_spaced_separator(self) -> None:
        """应兼容 Windows 换行和带空格的分隔符"""
        prompt = "# 系统指令\r\n系统内容\r\n  ---  \r\n# 用户输入\r\n用户内容"

        system_prompt, user_template = PromptService.split_prompt(prompt)

        assert system_prompt == "系统内容"
        assert user_template == "用户内容"

    def test_validate_prompt_rejects_unknown_variables(self) -> None:
        """保存提示词前应拦截未知模板变量"""
        prompt = """# 系统指令

系统内容

---

# 用户输入

{{file_content}}
{{unknown_var}}"""

        with pytest.raises(ValueError, match="unknown_var"):
            PromptService.validate_prompt("doc_analysis_overview", prompt)

    def test_render_prompt_serializes_structured_values_as_json(self) -> None:
        """字典和列表变量应以 JSON 形式渲染，避免 Python repr 污染提示词"""
        service = PromptService(db=None)

        rendered = service.render_prompt(
            "上下文：{{payload}}",
            {
                "payload": {
                    "name": "投标方案",
                    "tags": ["A", "B"],
                }
            },
        )

        assert '"name": "投标方案"' in rendered
        assert '"tags": [' in rendered
        assert "'name'" not in rendered


class TestBuiltinPrompts:
    """测试内置提示词契约"""

    def test_outline_l1_prompt_matches_runtime_contract(self) -> None:
        """一级目录提示词应与运行时代码要求的 JSON 结构一致"""
        prompt = get_builtin_prompt("outline_l1")["prompt"]

        assert "rating_item" in prompt
        assert "new_title" in prompt
        assert '"outline"' not in prompt

    def test_outline_and_chapter_prompts_accept_response_matrix(self) -> None:
        """目录生成函数应通过 rating_checklist 接受响应矩阵；章节生成函数应接受 project_response_matrix"""
        import inspect
        from app.services.openai_service import OpenAIService

        # outline_v2 通过 rating_checklist 参数间接支持响应矩阵（内部调用 _build_project_response_matrix）
        outline_sig = inspect.signature(OpenAIService.generate_outline_v2)
        assert "rating_checklist" in outline_sig.parameters, \
            "generate_outline_v2 应接受 rating_checklist 参数以构建响应矩阵"

        # 章节生成函数直接接受 project_response_matrix
        chapter_sig = inspect.signature(OpenAIService._generate_chapter_content)
        assert "project_response_matrix" in chapter_sig.parameters, \
            "_generate_chapter_content 应接受 project_response_matrix 参数"


class TestOpenAIServiceResponseMatrix:
    """测试项目响应矩阵构建"""

    def test_build_project_response_matrix_contains_rating_fields(self) -> None:
        matrix = OpenAIService._build_project_response_matrix(
            [
                {
                    "rating_item": "服务能力",
                    "score": "15分",
                    "response_targets": ["覆盖服务流程", "明确支撑措施"],
                    "evidence_suggestions": ["团队配置", "应急预案"],
                    "writing_focus": "强调响应机制",
                    "risk_points": ["内容空泛"],
                }
            ]
        )

        assert "服务能力" in matrix
        assert "覆盖服务流程" in matrix
        assert "应急预案" in matrix
        assert "内容空泛" in matrix

    def test_key_prompts_include_non_fabrication_and_evidence_guards(self) -> None:
        """关键 prompt 应包含防编造和基于证据判断的约束"""
        chapter_prompt = get_builtin_prompt("chapter_content")["prompt"]
        proofread_prompt = get_builtin_prompt("proofread")["prompt"]
        consistency_prompt = get_builtin_prompt("consistency_check")["prompt"]

        assert "不要编造" in chapter_prompt
        assert "如果资料未提及" in chapter_prompt
        assert "只报告有明确依据" in proofread_prompt
        assert "不要把正常的表述差异误判" in consistency_prompt


class TestProjectPromptRoute:
    """测试项目级提示词接口"""

    def test_set_project_prompt_uses_prompt_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """项目级提示词保存接口应传递完整 prompt 字段"""
        project_id = uuid.uuid4()
        user_id = uuid.uuid4()
        call_args: dict[str, str] = {}

        async def fake_get_project_for_user(*args, **kwargs):
            return object()

        async def fake_get_project_member_role(*args, **kwargs):
            return ProjectMemberRole.EDITOR

        class FakePromptService:
            def __init__(self, db):
                self.db = db

            async def set_project_prompt(self, *, project_id, scene_key, prompt):
                call_args["project_id"] = str(project_id)
                call_args["scene_key"] = scene_key
                call_args["prompt"] = prompt

            async def list_project_prompts(self, project_id):
                return [
                    {
                        "scene_key": "chapter_content",
                        "scene_name": "章节内容生成",
                        "category": "generation",
                        "prompt": call_args["prompt"],
                        "available_vars": None,
                        "source": "project",
                        "has_project_override": True,
                        "has_global_override": False,
                    }
                ]

        monkeypatch.setattr(projects_router, "get_project_for_user", fake_get_project_for_user)
        monkeypatch.setattr(projects_router, "get_project_member_role", fake_get_project_member_role)
        monkeypatch.setattr(projects_router, "PromptService", FakePromptService)

        response = asyncio.run(
            projects_router.set_project_prompt(
                project_id=project_id,
                scene_key="chapter_content",
                data=ProjectPromptOverride(prompt="完整提示词内容123"),
                current_user=SimpleNamespace(id=user_id),
                db=None,
            )
        )

        assert call_args == {
            "project_id": str(project_id),
            "scene_key": "chapter_content",
            "prompt": "完整提示词内容123",
        }
        assert response.prompt == "完整提示词内容123"


class TestOpenAIServicePromptContracts:
    """测试运行时补充的提示词契约"""

    def test_generate_outline_v2_appends_json_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """目录生成应在运行时追加明确的 JSON 输出契约"""
        service = OpenAIService(db=None)
        captured: dict[str, str] = {}

        class FakePromptService:
            async def get_prompt(self, scene_key, project_id):
                return (
                    """# 系统指令

基础规则

---

# 用户输入

{{overview}}
{{requirements}}""",
                    "builtin",
                )

            def render_prompt(self, template, variables):
                return PromptService(None).render_prompt(template, variables)

        async def fake_generate_with_json_check(*, messages, schema, **kwargs):
            captured["system_prompt"] = messages[0]["content"]
            return '[{"rating_item":"评分项A","new_title":"第一章"}]'

        async def fake_process_level1_node(
            i, level1_node, nodes_distribution, level_l1, overview, requirements
        ):
            return {
                "id": str(i + 1),
                "title": level1_node["new_title"],
                "children": [],
            }

        service._prompt_service = FakePromptService()
        monkeypatch.setattr(service, "_generate_with_json_check", fake_generate_with_json_check)
        monkeypatch.setattr(service, "process_level1_node", fake_process_level1_node)
        monkeypatch.setattr(openai_service_module, "get_random_indexes", lambda _: (0, 0))
        monkeypatch.setattr(openai_service_module, "calculate_nodes_distribution", lambda *args, **kwargs: [1])

        result = asyncio.run(service.generate_outline_v2("项目概述", "评分要求"))

        assert "rating_item" in captured["system_prompt"]
        assert "new_title" in captured["system_prompt"]
        assert result == {
            "outline": [
                {
                    "id": "1",
                    "title": "第一章",
                    "children": [],
                }
            ]
        }

    def test_process_level1_node_appends_json_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """二三级目录生成也应在运行时追加 JSON 输出契约"""
        service = OpenAIService(db=None)
        captured: dict[str, str] = {}

        class FakePromptService:
            async def get_prompt(self, scene_key, project_id):
                return (
                    """# 系统指令

基础规则

---

# 用户输入

{{overview}}
{{requirements}}
{{other_outline}}
{{current_outline_json}}""",
                    "builtin",
                )

            def render_prompt(self, template, variables):
                return PromptService(None).render_prompt(template, variables)

        async def fake_generate_with_json_check(*, messages, schema, **kwargs):
            captured["system_prompt"] = messages[0]["content"]
            return '{"id":"1","title":"二级标题","description":"说明","children":[]}'

        service._prompt_service = FakePromptService()
        monkeypatch.setattr(service, "_generate_with_json_check", fake_generate_with_json_check)
        monkeypatch.setattr(
            openai_service_module,
            "generate_one_outline_json_by_level1",
            lambda *args, **kwargs: {"id": "1", "title": "第一章", "description": "", "children": []},
        )

        result = asyncio.run(
            service.process_level1_node(
                0,
                {"new_title": "第一章"},
                [1, 1],
                [{"new_title": "第一章"}, {"new_title": "第二章"}],
                "项目概述",
                "评分要求",
            )
        )

        assert "输出格式约束" in captured["system_prompt"]
        assert '"children"' in captured["system_prompt"]
        assert result["title"] == "二级标题"

    def test_proofread_chapter_appends_json_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """章节校对应在运行时追加 JSON 输出契约"""
        service = OpenAIService(db=None)
        captured: dict[str, str] = {}

        class FakePromptService:
            async def get_prompt(self, scene_key, project_id):
                return (
                    """# 系统指令

基础规则

---

# 用户输入

{{chapter_title}}
{{chapter_content}}
{{tech_requirements}}""",
                    "builtin",
                )

            def render_prompt(self, template, variables):
                return PromptService(None).render_prompt(template, variables)

        async def fake_stream_chat_completion(messages, temperature=0.3, response_format=None, max_tokens=8192):
            captured["system_prompt"] = messages[0]["content"]
            yield '{"issues":[],"summary":"ok"}'

        service._prompt_service = FakePromptService()
        monkeypatch.setattr(service, "stream_chat_completion", fake_stream_chat_completion)

        chunks = asyncio.run(
            collect_chunks(
                service.proofread_chapter(
                    chapter_title="章节A",
                    chapter_content="正文",
                    tech_requirements="评分要求",
                )
            )
        )

        assert '"issues"' in captured["system_prompt"]
        assert '"severity"' in captured["system_prompt"]
        assert chunks == ['{"issues":[],"summary":"ok"}']

    def test_check_consistency_appends_json_contract(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """一致性检查应在运行时追加 JSON 输出契约"""
        service = OpenAIService(db=None)
        captured: dict[str, str] = {}

        class FakePromptService:
            async def get_prompt(self, scene_key, project_id):
                return (
                    """# 系统指令

基础规则

---

# 用户输入

{{chapter_summaries}}
{{tech_requirements}}""",
                    "builtin",
                )

            def render_prompt(self, template, variables):
                return PromptService(None).render_prompt(template, variables)

        async def fake_stream_chat_completion(messages, temperature=0.3, response_format=None, max_tokens=4096):
            captured["system_prompt"] = messages[0]["content"]
            yield '{"contradictions":[],"summary":"ok","overall_consistency":"consistent"}'

        service._prompt_service = FakePromptService()
        monkeypatch.setattr(service, "stream_chat_completion", fake_stream_chat_completion)

        chunks = asyncio.run(
            collect_chunks(
                service.check_consistency(
                    chapter_summaries=[{"chapter_number": "1", "title": "章节A", "summary": "内容"}],
                    tech_requirements="评分要求",
                )
            )
        )

        assert '"contradictions"' in captured["system_prompt"]
        assert '"overall_consistency"' in captured["system_prompt"]
        assert chunks == ['{"contradictions":[],"summary":"ok","overall_consistency":"consistent"}']

    def test_generate_with_json_check_keeps_list_schema_as_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """列表 schema 应保持数组结构，不应被自动拆成单个对象。"""
        service = OpenAIService(db=None)

        async def fake_collect_stream_text(messages, temperature=0.7, response_format=None):
            return '[{"rating_item":"服务能力","score":"15分","response_targets":["覆盖服务流程"]}]'

        monkeypatch.setattr(service, "_collect_stream_text", fake_collect_stream_text)

        result = asyncio.run(
            service._generate_with_json_check(
                messages=[{"role": "user", "content": "test"}],
                schema=[{"rating_item": "评分项名称", "score": "分值或权重", "response_targets": ["必须覆盖的响应点"]}],
                max_retries=0,
                temperature=0.1,
                response_format=None,
                log_prefix="评分响应清单",
                raise_on_fail=True,
            )
        )

        assert result.startswith('[')
        assert '"rating_item":"服务能力"' in result or '"rating_item": "服务能力"' in result

    def test_generate_with_json_check_keeps_json_string_list_schema_as_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """字符串形式的列表 schema 也不应被错误降级成单对象。"""
        service = OpenAIService(db=None)

        async def fake_collect_stream_text(messages, temperature=0.7, response_format=None):
            return '[{"rating_item":"服务能力","score":"15分","response_targets":["覆盖服务流程"]}]'

        monkeypatch.setattr(service, "_collect_stream_text", fake_collect_stream_text)

        result = asyncio.run(
            service._generate_with_json_check(
                messages=[{"role": "user", "content": "test"}],
                schema='[{"rating_item":"评分项名称","score":"分值或权重","response_targets":["必须覆盖的响应点"]}]',
                max_retries=0,
                temperature=0.1,
                response_format=None,
                log_prefix="评分响应清单",
                raise_on_fail=True,
            )
        )

        assert result.startswith('[')
        assert '"rating_item":"服务能力"' in result or '"rating_item": "服务能力"' in result
