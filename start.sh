#!/bin/bash
# Multi-Agent 平台一键启动脚本（macOS / Hermes on Ollama）

set -e

PLATFORM_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PLATFORM_DIR/backend"
FRONTEND_DIR="$PLATFORM_DIR/frontend"
SDK_DIR="$PLATFORM_DIR/sdk"
PORT=8000

echo "╔══════════════════════════════════════════════╗"
echo "║    Multi-Agent 智能体协同平台 启动脚本         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 检查 Ollama
echo "▸ 检查 Ollama 服务..."
if ! command -v ollama &>/dev/null; then
  echo "  ✗ Ollama 未安装，请先安装: https://ollama.com"
  echo "    brew install ollama"
  exit 1
fi

if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
  echo "  ✗ Ollama 未运行，正在后台启动..."
  ollama serve &>/tmp/ollama.log &
  sleep 2
fi
echo "  ✓ Ollama 服务就绪"

# 2. 检查 Hermes 模型
echo "▸ 检查 Hermes 模型..."
if ! ollama list 2>/dev/null | grep -q hermes; then
  echo "  ! Hermes 模型未找到，正在拉取 hermes3..."
  echo "  (首次下载可能需要几分钟)"
  ollama pull hermes3
fi
echo "  ✓ Hermes 模型就绪"

# 3. Python 虚拟环境
echo "▸ 配置 Python 环境..."
if [ ! -d "$PLATFORM_DIR/.venv" ]; then
  python3 -m venv "$PLATFORM_DIR/.venv"
fi
source "$PLATFORM_DIR/.venv/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements.txt"
# 为 SDK 安装额外依赖
pip install -q httpx
echo "  ✓ Python 依赖就绪"

# 4. 启动后端
echo "▸ 启动 FastAPI 后端 (port $PORT)..."
cd "$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port $PORT --reload &
BACKEND_PID=$!
sleep 2

# 检查后端是否正常
if curl -s http://localhost:$PORT/health &>/dev/null; then
  echo "  ✓ 后端服务就绪 → http://localhost:$PORT"
else
  echo "  ✗ 后端启动失败，请查看日志"
  exit 1
fi

# 5. 打开前端
echo "▸ 打开前端看板..."
open "$FRONTEND_DIR/index.html"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🚀 平台启动成功！                             ║"
echo "║                                              ║"
echo "║  前端看板:  file://$FRONTEND_DIR/index.html"
echo "║  后端 API:  http://localhost:$PORT             ║"
echo "║  API 文档:  http://localhost:$PORT/docs        ║"
echo "║  WS 地址:   ws://localhost:$PORT/ws            ║"
echo "║                                              ║"
echo "║  按 Ctrl+C 停止所有服务                        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "提示：将你的智能体接入平台："
echo "  from agent_sdk import AgentClient"
echo "  agent = AgentClient(name='我的智能体', role='analyzer')"
echo "  asyncio.run(agent.run())"
echo ""

# 等待退出
trap "echo ''; echo '正在停止...'; kill $BACKEND_PID 2>/dev/null; echo '已停止。'; exit 0" INT TERM
wait $BACKEND_PID
