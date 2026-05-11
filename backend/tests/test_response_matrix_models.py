"""Tests for M2 Response Matrix models, schemas, and service logic.

Pure unit tests — no database required.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. Enum smoke tests
# ---------------------------------------------------------------------------

class TestClauseType:
    def test_values(self):
        from app.models.response_matrix import ClauseType

        assert ClauseType.technical.value == "technical"
        assert ClauseType.scoring.value == "scoring"
        assert ClauseType.disqualification.value == "disqualification"
        assert ClauseType.format.value == "format"
        assert ClauseType.qualification.value == "qualification"
        assert ClauseType.commercial.value == "commercial"
        assert ClauseType.other.value == "other"


class TestResponseStatus:
    def test_values(self):
        from app.models.response_matrix import ResponseStatus

        assert ResponseStatus.not_started.value == "not_started"
        assert ResponseStatus.covered.value == "covered"
        assert ResponseStatus.partial.value == "partial"
        assert ResponseStatus.missing.value == "missing"
        assert ResponseStatus.risk.value == "risk"
        assert ResponseStatus.not_applicable.value == "not_applicable"


# ---------------------------------------------------------------------------
# 2. Model instantiation (no DB, just constructor)
# ---------------------------------------------------------------------------

class TestTenderClauseModel:
    def test_create_defaults(self):
        from app.models.response_matrix import TenderClause, ClauseType

        tc = TenderClause(
            project_id=uuid.uuid4(),
            clause_type=ClauseType.scoring,
            title="技术方案评分",
            content="满分20分",
            is_fatal=False,
            metadata_json={},
        )
        assert tc.title == "技术方案评分"
        assert tc.clause_type == ClauseType.scoring
        assert tc.is_fatal is False
        assert tc.score_value is None
        assert tc.metadata_json == {}

    def test_fatal_clause(self):
        from app.models.response_matrix import TenderClause, ClauseType

        tc = TenderClause(
            project_id=uuid.uuid4(),
            clause_type=ClauseType.disqualification,
            title="必须提供营业执照",
            is_fatal=True,
        )
        assert tc.is_fatal is True


class TestResponseMatrixItemModel:
    def test_create_defaults(self):
        from app.models.response_matrix import ResponseMatrixItem, ResponseStatus

        item = ResponseMatrixItem(
            project_id=uuid.uuid4(),
            clause_id=uuid.uuid4(),
            response_status=ResponseStatus.not_started,
            confidence="medium",
            chapter_id="",
        )
        assert item.response_status == ResponseStatus.not_started
        assert item.confidence == "medium"
        assert item.chapter_id == ""


# ---------------------------------------------------------------------------
# 3. Schema tests
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_tender_clause_response(self):
        from app.schemas.response_matrix import TenderClauseResponse

        resp = TenderClauseResponse(
            id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            clause_type="scoring",
            title="test",
        )
        assert resp.clause_type == "scoring"
        assert resp.is_fatal is False

    def test_response_matrix_summary_defaults(self):
        from app.schemas.response_matrix import ResponseMatrixSummary

        s = ResponseMatrixSummary()
        assert s.total_clauses == 0
        assert s.overall_status == "not_ready"
        assert s.scoring_coverage_rate == 0

    def test_bind_clause_request(self):
        from app.schemas.response_matrix import BindClauseRequest

        req = BindClauseRequest(clause_id=str(uuid.uuid4()), chapter_id="ch1")
        assert req.chapter_id == "ch1"

    def test_update_matrix_item_request(self):
        from app.schemas.response_matrix import UpdateMatrixItemRequest

        req = UpdateMatrixItemRequest(response_status="covered", confidence="high")
        assert req.response_status == "covered"
        assert req.confidence == "high"


# ---------------------------------------------------------------------------
# 4. Summary calculation with mock data
# ---------------------------------------------------------------------------

class TestSummarizeLogic:
    """Test the summarize function's counting logic by mocking DB layer."""

    @pytest.mark.asyncio
    async def test_empty_project(self):
        from app.services.response_matrix_service import summarize
        from app.schemas.response_matrix import ResponseMatrixSummary

        mock_db = AsyncMock()

        # Mock clauses query returns empty
        clauses_result = MagicMock()
        clauses_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(return_value=clauses_result)

        summary = await summarize(mock_db, uuid.uuid4())
        assert summary.total_clauses == 0
        assert summary.covered == 0

    @pytest.mark.asyncio
    async def test_all_covered(self):
        from app.services.response_matrix_service import summarize
        from app.models.response_matrix import TenderClause, ResponseMatrixItem, ClauseType, ResponseStatus

        mock_db = AsyncMock()
        pid = uuid.uuid4()

        tc = TenderClause(
            project_id=pid,
            clause_type=ClauseType.scoring,
            title="SC1",
            score_value=10,
        )
        tc.id = uuid.uuid4()

        item = ResponseMatrixItem(
            project_id=pid,
            clause_id=tc.id,
            response_status=ResponseStatus.covered,
        )

        clauses_result = MagicMock()
        clauses_result.scalars.return_value.all.return_value = [tc]

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [item]

        mock_db.execute = AsyncMock(side_effect=[clauses_result, items_result])

        summary = await summarize(mock_db, pid)
        assert summary.total_clauses == 1
        assert summary.covered == 1
        assert summary.missing == 0
        assert summary.overall_status == "ready"

    @pytest.mark.asyncio
    async def test_fatal_missing_gives_risk(self):
        from app.services.response_matrix_service import summarize
        from app.models.response_matrix import TenderClause, ResponseMatrixItem, ClauseType, ResponseStatus

        mock_db = AsyncMock()
        pid = uuid.uuid4()

        tc = TenderClause(
            project_id=pid,
            clause_type=ClauseType.disqualification,
            title="营业执照",
            is_fatal=True,
        )
        tc.id = uuid.uuid4()

        # No items → clause is missing → fatal_missing = 1
        clauses_result = MagicMock()
        clauses_result.scalars.return_value.all.return_value = [tc]

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[clauses_result, items_result])

        summary = await summarize(mock_db, pid)
        assert summary.total_clauses == 1
        assert summary.missing == 1
        assert summary.fatal_missing == 1
        assert summary.overall_status == "risk"


# ---------------------------------------------------------------------------
# 5. Auto-bind heuristic test
# ---------------------------------------------------------------------------

class TestAutoBindHeuristic:
    @pytest.mark.asyncio
    async def test_keyword_matching(self):
        from app.services.response_matrix_service import auto_bind_to_chapters
        from app.models.response_matrix import TenderClause, ClauseType
        from app.models.chapter import Chapter

        mock_db = AsyncMock()
        pid = uuid.uuid4()

        tc = TenderClause(
            project_id=pid,
            clause_type=ClauseType.scoring,
            title="技术方案实施计划",
            content="",
            score_value=10,
        )
        tc.id = uuid.uuid4()
        tc.metadata_json = {"keywords": ["实施方案", "计划"]}

        ch = Chapter(
            project_id=pid,
            chapter_number="3",
            title="技术实施方案与计划",
        )
        ch.id = uuid.uuid4()

        clauses_result = MagicMock()
        clauses_result.scalars.return_value.all.return_value = [tc]

        existing_result = MagicMock()
        existing_result.all.return_value = []  # no bound clauses yet

        chapters_result = MagicMock()
        chapters_result.scalars.return_value.all.return_value = [ch]

        mock_db.execute = AsyncMock(
            side_effect=[clauses_result, existing_result, chapters_result]
        )
        mock_db.flush = AsyncMock()

        count = await auto_bind_to_chapters(mock_db, pid)
        assert count == 1

    @pytest.mark.asyncio
    async def test_no_match(self):
        from app.services.response_matrix_service import auto_bind_to_chapters
        from app.models.response_matrix import TenderClause, ClauseType
        from app.models.chapter import Chapter

        mock_db = AsyncMock()
        pid = uuid.uuid4()

        tc = TenderClause(
            project_id=pid,
            clause_type=ClauseType.scoring,
            title="价格评分",
            content="",
        )
        tc.id = uuid.uuid4()
        tc.metadata_json = {"keywords": ["报价", "价格"]}

        ch = Chapter(
            project_id=pid,
            chapter_number="5",
            title="售后服务承诺",
        )
        ch.id = uuid.uuid4()

        clauses_result = MagicMock()
        clauses_result.scalars.return_value.all.return_value = [tc]

        existing_result = MagicMock()
        existing_result.all.return_value = []

        chapters_result = MagicMock()
        chapters_result.scalars.return_value.all.return_value = [ch]

        mock_db.execute = AsyncMock(
            side_effect=[clauses_result, existing_result, chapters_result]
        )
        mock_db.flush = AsyncMock()

        count = await auto_bind_to_chapters(mock_db, pid)
        assert count == 0  # no keyword overlap → no bind


# ---------------------------------------------------------------------------
# 6. Service helper: _clause_to_dict / _item_to_dict
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_clause_to_dict(self):
        from app.services.response_matrix_service import _clause_to_dict
        from app.models.response_matrix import TenderClause, ClauseType

        pid = uuid.uuid4()
        tc = TenderClause(
            project_id=pid,
            clause_type=ClauseType.scoring,
            title="技术评分",
            content="满分10分",
            score_value=10.0,
            is_fatal=False,
        )
        tc.id = uuid.uuid4()

        d = _clause_to_dict(tc)
        assert d["clause_type"] == "scoring"
        assert d["score_value"] == 10.0
        assert d["is_fatal"] is False

    def test_item_to_dict(self):
        from app.services.response_matrix_service import _item_to_dict
        from app.models.response_matrix import ResponseMatrixItem, ResponseStatus

        item = ResponseMatrixItem(
            project_id=uuid.uuid4(),
            clause_id=uuid.uuid4(),
            response_status=ResponseStatus.covered,
            chapter_id="ch-1",
            chapter_title="技术方案",
        )
        item.id = uuid.uuid4()

        d = _item_to_dict(item)
        assert d["response_status"] == "covered"
        assert d["chapter_id"] == "ch-1"
