from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Header, HTTPException

from .cognitive.runtime import arbitration_service, meta_eval_service
from .config import COGNITIVE_ROUTE_PRIMARY
from .embedding_provider import embedding_provider
from .llm_client import llm_client
from .memory import memory_service, new_task_id
from .reasoning import reasoning_arbitrator
from .schemas import ArbitrationMeta, LLMChatRequest, LLMChatResponse

router = APIRouter(tags=["llm"])


def _require_user_id(x_user_id: str | None) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id


def _format_memory_context(rows: List[dict]) -> str:
    if not rows:
        return ""
    lines: List[str] = []
    for r in rows:
        lines.append(
            f"- [{r.get('memory_type', '?')}] conf={r.get('confidence', 0)} "
            f"created={r.get('created_at', '')} :: {r.get('content', '')}"
        )
    return "\n".join(lines)


def _is_noise_row(row: dict) -> bool:
    content = str(row.get("content", "")).strip().lower()
    return content.startswith("llm response:")


def _normalize_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _dedupe_rows(rows: List[dict], limit: int) -> List[dict]:
    """
    Keep first occurrence of normalized content while preserving order.
    """
    seen: set[str] = set()
    out: List[dict] = []

    for r in rows:
        key = _normalize_text(str(r.get("content", "")))
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break

    return out


def _fallback_semantic_rows(user_id: str, query: str, limit: int) -> List[dict]:
    """
    Deterministic lexical fallback:
    pull recent semantic rows and rank by token overlap.
    Used only when primary retrieval returns zero rows.
    """
    tokens = [
        t
        for t in query.lower().replace("?", " ").replace(",", " ").split()
        if len(t) > 2
    ]
    if not tokens:
        return []

    rows = memory_service.recent(user_id=user_id, memory_type="semantic", limit=200)

    scored: List[Tuple[int, dict]] = []
    for r in rows:
        if _is_noise_row(r):
            continue
        content = str(r.get("content", "")).lower()
        score = sum(1 for t in tokens if t in content)
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [r for _, r in scored]
    return _dedupe_rows(ranked, limit=max(1, min(limit, 20)))


def _merge_arbitration(
    *,
    base_mode: str,
    base_confidence: float,
    base_scores: Dict[str, Any] | None,
    base_rationale: str,
    cognitive: Dict[str, Any] | None,
) -> ArbitrationMeta:
    merged_scores: Dict[str, Any] = dict(base_scores or {})
    cog = cognitive or {}
    meta = cog.get("metadata", {}) or {}

    merged_scores["cognitive_final_score"] = float(cog.get("final_score", 0.0))
    merged_scores["cognitive_route_mode"] = str(cog.get("route_mode", "model"))

    components = meta.get("component_scores", {}) or {}
    for k, v in components.items():
        try:
            merged_scores[f"cog_{k}"] = float(v)
        except Exception:
            merged_scores[f"cog_{k}"] = v

    merged_scores["cog_contradiction_hits"] = int(meta.get("contradiction_hits", 0))
    merged_scores["cog_selected_memory_id"] = meta.get("selected_memory_id")

    rationale = (base_rationale or "").strip()
    cog_rationale = str(meta.get("rationale", "")).strip()
    if cog_rationale:
        rationale = (
            f"{rationale} | cognitive={cog_rationale}"
            if rationale
            else f"cognitive={cog_rationale}"
        )

    return ArbitrationMeta(
        mode=base_mode,
        confidence=float(base_confidence or 0.0),
        scores=merged_scores,
        rationale=rationale,
    )


def _map_cognitive_to_legacy_mode(cog_mode: str) -> str:
    c = (cog_mode or "").strip().lower()
    if c == "memory":
        return "memory_only"
    if c == "hybrid":
        return "hybrid"
    return "llm_only"


def _resolve_effective_mode(
    *,
    arb_mode: str,
    cognitive: Dict[str, Any] | None,
) -> str:
    """
    If cognitive routing is enabled but returns empty/default model state,
    fall back to base arbitrator mode.
    """
    if not COGNITIVE_ROUTE_PRIMARY:
        return arb_mode

    cog = cognitive or {}
    cog_mode = str(cog.get("route_mode", "model")).strip().lower()
    cog_score = float(cog.get("final_score", 0.0) or 0.0)

    if cog_mode == "model" and cog_score == 0.0:
        return arb_mode

    return _map_cognitive_to_legacy_mode(cog_mode)


def _persist_llm_chat_event(
    *,
    user_id: str,
    user_text: str,
    response_text: str,
    memory_used: int,
    arbitration: ArbitrationMeta,
    effective_mode: str,
    llm_enabled_flag: bool,
    used_memory_rows: List[dict],
) -> None:
    try:
        task_id = new_task_id()
        memory_service.write_task_event(
            user_id=user_id,
            task_id=task_id,
            intent="llm_chat",
            user_input=user_text,
            outcome="llm_chat_completed",
            executor="llm_routes.llm_chat",
            status="success",
            extra={
                "effective_mode": effective_mode,
                "llm_enabled": llm_enabled_flag,
                "memory_used": memory_used,
                "memory_preview": [r.get("id") for r in used_memory_rows[:12]],
                "arbitration": {
                    "mode": getattr(arbitration, "mode", effective_mode),
                    "confidence": getattr(arbitration, "confidence", 0.0),
                    "scores": getattr(arbitration, "scores", {}),
                    "rationale": getattr(arbitration, "rationale", ""),
                },
                "response_preview": (response_text or "")[:1500],
                "cognitive_route_primary": COGNITIVE_ROUTE_PRIMARY,
            },
        )
    except Exception:
        # non-fatal telemetry path
        pass


def _persist_meta_eval(
    *,
    user_id: str,
    trace_id: str,
    req: LLMChatRequest,
    mode: str,
    memory_count: int,
    message_text: str,
    had_exception: bool,
    extra_notes: Dict[str, Any] | None = None,
) -> None:
    try:
        decision = meta_eval_service.evaluate_response(
            used_memory=req.use_memory,
            memory_count=memory_count,
            llm_enabled=llm_client.enabled,
            arbitration_mode=mode,
            response_text=message_text,
            had_exception=had_exception,
        )
        notes: Dict[str, Any] = {
            "mode": mode,
            "memory_used": memory_count,
        }
        if extra_notes:
            notes.update(extra_notes)

        meta_eval_service.persist_event(
            user_id=user_id,
            trace_id=trace_id,
            endpoint="/llm/chat",
            decision=decision,
            notes=notes,
        )
    except Exception:
        # non-fatal telemetry path
        pass


@router.post("/llm/chat", response_model=LLMChatResponse)
async def llm_chat(
    req: LLMChatRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    user_id = _require_user_id(x_user_id)
    user_text = (req.message or "").strip()
    trace_id = str(uuid.uuid4())

    if not user_text:
        _persist_meta_eval(
            user_id=user_id,
            trace_id=trace_id,
            req=req,
            mode="llm_only",
            memory_count=0,
            message_text="",
            had_exception=False,
            extra_notes={"empty_input": True},
        )
        return LLMChatResponse(ok=True, message="", memory_used=0)

    memory_rows: List[dict] = []
    vector_ranked: List[Tuple[int, float]] = []
    limit = max(1, min(req.memory_limit, 20))

    try:
        # 1) Retrieval path
        if req.use_memory:
            try:
                memory_rows = memory_service.retrieve(
                    user_id=user_id,
                    query=user_text,
                    memory_types=["semantic", "procedural", "episodic"],
                    limit=limit,
                )
            except Exception:
                memory_rows = []

            try:
                qvec = embedding_provider.embed(user_text)
                vector_ranked = memory_service.vector_store.search(
                    user_id=user_id,
                    query_vector=qvec,
                    namespace=memory_service.namespace,
                    model=memory_service.embedding_model_name,
                    top_k=limit,
                    memory_types=["semantic", "procedural", "episodic"],
                )
            except Exception:
                vector_ranked = []

            # lexical fallback if primary retrieval returns nothing
            if not memory_rows:
                try:
                    memory_rows = _fallback_semantic_rows(
                        user_id=user_id,
                        query=user_text,
                        limit=limit,
                    )
                except Exception:
                    memory_rows = []

            # clean + dedupe retrieved memory
            if memory_rows:
                memory_rows = [r for r in memory_rows if not _is_noise_row(r)]
                memory_rows = _dedupe_rows(memory_rows, limit=limit)

        # 2) Arbitration
        arb = reasoning_arbitrator.decide(
            query=user_text,
            memory_rows=memory_rows,
            vector_ranked=vector_ranked,
        )

        cognitive = arbitration_service.arbitrate(
            user_id=user_id,
            prompt=user_text,
            candidate_action=None,
            memory_types=["semantic", "procedural", "episodic"] if req.use_memory else None,
            limit=limit,
        )

        merged_meta = _merge_arbitration(
            base_mode=arb.mode,
            base_confidence=arb.confidence,
            base_scores=arb.scores,
            base_rationale=arb.rationale,
            cognitive=cognitive,
        )

        effective_mode = _resolve_effective_mode(
            arb_mode=arb.mode,
            cognitive=cognitive,
        )

        # 3) Deterministic fallback when LLM is disabled
        if not llm_client.enabled:
            if req.use_memory and memory_rows:
                fallback = "Memory-grounded fallback:\n" + _format_memory_context(memory_rows[:8])
            else:
                fallback = "LLM disabled: OPENAI_API_KEY is missing."

            _persist_llm_chat_event(
                user_id=user_id,
                user_text=user_text,
                response_text=fallback,
                memory_used=len(memory_rows),
                arbitration=merged_meta,
                effective_mode=effective_mode,
                llm_enabled_flag=False,
                used_memory_rows=memory_rows,
            )
            _persist_meta_eval(
                user_id=user_id,
                trace_id=trace_id,
                req=req,
                mode=effective_mode,
                memory_count=len(memory_rows),
                message_text=fallback,
                had_exception=False,
            )
            return LLMChatResponse(
                ok=True,
                message=fallback,
                memory_used=len(memory_rows),
                arbitration=merged_meta,
            )

        # 4) Memory-only route
        if effective_mode == "memory_only":
            msg = "Memory-grounded context:\n" + _format_memory_context(memory_rows[:8])

            _persist_llm_chat_event(
                user_id=user_id,
                user_text=user_text,
                response_text=msg,
                memory_used=len(memory_rows),
                arbitration=merged_meta,
                effective_mode=effective_mode,
                llm_enabled_flag=True,
                used_memory_rows=memory_rows,
            )
            _persist_meta_eval(
                user_id=user_id,
                trace_id=trace_id,
                req=req,
                mode=effective_mode,
                memory_count=len(memory_rows),
                message_text=msg,
                had_exception=False,
            )
            return LLMChatResponse(
                ok=True,
                message=msg,
                memory_used=len(memory_rows),
                arbitration=merged_meta,
            )

        # 5) Prompt build + model call
        if effective_mode == "llm_only":
            prompt = (
                "You are an execution-focused systems assistant.\n"
                "Answer concisely with concrete next actions.\n\n"
                f"User message:\n{user_text}"
            )
        else:
            mem_ctx = _format_memory_context(memory_rows[:12])
            prompt = (
                "You are an execution-focused systems assistant.\n"
                "Use memory context where relevant; avoid fabricating facts.\n\n"
                f"Memory context:\n{mem_ctx}\n\n"
                f"User message:\n{user_text}"
            )

        answer = await llm_client.chat(prompt)

        _persist_llm_chat_event(
            user_id=user_id,
            user_text=user_text,
            response_text=answer,
            memory_used=len(memory_rows),
            arbitration=merged_meta,
            effective_mode=effective_mode,
            llm_enabled_flag=True,
            used_memory_rows=memory_rows,
        )
        _persist_meta_eval(
            user_id=user_id,
            trace_id=trace_id,
            req=req,
            mode=effective_mode,
            memory_count=len(memory_rows),
            message_text=answer,
            had_exception=False,
        )

        return LLMChatResponse(
            ok=True,
            message=answer,
            memory_used=len(memory_rows),
            arbitration=merged_meta,
        )

    except Exception as exc:
        _persist_meta_eval(
            user_id=user_id,
            trace_id=trace_id,
            req=req,
            mode="llm_only",
            memory_count=len(memory_rows),
            message_text=f"exception: {exc}",
            had_exception=True,
            extra_notes={"exception_type": type(exc).__name__},
        )
        raise
from fastapi.responses import StreamingResponse
import json
import asyncio


@router.post("/llm/stream")
async def llm_stream(
    req: LLMChatRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    user_id = _require_user_id(x_user_id)
    user_text = (req.message or "").strip()

    if not user_text:
        async def empty_stream():
            yield "data: {}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def event_generator():
        try:
            prompt = (
                "You are an execution-focused systems assistant.\n"
                "Stream your answer progressively.\n\n"
                f"User message:\n{user_text}"
            )

            async for chunk in llm_client.chat_stream(prompt):
                payload = {"token": chunk}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0)

            yield "data: {\"done\": true}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
