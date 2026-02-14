from __future__ import annotations

import re
from typing import Any, Dict


INTENTS = {"reminder", "save_note", "list_notes", "semantic", "plan"}


def classify_intent(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    lower = raw.lower()

    if _is_list_notes(lower):
        return {"intent": "list_notes", "slots": {}}

    if _is_save_note(lower):
        return {"intent": "save_note", "slots": {"text": _extract_note_text(raw)}}

    if _is_reminder(lower):
        parsed = _extract_reminder(raw)
        return {"intent": "reminder", "slots": parsed}

    if _is_plan(lower):
        return {"intent": "plan", "slots": {"goal": _extract_plan_goal(raw)}}

    return {"intent": "semantic", "slots": {"query": raw}}


def _is_list_notes(text: str) -> bool:
    patterns = [
        r"\blist notes\b",
        r"\bshow notes\b",
        r"\bmy notes\b",
        r"\bnotes list\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_save_note(text: str) -> bool:
    patterns = [
        r"\bsave note\b",
        r"\bnote this\b",
        r"\bremember this\b",
        r"\badd note\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_reminder(text: str) -> bool:
    patterns = [
        r"\bremind me\b",
        r"\bset reminder\b",
        r"\breminder\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_plan(text: str) -> bool:
    patterns = [
        r"\bplan\b",
        r"\bmake a plan\b",
        r"\bhelp me plan\b",
        r"\broadmap\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _extract_note_text(raw: str) -> str:
    text = re.sub(r"(?i)\b(save note|note this|remember this|add note)\b[:\- ]*", "", raw).strip()
    return text if text else raw.strip()


def _extract_plan_goal(raw: str) -> str:
    text = re.sub(r"(?i)\b(make a plan|help me plan|plan|roadmap)\b[:\- ]*", "", raw).strip()
    return text if text else raw.strip()


def _extract_reminder(raw: str) -> Dict[str, Any]:
    cleaned = re.sub(r"(?i)\b(remind me|set reminder|reminder)\b[:\- ]*", "", raw).strip()
    when = None

    m = re.search(r"(?i)\b(at|on|tomorrow|today|next)\b.*$", cleaned)
    if m:
        when = m.group(0).strip()
        text = cleaned[: m.start()].strip(" ,.-")
    else:
        text = cleaned

    return {"text": text or raw.strip(), "when": when}
