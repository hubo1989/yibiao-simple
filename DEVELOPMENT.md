# 开发环境设置指南

本文档介绍如何在本地设置 AI 写标书助手的开发环境。

---

## 环境要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.11 - 3.13 | **3.14+ 不兼容** |
| Node.js | 18+ | 推荐使用 LTS 版本 |
| PostgreSQL | 17+ | 开发环境可选 |
| Git | 最新版 | - |

### 检查版本

```bash
python --version  # 应显示 Python 3.11-3.13
node --version    # 应显示 v18+
npm --version     # 应显示 9.x+
psql --version    # PostgreSQL（可选）
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yibiaoai/yibiao-simple.git
cd yibiao-simple
```

### 2. 后端设置

```bash
# 创建虚拟环境（推荐）
python3.13 -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
cd backend
pip install -r requirements.txt
```

### 3. 数据库设置（可选）

```bash
# 创建数据库
createdb yibiao

# 运行数据库迁移
alembic upgrade head
```

### 4. 前端设置

```bash
cd frontend
npm install
```

### 5. 启动应用

**方式一：分别启动**

```bash
# 终端1：启动后端
cd backend
python run.py

# 终端2：启动前端
cd frontend
npm start
```

**方式二：统一启动器**

```bash
# 从项目根目录
python app_launcher.py
```

应用将在 http://localhost:8000 自动打开。

---

## 开发工具推荐

### VS Code 扩展

- Python - Microsoft
- Pylance - Microsoft
- ES7+ React/Redux/React-Native snippets
- TypeScript Importer
- Tailwind CSS IntelliSense
- PostgreSQL

### 代码风格

- **Python**: 遵循 PEP 8
- **TypeScript/React**: 遵循项目 ESLint 配置

---

## 常见问题

### Python 版本问题

**问题**: `ImportError: cannot import name 'url_quote' from 'werkzeug.urls'`  
**解决**: 你使用了 Python 3.14，请降级到 Python 3.13 或更低版本。

### pytest 运行失败

**问题**: pytest 与 seleniumbase 版本冲突  
**解决**: 相关依赖已移至 `requirements-optional.txt`，开发环境不需要 seleniumbase。

### 前端构建失败

**问题**: `npm install` 失败  
**解决**: 尝试删除 `node_modules` 和 `package-lock.json`，重新运行 `npm install`。

### 数据库连接失败

**问题**: `connection refused`  
**解决**: 确保 PostgreSQL 正在运行，检查 `DATABASE_URL` 环境变量。

---

## 数据库迁移

### 创建新迁移

```bash
cd backend
alembic revision --autogenerate -m "描述"
```

### 应用迁移

```bash
alembic upgrade head
```

### 回滚迁移

```bash
alembic downgrade -1
```

---

## 测试

### 运行后端测试

```bash
cd backend
pytest
```

### 运行前端测试

```bash
cd frontend
npm test
```

---

## 生产构建

```bash
# 从项目根目录
python build.py
# 或使用批处理脚本（Windows）
build.bat
```

构建完成后，exe 文件位于 `dist/yibiao-simple.exe`。

---

## 提交代码

1. 确保代码通过测试
2. 遵循项目的代码风格
3. 编写清晰的提交信息
4. 创建 Pull Request

---

## 获取帮助

- 查看 [README.md](README.md) 了解项目概述
- 查看 [API文档](http://localhost:8000/docs) 了解接口
- 在 [GitHub Issues](https://github.com/yibiaoai/yibiao-simple/issues) 提问
