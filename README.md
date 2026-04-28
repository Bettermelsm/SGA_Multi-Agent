# Multi-Agent 智能体协同平台

> 基于 Hermes (Ollama) 的多智能体统一管理平台，带实时看板监控。

## 架构

```
┌─────────────────────────────────────────────────────┐
│  前端看板 (frontend/index.html)                        │
│  WebSocket 实时推送 · Chart.js 可视化                  │
└────────────────────┬────────────────────────────────┘
                     │ WS / REST
┌────────────────────▼────────────────────────────────┐
│  FastAPI 后端 (backend/main.py)                       │
│  智能体注册表 · 任务队列 · 事件广播                     │
└──────────┬─────────────────────┬───────────────────-┘
           │ HTTP                │ HTTP/WS
┌──────────▼─────────┐  ┌───────▼──────────────────-──┐
│  Ollama / Hermes   │  │  你的智能体 (agent_sdk.py)   │
│  LLM 推理引擎       │  │  注册 · 心跳 · 任务汇报       │
└────────────────────┘  └─────────────────────────────┘
```

## 快速开始

### 1. 启动平台

```bash
# 赋予执行权限（只需一次）
chmod +x scripts/start.sh

# 一键启动（会自动检查 Ollama、Hermes、Python 环境）
./scripts/start.sh
```

脚本会自动：
- 检查并启动 Ollama 服务
- 拉取 Hermes 模型（如未安装）
- 创建 Python 虚拟环境并安装依赖
- 启动 FastAPI 后端
- 在浏览器打开前端看板

### 2. 运行演示

```bash
# 在另一个终端
source .venv/bin/activate
python scripts/demo_agents.py
```

这会模拟 5 个智能体注册并执行任务，看板实时更新。

### 3. 接入你自己的智能体

```python
import asyncio
from sdk.agent_sdk import AgentClient

agent = AgentClient(
    name="我的智能体",
    role="analyzer",           # planner / coder / retriever / analyzer / chat / evaluator / custom
    capabilities=["数据分析", "报告生成"],
    platform_url="http://localhost:8000",
)

# 可选：使用 Hermes LLM
async def main():
    await agent.register()
    
    # 创建并完成一个任务
    task_id = await agent.create_task("分析用户数据", priority="P1")
    result = await agent.llm("分析以下数据并给出洞察：...")
    await agent.complete_task(task_id, summary=result[:100])
    
    # 保持心跳
    await agent.run()

asyncio.run(main())
```

## API 参考

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agents/register` | 注册智能体 |
| POST | `/api/agents/{id}/heartbeat` | 发送心跳 |
| DELETE | `/api/agents/{id}` | 下线 |
| POST | `/api/tasks` | 创建任务 |
| POST | `/api/tasks/{id}/complete` | 完成任务 |
| POST | `/api/chat` | 调用 Hermes LLM |
| GET  | `/api/stats` | 获取全局统计 |
| WS   | `/ws` | 实时推送 |
| GET  | `/docs` | Swagger API 文档 |

## 项目结构

```
multi-agent-platform/
├── backend/
│   ├── main.py              # FastAPI 后端
│   └── requirements.txt
├── frontend/
│   └── index.html           # 看板（单文件，无需构建）
├── sdk/
│   └── agent_sdk.py         # 智能体 SDK
└── scripts/
    ├── start.sh             # 一键启动
    └── demo_agents.py       # 演示脚本
```

## 自定义 Hermes 模型

编辑 `backend/main.py` 顶部：

```python
HERMES_MODEL = "hermes3"   # 改为你的模型名，如 "nous-hermes2"
```

查看已安装模型：`ollama list`

## 看板功能

- **全局态势总览** — 智能体数、任务数、交互次数、数据处理量
- **多智能体协同网络** — 实时展示各智能体状态与连接关系
- **任务执行趋势** — 折线图，实时滚动
- **智能体能力分布** — 雷达图
- **系统资源监控** — CPU/内存/GPU/存储仪表盘
- **协同事件流** — 实时事件日志
- **智能体状态/任务优先级** — 甜甜圈图
- **Top5 智能体** — 按任务完成数排行
- **告警与通知** — 系统告警面板
