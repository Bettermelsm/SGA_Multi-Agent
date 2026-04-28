"""
Multi-Agent Platform SDK
使用方法:
    from agent_sdk import AgentClient

    agent = AgentClient(
        name="我的分析智能体",
        role="analyzer",
        capabilities=["数据分析", "图表生成"],
        platform_url="http://localhost:8000",
    )

    @agent.on_task
    async def handle_task(task):
        result = do_analysis(task["description"])
        return {"summary": result}

    asyncio.run(agent.run())
"""

import asyncio
import json
import time
import uuid
from typing import Callable, Optional

import httpx


class AgentClient:
    def __init__(
        self,
        name: str,
        role: str,
        capabilities: list[str] = None,
        platform_url: str = "http://localhost:8000",
        description: str = "",
        heartbeat_interval: int = 15,
    ):
        self.name = name
        self.role = role
        self.capabilities = capabilities or []
        self.platform_url = platform_url.rstrip("/")
        self.description = description
        self.heartbeat_interval = heartbeat_interval

        self.agent_id: Optional[str] = None
        self._task_handler: Optional[Callable] = None
        self._running = False
        self._status = "idle"

    # ─── 装饰器注册任务处理函数 ──────────────────────────────
    def on_task(self, fn: Callable):
        self._task_handler = fn
        return fn

    # ─── 注册到平台 ───────────────────────────────────────────
    async def register(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.platform_url}/api/agents/register",
                json={
                    "name": self.name,
                    "role": self.role,
                    "capabilities": self.capabilities,
                    "description": self.description,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.agent_id = data["agent_id"]
            print(f"[{self.name}] 注册成功 agent_id={self.agent_id}")

    # ─── 发送心跳 ──────────────────────────────────────────────
    async def _send_heartbeat(self):
        if not self.agent_id:
            return
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.platform_url}/api/agents/{self.agent_id}/heartbeat",
                    json={"status": self._status, "metrics": {}},
                    timeout=5,
                )
        except Exception as e:
            print(f"[{self.name}] 心跳失败: {e}")

    # ─── 心跳循环 ──────────────────────────────────────────────
    async def _heartbeat_loop(self):
        while self._running:
            await self._send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)

    # ─── 创建任务（向平台提交） ────────────────────────────────
    async def create_task(
        self, title: str, description: str = "",
        priority: str = "P2", assigned_to: str = None
    ) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.platform_url}/api/tasks",
                json={
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "assigned_to": assigned_to or self.agent_id,
                },
                timeout=10,
            )
            resp.raise_for_status()
            task_id = resp.json()["task_id"]
            print(f"[{self.name}] 创建任务 {task_id}")
            return task_id

    # ─── 完成任务 ──────────────────────────────────────────────
    async def complete_task(self, task_id: str, summary: str, data: dict = None):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.platform_url}/api/tasks/{task_id}/complete"
                f"?agent_id={self.agent_id}",
                json={"summary": summary, "data": data or {}},
                timeout=10,
            )
        self._status = "idle"
        print(f"[{self.name}] 完成任务 {task_id}")

    # ─── 调用 Hermes LLM ──────────────────────────────────────
    async def llm(self, prompt: str, system: str = None) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.platform_url}/api/chat",
                json={
                    "prompt": prompt,
                    "agent_id": self.agent_id,
                    "system": system or f"You are {self.name}, a {self.role} agent.",
                },
            )
            resp.raise_for_status()
            return resp.json()["response"]

    # ─── 运行智能体（注册 + 心跳） ────────────────────────────
    async def run(self):
        await self.register()
        self._running = True
        print(f"[{self.name}] 开始运行，心跳间隔 {self.heartbeat_interval}s")
        await self._heartbeat_loop()

    async def stop(self):
        self._running = False
        if self.agent_id:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{self.platform_url}/api/agents/{self.agent_id}",
                    timeout=5,
                )
        print(f"[{self.name}] 已下线")


# ─── 示例智能体 ───────────────────────────────────────────
class ExampleAnalystAgent(AgentClient):
    """示例：分析智能体，演示如何继承 AgentClient"""

    def __init__(self, platform_url="http://localhost:8000"):
        super().__init__(
            name="分析智能体",
            role="analyzer",
            capabilities=["数据分析", "趋势预测", "报告生成"],
            platform_url=platform_url,
            description="负责数据分析与洞察提取",
        )

    async def run_analysis(self, data_description: str):
        """执行一次分析任务"""
        self._status = "running"

        task_id = await self.create_task(
            title=f"分析: {data_description[:30]}",
            description=data_description,
            priority="P1",
        )

        # 调用 Hermes 执行分析
        response = await self.llm(
            prompt=f"请分析以下内容并给出关键洞察：\n{data_description}",
            system="你是专业的数据分析师，提供简洁有力的分析报告。",
        )

        await self.complete_task(
            task_id=task_id,
            summary=response[:100],
            data={"full_response": response},
        )
        return response


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    agent = ExampleAnalystAgent(platform_url=url)
    asyncio.run(agent.run())
