# 标书审查功能 - 产品需求文档 (PRD)

| 字段 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-26 |
| 状态 | 待评审 |
| 所属系统 | AI 写标书助手 |

---

## 1. 产品概述

### 1.1 背景

当前系统已具备招标文件解析、标书目录生成、章节内容生成、校对和一致性检查等能力，但缺少对标书成品的审查环节。用户在实际投标流程中，需要在提交前对标书进行全面质量把关，检查投标文件是否充分响应了招标文件的要求。

### 1.2 目标

为系统新增「标书审查」功能模块，作为项目工作流的一部分，提供三维度（响应性、合规性、一致性）的 AI 智能审查能力，审查结果以页面报告和 Word 批注两种形式呈现，帮助用户快速定位问题并修改完善投标文件。

### 1.3 核心价值

- **效率提升**：将人工逐条对标审查的数小时工作缩短至数分钟
- **质量保障**：多维度交叉审查，降低遗漏关键评分项的风险
- **直观交付**：批注直接嵌入 Word 原文，审查意见与问题段落一目了然

### 1.4 模块定位

标书审查是项目工作流中的一个环节，在项目下运行，复用现有项目的以下能力：
- **成员体系**：复用项目成员角色（owner/editor/reviewer），审查操作记录到审计日志
- **知识库**：审查时可调用项目关联的知识库作为参考依据
- **招标文件分析结果**：复用已有的 `project_overview` 和 `tech_requirements`
- **评分项清单**：复用已有的 `rating_checklist` 能力
- **提示词体系**：通过 `PromptService` 管理审查相关提示词

---

## 2. 用户角色与使用场景

### 2.1 角色

| 角色 | 权限 | 说明 |
|------|------|------|
| Owner（项目负责人） | 发起审查、查看报告、导出 Word | 项目的创建者，拥有完整权限 |
| Editor（编辑） | 发起审查、查看报告、导出 Word | 标书编写人员 |
| Reviewer（审核员） | 查看报告、导出 Word | 标书审核人员，不可发起审查 |

### 2.2 典型场景

**场景一：标书提交前全面审查**

> 项目负责人张三完成标书编写后，在项目审查页面上传投标文件 Word 文档。系统自动调取已解析的招标文件内容和评分项清单，执行三维度审查。审查完成后，张三在页面上查看审查报告，发现"售后服务方案"章节未覆盖评分项中要求的"7×24 小时响应"，随即下载带批注的 Word 文档，在标注位置补充内容后重新上传。

**场景二：分章节针对性审查**

> 编辑李四修改了"技术方案"章节后，只想审查该章节的响应性。他在审查配置中选择仅检查"响应性"维度，并指定审查范围为"技术方案"相关章节，系统快速返回针对性的审查结果。

---

## 3. 功能需求

### 3.1 核心工作流

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Step 1      │    │  Step 2      │    │  Step 3      │    │  Step 4      │    │  Step 5      │
│  配置审查     │───▶│  上传投标文件 │───▶│  执行审查     │───▶│  查看报告     │───▶│  导出 Word   │
│              │    │              │    │              │    │              │    │              │
│  选择维度     │    │  上传 .docx  │    │  AI 三维度    │    │  页面在线查看 │    │  下载带批注   │
│  选择范围     │    │  文本提取     │    │  并行/串行    │    │  筛选/排序   │    │  的 Word 文档 │
│  选择模型     │    │              │    │  流式进度     │    │  定位问题    │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### 3.2 Step 1 - 配置审查

**入口**：项目工作空间 → 审查 Tab 页（复用现有路由 `project/:projectId/review`）

**功能描述**：用户在发起审查前进行参数配置

**UI 元素**：

| 元素 | 类型 | 说明 |
|------|------|------|
| 审查维度选择 | Checkbox.Group | 响应性（默认选中）、合规性（默认选中）、一致性（默认选中） |
| 审查范围 | Radio.Group | 全文档（默认） / 指定章节（多选，显示章节树） |
| AI 模型选择 | Select | 复用现有的模型选择器，支持 Provider + 模型切换 |
| 知识库关联 | Switch + Select | 是否使用知识库作为审查参考（复用知识库检索能力） |
| 开始审查按钮 | Button | 前置校验：项目已上传招标文件且已完成分析 |

**前置条件校验**：
- 项目必须已上传招标文件（`project.file_content` 非空）
- 项目必须已完成招标文件分析（`project.project_overview` 和 `project.tech_requirements` 非空）
- 若不满足，显示引导提示并跳转到对应步骤

### 3.3 Step 2 - 上传投标文件

**功能描述**：用户上传待审查的投标文件（Word 格式）

**技术要求**：
- 仅支持 `.docx` 格式
- 文件大小限制：50MB
- 上传后自动提取文本内容用于 AI 审查
- **保留原始文件**：上传的 Word 文件存储到服务器磁盘，后续导出时基于此文件添加批注
- 文件存储路径：`{upload_dir}/review/{project_id}/{timestamp}_{filename}`

**上传流程**：
1. 用户拖拽或点击上传 `.docx` 文件
2. 前端校验文件格式和大小
3. 后端保存原始文件到磁盘，记录文件路径
4. 后端使用 `FileService` 提取文本内容
5. 使用 `python-docx` 解析文档结构（段落/标题/表格），构建段落索引（段落序号 → 文本内容映射）
6. 返回上传成功确认和文件基本信息（段落数、章节数等）

**数据存储**：
- 原始文件路径存入审查记录（`BidReview.task.bid_file_path`）
- 提取的文本内容存入审查记录（`BidReview.task.bid_content`）
- 文档段落索引存入审查记录（`BidReview.task.paragraph_index`），结构如下：

```json
[
  {"index": 0, "type": "heading", "level": 1, "text": "第一章 技术方案"},
  {"index": 1, "type": "paragraph", "text": "本项目采用..."},
  {"index": 2, "type": "table", "text": "序号|项目|内容\n1|技术路线|..."},
  ...
]
```

### 3.4 Step 3 - 执行审查

**功能描述**：系统按用户配置的维度执行 AI 审查，三维度并行处理

**审查维度**：

#### 3.4.1 响应性审查

**目标**：逐条对比招标文件评分项与投标文件内容，检查每个评分项的覆盖程度和响应质量

**输入**：
- 招标文件文本（`project.file_content`）
- 招标文件分析结果（`project.project_overview`、`project.tech_requirements`）
- 评分项清单（通过 `rating_checklist` 生成或手动维护）
- 投标文件文本（`bid_content`）
- 知识库检索结果（可选）

**输出结构**（复用现有 `BID_REVIEW_ITEM_SCHEMA`）：
```json
{
  "rating_item": "售后服务方案（15分）",
  "score": 15,
  "max_score": 15,
  "coverage_status": "partial",
  "evidence": "见投标文件第4.3节，但未明确7×24响应承诺",
  "source_refs": [
    {
      "ref_id": "tender_p5",
      "source_type": "tender_document",
      "location": "招标文件第52页",
      "quote": "供应商须提供7×24小时售后服务...",
      "relation": "该条款要求7×24小时响应，投标文件未明确承诺"
    }
  ],
  "issues": ["未承诺7×24小时响应时间", "缺少具体故障响应时效"],
  "suggestions": ["在第4.3节增加'提供7×24小时技术支持热线'"],
  "rewrite_suggestions": ["本公司承诺提供7×24小时售后服务热线，故障响应时间不超过2小时"],
  "chapter_targets": ["4.3 售后服务保障"],
  "confidence": "high"
}
```

**AI 提示词场景 Key**：`bid_review_responsiveness`

#### 3.4.2 合规性审查

**目标**：检查投标文件是否符合招标文件中的格式要求、资质要求、签署要求等硬性合规条款

**输入**：
- 招标文件文本（重点关注"投标人须知""资格审查""格式要求"等章节）
- 投标文件文本
- 投标文件结构信息（目录、页数等）

**输出结构**：
```json
{
  "compliance_category": "格式要求",
  "clause_text": "投标文件正本1份、副本5份",
  "check_result": "warning",
  "detail": "招标文件要求正本1份副本5份，请确认投标文件份数是否符合",
  "bid_location": "封面/目录",
  "severity": "warning",
  "suggestion": "确认副本数量是否为5份，如不符合请调整"
}
```

**检查类别**：
| 类别 | 说明 |
|------|------|
| 格式要求 | 页数、份数、装订、字体字号等 |
| 资质要求 | 营业执照、资质证书、人员证书等是否提及 |
| 签署要求 | 法定代表人签字、盖章、日期等 |
| 排他条款 | 是否包含禁止的联合体、分包等限制 |
| 报价要求 | 投标报价格式、有效期、是否超过预算 |

**AI 提示词场景 Key**：`bid_review_compliance`

#### 3.4.3 一致性审查

**目标**：检查投标文件内部各章节之间的数据、术语、描述是否一致

**输入**：
- 投标文件全文（按章节拆分）
- 项目概述信息

**输出结构**（复用现有 `CONSISTENCY_CONTRADICTION_SCHEMA`）：
```json
{
  "severity": "critical",
  "category": "data",
  "description": "项目工期前后表述不一致",
  "chapter_a": "1.2 项目概况",
  "detail_a": "项目建设工期为18个月",
  "chapter_b": "3.1 实施计划",
  "detail_b": "总工期为24个月",
  "suggestion": "统一工期描述，建议核实后统一修改为实际工期"
}
```

**检查类别**：
| 类别 | 说明 |
|------|------|
| 数据一致 | 工期、人数、金额、面积等数值是否前后矛盾 |
| 术语一致 | 同一概念是否使用了不同表述 |
| 时间线一致 | 项目里程碑、交付节点是否自洽 |
| 承诺一致 | 响应条款的承诺是否在各章节保持一致 |
| 范围一致 | 项目范围描述是否各处一致 |

**AI 提示词场景 Key**：`bid_review_consistency`

### 3.5 Step 4 - 查看审查报告

**功能描述**：页面化展示审查结果，支持多维度筛选、排序和问题定位

**页面布局**：

```
┌─────────────────────────────────────────────────────────┐
│  审查报告标题栏                                          │
│  项目名称 | 审查时间 | 模型 | 状态标签                     │
├─────────────────────────────────────────────────────────┤
│  总览卡片区域                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 总评分项  │ │ 覆盖率   │ │ 问题总数  │ │ 风险等级  │  │
│  │   32     │ │  85%    │ │   12     │ │  中等    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────┤
│  维度 Tab：全部 | 响应性 | 合规性 | 一致性                  │
├─────────────────────────────────────────────────────────┤
│  筛选工具栏                                              │
│  严重程度：🔴高 🟡中 🔵低   覆盖状态：全部|已覆盖|部分|未覆盖  │
│  排序：按评分项顺序 | 按严重程度 | 按章节                   │
├─────────────────────────────────────────────────────────┤
│  审查结果列表                                            │
│  ┌─────────────────────────────────────────────────────┐│
│  │  🔴 售后服务方案（15分）- 部分覆盖                     ││
│  │  招标要求：提供7×24小时售后服务...                      ││
│  │  问题：未承诺7×24小时响应时间                          ││
│  │  建议：增加'提供7×24小时技术支持热线'                  ││
│  │  位置：第4.3节 售后服务保障                           ││
│  │  置信度：高                           [展开详情 ▼]    ││
│  ├─────────────────────────────────────────────────────┤│
│  │  🟡 项目工期描述不一致 - 一致性问题                     ││
│  │  1.2节："工期18个月" vs 3.1节："工期24个月"            ││
│  │  建议：统一工期描述                                    ││
│  │  置信度：中                           [展开详情 ▼]    ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  底部操作栏                                              │
│  [导出带批注的 Word]  [重新审查]  [审查历史]               │
└─────────────────────────────────────────────────────────┘
```

**总览卡片**：

| 卡片 | 指标 | 计算方式 |
|------|------|----------|
| 总评分项 | 审查的评分项总数 | 响应性审查返回的 items 数量 |
| 覆盖率 | 已覆盖评分项占比 | (covered + partial) / total × 100% |
| 问题总数 | 所有维度的问题数量 | 各维度 issues 之和 |
| 风险等级 | 整体风险判断 | 基于 coverage_rate 和 critical 问题数量 |

**列表项操作**：
- **展开详情**：显示完整的 source_refs、issues、suggestions、rewrite_suggestions
- **一键应用建议**：点击后将 `rewrite_suggestions` 中的内容复制到剪贴板
- **跳转定位**：显示问题在投标文件中的章节位置

### 3.6 Step 5 - 导出带批注的 Word

**功能描述**：将审查结果以 Word 批注（Comment）形式嵌入原始投标文件

**技术方案**：

使用 `python-docx` 的 `OPC` 接口直接操作 Word 的批注 XML 结构：

```python
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree
import copy

# Word 批注所需的 XML 命名空间
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W14_NS = 'http://schemas.microsoft.com/office/word/2010/wordml'

def add_word_comment(doc: Document, paragraph_index: int,
                     comment_text: str, author: str) -> None:
    """
    在指定段落添加 Word 批注。

    Args:
        doc: python-docx Document 对象（基于原始投标文件打开）
        paragraph_index: 段落索引（从0开始）
        comment_text: 批注内容（审查建议的格式化文本）
        author: 批注作者（系统/AI审查）
    """
    # 1. 在 comments.xml part 中创建 comment 元素
    # 2. 在目标段落的 run 前后插入 commentRangeStart/commentRangeEnd
    # 3. 在段落末尾插入 commentReference
    # 4. 建立 comments part 与 document part 的关系
```

**批注内容格式**：

每个评分项/条款对应一条 Word 批注，格式如下：

```
【AI 标书审查 - 响应性】
评分项：售后服务方案（15分）
覆盖状态：部分覆盖

招标要求：
供应商须提供7×24小时售后服务...

存在问题：
1. 未承诺7×24小时响应时间
2. 缺少具体故障响应时效

修改建议：
1. 在第4.3节增加"提供7×24小时技术支持热线"
2. 补充故障响应时效承诺

参考改写：
本公司承诺提供7×24小时售后服务热线，故障响应时间不超过2小时。

置信度：高
```

**批注定位策略**：

由于 AI 无法精确返回投标文件中的字符偏移量，采用以下策略定位批注：

1. **章节标题匹配**：AI 返回的 `chapter_targets` 包含章节编号和标题，在段落索引中搜索匹配的标题段落
2. **关键词搜索**：在目标章节的后续段落中搜索与 `evidence` 或 `source_refs.quote` 相关的文本
3. **兜底方案**：若无法精确定位，在匹配到的章节标题段落插入批注

**导出流程**：
1. 从磁盘读取原始投标文件（`bid_file_path`）
2. 使用 `python-docx` 打开文档
3. 遍历审查结果，按上述策略定位段落并添加批注
4. 保存为新文件：`{filename}_审查批注_{timestamp}.docx`
5. 以 StreamingResponse 返回文件下载

---

## 4. API 接口设计

### 4.1 审查任务管理

#### POST /api/review/upload-bid

上传投标文件到指定项目的审查任务

**Request**：
- `project_id`: string (Form) - 项目 ID
- `file`: UploadFile - 投标文件 (.docx)

**Response**：
```json
{
  "success": true,
  "message": "投标文件上传成功",
  "task_id": "uuid",
  "file_info": {
    "filename": "投标文件.docx",
    "file_size": 2048000,
    "paragraph_count": 156,
    "heading_count": 12
  }
}
```

#### POST /api/review/execute

执行审查任务

**Request**：
```json
{
  "task_id": "uuid",
  "dimensions": ["responsiveness", "compliance", "consistency"],
  "scope": "full",
  "chapter_ids": null,
  "model_name": "gpt-4o",
  "provider_config_id": "uuid",
  "use_knowledge": true,
  "knowledge_ids": ["uuid1", "uuid2"]
}
```

**Response**：SSE 流式响应

```
data: {"type": "progress", "dimension": "responsiveness", "status": "processing", "message": "正在执行响应性审查..."}

data: {"type": "progress", "dimension": "compliance", "status": "processing", "message": "正在执行合规性审查..."}

data: {"type": "progress", "dimension": "consistency", "status": "completed", "message": "一致性审查完成"}

data: {"type": "result", "dimension": "responsiveness", "data": {...}}

data: {"type": "result", "dimension": "compliance", "data": {...}}

data: {"type": "result", "dimension": "consistency", "data": {...}}

data: {"type": "summary", "data": {"overall_score": 78, "coverage_rate": 0.85, "risk_level": "medium", "total_issues": 12}}

data: [DONE]
```

#### GET /api/review/result/{task_id}

获取审查结果（用于页面刷新后恢复）

**Response**：
```json
{
  "task_id": "uuid",
  "project_id": "uuid",
  "status": "completed",
  "config": {
    "dimensions": ["responsiveness", "compliance", "consistency"],
    "model_name": "gpt-4o"
  },
  "summary": {
    "overall_score": 78,
    "score_max": 100,
    "coverage_rate": 0.85,
    "risk_level": "medium",
    "total_issues": 12,
    "issue_distribution": {
      "critical": 2,
      "warning": 6,
      "info": 4
    }
  },
  "responsiveness": { "items": [...] },
  "compliance": { "items": [...] },
  "consistency": { "contradictions": [...] },
  "created_at": "2026-03-26T12:00:00Z"
}
```

#### GET /api/review/history/{project_id}

获取项目的审查历史列表

**Response**：
```json
{
  "items": [
    {
      "task_id": "uuid",
      "status": "completed",
      "summary": { "overall_score": 78, "coverage_rate": 0.85, "risk_level": "medium" },
      "model_name": "gpt-4o",
      "created_at": "2026-03-26T12:00:00Z"
    }
  ]
}
```

#### POST /api/review/export-word

导出带批注的 Word 文档

**Request**：
```json
{
  "task_id": "uuid",
  "dimensions": ["responsiveness", "compliance", "consistency"]
}
```

**Response**：Word 文件下载（StreamingResponse）

---

## 5. 数据模型设计

### 5.1 审查任务表 `bid_review_tasks`

```python
class ReviewTaskStatus(str, PyEnum):
    """审查任务状态"""
    PENDING = "pending"           # 待执行
    PROCESSING = "processing"     # 审查中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败

class BidReviewTask(Base):
    __tablename__ = "bid_review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    status: Mapped[ReviewTaskStatus] = mapped_column(
        Enum(ReviewTaskStatus, native_enum=False, length=20),
        nullable=False, default=ReviewTaskStatus.PENDING
    )

    # 投标文件信息
    bid_file_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="投标文件磁盘路径")
    bid_filename: Mapped[str] = mapped_column(String(255), nullable=False, comment="投标文件原始文件名")
    bid_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="投标文件提取文本")
    paragraph_index: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="文档段落索引")

    # 审查配置
    dimensions: Mapped[list] = mapped_column(JSONB, nullable=False, comment="审查维度列表")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="full", comment="审查范围")
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="使用的模型名称")
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_key_configs.id", ondelete="SET NULL"),
        nullable=True
    )

    # 审查结果
    responsiveness_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="响应性审查结果")
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="合规性审查结果")
    consistency_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="一致性审查结果")
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True, comment="审查汇总")

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败时的错误信息")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="审查完成时间")

    # 关系
    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id], backref="review_tasks")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
```

### 5.2 数据库迁移

新增 Alembic 迁移文件 `0018_create_bid_review_tasks.py`，包含：
- 创建 `bid_review_tasks` 表
- 添加 `created_by` 字段（关联 users 表）
- 添加相关索引

---

## 6. 前端页面设计

### 6.1 路由与导航

复用现有路由 `project/:projectId/review`，改造 `BidReview.tsx` 页面。

### 6.2 页面组件拆分

```
pages/BidReview.tsx              # 主页面容器，步骤流程控制
components/review/
  ReviewConfig.tsx               # Step 1: 审查配置面板
  BidFileUpload.tsx              # Step 2: 投标文件上传
  ReviewProgress.tsx             # Step 3: 审查进度展示（三维度并行进度）
  ReviewReport.tsx               # Step 4: 审查报告主体
  ReviewSummaryCards.tsx         # 总览卡片区域
  ReviewIssueList.tsx            # 审查结果列表
  ReviewIssueItem.tsx            # 单条审查结果卡片
  ReviewHistoryDrawer.tsx        # 审查历史抽屉面板
```

### 6.3 前端类型定义

新增 `frontend/src/types/review.ts`：

```typescript
// 审查维度
type ReviewDimension = 'responsiveness' | 'compliance' | 'consistency';

// 审查任务状态
type ReviewTaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

// 覆盖状态
type CoverageStatus = 'covered' | 'partial' | 'missing' | 'risk';

// 严重程度
type Severity = 'critical' | 'warning' | 'info';

// 响应性审查项
interface ResponsivenessItem {
  rating_item: string;
  score: number;
  max_score: number;
  coverage_status: CoverageStatus;
  evidence: string;
  source_refs: SourceRef[];
  issues: string[];
  suggestions: string[];
  rewrite_suggestions: string[];
  chapter_targets: string[];
  confidence: 'high' | 'medium' | 'low';
}

// 合规性审查项
interface ComplianceItem {
  compliance_category: string;
  clause_text: string;
  check_result: 'pass' | 'warning' | 'fail';
  detail: string;
  bid_location: string;
  severity: Severity;
  suggestion: string;
}

// 一致性审查项
interface ConsistencyItem {
  severity: Severity;
  category: string;
  description: string;
  chapter_a: string;
  detail_a: string;
  chapter_b: string;
  detail_b: string;
  suggestion: string;
}

// 审查汇总
interface ReviewSummary {
  overall_score: number;
  score_max: number;
  coverage_rate: number;
  risk_level: 'low' | 'medium' | 'high';
  total_issues: number;
  issue_distribution: {
    critical: number;
    warning: number;
    info: number;
  };
}

// 审查任务
interface ReviewTask {
  task_id: string;
  project_id: string;
  status: ReviewTaskStatus;
  config: {
    dimensions: ReviewDimension[];
    model_name: string;
  };
  summary: ReviewSummary | null;
  responsiveness: { items: ResponsivenessItem[] } | null;
  compliance: { items: ComplianceItem[] } | null;
  consistency: { contradictions: ConsistencyItem[] } | null;
  created_at: string;
}
```

### 6.4 交互规范

| 操作 | 交互 |
|------|------|
| 审查进度 | 三维度并行进度条，每个维度显示当前状态和处理进度 |
| 展开详情 | 手风琴折叠面板，点击展开/收起 |
| 一键应用 | 点击后 Toast 提示"已复制到剪贴板" |
| 导出 Word | 点击后 Loading 状态，下载完成后自动保存文件 |
| 重新审查 | 二次确认弹窗，确认后重置当前审查结果 |
| 页面刷新 | 从 API 恢复审查结果，保持筛选状态 |

---

## 7. 后端实现要点

### 7.1 新增文件

| 文件路径 | 说明 |
|----------|------|
| `backend/app/routers/review.py` | 审查 API 路由 |
| `backend/app/schemas/review.py` | 审查相关 Pydantic Schema |
| `backend/app/models/bid_review_task.py` | 审查任务 ORM 模型 |
| `backend/app/services/review_service.py` | 审查业务逻辑服务 |
| `backend/app/services/word_comment_service.py` | Word 批注生成服务 |
| `backend/alembic/versions/0018_create_bid_review_tasks.py` | 数据库迁移 |

### 7.2 Word 批注服务 (`word_comment_service.py`)

核心职责：
- 基于原始 `.docx` 文件添加 Word 批注
- 按审查维度格式化批注内容
- 按章节标题 + 关键词策略定位批注插入位置
- 处理批量批注添加的性能优化

关键技术点：
- python-docx 本身不提供高级批注 API，需通过 `OPC` 和 `lxml` 直接操作 `comments.xml`
- 批注的 `commentRangeStart` / `commentRangeEnd` 需要包裹在段落文本的 `w:r` 元素上
- 每个 `w:commentReference` 必须在对应的 `commentsExtended.xml` 或 `comments.xml` 中有对应条目
- 需要处理文档中已有批注的情况（追加而非覆盖）

### 7.3 审查服务 (`review_service.py`)

核心职责：
- 编排三维度审查的执行（可并行）
- 调用 `OpenAIService` 执行各维度 AI 分析
- 管理审查任务生命周期（状态流转）
- 生成审查汇总数据

审查执行策略：
- 三维度并行处理，使用 `asyncio.gather` 并发调用
- 每个维度独立捕获异常，单个维度失败不影响其他维度
- 流式进度通过 SSE 推送到前端

### 7.4 路由注册

在 `backend/app/main.py` 中注册新路由：

```python
from .routers import review
app.include_router(review.router)
```

---

## 8. 提示词设计

### 8.1 提示词场景 Key

| 场景 Key | 用途 | 对应现有/新增 |
|----------|------|---------------|
| `bid_review_responsiveness` | 响应性审查 | 新增 |
| `bid_review_compliance` | 合规性审查 | 新增 |
| `bid_review_consistency` | 一致性审查 | 新增 |

### 8.2 提示词管理

通过 `PromptService` 管理，支持：
- 全局默认提示词（管理员配置）
- 项目级提示词覆盖（复用 `project.custom_prompts`）

---

## 9. 非功能需求

### 9.1 性能

| 指标 | 要求 |
|------|------|
| 投标文件上传 | 50MB 文件上传 ≤ 10s |
| 文本提取 | 200页文档 ≤ 5s |
| 单维度审查 | ≤ 60s（取决于 AI 模型响应速度） |
| 三维度并行审查 | ≤ 90s（总耗时取决于最慢维度） |
| Word 批注导出 | ≤ 10s |
| 审查结果加载 | ≤ 1s |

### 9.2 安全

- 投标文件存储在服务器磁盘，路径不可枚举（使用 UUID 命名）
- 审查任务接口需项目成员权限验证（复用 `require_editor`）
- 文件上传复用现有的 magic bytes 校验
- 导出的 Word 文件为临时文件，定期清理（建议 7 天）

### 9.3 可靠性

- 单维度审查失败不阻断整体审查流程
- 审查结果持久化到数据库，支持页面刷新后恢复
- 审查历史保留，支持回溯对比
- 大文档处理使用流式读取，避免 OOM

### 9.4 可扩展性

- 审查维度支持后续扩展（如增加"逻辑性审查"等新维度）
- 提示词通过 `PromptService` 管理，无需修改代码即可调整
- Word 批注格式可配置

---

## 10. 验收标准

### 10.1 功能验收

- [ ] 在项目审查页面可配置审查维度和范围
- [ ] 可上传 .docx 格式投标文件，上传后自动提取文本
- [ ] 点击"开始审查"后，三维度并行执行并显示实时进度
- [ ] 审查完成后页面展示总览卡片（总评分项、覆盖率、问题总数、风险等级）
- [ ] 审查结果支持按维度 Tab 切换、按严重程度和覆盖状态筛选
- [ ] 审查结果列表支持展开详情、一键复制建议
- [ ] 导出的 Word 文档在对应位置包含格式化的审查批注
- [ ] 批注内容清晰标注维度、评分项、问题和建议
- [ ] 支持查看审查历史列表
- [ ] 页面刷新后审查结果不丢失

### 10.2 异常场景

- [ ] 招标文件未上传/未分析时，显示引导提示
- [ ] 上传非 .docx 文件时，给出明确错误提示
- [ ] 单维度审查失败时，其他维度结果正常展示
- [ ] AI 模型不可用时，给出明确错误提示
- [ ] 导出 Word 失败时，提示重试

### 10.3 性能验收

- [ ] 50 页 Word 文档上传和文本提取在 10 秒内完成
- [ ] 三维度审查总耗时在 2 分钟内（取决于 AI 模型）
- [ ] 审查结果页面加载在 1 秒内
- [ ] Word 批注导出在 10 秒内完成
