from __future__ import annotations

from typing import Any, Dict, List

from .memory import memory_service


def _strip_command_prefix(text: str, prefixes: List[str]) -> str:
    t = (text or "").strip()
    lower = t.lower()
    for p in prefixes:
        if lower.startswith(p):
            return t[len(p):].strip(" :,-")
    return t


def _tokens(s: str) -> List[str]:
    raw = (s or "").lower().replace("\n", " ")
    for ch in [",", ".", ":", ";", "?", "!", "(", ")", "[", "]", "{", "}", "\"", "'"]:
        raw = raw.replace(ch, " ")
    parts = [p.strip() for p in raw.split(" ") if p.strip()]
    # lightweight stopword filter
    stop = {"the", "a", "an", "is", "are", "to", "for", "of", "and", "or", "about", "any", "anything"}
    return [p for p in parts if p not in stop and len(p) > 2]


def exec_save_note(text: str, user_id: str = "local-dev") -> Dict[str, Any]:
    note = _strip_command_prefix(
        text,
        prefixes=["save note", "save_note", "note", "remember"],
    )
    if not note:
        return {
            "ok": False,
            "message": "note_empty",
            "executor": "exec_save_note",
            "data": {},
        }

    memory_id = memory_service.write_semantic_fact(
        user_id=user_id,
        fact_text=note,
        metadata={"source": "save_note"},
        confidence=0.78,
    )

    return {
        "ok": True,
        "message": "note_saved",
        "executor": "exec_save_note",
        "data": {"memory_id": memory_id},
    }


def exec_list_notes(user_id: str = "local-dev", limit: int = 20) -> Dict[str, Any]:
    rows = memory_service.recent(
        user_id=user_id,
        memory_type="semantic",
        limit=max(1, min(limit, 100)),
    )
    notes = [
        {
            "id": r.get("id"),
            "content": r.get("content"),
            "created_at": r.get("created_at"),
            "confidence": r.get("confidence", 0.5),
        }
        for r in rows
    ]
    return {
        "ok": True,
        "message": "notes_listed",
        "executor": "exec_list_notes",
        "data": {"notes": notes, "count": len(notes)},
    }


def exec_semantic(text: str, user_id: str = "local-dev", limit: int = 10) -> Dict[str, Any]:
    query = _strip_command_prefix(
        text,
        prefixes=["semantic", "search", "find", "query", "memory"],
    )
    if not query:
        query = (text or "").strip()

    safe_limit = max(1, min(limit, 25))

    # Primary retrieval path (vector + lexical hybrid inside memory_service.retrieve)
    rows = memory_service.retrieve(
        user_id=user_id,
        query=query,
        memory_types=["semantic", "procedural", "episodic"],
        limit=safe_limit,
    )

    # Fallback path when retrieve returns empty but we clearly have notes:
    # do token overlap against recent semantic rows to avoid "false empty".
    if not rows:
        recent_semantic = memory_service.recent(
            user_id=user_id,
            memory_type="semantic",
            limit=200,
        )
        qtokens = set(_tokens(query))
        scored: List[tuple[int, dict]] = []

        for r in recent_semantic:
            content = str(r.get("content", ""))
            ctokens = set(_tokens(content))
            score = len(qtokens.intersection(ctokens))
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        rows = [r for _, r in scored[:safe_limit]]

    return {
        "ok": True,
        "message": "semantic_results",
        "executor": "exec_semantic",
        "data": {"query": query, "results": rows, "count": len(rows)},
    }


def exec_plan(text: str, user_id: str = "local-dev") -> Dict[str, Any]:
    request = _strip_command_prefix(
        text,
        prefixes=["plan", "planner", "make plan"],
    )
    if not request:
        request = (text or "").strip()

    steps = [
        f"Define objective for: {request}",
        "Break objective into 3 executable milestones",
        "Execute milestone 1 and log result",
    ]
    return {
        "ok": True,
        "message": "plan_generated",
        "executor": "exec_plan",
        "data": {"input": request, "steps": steps},
    }


def exec_set_reminder(text: str, user_id: str = "local-dev") -> Dict[str, Any]:
    reminder_text = _strip_command_prefix(
        text,
        prefixes=["remind me", "set reminder", "reminder"],
    )
    if not reminder_text:
        reminder_text = (text or "").strip()

    return {
        "ok": True,
        "message": "reminder_stub_created",
        "executor": "exec_set_reminder",
        "data": {"text": reminder_text, "status": "stub"},
    }
