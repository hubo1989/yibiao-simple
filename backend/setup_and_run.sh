#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 易标AI 后端完整启动脚本
# 在你自己的终端中运行: bash backend/setup_and_run.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  易标AI 后端启动脚本"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: PostgreSQL ──
echo ""
echo "📦 Step 1/5: 检查 PostgreSQL..."

# 清理旧的 lock file
PG_DATA="/opt/homebrew/var/postgresql@15"
if [ -f "$PG_DATA/postmaster.pid" ]; then
  PG_PID=$(head -1 "$PG_DATA/postmaster.pid")
  if ! kill -0 "$PG_PID" 2>/dev/null; then
    echo "   清理残留的 PID 文件..."
    rm -f "$PG_DATA/postmaster.pid"
  fi
fi

# 启动 PostgreSQL
if ! /opt/homebrew/opt/postgresql@15/bin/pg_isready -p 5432 >/dev/null 2>&1; then
  echo "   启动 PostgreSQL@15..."
  /opt/homebrew/opt/postgresql@15/bin/pg_ctl -D "$PG_DATA" -o "-p 5432" start -w
  sleep 2
fi

if /opt/homebrew/opt/postgresql@15/bin/pg_isready -p 5432 >/dev/null 2>&1; then
  echo "   ✅ PostgreSQL 运行中 (端口 5432)"
else
  echo "   ❌ PostgreSQL 启动失败"
  echo "   尝试: brew services restart postgresql@15"
  exit 1
fi

# 创建数据库（如果不存在）
/opt/homebrew/opt/postgresql@15/bin/createdb yibiao 2>/dev/null || echo "   数据库 yibiao 已存在"

# ── Step 2: Python 虚拟环境 ──
echo ""
echo "🐍 Step 2/5: 配置 Python 环境..."

PYTHON_BIN=""
for ver in 3.13 3.12 3.11; do
  candidate="/opt/homebrew/opt/python@${ver}/bin/python${ver}"
  if [ -x "$candidate" ]; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "   ❌ 未找到 Python 3.11-3.13"
  echo "   请运行: brew install python@3.13"
  exit 1
fi

echo "   使用: $($PYTHON_BIN --version)"

if [ ! -d "venv" ]; then
  echo "   创建虚拟环境..."
  $PYTHON_BIN -m venv venv
fi

source venv/bin/activate

# ── Step 3: 安装依赖 ──
echo ""
echo "📥 Step 3/5: 安装 Python 依赖..."
pip install --upgrade pip -q 2>/dev/null
pip install -r requirements.txt \
  -i https://mirrors.aliyun.com/pypi/simple/ \
  --trusted-host mirrors.aliyun.com \
  2>&1 | tail -3

echo "   ✅ 依赖安装完成"

# ── Step 4: 配置文件 ──
echo ""
echo "📝 Step 4/5: 检查配置..."

if [ ! -f ".env" ]; then
  cat > .env << 'ENVEOF'
# ━━━ 数据库 ━━━
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/yibiao

# ━━━ JWT 密钥 ━━━
SECRET_KEY=yibiao-dev-secret-key-2024

# ━━━ LLM API ━━━
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# ━━━ 搜索 (可选) ━━━
# SERP_API_KEY=your-key
ENVEOF
  echo "   ⚠️  已创建 .env，请编辑填入你的 OPENAI_API_KEY"
else
  echo "   ✅ .env 已存在"
fi

# ── Step 5: 数据库迁移 & 启动 ──
echo ""
echo "🗄️  Step 5/5: 数据库迁移..."
python -m alembic upgrade head 2>&1 | tail -3
echo "   ✅ 数据库迁移完成"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 启动后端服务: http://127.0.0.1:8000"
echo "   API 文档: http://127.0.0.1:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
