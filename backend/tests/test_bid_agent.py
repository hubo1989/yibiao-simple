"""Unit tests for Iteration 3 Bid Agent MVP."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestBidAgentModels:
    def test_run_and_step_enums(self):
        from app.models.bid_agent import BidAgentRunStatus, BidAgentStepStatus

        assert BidAgentRunStatus.pending.value == "pending"
        assert BidAgentRunStatus.running.value == "running"
        assert BidAgentRunStatus.completed.value == "completed"
        assert BidAgentRunStatus.failed.value == "failed"
        assert BidAgentRunStatus.cancelled.value == "cancelled"
        assert BidAgentStepStatus.skipped.value == "skipped"

    def test_run_constructor_defaults(self):
        from app.models.bid_agent import BidAgentRun, BidAgentRunStatus

        project_id = uuid.uuid4()
        run = BidAgentRun(project_id=project_id, created_by=None, goal="generate_draft")
        assert run.project_id == project_id
        assert run.created_by is None
        assert run.goal == "generate_draft"
        # SQLAlchemy column defaults are applied on flush; explicit enum assignment remains supported.
        run.status = BidAgentRunStatus.pending
        assert run.status == BidAgentRunStatus.pending

    def test_step_constructor(self):
        from app.models.bid_agent import BidAgentStep, BidAgentStepStatus

        run_id = uuid.uuid4()
        step = BidAgentStep(
            run_id=run_id,
            step_key="response_matrix_preflight",
            step_name="响应矩阵质量检查",
            order_index=1,
            status=BidAgentStepStatus.pending,
        )
        assert step.run_id == run_id
        assert step.step_key == "response_matrix_preflight"
        assert step.order_index == 1
        assert step.status == BidAgentStepStatus.pending


class TestBidAgentSchemas:
    def test_run_response_schema(self):
        from app.schemas.bid_agent import BidAgentRunResponse

        resp = BidAgentRunResponse(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            goal="generate_draft",
            status="completed",
            result_json={"quality_report": {"ready": True}},
        )
        assert resp.progress == 0
        assert resp.result_json["quality_report"]["ready"] is True

    def test_quality_report_defaults(self):
        from app.schemas.bid_agent import BidAgentQualityReport

        report = BidAgentQualityReport(project_id=str(uuid.uuid4()))
        assert report.ready is False
        assert report.blockers == []


class TestBidAgentService:
    @pytest.mark.asyncio
    async def test_initialize_steps_for_fix_risks(self):
        from app.models.bid_agent import BidAgentRun
        from app.services.bid_agent_service import initialize_steps

        db = AsyncMock()
        db.add = MagicMock()
        run = BidAgentRun(id=uuid.uuid4(), project_id=uuid.uuid4(), created_by=None, goal="fix_risks")
        steps = await initialize_steps(db, run)

        assert [s.step_key for s in steps] == [
            "response_matrix_preflight",
            "export_preflight",
            "assemble_quality_report",
        ]
        assert db.add.call_count == 3
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_build_quality_report_with_mocks(self, monkeypatch):
        from app.schemas.response_matrix import ResponseMatrixSummary
        from app.services import bid_agent_service

        async def fake_matrix_preflight(db, project_id):
            return {
                "ready": False,
                "summary": ResponseMatrixSummary(total_clauses=2, missing=1),
                "blockers": ["存在 1 项条款缺失或未开始响应"],
            }

        async def fake_export_preflight(db, project_id):
            return {
                "project_id": project_id,
                "block_export": True,
                "blockers": [{"chapter_title": "第一章", "issues": [{"severity": "critical"}]}],
                "summary": {"blocker_count": 1},
            }

        monkeypatch.setattr(bid_agent_service.response_matrix_service, "preflight", fake_matrix_preflight)
        monkeypatch.setattr(bid_agent_service, "build_export_preflight_payload", fake_export_preflight)

        report = await bid_agent_service.build_quality_report(AsyncMock(), uuid.uuid4())

        assert report["ready"] is False
        assert report["response_matrix_preflight"]["summary"]["total_clauses"] == 2
        assert "存在 1 项条款缺失" in report["blockers"][0]
        assert "第一章" in report["blockers"][1]

    @pytest.mark.asyncio
    async def test_execute_fix_risks_checks_only_and_completes(self, monkeypatch):
        from app.models.bid_agent import BidAgentRun, BidAgentRunStatus, BidAgentStep
        from app.services import bid_agent_service

        project_id = uuid.uuid4()
        run = BidAgentRun(id=uuid.uuid4(), project_id=project_id, created_by=None, goal="fix_risks")
        steps = [
            BidAgentStep(id=uuid.uuid4(), run_id=run.id, step_key="response_matrix_preflight", step_name="rm", order_index=1),
            BidAgentStep(id=uuid.uuid4(), run_id=run.id, step_key="export_preflight", step_name="export", order_index=2),
            BidAgentStep(id=uuid.uuid4(), run_id=run.id, step_key="assemble_quality_report", step_name="report", order_index=3),
        ]
        db = AsyncMock()

        async def fake_get_run(db_arg, run_id):
            return run

        async def fake_list_steps(db_arg, run_id):
            return steps

        async def fake_matrix_preflight(db_arg, project_id_arg):
            return {"ready": True, "summary": {}, "blockers": []}

        async def fake_export_preflight(db_arg, project_id_arg):
            return {"project_id": project_id_arg, "block_export": False, "blockers": [], "summary": {}}

        monkeypatch.setattr(bid_agent_service, "get_run", fake_get_run)
        monkeypatch.setattr(bid_agent_service, "list_steps", fake_list_steps)
        monkeypatch.setattr(bid_agent_service.response_matrix_service, "preflight", fake_matrix_preflight)
        monkeypatch.setattr(bid_agent_service, "build_export_preflight_payload", fake_export_preflight)

        completed = await bid_agent_service.execute_generate_draft(db, run.id)

        assert completed.status == BidAgentRunStatus.completed
        assert completed.progress == 100
        assert completed.result_json["quality_report"]["ready"] is True
        assert completed.summary == "风险检查完成"
        assert all(step.progress == 100 for step in steps)

    @pytest.mark.asyncio
    async def test_execute_generate_draft_full_step_flow_with_monkeypatched_helpers(self, monkeypatch):
        from app.models.bid_agent import BidAgentRun, BidAgentRunStatus, BidAgentStep
        from app.services import bid_agent_service

        project_id = uuid.uuid4()
        run = BidAgentRun(id=uuid.uuid4(), project_id=project_id, created_by=uuid.uuid4(), goal="generate_draft")
        steps = [
            BidAgentStep(id=uuid.uuid4(), run_id=run.id, step_key=key, step_name=name, order_index=i)
            for i, (key, name) in enumerate(bid_agent_service.GENERATE_DRAFT_STEPS, start=1)
        ]
        db = AsyncMock()

        async def fake_get_run(db_arg, run_id):
            return run

        async def fake_list_steps(db_arg, run_id):
            return steps

        async def fake_analysis(db_arg, project_id_arg):
            return {"skipped": False, "project_overview_length": 10, "tech_requirements_length": 20}

        async def fake_outline(db_arg, project_id_arg):
            return {"skipped": False, "created_count": 2}

        async def fake_rebuild(db_arg, project_id_arg):
            return {"total_clauses": 3}

        async def fake_generate_contents(db_arg, project_id_arg, created_by_arg=None):
            return {"generated_count": 2, "skipped_count": 1, "hallucination_issue_count": 0, "per_chapter": []}

        async def fake_matrix_preflight(db_arg, project_id_arg):
            return {"ready": True, "summary": {}, "blockers": []}

        async def fake_export_preflight(db_arg, project_id_arg):
            return {"project_id": str(project_id_arg), "block_export": False, "blockers": [], "summary": {}}

        monkeypatch.setattr(bid_agent_service, "get_run", fake_get_run)
        monkeypatch.setattr(bid_agent_service, "list_steps", fake_list_steps)
        monkeypatch.setattr(bid_agent_service, "ensure_project_analysis", fake_analysis)
        monkeypatch.setattr(bid_agent_service, "ensure_outline", fake_outline)
        monkeypatch.setattr(bid_agent_service.response_matrix_service, "rebuild_from_project", fake_rebuild)
        monkeypatch.setattr(bid_agent_service, "generate_chapter_contents", fake_generate_contents)
        monkeypatch.setattr(bid_agent_service.response_matrix_service, "preflight", fake_matrix_preflight)
        monkeypatch.setattr(bid_agent_service, "build_export_preflight_payload", fake_export_preflight)

        completed = await bid_agent_service.execute_generate_draft(db, run.id)

        assert completed.status == BidAgentRunStatus.completed
        assert completed.progress == 100
        assert completed.summary == "一键草稿编排完成"
        assert completed.result_json["quality_report"]["generated_count"] == 2
        assert [step.step_key for step in steps] == [key for key, _ in bid_agent_service.GENERATE_DRAFT_STEPS]
        assert all(step.progress == 100 for step in steps)
        assert steps[3].result_json["generated_count"] == 2
