# 知识库功能使用说明

## PageIndex 集成

本项目使用 [PageIndex](https://github.com/VectifyAI/PageIndex) 作为知识库的索引和检索引擎。

### 更新 PageIndex

```bash
# 更新到最新版本
cd backend/PageIndex
git pull origin main
cd ../..

# 提交更新
git add backend/PageIndex
git commit -m "chore: update PageIndex to latest version"
```

### 初始化（首次克隆项目后）

```bash
# 克隆项目时自动初始化 submodule
git clone --recursive <repository-url>

# 或者如果已经克隆，手动初始化
git submodule update --init --recursive
```

## 环境配置

在 `.env` 文件中添加以下配置：

```bash
# PageIndex 配置（可选）
PAGEINDEX_MODEL=gpt-4o-2024-11-20
PAGEINDEX_TIMEOUT=300
```

## 运行数据库迁移

```bash
cd backend
alembic upgrade head
```

## 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

## 功能说明

### 1. 创建知识库条目

- **文件上传**: 支持 PDF 和 DOCX 格式
- **手动输入**: 直接编辑 Markdown 内容

### 2. 智能检索

- 基于 PageIndex 树搜索
- 使用 LLM 推理判断相关性
- 自动推荐最相关的知识库内容

### 3. 集成到内容生成

- 生成标书章节时自动检索知识库
- 用户可以确认、取消或补充选择
- 将知识库内容注入到生成提示词中

## 后续开发

- [ ] 完成知识库管理 API
- [ ] 集成到内容生成流程
- [ ] 前端界面开发
- [ ] 测试和优化
