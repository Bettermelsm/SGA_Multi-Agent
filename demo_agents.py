"""
demo_agents.py — Multi-Agent Platform v2 演示脚本

演示内容:
  1. 注册 5 个不同角色的智能体
  2. 创建并执行任务（含优先级）
  3. 智能体间消息传递
  4. 流式 LLM 输出
  5. 工具调用（CoderAgent.run_python）
  6. 多轮对话（AnalystAgent.analyze）
  7. 自动心跳与断线重连

运行: python scripts/demo_agents.py [platform_url]
"""

import asyncio
import random
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../sdk'))
from agent_sdk import AgentClient, PlannerAgent, CoderAgent, AnalystAgent

PLATFORM = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9527"

# ── Task sets for each role ───────────────────────────────────────────
TASK_POOL = {
    "planner":   [("制定 Q3 产品路线图", "P1"), ("分解用户增长目标", "P2"),   ("制定 API 重构计划", "P2")],
    "coder":     [("生成 CSV 解析工具",   "P2"), ("实现 JWT 鉴权模块",  "P1"), ("编写单元测试套件",  "P3")],
    "retriever": [("检索竞品分析报告",    "P2"), ("搜索技术文档",       "P3"), ("返回 RAG 检索结果", "P2")],
    "analyzer":  [("分析 DAU 趋势数据",  "P1"), ("生成用户行为报告",   "P2"), ("预测下月留存率",    "P1")],
    "evaluator": [("评估代码质量",        "P2"), ("验证分析结论",       "P2"), ("审核测试覆盖率",    "P3")],
}


async def check_platform(url: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{url}/health")
            data = r.json()
            print(f"  ✓ 平台状态: {data.get('status')} | Ollama: {data.get('ollama')} | DB: {data.get('db')}")
            return True
    except Exception as e:
        print(f"  ✗ 无法连接平台: {e}")
        return False


# ── Worker for each non-specialist agent ─────────────────────────────
async def agent_worker(role: str, stop: asyncio.Event):
    agent = AgentClient(
        name={"retriever": "检索智能体", "evaluator": "评估智能体"}.get(role, f"{role}智能体"),
        role=role,
        capabilities={"retriever": ["全文搜索","向量检索","RAG"],
                      "evaluator": ["质量评估","结果验证","指标计算"]}.get(role, []),
        platform_url=PLATFORM,
        heartbeat_interval=10,
    )
    try:
        await agent.register()
        tasks_done = 0
        while not stop.is_set():
            # Random work cycle
            await asyncio.sleep(random.uniform(6, 14))
            if stop.is_set(): break
            pool = TASK_POOL.get(role, [])
            if not pool: continue
            title, priority = random.choice(pool)
            try:
                task_id = await agent.create_task(title, f"自动演示: {title}", priority)
                work_time = random.uniform(2, 6)
                await asyncio.sleep(work_time)
                await agent.complete_task(task_id, f"完成: {title}", {"duration": round(work_time,1)})
                tasks_done += 1
                print(f"  [{agent.name}] ✓ {title} ({priority}) — 共 {tasks_done} 个")
            except Exception as e:
                print(f"  [{agent.name}] ! 任务失败: {e}")
    finally:
        await agent.stop()


# ── Planner: demonstrates multi-step planning ────────────────────────
async def run_planner(stop: asyncio.Event):
    agent = PlannerAgent(platform_url=PLATFORM)
    try:
        await agent.register()
        print(f"\n[{agent.name}] 开始规划演示...")
        while not stop.is_set():
            await asyncio.sleep(random.uniform(15, 25))
            if stop.is_set(): break
            goals = ["提升产品用户留存率", "降低服务响应延迟", "扩大海外市场覆盖"]
            goal = random.choice(goals)
            try:
                steps = await agent.plan(goal)
                print(f"  [规划智能体] 目标「{goal}」→ {len(steps)} 步计划")
            except Exception as e:
                # Ollama not available — fallback task
                try:
                    task_id = await agent.create_task(f"规划: {goal}", goal, "P1")
                    await asyncio.sleep(3)
                    await agent.complete_task(task_id, f"规划完成(模拟): {goal}", {})
                    print(f"  [规划智能体] ✓ 规划任务完成 (Ollama 不可用，使用模拟)")
                except Exception:
                    pass
    finally:
        await agent.stop()


# ── Coder: demonstrates tool calls ───────────────────────────────────
async def run_coder(stop: asyncio.Event):
    agent = CoderAgent(platform_url=PLATFORM)
    try:
        await agent.register()
        print(f"[{agent.name}] 开始代码演示...")
        iterations = 0
        while not stop.is_set():
            await asyncio.sleep(random.uniform(12, 20))
            if stop.is_set(): break
            iterations += 1
            specs = [
                ("生成斐波那契数列函数", "Python"),
                ("实现二分查找算法",     "Python"),
                ("编写 HTTP 请求工具函数","Python"),
            ]
            spec, lang = random.choice(specs)
            try:
                code = await agent.generate(spec, lang)
                print(f"  [代码智能体] ✓ 生成: {spec} ({len(code)} chars)")
            except Exception as e:
                try:
                    task_id = await agent.create_task(spec, spec, "P2")
                    await asyncio.sleep(3)
                    await agent.complete_task(task_id, f"代码生成完成(模拟)", {"lines": 15})
                    print(f"  [代码智能体] ✓ 代码任务完成 (模拟)")
                except Exception:
                    pass
    finally:
        await agent.stop()


# ── Analyst: demonstrates multi-turn + streaming ─────────────────────
async def run_analyst(stop: asyncio.Event):
    agent = AnalystAgent(platform_url=PLATFORM)
    try:
        await agent.register()
        print(f"[{agent.name}] 开始分析演示...")
        while not stop.is_set():
            await asyncio.sleep(random.uniform(18, 30))
            if stop.is_set(): break
            datasets = [
                "过去 30 天 DAU 从 12000 下降到 9500，周末数据回升明显",
                "转化漏斗：浏览 10000 → 注册 2100 → 付费 340，各环节流失分析",
                "API P99 延迟从 120ms 上升到 890ms，主要集中在数据库查询",
            ]
            data = random.choice(datasets)
            try:
                result = await agent.analyze(data)
                summary = result.get("interpretation","")[:60]
                print(f"  [分析智能体] ✓ 分析完成: {summary}...")
            except Exception:
                try:
                    task_id = await agent.create_task(f"分析数据", data[:40], "P1")
                    await asyncio.sleep(4)
                    score = random.randint(70, 99)
                    await agent.complete_task(task_id, f"分析完成，置信度 {score}%", {"score": score})
                    print(f"  [分析智能体] ✓ 分析任务完成(模拟) 置信度 {score}%")
                except Exception:
                    pass
    finally:
        await agent.stop()


# ── Messaging demo: planner sends task to coder ───────────────────────
async def run_messaging_demo(stop: asyncio.Event):
    """Demonstrates agent-to-agent messaging."""
    await asyncio.sleep(20)  # let other agents register first
    if stop.is_set(): return

    sender = AgentClient(
        name="协调智能体", role="planner",
        capabilities=["协调", "消息路由"],
        platform_url=PLATFORM,
    )
    await sender.register()
    print(f"\n[{sender.name}] 开始消息演示...")

    try:
        import httpx
        while not stop.is_set():
            await asyncio.sleep(random.uniform(25, 40))
            if stop.is_set(): break
            # Find a coder agent to message
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get(f"{PLATFORM}/api/agents?role=coder")
                agents_list = resp.json().get("agents", [])
            if not agents_list: continue
            target = agents_list[0]["agent_id"]
            try:
                msg_id = await sender.send_message(
                    target,
                    "请帮忙生成一个数据处理的 Python 函数",
                    msg_type="task",
                )
                print(f"  [协调智能体] → 消息 {msg_id} 已发送至代码智能体")
            except Exception as e:
                print(f"  [协调智能体] ! 消息发送失败: {e}")
    finally:
        await sender.stop()


# ── Main ──────────────────────────────────────────────────────────────
async def main():
    print("╔══════════════════════════════════════════════╗")
    print("║  Multi-Agent Platform v2 — 演示脚本           ║")
    print("╚══════════════════════════════════════════════╝\n")

    print("▸ 检查平台连接...")
    if not await check_platform(PLATFORM):
        print("\n请先运行: ./scripts/start.sh")
        return

    print(f"\n▸ 启动 7 个智能体 (Ctrl+C 停止)\n")

    stop = asyncio.Event()

    tasks = [
        asyncio.create_task(run_planner(stop)),
        asyncio.create_task(run_coder(stop)),
        asyncio.create_task(run_analyst(stop)),
        asyncio.create_task(agent_worker("retriever", stop)),
        asyncio.create_task(agent_worker("evaluator", stop)),
        asyncio.create_task(run_messaging_demo(stop)),
    ]

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n▸ 正在关闭所有智能体...")
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("✓ 所有智能体已下线")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已停止")
