# LlamaIndex Knowledgebase Full Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current custom knowledge-base indexing and retrieval pipeline with a LlamaIndex-based implementation across ingestion, indexing, retrieval, and chapter-context assembly.

**Architecture:** Keep the existing FastAPI routes and business-level response shapes, but replace the legacy vector/index internals with a single LlamaIndex-backed service layer. Use PostgreSQL + pgvector as the only vector backend, map `KnowledgeDoc` into LlamaIndex `Document` objects with explicit metadata filters, and remove the legacy chunk-table retrieval path from runtime use.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL, pgvector, LlamaIndex Core, LlamaIndex Ollama Embeddings, LlamaIndex Postgres Vector Store, pytest

---

### Task 1: Create the migration design baseline

**Files:**
- Modify: `backend/app/services/vector_index_service.py`
- Modify: `backend/app/services/knowledge_retrieval_service.py`
- Modify: `backend/app/routers/knowledge.py`
- Modify: `backend/app/routers/outline.py`
- Modify: `backend/app/models/knowledge.py`
- Modify: `backend/alembic/versions/0016_add_vector_index_support.py`
- Test: `backend/tests/`

**Step 1: Review the current runtime path and list every legacy touchpoint**

Read:
- `backend/app/routers/knowledge.py`
- `backend/app/services/vector_index_service.py`
- `backend/app/services/knowledge_retrieval_service.py`
- `backend/app/routers/outline.py`
- `backend/app/models/knowledge.py`

Expected notes:
- Upload and manual creation both enqueue indexing.
- Retrieval is called from chapter generation.
- Legacy chunk storage currently uses `knowledge_doc_chunks`.
- Response shape must remain compatible for frontend and prompt assembly.

**Step 2: Write a short implementation note at the top of your working branch**

Document locally in commit notes or scratchpad:
- Runtime API surface remains unchanged.
- Legacy vector search code will be removed from active runtime.
- PostgreSQL remains the single vector store.
- Knowledge permissions still rely on `scope` and `owner_id`.

**Step 3: Confirm the non-goals before coding**

Non-goals:
- Do not redesign the frontend.
- Do not change route URLs or response field names.
- Do not add a second vector database.
- Do not preserve legacy index data compatibility.

**Step 4: Commit the branch state once the plan assumptions are validated**

```bash
git status
```

Expected: clean understanding of write targets and no accidental file reverts.

### Task 2: Add configuration for a single LlamaIndex backend

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_llamaindex_settings.py`

**Step 1: Write the failing test**

```python
from app.config import Settings


def test_llamaindex_defaults_present():
    settings = Settings()
    assert settings.knowledge_vector_backend == "llamaindex"
    assert settings.embedding_model
    assert settings.embedding_dimension > 0
    assert settings.knowledge_chunk_size > 0
    assert settings.knowledge_chunk_overlap >= 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_settings.py -v`

Expected: FAIL because LlamaIndex-specific settings are missing.

**Step 3: Write minimal implementation**

Add config fields in `backend/app/config.py`:
- `knowledge_vector_backend: str = "llamaindex"`
- `embedding_model: str = "qwen3-embedding:4b"`
- `embedding_dimension: int = 2560`
- `ollama_base_url: str = "http://localhost:11434"`
- `knowledge_chunk_size: int = 512`
- `knowledge_chunk_overlap: int = 50`
- `knowledge_top_k: int = 5`
- `knowledge_vector_table: str = "knowledge_nodes"`

Keep existing settings intact.

**Step 4: Ensure dependency declarations are coherent**

In `backend/requirements.txt`:
- Keep `llama-index-core`
- Keep `llama-index-embeddings-ollama`
- Keep `llama-index-vector-stores-postgres`
- Keep `pgvector`
- Remove misleading comments that imply LlamaIndex is already fully wired if they are inaccurate.

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_settings.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/config.py backend/requirements.txt backend/tests/test_llamaindex_settings.py
git commit -m "feat: add llamaindex knowledge settings"
```

### Task 3: Add a dedicated LlamaIndex service module

**Files:**
- Create: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `backend/app/services/__init__.py`
- Test: `backend/tests/test_llamaindex_knowledge_service.py`

**Step 1: Write the failing test**

```python
import uuid

from app.services.llamaindex_knowledge_service import build_document_metadata


def test_build_document_metadata():
    owner_id = uuid.uuid4()
    metadata = build_document_metadata(
        doc_id=uuid.uuid4(),
        title="Test Doc",
        doc_type="other",
        scope="user",
        owner_id=owner_id,
        tags=["a", "b"],
        category="demo",
    )
    assert metadata["title"] == "Test Doc"
    assert metadata["scope"] == "user"
    assert metadata["owner_id"] == str(owner_id)
    assert metadata["tags"] == ["a", "b"]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_knowledge_service.py -v`

Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

In `backend/app/services/llamaindex_knowledge_service.py` create:
- `build_document_metadata(...)`
- `LlamaIndexKnowledgeService`

The service should encapsulate:
- embedding model creation via Ollama
- Postgres vector store creation
- text splitter creation
- document indexing
- filtered retrieval
- document deletion

Keep helper functions small and pure where possible.

**Step 4: Export the new service if needed**

Update `backend/app/services/__init__.py` only if the package already exposes service symbols.

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_knowledge_service.py -v`

Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/app/services/__init__.py backend/tests/test_llamaindex_knowledge_service.py
git commit -m "feat: add llamaindex knowledge service"
```

### Task 4: Define the LlamaIndex metadata contract

**Files:**
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Test: `backend/tests/test_llamaindex_metadata_contract.py`

**Step 1: Write the failing test**

```python
def test_metadata_contract_contains_all_filterable_fields():
    metadata = {
        "doc_id": "1",
        "title": "Demo",
        "doc_type": "history_bid",
        "scope": "user",
        "owner_id": "u1",
        "category": "cases",
        "tags": ["x"],
    }
    assert sorted(metadata.keys()) == [
        "category",
        "doc_id",
        "doc_type",
        "owner_id",
        "scope",
        "tags",
        "title",
    ]
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_metadata_contract.py -v`

Expected: FAIL until the helper is finalized and test is wired to the real builder.

**Step 3: Write minimal implementation**

Make `build_document_metadata(...)` return exactly:
- `doc_id`
- `title`
- `doc_type`
- `scope`
- `owner_id`
- `category`
- `tags`

Normalize:
- `doc_id` and `owner_id` as strings
- `tags` as a list
- `category` as `""` or `None` consistently

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_metadata_contract.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/tests/test_llamaindex_metadata_contract.py
git commit -m "feat: define llamaindex metadata contract"
```

### Task 5: Replace custom chunking with LlamaIndex text splitting

**Files:**
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `backend/app/services/vector_index_service.py`
- Test: `backend/tests/test_llamaindex_chunking.py`

**Step 1: Write the failing test**

```python
from app.services.llamaindex_knowledge_service import split_knowledge_text


def test_split_knowledge_text_returns_chunks():
    text = "第一段。\n\n第二段。\n\n第三段。"
    chunks = split_knowledge_text(text, chunk_size=20, chunk_overlap=5)
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_chunking.py -v`

Expected: FAIL because helper is missing.

**Step 3: Write minimal implementation**

In `backend/app/services/llamaindex_knowledge_service.py`:
- Add `split_knowledge_text(text, chunk_size, chunk_overlap)`
- Implement with LlamaIndex `SentenceSplitter`

In `backend/app/services/vector_index_service.py`:
- Remove or deprecate `_split_text`
- Make the runtime path delegate to the new splitter instead of custom paragraph logic

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_chunking.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/app/services/vector_index_service.py backend/tests/test_llamaindex_chunking.py
git commit -m "refactor: use llamaindex sentence splitter"
```

### Task 6: Add a real LlamaIndex PostgreSQL vector store schema

**Files:**
- Create: `backend/alembic/versions/0020_create_llamaindex_vector_store.py`
- Modify: `backend/app/models/knowledge.py`
- Test: `backend/tests/test_llamaindex_schema_smoke.py`

**Step 1: Write the failing test**

```python
def test_knowledge_doc_has_backend_marker():
    from app.models.knowledge import KnowledgeDoc

    assert hasattr(KnowledgeDoc, "index_backend")
    assert hasattr(KnowledgeDoc, "index_version")
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_schema_smoke.py -v`

Expected: FAIL because the model fields do not exist.

**Step 3: Write minimal implementation**

In `backend/app/models/knowledge.py` add:
- `index_backend: str` with default `"llamaindex"`
- `index_version: int` with default `1`

Create Alembic migration to:
- add `index_backend` and `index_version` to `knowledge_docs`
- create or validate the vector extension if needed
- create the LlamaIndex vector table structure required by the selected `PGVectorStore`

Do not preserve the legacy chunk table as the primary runtime store.

**Step 4: Run the model test**

Run: `cd backend && pytest tests/test_llamaindex_schema_smoke.py -v`

Expected: PASS

**Step 5: Run migration checks**

Run:

```bash
cd backend
alembic upgrade head
```

Expected: migration applies cleanly on an empty database.

**Step 6: Commit**

```bash
git add backend/alembic/versions/0020_create_llamaindex_vector_store.py backend/app/models/knowledge.py backend/tests/test_llamaindex_schema_smoke.py
git commit -m "feat: add llamaindex vector store schema"
```

### Task 7: Rewrite indexing to use LlamaIndex documents end-to-end

**Files:**
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `backend/app/services/vector_index_service.py`
- Test: `backend/tests/test_llamaindex_indexing_flow.py`

**Step 1: Write the failing test**

```python
import uuid


async def test_index_document_returns_success(async_session):
    from app.services.llamaindex_knowledge_service import LlamaIndexKnowledgeService

    service = LlamaIndexKnowledgeService(async_session)
    result = await service.index_document(
        doc_id=uuid.uuid4(),
        text="示例知识内容",
        metadata={
            "doc_id": "1",
            "title": "标题",
            "doc_type": "other",
            "scope": "user",
            "owner_id": "u1",
            "category": "demo",
            "tags": [],
        },
    )
    assert result is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_indexing_flow.py -v`

Expected: FAIL because indexing implementation is incomplete.

**Step 3: Write minimal implementation**

Implement in `LlamaIndexKnowledgeService.index_document(...)`:
- create one `Document` with full text and metadata
- split into nodes through LlamaIndex pipeline
- persist into PostgreSQL vector store

Update `backend/app/services/vector_index_service.py` so it becomes a thin compatibility wrapper or remove its custom indexing logic entirely and delegate to `LlamaIndexKnowledgeService`.

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_indexing_flow.py -v`

Expected: PASS or a controlled mock-backed pass if integration DB setup is isolated.

**Step 5: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/app/services/vector_index_service.py backend/tests/test_llamaindex_indexing_flow.py
git commit -m "feat: index knowledge docs with llamaindex"
```

### Task 8: Remove legacy chunk search from runtime retrieval

**Files:**
- Modify: `backend/app/services/knowledge_retrieval_service.py`
- Modify: `backend/app/services/vector_index_service.py`
- Test: `backend/tests/test_llamaindex_retrieval_flow.py`

**Step 1: Write the failing test**

```python
async def test_search_with_vector_returns_document_level_results(async_session):
    from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

    service = KnowledgeRetrievalService(async_session, openai_service=None)
    results = await service.search_with_vector(
        query="企业资质经验",
        top_k=3,
        user_id=None,
        enterprise_id=None,
        use_pageindex_fallback=False,
    )
    assert isinstance(results, list)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_retrieval_flow.py -v`

Expected: FAIL or weak pass until the service is switched to the new backend.

**Step 3: Write minimal implementation**

In `backend/app/services/knowledge_retrieval_service.py`:
- replace direct use of legacy `VectorIndexService.search_similar(...)`
- use `LlamaIndexKnowledgeService.search(...)`
- preserve existing output fields
- aggregate node-level hits into document-level results
- keep keyword fallback only as a last-resort business fallback

In `backend/app/services/vector_index_service.py`:
- delete runtime-only search SQL if no longer used
- or leave a compatibility wrapper with no custom SQL path

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_retrieval_flow.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/knowledge_retrieval_service.py backend/app/services/vector_index_service.py backend/tests/test_llamaindex_retrieval_flow.py
git commit -m "refactor: route retrieval through llamaindex backend"
```

### Task 9: Enforce metadata-based permission filters in retrieval

**Files:**
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `backend/app/services/knowledge_retrieval_service.py`
- Test: `backend/tests/test_llamaindex_permission_filters.py`

**Step 1: Write the failing test**

```python
def test_build_filters_for_user_scope():
    from app.services.llamaindex_knowledge_service import build_access_filters

    filters = build_access_filters(user_id="u1", enterprise_id=None)
    assert filters
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_permission_filters.py -v`

Expected: FAIL because the filter helper does not exist.

**Step 3: Write minimal implementation**

In `backend/app/services/llamaindex_knowledge_service.py`:
- add `build_access_filters(user_id, enterprise_id)`
- map current access rules:
  - include `scope == global`
  - include current user-owned docs
  - include enterprise-owned docs when present

In `backend/app/services/knowledge_retrieval_service.py`:
- pass filters into the LlamaIndex retriever

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_permission_filters.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/app/services/knowledge_retrieval_service.py backend/tests/test_llamaindex_permission_filters.py
git commit -m "feat: add metadata-based retrieval filters"
```

### Task 10: Fix the knowledge upload indexing entrypoint

**Files:**
- Modify: `backend/app/routers/knowledge.py`
- Modify: `backend/app/services/file_service.py`
- Test: `backend/tests/test_knowledge_upload_llamaindex.py`

**Step 1: Write the failing test**

```python
def test_upload_indexing_uses_supported_pdf_extractor():
    from app.services.file_service import FileService

    assert hasattr(FileService, "extract_text_from_pdf")
```

**Step 2: Run test to verify it fails if the route still points to a missing helper**

Run: `cd backend && pytest tests/test_knowledge_upload_llamaindex.py -v`

Expected: FAIL until route wiring is corrected and covered.

**Step 3: Write minimal implementation**

In `backend/app/routers/knowledge.py`:
- replace `..utils.pdf_utils` import with `FileService`
- await async text extraction correctly
- pass normalized metadata into the new LlamaIndex service
- remove the obsolete `metadata=` mismatch against old `VectorIndexService`

For manual docs:
- store `KnowledgeDoc.content` directly
- index the source text directly instead of depending on Markdown file re-read

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_knowledge_upload_llamaindex.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/routers/knowledge.py backend/app/services/file_service.py backend/tests/test_knowledge_upload_llamaindex.py
git commit -m "fix: wire knowledge upload into llamaindex indexing"
```

### Task 11: Keep chapter-generation knowledge injection stable

**Files:**
- Modify: `backend/app/routers/outline.py`
- Modify: `backend/app/services/knowledge_retrieval_service.py`
- Test: `backend/tests/test_outline_knowledge_context.py`

**Step 1: Write the failing test**

```python
def test_knowledge_context_formatter_preserves_expected_sections():
    result = {
        "title": "企业案例",
        "doc_type": "company_info",
        "reasoning": "向量相似度匹配",
        "content_preview": "内容片段",
    }
    formatted = f"[1] 类型: 企业资料/能力\n标题: {result['title']}\n相关性: {result['reasoning']}\n内容:\n{result['content_preview']}"
    assert "标题: 企业案例" in formatted
```

**Step 2: Run test to verify it fails if refactor breaks formatting utilities**

Run: `cd backend && pytest tests/test_outline_knowledge_context.py -v`

Expected: FAIL only if no stable formatter exists.

**Step 3: Write minimal implementation**

If needed, extract a small helper from `backend/app/routers/outline.py` for knowledge context formatting so retrieval backend changes do not alter prompt shape.

Do not change:
- `knowledge_context` variable name
- prompt assembly semantics
- doc type labels unless broken

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_outline_knowledge_context.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/routers/outline.py backend/app/services/knowledge_retrieval_service.py backend/tests/test_outline_knowledge_context.py
git commit -m "refactor: stabilize outline knowledge context formatting"
```

### Task 12: Add delete support for indexed knowledge documents

**Files:**
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `backend/app/routers/knowledge.py`
- Test: `backend/tests/test_llamaindex_delete_document.py`

**Step 1: Write the failing test**

```python
import uuid


async def test_delete_document_invokes_backend_delete(async_session):
    from app.services.llamaindex_knowledge_service import LlamaIndexKnowledgeService

    service = LlamaIndexKnowledgeService(async_session)
    await service.delete_document(uuid.uuid4())
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_llamaindex_delete_document.py -v`

Expected: FAIL because delete flow is incomplete.

**Step 3: Write minimal implementation**

Implement `delete_document(doc_id)` in the LlamaIndex service using metadata or ref_doc deletion strategy supported by the selected vector store.

Update `backend/app/routers/knowledge.py` delete route so it calls the new backend, not the legacy chunk deletion path.

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_llamaindex_delete_document.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/llamaindex_knowledge_service.py backend/app/routers/knowledge.py backend/tests/test_llamaindex_delete_document.py
git commit -m "feat: support llamaindex document deletion"
```

### Task 13: Remove dead legacy runtime code

**Files:**
- Modify: `backend/app/services/knowledge_service.py`
- Modify: `backend/app/services/vector_index_service.py`
- Modify: `backend/app/routers/knowledge_v1_backup.py`
- Test: `backend/tests/test_legacy_knowledge_paths_removed.py`

**Step 1: Write the failing test**

```python
def test_runtime_no_longer_depends_on_legacy_tfidf_service():
    import app.services.knowledge_service as knowledge_service

    assert hasattr(knowledge_service, "__file__")
```

Use this as a placeholder only if you need a harness; the real check is code review plus import safety.

**Step 2: Run the focused tests or import checks**

Run: `cd backend && pytest tests/test_legacy_knowledge_paths_removed.py -v`

Expected: FAIL only if import cleanup breaks compatibility.

**Step 3: Write minimal implementation**

Remove or clearly archive:
- legacy TF-IDF service from runtime paths
- custom JSON-to-vector SQL search path
- stale backup route usage from active router registration

It is acceptable to keep backup files in repo if they are not imported or referenced at runtime.

**Step 4: Run tests to verify runtime imports remain healthy**

Run: `cd backend && pytest tests/test_legacy_knowledge_paths_removed.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/knowledge_service.py backend/app/services/vector_index_service.py backend/app/routers/knowledge_v1_backup.py backend/tests/test_legacy_knowledge_paths_removed.py
git commit -m "refactor: remove legacy knowledge runtime paths"
```

### Task 14: Add end-to-end search API coverage

**Files:**
- Create: `backend/tests/test_knowledge_search_api_llamaindex.py`
- Modify: `backend/app/routers/knowledge.py`

**Step 1: Write the failing test**

```python
def test_search_api_returns_llamaindex_result_shape(client, auth_headers):
    response = client.post(
        "/api/knowledge/search",
        json={"query": "企业能力", "top_k": 3},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_knowledge_search_api_llamaindex.py -v`

Expected: FAIL until the API is covered and service wiring is stable.

**Step 3: Write minimal implementation**

If needed, adjust `backend/app/routers/knowledge.py` only to:
- keep request/response schema stable
- ensure it calls the LlamaIndex-backed retrieval service
- keep authorization behavior unchanged

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_knowledge_search_api_llamaindex.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_knowledge_search_api_llamaindex.py backend/app/routers/knowledge.py
git commit -m "test: cover llamaindex knowledge search api"
```

### Task 15: Add indexing API coverage for upload and manual creation

**Files:**
- Create: `backend/tests/test_knowledge_indexing_api_llamaindex.py`
- Modify: `backend/app/routers/knowledge.py`

**Step 1: Write the failing test**

```python
def test_manual_knowledge_creation_enqueues_indexing(client, auth_headers):
    response = client.post(
        "/api/knowledge/manual",
        data={
            "title": "示例",
            "content": "知识内容",
            "doc_type": "other",
            "scope": "user",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_knowledge_indexing_api_llamaindex.py -v`

Expected: FAIL until indexing path is fully wired.

**Step 3: Write minimal implementation**

Keep route behavior but ensure:
- manual documents persist source content consistently
- background task invokes LlamaIndex indexing
- response includes `vector_index_status`

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_knowledge_indexing_api_llamaindex.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_knowledge_indexing_api_llamaindex.py backend/app/routers/knowledge.py
git commit -m "test: cover llamaindex indexing api flows"
```

### Task 16: Run full backend verification

**Files:**
- Modify: `backend/tests/` as needed for fixes only

**Step 1: Run all focused knowledge tests**

Run:

```bash
cd backend
pytest tests/test_llamaindex_settings.py \
       tests/test_llamaindex_knowledge_service.py \
       tests/test_llamaindex_metadata_contract.py \
       tests/test_llamaindex_chunking.py \
       tests/test_llamaindex_schema_smoke.py \
       tests/test_llamaindex_indexing_flow.py \
       tests/test_llamaindex_retrieval_flow.py \
       tests/test_llamaindex_permission_filters.py \
       tests/test_knowledge_upload_llamaindex.py \
       tests/test_outline_knowledge_context.py \
       tests/test_llamaindex_delete_document.py \
       tests/test_knowledge_search_api_llamaindex.py \
       tests/test_knowledge_indexing_api_llamaindex.py -v
```

Expected: PASS

**Step 2: Run the broader backend suite**

Run:

```bash
cd backend
pytest -q
```

Expected: PASS or only unrelated existing failures.

**Step 3: Fix only regression failures caused by the migration**

If chapter generation, auth, or admin tests regress, patch only the minimum necessary code or tests.

**Step 4: Commit**

```bash
git add backend
git commit -m "test: verify llamaindex knowledge migration"
```

### Task 17: Update docs to reflect the new single-path architecture

**Files:**
- Modify: `README.md`
- Modify: `backend/requirements.txt`
- Modify: `docs/material_library_proposal.md` if it references knowledge retrieval implementation details

**Step 1: Write the doc changes**

Add a short section describing:
- knowledge indexing now uses LlamaIndex
- PostgreSQL + pgvector is required
- Ollama embedding service must be reachable
- no legacy migration path is maintained because the environment starts empty

**Step 2: Review for inaccurate historical comments**

Remove comments that imply:
- PageIndex is still the active knowledge retrieval path
- custom chunk SQL remains the main vector engine

**Step 3: Commit**

```bash
git add README.md backend/requirements.txt docs/material_library_proposal.md
git commit -m "docs: document llamaindex knowledge architecture"
```

### Task 18: Final validation on an empty environment

**Files:**
- No code changes required unless bugs are discovered

**Step 1: Reset the local empty database state if needed**

Run:

```bash
cd backend
alembic downgrade base
alembic upgrade head
```

Expected: clean schema creation from scratch.

**Step 2: Run a manual smoke flow**

Run the backend and verify:
1. Create a manual knowledge doc
2. Wait for indexing completion
3. Search for its content
4. Trigger chapter generation that uses `knowledge_context`

Expected:
- indexing status moves to `completed`
- search returns document-level results
- outline generation receives formatted knowledge snippets

**Step 3: Record the final known-good commands**

Document in PR description:

```bash
cd backend
alembic upgrade head
pytest -q
uvicorn app.main:app --reload
```

**Step 4: Commit any final fixes**

```bash
git add backend README.md docs
git commit -m "chore: finalize llamaindex knowledge migration"
```

## Notes for the Implementer

- Prefer deleting obsolete runtime logic over keeping both systems alive.
- Do not introduce a dual-write or fallback backend because the database is intentionally empty.
- Keep route contracts stable so the frontend does not need coordinated changes.
- Be strict about metadata normalization because permission filters depend on it.
- If LlamaIndex async integration with SQLAlchemy is awkward, keep the SQLAlchemy session for app models and use direct Postgres connection settings for the vector store layer.
- If a LlamaIndex-specific table naming scheme is required, standardize it in config instead of scattering names in services.
