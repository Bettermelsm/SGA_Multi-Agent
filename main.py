"""
Multi-Agent 智能体协同平台 - 后端服务
依赖: pip install fastapi uvicorn httpx python-multipart
启动: uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Multi-Agent Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 配置 ───────────────────────────────────────────────
OLLAMA_BASE = "http://localhost:11434"
HERMES_MODEL = "hermes3"           # 改为你实际的 Hermes 模型名
HEARTBEAT_TIMEOUT = 60             # 秒，超时则标记为离线

# ─── 内存存储 ────────────────────────────────────────────
class AgentRegistry:
    def __init__(self):
        self.agents: dict[str, dict] = {}       # agent_id -> agent_info
        self.tasks: dict[str, dict] = {}        # task_id -> task_info
        self.events: deque = deque(maxlen=200)  # 最近协同事件流

    def register(self, info: dict) -> str:
        agent_id = info.get("agent_id") or str(uuid.uuid4())[:8]
        self.agents[agent_id] = {
            **info,
            "agent_id": agent_id,
            "status": "idle",
            "last_heartbeat": time.time(),
            "tasks_completed": info.get("tasks_completed", 0),
            "registered_at": datetime.now().isoformat(),
        }
        self._add_event("system", agent_id, f"智能体 {info.get('name','?')} 注册上线", "info")
        return agent_id

    def heartbeat(self, agent_id: str, payload: dict):
        if agent_id not in self.agents:
            return False
        self.agents[agent_id]["last_heartbeat"] = time.time()
        if "status" in payload:
            self.agents[agent_id]["status"] = payload["status"]
        if "metrics" in payload:
            self.agents[agent_id]["metrics"] = payload["metrics"]
        return True

    def update_status(self, agent_id: str, status: str, task_id: str = None):
        if agent_id in self.agents:
            self.agents[agent_id]["status"] = status
            if task_id:
                self.agents[agent_id]["current_task"] = task_id

    def complete_task(self, agent_id: str, task_id: str, result: dict):
        if agent_id in self.agents:
            self.agents[agent_id]["status"] = "idle"
            self.agents[agent_id]["tasks_completed"] = \
                self.agents[agent_id].get("tasks_completed", 0) + 1
            self.agents[agent_id].pop("current_task", None)
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "completed"
            self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
            self.tasks[task_id]["result"] = result
        agent_name = self.agents.get(agent_id, {}).get("name", agent_id)
        self._add_event(agent_id, None, f"完成任务", "success",
                        task_id=task_id, result_summary=result.get("summary", ""))

    def check_timeouts(self):
        now = time.time()
        for aid, info in self.agents.items():
            elapsed = now - info.get("last_heartbeat", now)
            if elapsed > HEARTBEAT_TIMEOUT and info["status"] != "offline":
                self.agents[aid]["status"] = "offline"
                self._add_event("system", aid, f"心跳超时，标记离线", "warning")

    def get_stats(self) -> dict:
        self.check_timeouts()
        statuses = {"running": 0, "idle": 0, "busy": 0, "offline": 0}
        for a in self.agents.values():
            s = a.get("status", "idle")
            statuses[s] = statuses.get(s, 0) + 1

        task_priorities = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        task_statuses   = {"pending": 0, "running": 0, "completed": 0}
        for t in self.tasks.values():
            p = t.get("priority", "P2")
            task_priorities[p] = task_priorities.get(p, 0) + 1
            ts = t.get("status", "pending")
            task_statuses[ts] = task_statuses.get(ts, 0) + 1

        top5 = sorted(
            [{"name": a["name"], "agent_id": k, "tasks_completed": a.get("tasks_completed", 0)}
             for k, a in self.agents.items()],
            key=lambda x: x["tasks_completed"], reverse=True
        )[:5]

        resources = {
            "cpu": _fake_cpu(),
            "memory": _fake_mem(),
            "gpu": _fake_gpu(),
            "storage": _fake_storage(),
        }

        return {
            "agents": list(self.agents.values()),
            "agent_count": len(self.agents),
            "agent_statuses": statuses,
            "tasks": list(self.tasks.values()),
            "task_count": len(self.tasks),
            "task_priorities": task_priorities,
            "task_statuses": task_statuses,
            "top5_agents": top5,
            "events": list(self.events)[-30:],
            "resources": resources,
            "interactions": _fake_interactions(),
            "data_processed": _fake_data(),
        }

    def _add_event(self, from_agent: str, to_agent: Optional[str],
                   action: str, level: str = "info",
                   task_id: str = None, result_summary: str = ""):
        from_name = self.agents.get(from_agent, {}).get("name", from_agent)
        to_name   = self.agents.get(to_agent, {}).get("name", to_agent) if to_agent else None
        self.events.append({
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "from_agent": from_agent,
            "from_name": from_name,
            "to_agent": to_agent,
            "to_name": to_name,
            "action": action,
            "level": level,
            "task_id": task_id,
            "result_summary": result_summary,
        })


registry = AgentRegistry()

# ─── WebSocket 连接管理器 ─────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


# ─── 数据模型 ────────────────────────────────────────────
class AgentRegisterRequest(BaseModel):
    name: str
    role: str                           # planner / coder / retriever / analyzer / chat / evaluator / custom
    capabilities: list[str] = []
    agent_id: Optional[str] = None
    description: str = ""

class HeartbeatRequest(BaseModel):
    status: str = "idle"               # idle / running / busy
    metrics: dict = {}

class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "P2"               # P0 / P1 / P2 / P3
    assigned_to: Optional[str] = None  # agent_id, None = auto-assign

class TaskResultRequest(BaseModel):
    summary: str
    data: dict = {}

class ChatRequest(BaseModel):
    prompt: str
    agent_id: Optional[str] = None
    system: str = "You are a helpful assistant."
    stream: bool = False


# ─── 辅助函数 ────────────────────────────────────────────
import random

_interaction_counter = 3682
_data_base = 2340

def _fake_cpu():   return random.randint(35, 75)
def _fake_mem():   return random.randint(55, 80)
def _fake_gpu():   return random.randint(40, 85)
def _fake_storage(): return random.randint(45, 70)
def _fake_interactions():
    global _interaction_counter
    _interaction_counter += random.randint(0, 5)
    return _interaction_counter
def _fake_data():
    global _data_base
    _data_base += random.randint(0, 10)
    return round(_data_base / 1000, 2)


# ─── 后台广播任务 ─────────────────────────────────────────
async def broadcast_loop():
    while True:
        await asyncio.sleep(3)
        stats = registry.get_stats()
        stats["ts"] = time.time()
        await manager.broadcast({"type": "stats_update", "data": stats})


@app.on_event("startup")
async def startup():
    asyncio.create_task(broadcast_loop())


# ─── 路由：智能体注册 ─────────────────────────────────────
@app.post("/api/agents/register")
async def register_agent(req: AgentRegisterRequest):
    agent_id = registry.register(req.dict())
    stats = registry.get_stats()
    await manager.broadcast({"type": "agent_joined", "agent_id": agent_id, "data": stats})
    return {"agent_id": agent_id, "status": "registered"}


@app.get("/api/agents")
async def list_agents():
    registry.check_timeouts()
    return {"agents": list(registry.agents.values())}


@app.post("/api/agents/{agent_id}/heartbeat")
async def heartbeat(agent_id: str, req: HeartbeatRequest):
    ok = registry.heartbeat(agent_id, req.dict())
    if not ok:
        raise HTTPException(404, "Agent not found")
    return {"ok": True}


@app.delete("/api/agents/{agent_id}")
async def deregister_agent(agent_id: str):
    if agent_id in registry.agents:
        name = registry.agents[agent_id]["name"]
        registry.agents[agent_id]["status"] = "offline"
        registry._add_event("system", agent_id, f"智能体 {name} 下线", "info")
        stats = registry.get_stats()
        await manager.broadcast({"type": "agent_left", "data": stats})
        return {"ok": True}
    raise HTTPException(404, "Agent not found")


# ─── 路由：任务管理 ───────────────────────────────────────
@app.post("/api/tasks")
async def create_task(req: TaskCreateRequest):
    task_id = "T-" + str(uuid.uuid4())[:6].upper()
    task = {
        **req.dict(),
        "task_id": task_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    registry.tasks[task_id] = task
    registry._add_event("system", req.assigned_to, f"创建任务: {req.title}", "info",
                        task_id=task_id)
    if req.assigned_to and req.assigned_to in registry.agents:
        registry.update_status(req.assigned_to, "running", task_id)
    stats = registry.get_stats()
    await manager.broadcast({"type": "task_created", "task_id": task_id, "data": stats})
    return {"task_id": task_id}


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: str, agent_id: str, req: TaskResultRequest):
    registry.complete_task(agent_id, task_id, req.dict())
    stats = registry.get_stats()
    await manager.broadcast({"type": "task_completed", "task_id": task_id, "data": stats})
    return {"ok": True}


@app.get("/api/tasks")
async def list_tasks(status: str = None):
    tasks = list(registry.tasks.values())
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return {"tasks": tasks}


# ─── 路由：Hermes / Ollama 代理 ──────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    """转发到 Ollama Hermes 模型，返回响应并记录到事件流"""
    agent_name = registry.agents.get(req.agent_id, {}).get("name", "外部请求") if req.agent_id else "用户"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "model": HERMES_MODEL,
                "messages": [
                    {"role": "system", "content": req.system},
                    {"role": "user",   "content": req.prompt},
                ],
                "stream": False,
            }
            resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]

        if req.agent_id:
            registry._add_event(req.agent_id, None,
                                 f"Hermes 推理完成 ({len(content)} chars)", "success")
            stats = registry.get_stats()
            await manager.broadcast({"type": "llm_response", "data": stats})

        return {"response": content, "model": HERMES_MODEL}

    except httpx.ConnectError:
        raise HTTPException(503, "Ollama 服务未启动，请先运行 `ollama serve`")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/models")
async def list_models():
    """列出 Ollama 可用模型"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.json()
    except Exception:
        return {"models": [], "error": "Ollama 不可达"}


# ─── 路由：统计与事件流 ────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    return registry.get_stats()


@app.get("/api/events")
async def get_events(limit: int = 30):
    return {"events": list(registry.events)[-limit:]}


# ─── WebSocket ────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # 连接后立即推送当前状态
    await ws.send_json({"type": "connected", "data": registry.get_stats()})
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30)
                data = json.loads(msg)
                if data.get("type") == "ping":
                    await ws.send_json({"type": "pong", "ts": time.time()})
            except asyncio.TimeoutError:
                await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ─── 健康检查 ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agents": len(registry.agents),
        "tasks": len(registry.tasks),
        "ws_clients": len(manager.active),
    }
