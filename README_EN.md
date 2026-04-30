> 🌐 [中文](./README.md) &nbsp;|&nbsp; **English**

# Multi-Agent Collaborative Platform v2

<p align="center">
  <img src="./SGAMultiagnetV1.png" alt="Platform Dashboard" width="800">
</p>

A unified multi-agent management platform based on Hermes (Ollama), featuring a real-time monitoring dashboard and persistent storage.

## Architecture

```
Frontend Dashboard (frontend/index.html)
  WebSocket real-time push · Chart.js · i18n (ZH/EN) · 6-page navigation
        ↕ WS / REST
FastAPI Backend (backend/main.py)
  SQLite persistence · 33 API endpoints · Alert rule engine · Streaming LLM · Message routing
        ↕ HTTP
Ollama / Hermes          Your Agents (sdk/agent_sdk.py)
  Local LLM inference    Register · Heartbeat · Tasks · Multi-turn chat · Tool calls
```

## Quick Start

```bash
chmod +x scripts/start.sh
./scripts/start.sh
# In another terminal:
source .venv/bin/activate
python scripts/demo_agents.py
```

## What's New in v2

| Module | Feature |
|--------|---------|
| Backend | SQLite persistence (data survives restarts) |
| Backend | Knowledge base CRUD API + sync trigger |
| Backend | Alert rules API + auto-detection engine |
| Backend | Inter-agent message routing + inbox |
| Backend | Streaming LLM output (SSE) |
| Backend | Real system metrics (psutil) |
| Backend | Task search / filter / pagination |
| SDK | Auto-reconnect on disconnect |
| SDK | `llm_stream()` streaming output |
| SDK | `llm_with_tools()` tool calling |
| SDK | Multi-turn conversation (`remember=True`) |
| SDK | `send_message()` / `get_inbox()` |
| SDK | `@agent.tool()` decorator |
| Frontend | Knowledge base / alerts connected to real API |
| Frontend | Seamless ZH/EN toggle (32 i18n keys) |
| Frontend | 6-page full navigation (incl. alert rule management) |

## API Reference

```
POST /api/agents/register          Register agent
POST /api/agents/{id}/heartbeat    Heartbeat
POST /api/agents/{id}/message      Send message
GET  /api/agents/{id}/inbox        Get inbox
POST /api/tasks                    Create task
POST /api/tasks/{id}/complete      Complete task
GET  /api/knowledge                List knowledge base
POST /api/knowledge/{id}/sync      Trigger sync
GET  /api/alerts/rules             List alert rules
POST /api/alerts/rules             Create alert rule
POST /api/chat                     LLM inference (supports streaming)
GET  /api/stats                    Global snapshot
WS   /ws                           Real-time push
GET  /health                       Health check
GET  /docs                         Swagger UI
```

## SDK Quick Reference

```python
from sdk.agent_sdk import AgentClient, AnalystAgent

agent = AgentClient(name="My Agent", role="analyzer")

# Single-shot LLM
answer = await agent.llm("Analyze this data...")

# Multi-turn conversation
await agent.llm("Question 1", remember=True)
await agent.llm("Follow-up question", remember=True)
agent.clear_history()

# Streaming output
async for token in agent.llm_stream("Generate a report..."):
    print(token, end="", flush=True)

# Tool calling
@agent.tool(name="calc", description="Evaluate an expression")
async def calc(expr: str) -> str:
    return str(eval(expr))
result = await agent.llm_with_tools("Calculate (100+50)*3/5")

# Messaging
await agent.send_message(other_agent_id, "Please help with this task")
msgs = await agent.get_inbox()
```
