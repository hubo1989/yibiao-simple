# Self-Hosted Bid Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a self-hosted web application that supports environment-configured LLM and embedding providers, tender-to-bid generation, and existing bid review.

**Architecture:** Keep the current FastAPI + React + PostgreSQL architecture. Use environment variables as the zero-initialization provider source, while preserving database-managed provider configs for administrators. Make the home page the single AI-native entry point and route users into existing project workspace, review, material, version, and export flows.

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL/pgvector, OpenAI-compatible SDK, LlamaIndex, React, TypeScript, Ant Design, Docker Compose.

---

### Task 1: Environment Provider Foundation

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/openai_service.py`
- Modify: `backend/app/routers/config.py`
- Modify: `backend/app/services/llamaindex_knowledge_service.py`
- Modify: `docker-compose.yml`
- Modify: `.env.docker.example`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_llamaindex_settings.py`
- Test: `backend/tests/test_env_provider_config.py`

- [x] **Step 1: Add LLM and embedding environment variables**

Add `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODELS`, `EMBEDDING_PROVIDER`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_MODELS`, and `EMBEDDING_DIMENSION` support.

- [x] **Step 2: Use env provider when database config is empty**

`OpenAIService` must load database configs first, then env config, then legacy local config.

- [x] **Step 3: Expose env provider through `/api/config/models`**

The frontend must see an `env` provider with generation and embedding model metadata.

- [x] **Step 4: Verify**

Run:

```bash
pytest backend/tests/test_llamaindex_settings.py backend/tests/test_env_provider_config.py backend/tests/test_api_key_config.py -q
```

Expected: all tests pass.

### Task 2: AI Native Workstation

**Files:**
- Create: `frontend/src/pages/AIWorkstation.tsx`
- Create: `frontend/src/pages/AIWorkstation.css`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Replace protected home route with AI workstation**

The `/` route should render a single command entry page after login.

- [x] **Step 2: Connect tender upload to real APIs**

Uploading a tender file must create a project through `projectApi.create`, upload the file through `documentApi.uploadToProject`, and route to `/project/:projectId`.

- [x] **Step 3: Connect existing project and review entry**

The workstation must list recent projects and allow opening `/project/:projectId` or `/project/:projectId/review`.

- [x] **Step 4: Verify**

Run:

```bash
npm test -- --watchAll=false
npm run build
```

Expected: tests pass and build succeeds.

### Task 3: Full Tender-To-Bid Orchestration

**Files:**
- Modify: `backend/app/routers/bid_agent.py`
- Modify: `backend/app/services/bid_agent_service.py`
- Modify: `frontend/src/pages/ProjectWorkspace.tsx`
- Create or modify tests under `backend/tests/test_bid_agent.py`

- [x] **Step 1: Add one-click run endpoint**

Expose an endpoint that starts the existing bid agent for a project and executes analysis, outline, response matrix, chapter generation, quality report, and export preflight.

- [x] **Step 2: Stream run progress**

Return step-level progress using SSE so the frontend can show serial workflow progress.

- [x] **Step 3: Show run state in workspace**

Project workspace should show the same serial steps as the prototype: upload, analysis, matrix, outline, draft, review, export.

- [x] **Step 4: Verify**

Run bid-agent unit tests and a frontend build.

Evidence from 2026-05-24:
- `pytest backend/tests/test_bid_agent.py -q` passed as part of the targeted backend suite.
- Docker runtime SSE smoke against `POST /api/bid-agent/{project_id}/generate-draft-stream` returned 23 events and a final `completed` event.
- The runtime smoke exercised project creation, tender upload, response matrix generation, quality report preflight, and no longer produced missing-table errors.
- `npm run build` under `frontend/` compiled successfully.

### Task 4: Existing Bid Review Completion

**Files:**
- Modify: `backend/app/routers/review.py`
- Modify: `backend/app/services/review_service.py`
- Modify: `frontend/src/pages/BidReview.tsx`
- Modify: `frontend/src/components/review/*`
- Test: review service and router tests

- [x] **Step 1: Allow review entry from existing project**

The review page must clearly guide users to upload an existing bid `.docx` for a selected project.

- [x] **Step 2: Persist review issues and fix suggestions**

Review output must persist enough metadata to reload history, filter issues, and export a report.

- [x] **Step 3: Add diff and version handoff**

AI fix suggestions must produce a review version record and allow users to compare before/after content.

- [x] **Step 4: Verify**

Run review tests and manually verify upload, execute, result, and export states.

Evidence from 2026-05-24:
- `pytest backend/tests/test_review_service.py -q` passed as part of the targeted backend suite.
- Review upload smoke passed through `POST /api/review/upload-bid` after tender upload and saved analysis.
- Review history/result recovery passed through `GET /api/review/history/{project_id}` and `GET /api/review/result/{task_id}`.
- Word export endpoint returned a `.docx` payload after marking the smoke review task completed with persisted empty review result sets.
- Live AI execution still requires a configured LLM API key; the no-key smoke validates non-LLM persistence and export paths.

### Task 5: Delivery Hardening

**Files:**
- Modify: `README.md`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `nginx.conf`
- Add: `scripts/self_host_smoke.sh`

- [x] **Step 1: Docker build smoke**

Run:

```bash
docker compose config
docker compose build
```

- [x] **Step 2: Runtime smoke**

Start the stack and verify `/health`, `/`, login/register, model config, project creation, and file upload.

Evidence from Docker project `yibiao_smoke` on 2026-05-23:
- `docker compose -p yibiao_smoke up -d --build` built the app image and started `db`, `app`, and `nginx`.
- `alembic_version` reached `0028_add_bid_agent`; public schema had 29 tables; `projects.default_template_id` existed.
- HTTP smoke passed for `/`, `/api/auth/register`, `/api/projects`, and `/api/document/upload-to-project` with a generated `.docx`.

Evidence from Docker project `yibiao_smoke` on 2026-05-24:
- `docker compose -p yibiao_smoke up -d --build` rebuilt and started `db`, `app`, and `nginx`.
- `/health` returned healthy; `/` returned the React app shell.
- `alembic_version` reached `0029_response_matrix_evidence`.
- `response_matrix_items`, `tender_clauses`, and `evidence_refs` existed in the public schema.
- HTTP smoke passed for register, project creation, tender upload, bid-agent SSE completion, review upload, review history/result recovery, and Word export.

- [x] **Step 3: Regression suite**

Run backend targeted tests, frontend tests, and production build.

- [x] **Step 4: Final audit**

Check the objective requirement by requirement and only mark complete when the current state proves all requirements.

Evidence from 2026-05-24:
- `bash scripts/self_host_smoke.sh` passed.
- `pytest backend/tests/test_llamaindex_settings.py backend/tests/test_env_provider_config.py backend/tests/test_api_key_config.py backend/tests/test_bid_agent.py backend/tests/test_review_service.py backend/tests/test_response_matrix_models.py backend/tests/test_evidence_model.py -q` passed: 60 tests.
- `CI=true npm test -- --watchAll=false` under `frontend/` passed: 6 suites, 15 tests.
- `npm run build` under `frontend/` compiled successfully.
- Docker empty-db runtime smoke passed from migration through key user workflows.
