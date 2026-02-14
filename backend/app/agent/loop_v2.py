from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Protocol, Set

from app.agent.arbiter import HybridArbiter
from app.agent.policy import AgentPolicy, RetryState, clamp_iterations
from app.tools.executor import ToolExecutor
from app.tools.models import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStepResult,
    FunctionCall,
)


class PlannerAdapter(Protocol):
    def next_step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


class IterativeAgentLoopV2:
    def __init__(
        self,
        llm_adapter: PlannerAdapter,
        tool_executor: ToolExecutor,
        *,
        policy: Optional[AgentPolicy] = None,
        arbiter: Optional[HybridArbiter] = None,
    ) -> None:
        self.llm = llm_adapter
        self.tools = tool_executor
        self.policy = policy or AgentPolicy()
        self.arbiter = arbiter or HybridArbiter()

    def run(self, *, user_id: str, req: AgentRunRequest) -> AgentRunResponse:
        trace_id = str(uuid.uuid4())
        started = time.perf_counter()

        max_iterations = clamp_iterations(req.max_iterations, self.policy)

        steps: List[AgentStepResult] = []
        tool_traces: List[Dict[str, Any]] = []
        working_memory: List[Dict[str, Any]] = []
        final_answer: Optional[str] = None
        error: Optional[str] = None

        retry_state = RetryState()
        last_tool_name: Optional[str] = None

        # Enforce allowed tool set at executor layer
        whitelist_set: Optional[Set[str]] = set(req.tool_whitelist) if req.tool_whitelist else None

        for i in range(max_iterations):
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if elapsed_ms > req.timeout_ms:
                error = f"Agent timeout after {elapsed_ms}ms"
                break

            llm_payload = {
                "trace_id": trace_id,
                "step": i,
                "prompt": req.prompt,
                "working_memory": working_memory,
                "allow_tools": req.allow_tools,
                "tool_whitelist": req.tool_whitelist,
            }

            planner_step = self.llm.next_step(llm_payload) or {}
            has_tool_result = any(x.get("type") == "tool_result" and x.get("ok") for x in working_memory)

            decision = self.arbiter.decide(
                planner_step=planner_step,
                allow_tools=req.allow_tools,
                min_confidence_to_finalize=self.policy.min_confidence_to_finalize,
                has_tool_result=has_tool_result,
            )

            if decision.action == "final":
                answer = str(decision.final_text or "")
                final_answer = answer
                steps.append(
                    AgentStepResult(
                        step_index=i,
                        thought=decision.thought,
                        action="final",
                        final_text=answer,
                        confidence=decision.confidence,
                        notes={"arbiter_reason": decision.reason} if decision.reason else {},
                    )
                )
                break

            if decision.action == "tool" and req.allow_tools:
                fc = decision.function_call or {}
                fname = str(fc.get("name", "")).strip()
                fargs = fc.get("arguments", {}) or {}
                last_tool_name = fname

                rec = self.tools.execute(
                    user_id=user_id,
                    tool_name=fname,
                    args=fargs,
                    trace_id=trace_id,
                    metadata={"step": i},
                    whitelist=whitelist_set,
                )

                tool_traces.append(
                    {
                        "step": i,
                        "tool": rec.tool_name,
                        "ok": rec.ok,
                        "latency_ms": rec.latency_ms,
                        "output": rec.output,
                        "error": rec.error,
                    }
                )

                working_memory.append(
                    {
                        "type": "tool_result",
                        "step": i,
                        "tool": rec.tool_name,
                        "ok": rec.ok,
                        "output": rec.output,
                        "error": rec.error,
                    }
                )

                steps.append(
                    AgentStepResult(
                        step_index=i,
                        thought=decision.thought,
                        action="tool",
                        function_call=FunctionCall(name=fname, arguments=fargs),
                        confidence=decision.confidence,
                        notes={"tool_ok": rec.ok, "tool_error": rec.error},
                    )
                )

                if not rec.ok:
                    if retry_state.can_retry(fname, self.policy):
                        retry_state.mark_retry(fname)
                        steps.append(
                            AgentStepResult(
                                step_index=i,
                                thought="Tool failed; retry authorized by policy.",
                                action="retry",
                                confidence=max(decision.confidence - 0.1, 0.0),
                                notes={
                                    "failed_tool": fname,
                                    "total_retries": retry_state.total_retries,
                                    "tool_retries": retry_state.per_tool.get(fname, 0),
                                },
                            )
                        )
                    else:
                        steps.append(
                            AgentStepResult(
                                step_index=i,
                                thought="Retry budget exhausted; switching to reflection.",
                                action="reflect",
                                confidence=max(decision.confidence - 0.2, 0.0),
                                notes={"failed_tool": fname, "retry_exhausted": True},
                            )
                        )
                continue

            if decision.action == "retry":
                if retry_state.can_retry(last_tool_name, self.policy):
                    retry_state.mark_retry(last_tool_name)
                    steps.append(
                        AgentStepResult(
                            step_index=i,
                            thought=decision.thought or "Retry selected.",
                            action="retry",
                            confidence=decision.confidence,
                            notes={
                                "retry_target_tool": last_tool_name,
                                "total_retries": retry_state.total_retries,
                                "tool_retries": retry_state.per_tool.get(last_tool_name or "", 0),
                            },
                        )
                    )
                else:
                    steps.append(
                        AgentStepResult(
                            step_index=i,
                            thought="Retry denied by policy budget.",
                            action="reflect",
                            confidence=max(decision.confidence - 0.2, 0.0),
                            notes={"retry_exhausted": True},
                        )
                    )
                continue

            steps.append(
                AgentStepResult(
                    step_index=i,
                    thought=decision.thought,
                    action="reflect",
                    confidence=decision.confidence,
                    notes={"arbiter_reason": decision.reason} if decision.reason else {},
                )
            )

        if final_answer is None and error is None:
            final_answer = "No final answer produced within iteration budget."

        decision_trace = {
            "trace_id": trace_id,
            "iterations": len(steps),
            "max_iterations": max_iterations,
            "timeout_ms": req.timeout_ms,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "retry_total": retry_state.total_retries,
            "retry_per_tool": retry_state.per_tool,
            "policy": {
                "min_confidence_to_finalize": self.policy.min_confidence_to_finalize,
                "max_total_retries": self.policy.retry.max_total_retries,
                "max_retries_per_tool": self.policy.retry.max_retries_per_tool,
            },
            "whitelist_active": whitelist_set is not None,
            "whitelist": sorted(list(whitelist_set)) if whitelist_set is not None else None,
        }

        return AgentRunResponse(
            ok=error is None,
            answer=final_answer or "",
            steps=steps,
            tool_traces=tool_traces,
            decision_trace=decision_trace,
            error=error,
        )
