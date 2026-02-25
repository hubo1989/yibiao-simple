# 用户模型选择功能设计

## 背景

当前系统存在的问题：
1. 管理员在后台配置 API Key 和默认模型
2. 用户在项目页面可以获取模型列表，但 API 限制为管理员权限
3. 用户选择的模型仅保存在前端，未传递给后端 AI 调用
4. 每次进入页面都会请求模型列表，未做缓存

## 目标

1. 模型选择与具体项目绑定（项目级别）
2. 模型列表缓存到 localStorage，仅在用户主动点击时重新获取
3. 用户选择的模型能实际影响 AI 调用

## 架构设计

### 数据流

```
管理员配置 API Key（后台）→ 数据库默认配置
用户获取模型列表 → 前端 localStorage 缓存
用户选择模型 → localStorage 保存
用户调用 AI → 前端传递 model_name → 后端覆盖默认模型
```

### 核心原则

- **前端传递模型参数**：每次 AI 调用时，前端在请求中携带 `model_name` 参数
- **向后兼容**：`model_name` 为可选参数，未传递时使用数据库默认配置
- **最小改动**：不新增数据库字段，利用现有 localStorage 机制

## 改动清单

### 前端

#### 1. ConfigPanel.tsx（已完成）
- localStorage 缓存模型列表和当前选择
- 组件加载时从缓存读取，不自动请求 API
- 按钮改为"重新获取模型列表"

#### 2. 新增 src/utils/modelCache.ts
```typescript
// 导出工具函数供其他组件调用
export function getCurrentModel(): string | null;
export function getModelCache(): { models: string[]; currentModel: string } | null;
```

#### 3. src/services/api.ts
- AI 相关请求增加 `model_name` 参数

#### 4. 页面组件改动
- `DocumentAnalysis.tsx` — 调用时传递模型
- `OutlineEdit.tsx` — 调用时传递模型
- `ContentEdit.tsx` — 调用时传递模型

### 后端

#### 1. backend/app/routers/config.py
- `POST /api/config/models` — 权限从 `require_admin` 改为 `require_editor`
- 删除 `POST /api/config/save-model` 接口（不再需要）

#### 2. backend/app/models/schemas.py
三个请求 Schema 增加 `model_name` 字段：

```python
class AnalysisRequest(BaseModel):
    file_content: str
    analysis_type: AnalysisType
    model_name: Optional[str] = None  # 新增

class OutlineRequest(BaseModel):
    overview: str
    requirements: str
    uploaded_expand: Optional[bool] = False
    old_outline: Optional[str] = None
    old_document: Optional[str] = None
    model_name: Optional[str] = None  # 新增

class ChapterContentRequest(BaseModel):
    chapter: Dict[str, Any]
    parent_chapters: Optional[List[Dict[str, Any]]] = None
    sibling_chapters: Optional[List[Dict[str, Any]]] = None
    project_overview: str = ""
    model_name: Optional[str] = None  # 新增
```

#### 3. backend/app/services/openai_service.py
新增方法：
```python
def set_model(self, model_name: str):
    """覆盖默认模型"""
    self.model_name = model_name
```

#### 4. backend/app/routers/document.py
- `analyze_stream()` 接收 `model_name` 参数
- 调用 `openai_service.set_model()` 覆盖模型

#### 5. backend/app/routers/outline.py
- `generate_stream()` 接收 `model_name` 参数
- 调用 `openai_service.set_model()` 覆盖模型

#### 6. backend/app/routers/content.py
- `generate_chapter_stream()` 接收 `model_name` 参数
- 调用 `openai_service.set_model()` 覆盖模型

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 前端传的 `model_name` 无效 | 后端使用默认模型，日志警告 |
| 前端未传 `model_name` | 后端使用数据库默认配置 |
| `getModels` API 失败 | 前端显示错误提示，保留缓存数据 |
| localStorage 无缓存 | 显示空状态，引导用户获取模型 |

## 测试要点

1. **权限测试**：普通用户可以获取模型列表
2. **缓存测试**：刷新页面后模型选择保留
3. **AI 调用测试**：选择不同模型，验证后端实际使用对应模型
4. **降级测试**：前端不传模型参数时，后端使用默认配置
