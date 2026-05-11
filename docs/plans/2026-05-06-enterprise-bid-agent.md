# Enterprise Bid Agent Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 将当前“AI 写标书助手”升级为可在企业内部试点并逐步走向生产级的“投标标书智能体”，具备项目级自动编排、响应矩阵、证据链、反幻觉质量门禁和正式 Word 交付能力。

**Architecture:** 在现有 FastAPI + React + PostgreSQL + LlamaIndex 架构上，不重写系统，而是新增一层项目级 Agent Orchestrator 和一组核心领域模型。现有 `document / outline / content / refine / review / disqualification / scoring / consistency / export / knowledge / materials` 模块保留，逐步被统一编排器调用，并围绕“响应矩阵”和“证据链”重构生成与审查流程。

**Tech Stack:** FastAPI, SQLAlchemy Async ORM, PostgreSQL + pgvector, LlamaIndex, OpenAI-compatible API, React + TypeScript, Ant Design/custom UI, python-docx, pytest, React Testing Library, Alembic.

---

## Current State Summary

当前项目已经具备企业内部标书辅助平台雏形：

- 招标文件上传与解析：`backend/app/routers/document.py`
- 目录生成：`backend/app/routers/outline.py`
- 章节生成：`backend/app/routers/content.py`
- 多轮精修：`backend/app/routers/refine.py`, `backend/app/services/refinement_service.py`
- 废标检查：`backend/app/routers/disqualification.py`
- 评分响应：`backend/app/routers/scoring.py`
- 全文一致性：`backend/app/routers/consistency.py`
- 标书复审：`backend/app/routers/review.py`, `backend/app/services/review_service.py`
- 知识库/RAG：`backend/app/services/llamaindex_knowledge_service.py`, `backend/app/services/knowledge_retrieval_service.py`
- 素材库：`backend/app/routers/materials.py`, `backend/app/services/material_service.py`
- Word 导出：`backend/app/routers/export.py`, `backend/app/services/word_export_service.py`
- 用户权限、版本、评论、审计日志等协作基础能力

但目前仍主要是“功能集合”，缺少：

1. 项目级智能体编排器
2. 中心化响应矩阵
3. 严格证据链
4. 反幻觉硬约束
5. 质量门禁
6. 正式标书模板级导出
7. 生产工程化闭环

---

## Delivery Milestones

| Milestone | Name | Target Outcome |
|---|---|---|
| M0 | 工程稳定性修复 | 构建、测试、迁移基础可用 |
| M1 | 企业内测版闭环 | 一条端到端流程可跑通：上传→分析→目录→章节→检查→导出 |
| M2 | 响应矩阵一等公民 | 所有生成/审查围绕条款、评分点、废标项展开 |
| M3 | 证据链与反幻觉 | 生成内容必须可追溯，禁止无证据企业能力表述 |
| M4 | 项目级 Agent Orchestrator | 支持“一键生成技术标初稿 / 一键修复风险” |
| M5 | 正式交付能力 | Word 模板套打、附件清单、质量报告、归档 |

---

# Milestone M0 — 工程稳定性修复

## Task 0.1: Fix frontend production build import ordering

**Objective:** 修复当前 `npm run build` 因 `import/first` 失败的问题，确保前端可生产构建。

**Files:**
- Modify: `frontend/src/services/api.ts`

**Problem:** 当前 `api.ts` 在 interface 定义后才出现多个 `import type`，触发 ESLint `import/first`。

**Step 1: Move all imports to the top**

将 `frontend/src/services/api.ts` 中第 59 行之后的这些 import：

```ts
import type {
  RatingChecklistResponse,
  ClauseResponseRequest,
  ClauseResponseResult,
  ChapterReverseEnhanceResponse,
} from '../types/bid';
import type {
  AdminUser,
  AdminUserListResponse,
  AdminUserCreate,
  AdminUserUpdate,
  ResetPasswordRequest,
  ApiKeyConfig,
  ApiKeyConfigListResponse,
  ApiKeyConfigCreate,
  ApiKeyConfigUpdate,
  OperationLogListResponse,
  OperationLogQuery,
  UsageStats,
} from '../types/admin';
import type {
  ReviewExecuteRequest,
  BidFileUploadResponse,
  ReviewResultResponse,
  ReviewHistoryResponse,
  ReviewExportRequest,
} from '../types/review';
import type {
  PromptResponse,
  PromptListResponse,
  PromptUpdate,
  PromptVersionListResponse,
  PromptRollbackRequest,
  ProjectPromptConfig,
  ProjectPromptConfigListResponse,
  ProjectPromptOverride,
} from '../types/prompt';
import type {
  RequestLog,
  RequestLogListResponse,
  RequestLogQuery,
  RequestStats,
} from '../types/requestLog';
import type {
  ChapterMaterialBinding,
  MaterialAsset,
  MaterialMatchCandidate,
  MaterialRequirement,
} from '../types/material';
```

移动到文件顶部所有 import 区域内，放在已有 import 之后、任何 interface/function 声明之前。

**Step 2: Run frontend build**

```bash
cd frontend
npm run build
```

Expected: build succeeds or only reveals next actionable compile issue.

**Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "fix: allow frontend production build"
```

---

## Task 0.2: Standardize backend test environment

**Objective:** 确保后端测试依赖可安装且 `pytest` 可执行。

**Files:**
- Modify if needed: `backend/requirements-test.txt`
- Modify if needed: `backend/requirements.txt`
- Create: `backend/pytest.ini` if missing

**Step 1: Inspect test dependency file**

```bash
cd backend
python3 -m pip install -r requirements-test.txt
```

Expected: test dependencies install successfully.

**Step 2: Add minimal pytest config if absent**

Create `backend/pytest.ini` if it does not exist:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -q --tb=short
```

**Step 3: Run backend tests**

```bash
cd backend
python3 -m pytest
```

Expected: tests run. Failures are allowed at this step if they are real application failures; dependency/import failure is not allowed.

**Step 4: Commit**

```bash
git add backend/requirements-test.txt backend/pytest.ini
git commit -m "test: standardize backend pytest setup"
```

---

## Task 0.3: Add Alembic migration baseline

**Objective:** 建立数据库 schema 迁移体系，避免生产部署依赖手工建表或历史环境。

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial_baseline.py`
- Modify: `backend/app/db/base.py` if metadata aggregation is incomplete

**Step 1: Initialize Alembic structure**

```bash
cd backend
alembic init alembic
```

If directory already exists, do not overwrite; inspect first.

**Step 2: Configure metadata in `backend/alembic/env.py`**

Ensure all models are imported before setting target metadata:

```python
from app.db.base import Base
from app.models import *  # noqa: F401,F403

target_metadata = Base.metadata
```

**Step 3: Configure DB URL from app settings**

In `env.py`, use:

```python
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))
```

For async migrations, either configure async Alembic properly or use sync URL for migrations.

**Step 4: Generate baseline migration**

```bash
cd backend
alembic revision --autogenerate -m "initial baseline"
```

Review generated migration carefully. It must include project, user, chapter, knowledge, material, review, disqualification, scoring, consistency, template, request log tables.

**Step 5: Run migration on clean dev DB**

```bash
cd backend
alembic upgrade head
```

Expected: tables are created without errors.

**Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/app/db/base.py
git commit -m "chore: add database migration baseline"
```

---

# Milestone M1 — 企业内测版端到端闭环

## Task 1.1: Add E2E smoke test for full bid workflow

**Objective:** 增加最小端到端测试，证明核心链路可跑通。

**Files:**
- Create: `backend/tests/test_e2e_bid_workflow.py`

**Test Scope:**

1. 创建测试用户或使用测试 fixture
2. 创建项目
3. 上传招标文件样本文本或 fixture docx/pdf
4. 调用分析接口
5. 调用目录生成接口
6. 调用章节生成接口
7. 调用废标检查/评分检查/一致性检查接口
8. 调用 Word 导出接口
9. 验证返回 `.docx` content-type 和非空字节流

**Step 1: Add fixture tender file**

Create: `backend/tests/fixtures/sample_tender.txt`

```text
项目名称：企业内部知识库建设项目
技术评分：
1. 总体方案完整性，20分。
2. 项目实施计划，20分。
3. 安全保障措施，20分。
废标条款：
1. 未提供营业执照复印件的，否决投标。
2. 投标文件未加盖公章的，否决投标。
```

**Step 2: Write API-level smoke test**

Use FastAPI `TestClient` or async client already used by existing tests. The test may mock LLM calls initially to keep deterministic.

**Step 3: Mock OpenAIService outputs**

Patch methods such as:

```python
OpenAIService.analyze_document
OpenAIService.generate_outline
OpenAIService.generate_chapter_content_collect
```

Return deterministic Chinese content.

**Step 4: Run test**

```bash
cd backend
python3 -m pytest tests/test_e2e_bid_workflow.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add backend/tests/test_e2e_bid_workflow.py backend/tests/fixtures/sample_tender.txt
git commit -m "test: add bid workflow smoke test"
```

---

## Task 1.2: Add export DOCX structural validation test

**Objective:** 验证 Word 导出结果不是空文件，并包含标题、正文、表格、页眉/页脚基础结构。

**Files:**
- Create: `backend/tests/test_word_export_service.py`

**Step 1: Write test**

```python
import pytest
from docx import Document
from io import BytesIO

from app.services.word_export_service import WordExportService


@pytest.mark.asyncio
async def test_export_to_docx_contains_core_sections():
    service = WordExportService()
    buffer = await service.export_to_docx(
        project_name="测试项目",
        project_overview="这是项目概述。",
        chapters=[
            {
                "title": "技术方案",
                "content": "## 系统架构\n\n本项目采用分层架构。\n\n| 模块 | 说明 |\n|---|---|\n| API | 接口服务 |",
            }
        ],
    )

    assert buffer.getbuffer().nbytes > 0
    doc = Document(BytesIO(buffer.getvalue()))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "测试项目" in text or "项目概述" in text
    assert "技术方案" in text
    assert doc.tables
```

**Step 2: Run test**

```bash
cd backend
python3 -m pytest tests/test_word_export_service.py -q
```

Expected: pass.

**Step 3: Commit**

```bash
git add backend/tests/test_word_export_service.py
git commit -m "test: validate word export structure"
```

---

# Milestone M2 — 响应矩阵成为一等公民

## Task 2.1: Add response matrix domain models

**Objective:** 新增中心化响应矩阵模型，让条款、评分点、废标项和章节覆盖关系可持久化、可查询、可审查。

**Files:**
- Create: `backend/app/models/response_matrix.py`
- Modify: `backend/app/models/__init__.py`
- Create migration: `backend/alembic/versions/xxxx_add_response_matrix.py`

**Models:**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ClauseType(str, enum.Enum):
    technical = "technical"
    commercial = "commercial"
    qualification = "qualification"
    disqualification = "disqualification"
    scoring = "scoring"
    format = "format"
    other = "other"


class ResponseStatus(str, enum.Enum):
    not_started = "not_started"
    covered = "covered"
    partial = "partial"
    missing = "missing"
    risk = "risk"
    not_applicable = "not_applicable"


class TenderClause(Base):
    __tablename__ = "tender_clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    clause_type: Mapped[ClauseType] = mapped_column(Enum(ClauseType), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_location: Mapped[str] = mapped_column(String(255), default="")
    raw_requirement: Mapped[str] = mapped_column(Text, default="")
    score_value: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    is_fatal: Mapped[bool] = mapped_column(default=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResponseMatrixItem(Base):
    __tablename__ = "response_matrix_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    clause_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tender_clauses.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    chapter_title: Mapped[str] = mapped_column(String(255), default="")
    response_status: Mapped[ResponseStatus] = mapped_column(Enum(ResponseStatus), default=ResponseStatus.not_started, index=True)
    response_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_summary: Mapped[str] = mapped_column(Text, default="")
    risk_note: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Step 1: Write model tests**

Create `backend/tests/test_response_matrix_models.py` validating enum values and model instantiation.

**Step 2: Create model file**

Add code above.

**Step 3: Register models**

Modify `backend/app/models/__init__.py`:

```python
from .response_matrix import TenderClause, ResponseMatrixItem, ClauseType, ResponseStatus
```

**Step 4: Create migration**

```bash
cd backend
alembic revision --autogenerate -m "add response matrix"
alembic upgrade head
```

**Step 5: Run tests**

```bash
cd backend
python3 -m pytest tests/test_response_matrix_models.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add backend/app/models/response_matrix.py backend/app/models/__init__.py backend/alembic/versions backend/tests/test_response_matrix_models.py
git commit -m "feat: add response matrix domain models"
```

---

## Task 2.2: Add response matrix schemas

**Objective:** 为响应矩阵 API 提供 Pydantic 请求/响应模型。

**Files:**
- Create: `backend/app/schemas/response_matrix.py`

**Schema:**

```python
from datetime import datetime
from pydantic import BaseModel, Field


class TenderClauseResponse(BaseModel):
    id: str
    project_id: str
    clause_type: str
    title: str
    content: str
    source_page: int | None = None
    source_location: str = ""
    score_value: float | None = None
    is_fatal: bool = False

    model_config = {"from_attributes": True}


class ResponseMatrixItemResponse(BaseModel):
    id: str
    project_id: str
    clause_id: str
    chapter_id: str
    chapter_title: str
    response_status: str
    response_summary: str
    evidence_summary: str
    risk_note: str
    confidence: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResponseMatrixSummary(BaseModel):
    total_clauses: int = 0
    covered: int = 0
    partial: int = 0
    missing: int = 0
    risk: int = 0
    fatal_missing: int = 0
    scoring_coverage_rate: float = 0
    overall_status: str = Field("not_ready", description="ready|not_ready|risk")
```

**Step 1: Create schema file**

Add above code.

**Step 2: Run type/import smoke test**

```bash
cd backend
python3 - <<'PY'
from app.schemas.response_matrix import ResponseMatrixSummary
print(ResponseMatrixSummary())
PY
```

Expected: object prints with defaults.

**Step 3: Commit**

```bash
git add backend/app/schemas/response_matrix.py
git commit -m "feat: add response matrix schemas"
```

---

## Task 2.3: Implement response matrix service

**Objective:** 新增服务层，负责从招标解析结果生成/更新响应矩阵，并计算覆盖率。

**Files:**
- Create: `backend/app/services/response_matrix_service.py`
- Test: `backend/tests/test_response_matrix_service.py`

**Core methods:**

```python
class ResponseMatrixService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_clauses_from_analysis(self, project_id: uuid.UUID, analysis: dict) -> list[TenderClause]:
        ...

    async def create_or_replace_matrix(self, project_id: uuid.UUID, clauses: list[dict]) -> list[TenderClause]:
        ...

    async def bind_clause_to_chapter(self, project_id: uuid.UUID, clause_id: uuid.UUID, chapter_id: str, chapter_title: str) -> ResponseMatrixItem:
        ...

    async def update_item_status(...):
        ...

    async def summarize(self, project_id: uuid.UUID) -> ResponseMatrixSummary:
        ...
```

**Step 1: Write tests for summary calculation**

Test that:

- 3 clauses total
- 1 covered, 1 partial, 1 missing
- 1 fatal missing
- overall_status becomes `risk`

**Step 2: Implement service minimally**

Use SQLAlchemy `select`, `delete`, `func.count` or simple queries.

**Step 3: Run tests**

```bash
cd backend
python3 -m pytest tests/test_response_matrix_service.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/app/services/response_matrix_service.py backend/tests/test_response_matrix_service.py
git commit -m "feat: add response matrix service"
```

---

## Task 2.4: Add response matrix API router

**Objective:** 提供前端查看、重建、刷新响应矩阵的 API。

**Files:**
- Create: `backend/app/routers/response_matrix.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_response_matrix_api.py`

**Endpoints:**

```text
GET  /api/response-matrix/{project_id}
POST /api/response-matrix/{project_id}/rebuild
POST /api/response-matrix/{project_id}/bind
PATCH /api/response-matrix/items/{item_id}
GET  /api/response-matrix/{project_id}/summary
```

**Step 1: Create router**

Use `require_editor` or project member verification pattern from `review.py`.

**Step 2: Register router**

Modify `backend/app/main.py`:

```python
from .routers import ..., response_matrix
...
app.include_router(response_matrix.router)
```

**Step 3: Write API tests**

Test unauthorized user cannot access another project. Test summary endpoint returns counts.

**Step 4: Run tests**

```bash
cd backend
python3 -m pytest tests/test_response_matrix_api.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add backend/app/routers/response_matrix.py backend/app/main.py backend/tests/test_response_matrix_api.py
git commit -m "feat: expose response matrix API"
```

---

# Milestone M3 — 证据链与反幻觉硬约束

## Task 3.1: Add evidence reference model

**Objective:** 所有生成内容、矩阵响应、素材引用都能追溯来源。

**Files:**
- Create: `backend/app/models/evidence.py`
- Modify: `backend/app/models/__init__.py`
- Create migration: `backend/alembic/versions/xxxx_add_evidence_refs.py`

**Model:**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class EvidenceSourceType(str, enum.Enum):
    tender_document = "tender_document"
    knowledge_doc = "knowledge_doc"
    material_asset = "material_asset"
    manual_input = "manual_input"
    generated_content = "generated_content"


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[EvidenceSourceType] = mapped_column(Enum(EvidenceSourceType), index=True)
    source_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    source_title: Mapped[str] = mapped_column(String(255), default="")
    source_location: Mapped[str] = mapped_column(String(255), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    relation: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Step 1: Add tests**

Create `backend/tests/test_evidence_model.py`.

**Step 2: Create model and migration**

```bash
cd backend
alembic revision --autogenerate -m "add evidence refs"
alembic upgrade head
```

**Step 3: Commit**

```bash
git add backend/app/models/evidence.py backend/app/models/__init__.py backend/alembic/versions backend/tests/test_evidence_model.py
git commit -m "feat: add evidence reference model"
```

---

## Task 3.2: Add anti-hallucination policy service

**Objective:** 在生成/精修/导出前拦截无证据的企业能力、资质、案例、人员、承诺类表述。

**Files:**
- Create: `backend/app/services/anti_hallucination_service.py`
- Test: `backend/tests/test_anti_hallucination_service.py`

**Rules:**

| Pattern Type | Examples | Required Evidence |
|---|---|---|
| 资质证书 | ISO9001、CMMI、等保、营业执照 | material_asset or knowledge_doc |
| 项目案例 | 成功实施、典型案例、服务过某客户 | material_asset or knowledge_doc |
| 人员能力 | 高级工程师、PMP、专家团队 | material_asset or manual_input |
| 确定承诺 | 保证、确保、完全满足、零风险 | tender clause + company evidence |
| 数字指标 | 99.99%、7x24、响应时间 | source evidence |

**Service skeleton:**

```python
import re
from dataclasses import dataclass


@dataclass
class HallucinationIssue:
    severity: str
    category: str
    text: str
    reason: str
    suggestion: str


class AntiHallucinationService:
    CERT_PATTERNS = [r"ISO\s?\d+", r"CMMI", r"等保", r"资质", r"证书"]
    CASE_PATTERNS = [r"成功实施", r"典型案例", r"服务过", r"类似项目"]
    COMMITMENT_PATTERNS = [r"保证", r"确保", r"完全满足", r"零风险"]

    def scan_text(self, text: str, evidence_refs: list[dict]) -> list[HallucinationIssue]:
        ...
```

**Step 1: Write tests**

Cases:

- Text says “我司具备 ISO9001 证书” with no evidence → critical issue
- Same text with evidence source title containing ISO9001 → no critical issue
- Text says “确保零风险” → warning/risk issue

**Step 2: Implement scanner**

Start deterministic/rule-based. Do not use LLM in this service.

**Step 3: Run tests**

```bash
cd backend
python3 -m pytest tests/test_anti_hallucination_service.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/app/services/anti_hallucination_service.py backend/tests/test_anti_hallucination_service.py
git commit -m "feat: add anti hallucination policy service"
```

---

## Task 3.3: Attach evidence refs to generated chapter content

**Objective:** 章节生成结果返回 `source_refs`，让前端和审查模块知道每段内容来源。

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/routers/content.py`
- Modify: `backend/app/services/openai_service.py`
- Test: `backend/tests/test_chapter_generation_evidence.py`

**Step 1: Add response schema**

In `schemas.py` add:

```python
class SourceRef(BaseModel):
    ref_id: str
    source_type: str
    source_id: Optional[str] = None
    location: str = ""
    quote: str = ""
    relation: str = ""


class ChapterGenerationResult(BaseModel):
    content: str
    source_refs: List[SourceRef] = Field(default_factory=list)
    hallucination_issues: List[Dict[str, Any]] = Field(default_factory=list)
```

**Step 2: Modify content generation flow**

In `content.py`, after retrieving knowledge/materials, construct source refs from:

- knowledge search results
- material suggestions
- tender clauses/redlines

Then pass refs into anti-hallucination scanner.

**Step 3: Preserve backward compatibility**

If current API returns plain content string, add a new endpoint first:

```text
POST /api/content/generate-chapter-v2
```

Do not break existing UI until frontend migration is complete.

**Step 4: Run tests**

```bash
cd backend
python3 -m pytest tests/test_chapter_generation_evidence.py -q
```

Expected: generated response includes source refs and hallucination issues.

**Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/routers/content.py backend/app/services/openai_service.py backend/tests/test_chapter_generation_evidence.py
git commit -m "feat: return evidence refs for generated chapters"
```

---

# Milestone M4 — 项目级 Agent Orchestrator

## Task 4.1: Add bid agent run models

**Objective:** 持久化项目级智能体运行记录，支持恢复、查看进度、失败重试。

**Files:**
- Create: `backend/app/models/bid_agent.py`
- Create migration: `backend/alembic/versions/xxxx_add_bid_agent_runs.py`

**Models:**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class BidAgentRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class BidAgentStepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class BidAgentRun(Base):
    __tablename__ = "bid_agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    goal: Mapped[str] = mapped_column(String(255), default="generate_technical_bid")
    status: Mapped[BidAgentRunStatus] = mapped_column(Enum(BidAgentRunStatus), default=BidAgentRunStatus.pending)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BidAgentStep(Base):
    __tablename__ = "bid_agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bid_agent_runs.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str] = mapped_column(String(100), index=True)
    step_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[BidAgentStepStatus] = mapped_column(Enum(BidAgentStepStatus), default=BidAgentStepStatus.pending)
    order_index: Mapped[int] = mapped_column(Integer)
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**Step 1: Add tests for model creation**

Create `backend/tests/test_bid_agent_models.py`.

**Step 2: Create migration and run it**

```bash
cd backend
alembic revision --autogenerate -m "add bid agent runs"
alembic upgrade head
```

**Step 3: Commit**

```bash
git add backend/app/models/bid_agent.py backend/alembic/versions backend/tests/test_bid_agent_models.py
git commit -m "feat: add bid agent run tracking models"
```

---

## Task 4.2: Implement BidAgentOrchestrator service

**Objective:** 新增项目级智能体编排服务，串联现有模块形成自动化流程。

**Files:**
- Create: `backend/app/services/bid_agent_orchestrator.py`
- Test: `backend/tests/test_bid_agent_orchestrator.py`

**Workflow:**

```text
1. validate_project_ready
2. analyze_tender
3. extract_response_matrix
4. generate_outline
5. bind_outline_to_matrix
6. generate_chapters
7. refine_chapters
8. run_quality_checks
9. repair_failed_items
10. prepare_export_package
```

**Service skeleton:**

```python
class BidAgentOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, run_id: uuid.UUID) -> AsyncGenerator[dict, None]:
        ...

    async def _execute_step(self, run, step, handler):
        ...

    async def _validate_project_ready(self, run):
        ...

    async def _analyze_tender(self, run):
        ...

    async def _extract_response_matrix(self, run):
        ...

    async def _generate_outline(self, run):
        ...

    async def _generate_chapters(self, run):
        ...

    async def _run_quality_checks(self, run):
        ...
```

**Step 1: Write test with mocked step handlers**

Test that a run:

- starts as pending
- emits step events in order
- ends completed
- progress becomes 100

**Step 2: Implement orchestration state transitions**

Use DB transactions carefully. Each step should persist status before and after execution.

**Step 3: Run tests**

```bash
cd backend
python3 -m pytest tests/test_bid_agent_orchestrator.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/app/services/bid_agent_orchestrator.py backend/tests/test_bid_agent_orchestrator.py
git commit -m "feat: add bid agent orchestrator"
```

---

## Task 4.3: Add bid agent API router

**Objective:** 前端可以启动、查看、取消项目级智能体任务。

**Files:**
- Create: `backend/app/routers/bid_agent.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_bid_agent_api.py`

**Endpoints:**

```text
POST /api/bid-agent/runs
GET  /api/bid-agent/runs/{run_id}
GET  /api/bid-agent/projects/{project_id}/runs
POST /api/bid-agent/runs/{run_id}/stream
POST /api/bid-agent/runs/{run_id}/cancel
```

**Step 1: Create request schemas**

```python
class CreateBidAgentRunRequest(BaseModel):
    project_id: str
    goal: str = "generate_technical_bid"
    options: dict = Field(default_factory=dict)
```

**Step 2: Implement create endpoint**

Creates `BidAgentRun` and default `BidAgentStep` rows.

**Step 3: Implement stream endpoint**

Use existing `sse_response` pattern from `refine.py`.

**Step 4: Register router**

Modify `main.py`:

```python
from .routers import ..., bid_agent
app.include_router(bid_agent.router)
```

**Step 5: Run tests**

```bash
cd backend
python3 -m pytest tests/test_bid_agent_api.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add backend/app/routers/bid_agent.py backend/app/main.py backend/tests/test_bid_agent_api.py
git commit -m "feat: expose bid agent run API"
```

---

## Task 4.4: Add frontend Bid Agent control panel

**Objective:** 在项目工作台提供“一键生成技术标初稿”入口，并显示步骤进度。

**Files:**
- Create: `frontend/src/components/BidAgentPanel.tsx`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/ProjectWorkspace.tsx`
- Test if feasible: `frontend/src/components/BidAgentPanel.test.tsx`

**UI Requirements:**

- Button: `一键生成技术标初稿`
- Progress list:
  - 招标文件分析
  - 响应矩阵抽取
  - 目录生成
  - 章节生成
  - 多轮精修
  - 质量检查
  - 导出准备
- Show final summary:
  - 生成章节数
  - 废标风险数
  - 未覆盖评分点数
  - 可导出状态

**Step 1: Add API methods**

In `frontend/src/services/api.ts`:

```ts
export interface BidAgentRun {
  id: string;
  project_id: string;
  goal: string;
  status: string;
  progress: number;
  summary: string;
  result_json?: Record<string, any>;
}

export async function createBidAgentRun(projectId: string): Promise<BidAgentRun> {
  const res = await api.post('/api/bid-agent/runs', { project_id: projectId });
  return res.data;
}
```

**Step 2: Create component**

Use EventSource/fetch streaming depending on existing SSE client pattern.

**Step 3: Add to project workspace**

Place panel near top of `ProjectWorkspace.tsx`.

**Step 4: Build frontend**

```bash
cd frontend
npm run build
```

Expected: pass.

**Step 5: Commit**

```bash
git add frontend/src/components/BidAgentPanel.tsx frontend/src/services/api.ts frontend/src/pages/ProjectWorkspace.tsx
git commit -m "feat: add bid agent control panel"
```

---

# Milestone M5 — 质量门禁与正式交付

## Task 5.1: Add quality gate service

**Objective:** 在导出/标记完成前强制检查废标、评分点覆盖、证据链和一致性。

**Files:**
- Create: `backend/app/services/quality_gate_service.py`
- Test: `backend/tests/test_quality_gate_service.py`

**Gate rules:**

```text
GATE_FATAL_DISQUALIFICATION: fatal 废标项必须全部 passed
GATE_SCORING_COVERAGE: scoring 覆盖率 >= 95%
GATE_CRITICAL_ISSUES: critical issue = 0
GATE_EVIDENCE_REQUIRED: 企业能力/资质/案例断言必须有 evidence refs
GATE_CONSISTENCY: major contradiction = 0
```

**Result shape:**

```python
@dataclass
class QualityGateResult:
    passed: bool
    blocking_issues: list[dict]
    warnings: list[dict]
    summary: str
```

**Step 1: Write tests**

Test that fatal missing blocks export.

**Step 2: Implement service**

Query existing disqualification/scoring/consistency/response_matrix/evidence models.

**Step 3: Run tests**

```bash
cd backend
python3 -m pytest tests/test_quality_gate_service.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add backend/app/services/quality_gate_service.py backend/tests/test_quality_gate_service.py
git commit -m "feat: add bid quality gate service"
```

---

## Task 5.2: Enforce quality gate before enhanced Word export

**Objective:** 导出正式标书前检查质量门禁，阻塞明显风险文件。

**Files:**
- Modify: `backend/app/routers/export.py`
- Test: `backend/tests/test_export_quality_gate.py`

**Step 1: Extend export request**

```python
class WordExportRequest(BaseModel):
    project_id: Optional[str] = Field(None, description="项目ID，用于质量门禁")
    project_name: str
    project_overview: str = ""
    chapters: List[ExportChapterItem]
    template_id: Optional[str] = None
    enforce_quality_gate: bool = Field(False, description="是否启用正式导出质量门禁")
```

**Step 2: Add gate check**

Before exporting:

```python
if request.enforce_quality_gate and request.project_id:
    gate = await QualityGateService(db).evaluate(uuid.UUID(request.project_id))
    if not gate.passed:
        raise HTTPException(status_code=409, detail={
            "message": "质量门禁未通过，禁止正式导出",
            "blocking_issues": gate.blocking_issues,
            "warnings": gate.warnings,
        })
```

**Step 3: Test blocked export**

Quality gate mock returns `passed=False`; endpoint returns 409.

**Step 4: Commit**

```bash
git add backend/app/routers/export.py backend/tests/test_export_quality_gate.py
git commit -m "feat: enforce quality gate before formal export"
```

---

## Task 5.3: Add export package manifest

**Objective:** 正式导出时生成标书包清单：正文、附件、证据、风险、审查报告。

**Files:**
- Create: `backend/app/services/export_package_service.py`
- Modify: `backend/app/routers/export.py`
- Test: `backend/tests/test_export_package_service.py`

**Manifest shape:**

```json
{
  "project_id": "...",
  "project_name": "...",
  "generated_at": "...",
  "files": [
    {"type": "technical_bid", "filename": "技术标.docx"},
    {"type": "quality_report", "filename": "质量检查报告.json"},
    {"type": "evidence_manifest", "filename": "证据链清单.json"}
  ],
  "quality_gate": {
    "passed": true,
    "blocking_issues": [],
    "warnings": []
  }
}
```

**Step 1: Implement manifest builder**

Do not implement zip packaging yet unless required. First return manifest JSON.

**Step 2: Add endpoint**

```text
POST /api/export/package-manifest
```

**Step 3: Test manifest output**

```bash
cd backend
python3 -m pytest tests/test_export_package_service.py -q
```

**Step 4: Commit**

```bash
git add backend/app/services/export_package_service.py backend/app/routers/export.py backend/tests/test_export_package_service.py
git commit -m "feat: add export package manifest"
```

---

## Task 5.4: Improve Word template support

**Objective:** 从“通用 GB/T 风格”升级为“企业模板套打”的基础能力。

**Files:**
- Modify: `backend/app/services/word_export_service.py`
- Modify: `backend/app/models/export_template.py`
- Modify: `backend/app/routers/export_template.py`
- Test: `backend/tests/test_word_template_export.py`

**Requirements:**

- 支持上传 `.docx` 模板文件
- 支持模板占位符：
  - `{{project_name}}`
  - `{{project_overview}}`
  - `{{technical_content}}`
  - `{{generated_at}}`
- 如果模板缺失占位符，回退当前标准导出

**Step 1: Add template file path field if missing**

In `ExportTemplate` model add:

```python
template_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Create migration.

**Step 2: Add placeholder replacement utility**

In `word_export_service.py`:

```python
def _replace_docx_placeholders(doc: Document, replacements: dict[str, str]) -> None:
    for para in doc.paragraphs:
        for key, value in replacements.items():
            if key in para.text:
                para.text = para.text.replace(key, value)
```

Start simple. Later improve run-level replacement to preserve styles.

**Step 3: Add tests**

Create minimal docx template in test using python-docx, export with replacements, assert placeholders replaced.

**Step 4: Commit**

```bash
git add backend/app/services/word_export_service.py backend/app/models/export_template.py backend/app/routers/export_template.py backend/alembic/versions backend/tests/test_word_template_export.py
git commit -m "feat: support docx export templates"
```

---

# Milestone M6 — Frontend Productization

## Task 6.1: Add Response Matrix page

**Objective:** 让用户可视化查看条款、评分点、章节响应和风险状态。

**Files:**
- Create: `frontend/src/pages/ResponseMatrix.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/services/api.ts`
- Modify if needed: `frontend/src/layouts/AppShell.tsx`

**UI:**

Columns:

```text
条款类型 | 原文摘要 | 分值 | 响应章节 | 状态 | 证据 | 风险
```

Filters:

```text
全部 / 废标 / 评分 / 技术 / 商务 / 未覆盖 / 风险
```

Actions:

```text
绑定章节
查看证据
生成补写建议
```

**Step 1: Add API methods**

```ts
export async function getResponseMatrix(projectId: string) { ... }
export async function getResponseMatrixSummary(projectId: string) { ... }
```

**Step 2: Create page**

Use Ant Design `Table`, `Tag`, `Progress`, `Drawer`.

**Step 3: Add route**

```tsx
<Route path="/project/:projectId/response-matrix" element={<ResponseMatrix />} />
```

**Step 4: Build**

```bash
cd frontend
npm run build
```

Expected: pass.

**Step 5: Commit**

```bash
git add frontend/src/pages/ResponseMatrix.tsx frontend/src/App.tsx frontend/src/services/api.ts frontend/src/layouts/AppShell.tsx
git commit -m "feat: add response matrix page"
```

---

## Task 6.2: Add Quality Gate panel

**Objective:** 在内容编辑/导出前显示是否可以正式提交。

**Files:**
- Create: `frontend/src/components/QualityGatePanel.tsx`
- Modify: `frontend/src/pages/ContentEdit.tsx`
- Modify: `frontend/src/components/ExportDialog.tsx`
- Modify: `frontend/src/services/api.ts`

**UI states:**

- ✅ 可以正式导出
- ⚠️ 有警告，可继续但建议处理
- ❌ 有阻塞问题，禁止正式导出

**Step 1: Add API method**

```ts
export async function evaluateQualityGate(projectId: string) { ... }
```

**Step 2: Add component**

Display blocking issues and warnings.

**Step 3: Integrate export dialog**

If gate failed, disable “正式导出” button and allow “导出草稿”。

**Step 4: Build**

```bash
cd frontend
npm run build
```

Expected: pass.

**Step 5: Commit**

```bash
git add frontend/src/components/QualityGatePanel.tsx frontend/src/pages/ContentEdit.tsx frontend/src/components/ExportDialog.tsx frontend/src/services/api.ts
git commit -m "feat: show quality gate before export"
```

---

# Milestone M7 — Operational Hardening

## Task 7.1: Add long-running task timeout and retry policy

**Objective:** 避免 Agent 运行无限卡死；支持失败重试。

**Files:**
- Modify: `backend/app/services/bid_agent_orchestrator.py`
- Modify: `backend/app/models/bid_agent.py`
- Test: `backend/tests/test_bid_agent_retry.py`

**Rules:**

```text
每个 step 默认 timeout 10 分钟
LLM 生成 step 最多重试 2 次
导出 step 不重试，失败直接暴露错误
取消任务应在 step 边界生效
```

**Step 1: Add retry_count field to BidAgentStep**

```python
retry_count: Mapped[int] = mapped_column(Integer, default=0)
max_retries: Mapped[int] = mapped_column(Integer, default=2)
```

Create migration.

**Step 2: Wrap step execution with timeout**

```python
await asyncio.wait_for(handler(run), timeout=step_timeout_seconds)
```

**Step 3: Add tests**

Mock handler raises twice then succeeds.

**Step 4: Commit**

```bash
git add backend/app/services/bid_agent_orchestrator.py backend/app/models/bid_agent.py backend/alembic/versions backend/tests/test_bid_agent_retry.py
git commit -m "feat: add bid agent retry and timeout policy"
```

---

## Task 7.2: Add LLM usage accounting

**Objective:** 记录每次 AI 调用成本、模型、token、项目归属，方便企业控费。

**Files:**
- Create: `backend/app/models/llm_usage.py`
- Modify: `backend/app/services/openai_service.py`
- Create migration
- Test: `backend/tests/test_llm_usage_logging.py`

**Fields:**

```python
project_id
user_id
provider_config_id
model_name
operation_type
prompt_tokens
completion_tokens
total_tokens
estimated_cost
latency_ms
success
error_message
created_at
```

**Step 1: Add model and migration**

**Step 2: Wrap OpenAI calls**

Centralize usage logging in one helper inside `OpenAIService`.

**Step 3: Add tests with mocked response usage**

**Step 4: Commit**

```bash
git add backend/app/models/llm_usage.py backend/app/services/openai_service.py backend/alembic/versions backend/tests/test_llm_usage_logging.py
git commit -m "feat: log llm usage and cost metadata"
```

---

# Definition of Done

The upgraded system is considered “enterprise internal pilot ready” when all conditions below are true:

## Engineering DoD

- `cd frontend && npm run build` passes
- `cd backend && python3 -m pytest` runs and core tests pass
- Alembic migrations exist and can initialize a clean DB
- E2E smoke test passes
- New services have unit tests

## Product DoD

- User can start a project-level Bid Agent run
- Agent can complete: analyze tender → extract response matrix → generate outline → generate chapters → run checks → prepare export
- Response matrix page shows coverage status
- Quality gate blocks formal export when fatal issues exist
- Draft export remains available
- Word export contains project name, overview, chapters, tables, and basic formatting

## Risk/Compliance DoD

- Fatal disqualification items are explicitly tracked
- Scoring points have coverage status
- Generated content has evidence refs where possible
- Anti-hallucination scanner flags unsupported capability/certification/case claims
- Final export manifest includes quality gate result and evidence summary

---

# Recommended Execution Order

1. M0 first. Do not add major features until build/test/migration foundation works.
2. M1 next. Establish one deterministic E2E smoke test before refactoring business logic.
3. M2 before M4. Agent orchestration should operate on response matrix, not raw strings.
4. M3 before formal export. Do not allow final export without evidence/anti-hallucination checks.
5. M4 then frontend panel. Backend orchestration must be stable before polishing UI.
6. M5/M6 last. Quality gate and UI should consume stable backend APIs.

---

# Suggested Branching Strategy

```bash
git checkout -b feat/enterprise-bid-agent
```

Commit after every task. Run pre-commit verification after each milestone:

```bash
cd backend && python3 -m pytest
cd ../frontend && npm run build
```

Before merging, run the requesting-code-review skill and require independent review approval.

---

# Non-Goals for This Plan

To keep scope controlled, this plan does **not** include:

- Full PDF conversion pipeline hardening
- OCR quality improvement for scanned tender files
- Real-time multi-user collaborative editing with CRDT
- External procurement platform integration
- Automatic bid price generation
- Legal approval workflow
- Enterprise SSO/SAML/OIDC integration

These can be planned after the internal pilot version is stable.
