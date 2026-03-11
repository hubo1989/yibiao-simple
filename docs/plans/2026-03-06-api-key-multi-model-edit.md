# API Key 多模型与编辑能力 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为管理员密钥管理页增加“修改已配置密钥”能力，并支持每个提供商配置多个模型 ID，分别指定生成模型与索引模型。

**Architecture:** 后端在保留旧 `model_name` 字段兼容的前提下，为 `api_key_configs` 新增多模型配置存储；路由统一返回解析后的模型列表及生成/索引模型。前端把新增与修改收敛到同一个弹窗，按模型行维护用途勾选，并通过新增的更新接口提交。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic v2、React、TypeScript

---

### Task 1: 定义多模型结构与兼容规则

**Files:**
- Modify: `backend/app/schemas/api_key_config.py`
- Modify: `backend/app/models/api_key_config.py`
- Test: `backend/tests/test_api_key_config.py`

**Step 1: Write the failing test**
- 为 schema/model 增加测试：`model_configs` 可用、可推导 `generation_model_name`/`index_model_name`、旧 `model_name` 仍兼容。

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/test_api_key_config.py -q`
- Expected: FAIL，提示新字段/新行为不存在。

**Step 3: Write minimal implementation**
- 定义 `ApiKeyModelConfig`。
- 为 ORM 模型添加多模型配置存储与解析/回填辅助方法。
- 为 schema 增加新字段与校验规则。

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/test_api_key_config.py -q`
- Expected: PASS。

### Task 2: 增加修改接口并接入运行时模型选择

**Files:**
- Modify: `backend/app/routers/admin.py`
- Modify: `backend/app/services/openai_service.py`
- Modify: `backend/app/services/pageindex_service.py`
- Create: `backend/alembic/versions/0015_add_multi_model_to_api_key_configs.py`
- Test: `backend/tests/test_api_key_config.py`

**Step 1: Write the failing test**
- 为响应转换/兼容逻辑补测试：返回多模型列表、正确暴露生成/索引模型。

**Step 2: Run test to verify it fails**
- Run: `pytest backend/tests/test_api_key_config.py -q`
- Expected: FAIL。

**Step 3: Write minimal implementation**
- 增加 `PUT /api/admin/api-keys/{config_id}`。
- 创建/更新时统一写入多模型配置。
- `openai_service` 读取生成模型，`pageindex_service` 读取索引模型。
- 增加数据库迁移并回填旧记录。

**Step 4: Run test to verify it passes**
- Run: `pytest backend/tests/test_api_key_config.py -q`
- Expected: PASS。

### Task 3: 更新管理员页面交互

**Files:**
- Modify: `frontend/src/types/admin.ts`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/Admin.tsx`

**Step 1: Write the failing test**
- 若已有合适前端测试位点则补，否则以类型/构建检查作为验证入口。

**Step 2: Run test to verify it fails**
- Run: `npm --prefix frontend run build`
- Expected: 若未实现类型更新则失败。

**Step 3: Write minimal implementation**
- 增加更新类型与 API。
- 复用弹窗支持新增/修改。
- 支持多模型行编辑、生成/索引用途选择、留空不改密钥。

**Step 4: Run test to verify it passes**
- Run: `npm --prefix frontend run build`
- Expected: PASS。

### Task 4: 针对性验证

**Files:**
- Verify only

**Step 1: Backend verification**
- Run: `pytest backend/tests/test_api_key_config.py -q`

**Step 2: Frontend verification**
- Run: `npm --prefix frontend run build`

**Step 3: Sanity review**
- 检查管理员页面表格与弹窗文案是否和行为一致。
