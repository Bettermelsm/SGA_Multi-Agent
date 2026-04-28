"""
demo_agents.py - 演示脚本：模拟多个智能体接入平台
运行: python demo_agents.py

这会向平台注册 5 个智能体并模拟任务执行，
让你看到看板实时更新。
"""

import asyncio
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../sdk'))

import httpx

PLATFORM = "http://localhost:8000"

AGENTS = [
    {"name": "规划智能体", "role": "planner",   "capabilities": ["任务规划", "流程编排"]},
    {"name": "代码智能体", "role": "coder",     "capabilities": ["代码生成", "代码审查", "Debug"]},
    {"name": "检索智能体", "role": "retriever", "capabilities": ["全文搜索", "向量检索", "RAG"]},
    {"name": "分析智能体", "role": "analyzer",  "capabilities": ["数据分析", "趋势预测", "报告生成"]},
    {"name": "对话智能体", "role": "chat",      "capabilities": ["多轮对话", "意图识别"]},
]

TASKS = [
    ("完成数据分析任务",   "analyzer", "P1"),
    ("返回检索结果",      "retriever","P2"),
    ("代码生成任务",      "coder",    "P2"),
    ("更新任务执行计划",  "planner",  "P1"),
    ("调用外部API接口",   "analyzer", "P0"),
    ("生成分析报告",      "analyzer", "P2"),
    ("搜索知识库",       "retriever","P3"),
    ("重构模块代码",      "coder",    "P2"),
]


async def register_agent(client, info):
    resp = await client.post(f"{PLATFORM}/api/agents/register", json=info, timeout=5)
    resp.raise_for_status()
    aid = resp.json()["agent_id"]
    print(f"  ✓ 注册 [{info['name']}] → {aid}")
    return aid


async def heartbeat_loop(client, agent_id, name, stop_event):
    statuses = ["idle", "idle", "running", "idle", "running", "busy", "idle"]
    i = 0
    while not stop_event.is_set():
        status = statuses[i % len(statuses)]
        try:
            await client.post(
                f"{PLATFORM}/api/agents/{agent_id}/heartbeat",
                json={"status": status, "metrics": {"latency": random.randint(50, 300)}},
                timeout=3,
            )
        except Exception:
            pass
        i += 1
        await asyncio.sleep(random.uniform(8, 15))


async def task_loop(client, agent_ids_by_role, stop_event):
    i = 0
    while not stop_event.is_set():
        await asyncio.sleep(random.uniform(5, 12))
        title, role, priority = random.choice(TASKS)
        agent_id = agent_ids_by_role.get(role)
        if not agent_id:
            continue
        try:
            resp = await client.post(f"{PLATFORM}/api/tasks", json={
                "title": title,
                "description": f"自动演示任务 #{i}",
                "priority": priority,
                "assigned_to": agent_id,
            }, timeout=5)
            task_id = resp.json()["task_id"]
            print(f"  → 创建任务 [{title}] → {task_id}")

            await asyncio.sleep(random.uniform(3, 8))

            await client.post(
                f"{PLATFORM}/api/tasks/{task_id}/complete?agent_id={agent_id}",
                json={"summary": f"演示完成: {title}", "data": {"score": random.randint(70, 99)}},
                timeout=5,
            )
            print(f"  ✓ 完成任务 {task_id}")
        except Exception as e:
            print(f"  ! 任务异常: {e}")
        i += 1


async def main():
    print("╔══════════════════════════════════════╗")
    print("║  Multi-Agent 演示脚本                  ║")
    print("╚══════════════════════════════════════╝")
    print()

    stop = asyncio.Event()
    agent_ids_by_role = {}

    async with httpx.AsyncClient() as client:
        # 检查平台
        try:
            r = await client.get(f"{PLATFORM}/health", timeout=3)
            print(f"▸ 平台状态: {r.json()['status']}")
        except Exception:
            print("✗ 无法连接平台，请先运行 start.sh")
            return

        # 注册所有智能体
        print("\n▸ 注册智能体...")
        for info in AGENTS:
            aid = await register_agent(client, info)
            agent_ids_by_role[info["role"]] = aid

        print(f"\n▸ 启动心跳 + 任务模拟 (Ctrl+C 停止)...")
        print()

        # 启动心跳协程
        hb_tasks = [
            asyncio.create_task(heartbeat_loop(client, aid, role, stop))
            for role, aid in agent_ids_by_role.items()
        ]
        task_task = asyncio.create_task(task_loop(client, agent_ids_by_role, stop))

        try:
            await asyncio.gather(*hb_tasks, task_task)
        except asyncio.CancelledError:
            pass
        finally:
            stop.set()
            # 下线所有智能体
            for aid in agent_ids_by_role.values():
                try:
                    await client.delete(f"{PLATFORM}/api/agents/{aid}", timeout=3)
                except Exception:
                    pass
            print("\n✓ 所有智能体已下线")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已停止演示")
