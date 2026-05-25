# 易标极速版 - AI智能标书写作助手

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11--3.13-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/React-19.1+-61dafb.svg" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.116+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-17+-336791.svg" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

> **重要提示**: Python 3.14+ 暂不兼容，请使用 Python 3.11-3.13

<p align="left">
  <strong>🚀 基于 AI 的智能标书写作助手，让标书制作变得简单高效</strong>
</p>

---

## ✨ 核心功能

### 基础功能
- **🤖 智能文档解析**：自动分析招标文件，提取关键信息和技术评分要求
- **📝 AI生成目录**：基于招标文件智能生成专业的三级标书目录结构
- **⚡ 内容自动生成**：为每个章节自动生成高质量、针对性的标书内容
- **🎯 多模型支持**：支持所有 OpenAI 兼容的大模型（推荐 DeepSeek）
- **💾 一键导出**：导出 Word 格式，自由编辑

### 新增功能 (library分支)
- **📚 素材库管理**：集中管理营业执照、资质证书、项目案例等素材
- **🔄 历史标书解析**：从历史标书中智能提取素材，建立企业知识库
- **🤖 AI 素材匹配**：自动分析项目需求，智能匹配可用素材
- **📋 章节素材绑定**：将素材插入标书特定位置，支持多种展示模式

### 🌟 产品优势
- ⏱️ **效率提升**: 将传统需要数天的标书制作缩短至几小时
- 🎨 **专业质量**: AI生成的内容结构清晰、逻辑严密、符合行业标准
- 🔧 **易于使用**: 简洁直观的界面设计，无需专业培训即可上手
- 🔄 **持续优化**: 基于用户反馈不断改进AI算法和用户体验

---

## 🌐 官方网站

**在线体验**: [https://yibiao.pro](https://yibiao.pro)

获取更多产品信息、在线体验和技术支持。

---

## 📦 使用说明

### 💻 系统要求

| 环境 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 (64位) / macOS / Linux |
| Python | **3.11 - 3.13** (3.14+ 不兼容) |
| Node.js | 18+ |
| 数据库 | PostgreSQL 17+ (开发环境可选) |
| 内存 | 至少 4GB |
| 磁盘 | 100MB 可用空间 |

### ⬇️ 下载安装

1. **直接下载**：从 [GitHub Releases](https://github.com/yibiaoai/yibiao-simple/releases) 下载最新版本的 exe 文件
2. **运行程序**：双击 `yibiao-simple.exe` 即可启动应用
3. **配置AI**：首次使用需要配置 API Key（推荐 DeepSeek）

---

## 🛠️ 开发指南

### 开发环境启动

#### 方式一：分别启动前后端

```bash
# 后端启动
cd backend
pip install -r requirements.txt
python run.py

# 前端启动（新终端）
cd frontend
npm install
npm start
```

#### 方式二：使用统一启动器

```bash
# 从项目根目录启动
python app_launcher.py
```

### 数据库设置

```bash
# 创建数据库
createdb yibiao

# 运行迁移
cd backend
alembic upgrade head
```

### 环境变量配置

创建 `.env` 文件（开发环境使用默认值）：

```bash
# 数据库连接
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/yibiao

# JWT 密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-here

# CORS 配置
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# LLM 配置：支持 OpenAI-compatible 接口
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your-api-key
LLM_MODEL=deepseek-chat
LLM_MODELS=deepseek-chat,deepseek-reasoner

# Embedding 配置：默认 Ollama，也可切换为 openai-compatible
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_API_KEY=
EMBEDDING_MODEL=qwen3-embedding:4b
EMBEDDING_MODELS=qwen3-embedding:4b
EMBEDDING_DIMENSION=2560

# Bid Agent 默认不逐章节调用 LLM，保证一键流程稳定快速；需要时可打开
BID_AGENT_USE_LLM_CHAPTERS=false
BID_AGENT_CHAPTER_TIMEOUT_SECONDS=15
```

### Docker 自托管启动

建议宿主机为 Docker/Colima 分配至少 2 CPU、4GB 内存和 20GB 可用磁盘空间；前端生产构建会在镜像构建阶段执行，2GB 内存环境可能被系统 OOM 终止。

```bash
cp .env.docker.example .env
# 修改 .env 中的 SECRET_KEY、ENCRYPTION_KEY、数据库密码、LLM 与 Embedding 配置
docker compose up -d --build
```

启动后访问 `http://localhost:8000`（或 `.env` 中配置的 `PORT`）。本地自托管默认由 FastAPI 直接托管前端静态文件和 API，不需要 Nginx；这样可以减少 SSE/AI 流式接口的代理缓冲和首包延迟。Docker 镜像会在构建阶段自动执行前端 `npm ci && npm run build`，并在启动时执行 `alembic upgrade head`；PostgreSQL 使用带 pgvector 扩展的镜像。若本机 5432 已被占用，可在 `.env` 中设置 `DB_PORT=15432` 等宿主机端口。

如果生产环境确实需要 Nginx 作为反向代理，可显式启用：

```bash
NGINX_PORT=80 docker compose --profile reverse-proxy up -d --build
```

### 模型配置说明

系统支持两种模型供给方式：

1. 环境变量配置：适合自托管部署，服务启动后无需先进入后台写入 API Key。`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 控制生成模型，`EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` 控制知识库索引模型。
2. 后台配置：管理员可以在系统设置中维护多个 Provider、API Key、生成模型和索引模型。数据库配置存在时，系统仍会保留环境变量 Provider 作为可选项。

`EMBEDDING_PROVIDER=ollama` 使用本地 Ollama embedding 服务；`EMBEDDING_PROVIDER=openai-compatible` 使用兼容 OpenAI embeddings 的服务，需要服务支持 `/embeddings` 能力。

Bid Agent 的章节正文默认基于已完成的招标分析、目录和响应矩阵进行确定性生成，避免自托管环境因逐章节模型调用变慢或挂起；需要更强生成效果时可设置 `BID_AGENT_USE_LLM_CHAPTERS=true`。

---

## 🏗️ 技术架构

### 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| **后端框架** | FastAPI | 0.116.1 |
| **ASGI服务器** | Uvicorn | 0.35.0 |
| **数据库** | PostgreSQL + SQLAlchemy (async) | 2.0.41 |
| **数据库迁移** | Alembic | 1.15.2 |
| **前端框架** | React | 19.1.1 |
| **语言** | TypeScript | 4.9.5 |
| **UI组件** | Ant Design | 5.29.3 |
| **样式** | Tailwind CSS | 3.4.17 |
| **AI服务** | OpenAI SDK | 1.106.1 |
| **向量数据库** | LlamaIndex + pgvector | - |

### 架构设计

采用现代化的**前后端分离架构**：

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   React前端     │ ───> │   FastAPI后端   │ ───> │   PostgreSQL    │
│  (TypeScript)   │      │   (Python)      │      │   数据库        │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                               │
                               ▼
                         ┌─────────────────┐
                         │  OpenAI API     │
                         │  AI服务         │
                         └─────────────────┘
```

### 项目结构

```
yibiao-simple/
├── backend/                      # 后端服务
│   ├── app/
│   │   ├── main.py              # FastAPI应用入口
│   │   ├── config.py            # 应用配置
│   │   ├── auth/                # JWT认证模块
│   │   ├── db/                  # 数据库连接
│   │   ├── middleware/          # 中间件（审计、日志）
│   │   ├── models/              # ORM模型
│   │   ├── routers/             # API路由
│   │   ├── schemas/             # Pydantic数据模型
│   │   └── services/            # 业务逻辑服务
│   ├── alembic/                 # 数据库迁移
│   ├── tests/                   # 测试套件
│   └── requirements.txt         # Python依赖
├── frontend/                     # 前端应用
│   ├── src/
│   │   ├── pages/               # 页面组件
│   │   ├── components/          # 可复用组件
│   │   ├── services/            # API服务
│   │   ├── hooks/               # React Hooks
│   │   ├── contexts/            # Context状态管理
│   │   └── types/               # TypeScript类型定义
│   └── package.json             # 前端依赖
├── app_launcher.py              # 统一启动器
├── build.py                     # 打包脚本
├── build.bat                    # Windows打包脚本
└── README.md                    # 项目文档
```

---

## 🔨 生产环境打包

### Windows 打包

```bash
# 方式一：批处理脚本
build.bat

# 方式二：Python脚本
python build.py
```

构建完成后，exe文件位于 `dist/yibiao-simple.exe`

---

## 📚 API文档

启动应用后访问以下地址查看完整文档：

- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 📝 使用流程

1. **📌 配置AI**：通过环境变量或后台配置 OpenAI-compatible LLM 与 Embedding 服务
2. **📄 上传招标文件**：从首页单一入口上传招标文件，自动创建项目并进入工作区
3. **🔍 文档分析**：AI 自动解析项目概述、技术要求、评分项、废标条款和材料需求
4. **📋 生成目录与响应矩阵**：基于招标要求生成目录，绑定评分项和响应条款
5. **✍️ 生成正文**：按章节生成正文，引用素材库证据，并支持版本历史
6. **🧪 质量审查**：对现有投标文件执行响应性、合规性、一致性审查，输出问题和修改建议
7. **📤 导出交付**：导出 Word、批注版和质量报告

---

## 🔧 常见问题

### Python 版本问题

**Q: 为什么 Python 3.14 不兼容？**  
A: 部分依赖库（如 pydantic-core、asyncpg、tiktoken）尚未支持 Python 3.14。建议使用 Python 3.13。

**Q: 如何检查 Python 版本？**  
A: 运行 `python --version` 命令查看。

### 测试问题

**Q: pytest 运行失败？**  
A: 已知 pytest-html 与 seleniumbase 在 Python 3.13+ 上存在兼容性问题。相关依赖已移至 `requirements-optional.txt`。

---

## 🤝 贡献指南

欢迎各种形式的贡献！

1. **🐛 问题反馈**: 在 [Issues](https://github.com/yibiaoai/yibiao-simple/issues) 中报告 bug
2. **💡 功能建议**: 提出新功能需求和改进建议
3. **🔧 代码贡献**: Fork 项目，提交 Pull Request
4. **📖 文档完善**: 帮助改进文档和使用说明

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源协议发布。

---

## 🙋‍♂️ 联系我们

- **官方网站**: [https://yibiao.pro](https://yibiao.pro)
- **问题反馈**: [GitHub Issues](https://github.com/yibiaoai/yibiao-simple/issues)
- **邮箱联系**: support@yibiao.pro

---

<p align="center">
  ⭐ 如果这个项目对您有帮助，请给我们一个Star支持！
</p>

<p align="center">
  Made with ❤️ by 易标团队
</p>
