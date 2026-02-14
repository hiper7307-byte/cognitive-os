from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class MetaEvalEvent:
    id: int
    user_id: str
    trace_id: str
    task_id: Optional[str]
    endpoint: str
    error_type: str
    severity: str
    self_accuracy_score: float
    hallucination_flag: int
    correction_of_event_id: Optional[int]
    notes_json: str
    created_at_epoch: int


class MetaEvalStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta_eval_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    task_id TEXT,
                    endpoint TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    self_accuracy_score REAL NOT NULL,
                    hallucination_flag INTEGER NOT NULL DEFAULT 0,
                    correction_of_event_id INTEGER,
                    notes_json TEXT NOT NULL DEFAULT '{}',
                    created_at_epoch INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_meta_eval_user_created
                ON meta_eval_events(user_id, created_at_epoch DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_meta_eval_trace
                ON meta_eval_events(trace_id)
                """
            )
            conn.commit()

    def write_event(
        self,
        *,
        user_id: str,
        trace_id: str,
        endpoint: str,
        error_type: str,
        severity: str,
        self_accuracy_score: float,
        hallucination_flag: bool,
        task_id: Optional[str] = None,
        correction_of_event_id: Optional[int] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = int(time.time())
        score = max(0.0, min(1.0, float(self_accuracy_score)))
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO meta_eval_events (
                    user_id, trace_id, task_id, endpoint, error_type, severity,
                    self_accuracy_score, hallucination_flag, correction_of_event_id,
                    notes_json, created_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    trace_id,
                    task_id,
                    endpoint,
                    error_type,
                    severity,
                    score,
                    1 if hallucination_flag else 0,
                    correction_of_event_id,
                    json.dumps(notes or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def recent_events(self, *, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        lim = max(1, min(int(limit), 200))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, trace_id, task_id, endpoint, error_type, severity,
                       self_accuracy_score, hallucination_flag, correction_of_event_id,
                       notes_json, created_at_epoch
                FROM meta_eval_events
                WHERE user_id = ?
                ORDER BY created_at_epoch DESC, id DESC
                LIMIT ?
                """,
                (user_id, lim),
            ).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "trace_id": r["trace_id"],
                    "task_id": r["task_id"],
                    "endpoint": r["endpoint"],
                    "error_type": r["error_type"],
                    "severity": r["severity"],
                    "self_accuracy_score": r["self_accuracy_score"],
                    "hallucination_flag": bool(r["hallucination_flag"]),
                    "correction_of_event_id": r["correction_of_event_id"],
                    "notes": json.loads(r["notes_json"] or "{}"),
                    "created_at_epoch": r["created_at_epoch"],
                }
            )
        return out
