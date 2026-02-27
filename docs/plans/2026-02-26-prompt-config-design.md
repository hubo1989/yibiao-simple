# 标书 Agent 提示词配置系统设计

## 概述

为标书 AI 写作助手添加灵活的提示词配置系统，支持管理员全局配置和项目级别自定义，实现三层优先级回退机制。

## 设计目标

1. 管理员可定义全局默认提示词，所有项目共用
2. 每个项目可独立覆盖任意场景的提示词
3. 所有场景支持自定义，但均为可选——不配置则使用上层默认
4. 提供可视化模板编辑器，支持变量点击插入
5. 管理员全局配置支持版本历史和回滚

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      AI 调用请求                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  提示词解析服务                              │
│  1. 检查项目是否有该场景的自定义提示词                        │
│  2. 如无，检查管理员全局配置                                  │
│  3. 如无，使用代码内置默认                                    │
└─────────────────────────────────────────────────────────────┘
```

**三层优先级**：
1. 项目级别自定义（最高优先级）
2. 管理员全局配置（支持版本历史）
3. 系统内置默认（硬编码在代码中）

## 数据库设计

### 新增表：`global_prompts`（管理员全局提示词）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| scene_key | String(50) | 场景标识，唯一索引 |
| scene_name | String(100) | 场景中文名 |
| category | String(20) | 分类：parse/generate/check |
| system_prompt | Text | 系统提示词 |
| user_prompt_template | Text | 用户提示词模板 |
| available_vars | JSONB | 可用变量列表 `[{key, label}]` |
| version | Integer | 当前版本号 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 新增表：`global_prompt_versions`（全局提示词版本历史）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| global_prompt_id | UUID | 关联全局提示词 |
| version | Integer | 版本号 |
| system_prompt | Text | 该版本的系统提示词 |
| user_prompt_template | Text | 该版本的用户提示词模板 |
| created_by | UUID | 创建者 ID |
| created_at | DateTime | 创建时间 |

### 修改表：`projects`（添加项目级提示词）

| 字段 | 类型 | 说明 |
|------|------|------|
| custom_prompts | JSONB | 项目自定义提示词 |

`custom_prompts` 结构示例：
```json
{
  "chapter_content": {
    "system_prompt": "自定义的系统提示词...",
    "user_prompt_template": "自定义的用户提示词模板..."
  },
  "outline_l1": {
    "system_prompt": "...",
    "user_prompt_template": "..."
  }
}
```

## 提示词场景定义

| scene_key | 场景名称 | 分类 | 可用变量 |
|-----------|----------|------|----------|
| `doc_analysis_overview` | 项目概述分析 | parse | `file_content` |
| `doc_analysis_requirements` | 技术评分分析 | parse | `file_content` |
| `outline_l1` | 一级目录生成 | generate | `overview`, `requirements` |
| `outline_l2l3` | 二三级目录生成 | generate | `overview`, `requirements`, `other_outline`, `level1_title` |
| `chapter_content` | 章节内容生成 | generate | `chapter_id`, `chapter_title`, `chapter_desc`, `parent_chapters`, `sibling_chapters`, `project_overview`, `knowledge_context` |
| `proofread` | 章节校对 | check | `chapter_title`, `chapter_content`, `tech_requirements`, `sibling_titles`, `project_overview` |
| `consistency_check` | 一致性检查 | check | `chapter_summaries`, `project_overview`, `tech_requirements` |
| `outline_extract` | 目录提取 | parse | `file_content` |

## 前端界面设计

### 管理员全局配置页面（/admin/prompts）

- 扁平列表展示所有场景
- 左侧分类标签筛选（解析/生成/检查）
- 每个场景卡片显示：
  - 场景名称
  - 当前版本号
  - 最后更新时间
  - 编辑按钮
- 点击编辑进入可视化编辑器

### 可视化模板编辑器

```
┌─────────────────────────────────────────────────────────────┐
│  章节内容生成 - 编辑提示词                                   │
├─────────────────────────────────────────────────────────────┤
│  可用变量（点击插入）:                                        │
│  [章节ID] [章节标题] [章节描述] [上级章节] [同级章节]         │
│  [项目概述] [知识库内容]                                     │
├─────────────────────────────────────────────────────────────┤
│  系统提示词:                                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 你是一个专业的标书编写专家...                            ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  用户提示词模板:                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 请为以下标书章节生成具体内容：                           ││
│  │ 章节ID: {chapter_id}                                    ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  [预览] [重置为默认] [保存] [取消]                           │
└─────────────────────────────────────────────────────────────┘
```

### 项目级提示词配置（位于项目设置中）

- 显示继承状态：`使用管理员全局配置` 或 `使用项目自定义`
- 每个场景可独立选择是否覆盖
- 只有 owner 和 editor 可编辑

## 后端 API 设计

### 管理员全局提示词

```
GET    /api/admin/prompts                     # 获取所有全局提示词列表
GET    /api/admin/prompts/:scene_key          # 获取单个场景提示词详情
PUT    /api/admin/prompts/:scene_key          # 更新提示词（自动创建版本）
GET    /api/admin/prompts/:scene_key/versions # 获取版本历史列表
POST   /api/admin/prompts/:scene_key/rollback # 回滚到指定版本
```

### 项目级提示词

```
GET    /api/projects/:id/prompts              # 获取项目提示词配置（含继承状态）
PUT    /api/projects/:id/prompts/:scene_key   # 设置项目自定义提示词
DELETE /api/projects/:id/prompts/:scene_key   # 删除自定义，恢复继承
```

## 权限控制

| 操作 | 管理员 | 项目 Owner | 项目 Editor | 项目 Reviewer | 普通用户 |
|------|--------|-----------|-------------|---------------|----------|
| 查看全局提示词 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 编辑全局提示词 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 查看项目提示词 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 编辑项目提示词 | ✅ | ✅ | ✅ | ❌ | ❌ |

## 后端实现要点

### PromptService 类

```python
class PromptService:
    async def get_prompt(
        self,
        scene_key: str,
        project_id: str | None = None
    ) -> tuple[str, str]:
        """
        获取提示词，按优先级回退
        返回: (system_prompt, user_prompt_template)
        """
        # 1. 检查项目自定义
        if project_id:
            project_prompt = await self._get_project_prompt(project_id, scene_key)
            if project_prompt:
                return project_prompt

        # 2. 检查管理员全局配置
        global_prompt = await self._get_global_prompt(scene_key)
        if global_prompt:
            return global_prompt

        # 3. 返回系统内置默认
        return self._get_builtin_prompt(scene_key)

    def _get_builtin_prompt(self, scene_key: str) -> tuple[str, str]:
        """返回代码中硬编码的默认提示词"""
        return BUILTIN_PROMPTS.get(scene_key, ("", ""))
```

### 变量替换

```python
def render_prompt(template: str, variables: dict) -> str:
    """将变量注入提示词模板"""
    return template.format(**variables)
```

## 前端组件结构

```
src/
├── pages/
│   └── AdminPrompts.tsx          # 管理员提示词配置页
├── components/
│   ├── PromptEditor.tsx          # 可视化提示词编辑器
│   ├── PromptVarButton.tsx       # 变量插入按钮
│   ├── PromptCard.tsx            # 提示词场景卡片
│   └── PromptVersionHistory.tsx  # 版本历史组件
└── services/
    └── promptApi.ts              # 提示词 API 封装
```

## 实施步骤

1. 创建数据库表和 ORM 模型
2. 实现后端 PromptService 和 API
3. 修改现有 AI 调用逻辑，接入 PromptService
4. 实现管理员提示词配置页面
5. 实现可视化提示词编辑器
6. 在项目设置中添加提示词配置入口
7. 测试三层回退逻辑
