from __future__ import annotations

from app.agent.arbiter import HybridArbiter
from app.agent.llm_planner_adapter import LLMPlannerAdapter
from app.agent.loop_v2 import IterativeAgentLoopV2
from app.agent.policy import AgentPolicy, RetryPolicy
from app.background import TemporalTaskRunner
from app.llm_client import llm_client
from app.tools.builtin.memory_tools import MemoryQueryTool, MemoryRecentTool, MemoryWriteNoteTool
from app.tools.builtin.system_tools import EchoTool, NowTool
from app.tools.builtin.temporal_tools import TemporalCreateTool
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry


class FallbackPlannerAdapter:
    def next_step(self, payload):
        step = int(payload.get("step", 0))
        prompt = str(payload.get("prompt", ""))
        if step == 0 and "time" in prompt.lower():
            return {
                "action": "tool",
                "thought": "Need current time.",
                "function_call": {"name": "now", "arguments": {"tz": "UTC"}},
                "confidence": 0.62,
            }
        wm = payload.get("working_memory", []) or []
        if wm and wm[-1].get("type") == "tool_result" and wm[-1].get("ok"):
            return {
                "action": "final",
                "thought": "Tool result available.",
                "final_text": f"Result: {wm[-1].get('output')}",
                "confidence": 0.71,
            }
        return {
            "action": "reflect",
            "thought": f"Need more evidence for: {prompt}",
            "confidence": 0.35,
        }


def build_tool_registry(runner: TemporalTaskRunner) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(NowTool())
    registry.register(MemoryQueryTool())
    registry.register(MemoryRecentTool())
    registry.register(MemoryWriteNoteTool())
    registry.register(TemporalCreateTool(runner=runner))
    return registry


def build_agent_loop_v2(registry: ToolRegistry) -> IterativeAgentLoopV2:
    executor = ToolExecutor(registry)
    planner = LLMPlannerAdapter(registry=registry) if llm_client.enabled else FallbackPlannerAdapter()
    policy = AgentPolicy(
        max_iterations_default=6,
        max_iterations_cap=20,
        min_confidence_to_finalize=0.45,
        retry=RetryPolicy(max_total_retries=3, max_retries_per_tool=2, backoff_base_ms=150),
    )
    arbiter = HybridArbiter()
    return IterativeAgentLoopV2(
        llm_adapter=planner,
        tool_executor=executor,
        policy=policy,
        arbiter=arbiter,
    )
