from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_FILENAME = "ai_os_memory.db"


class IdentityStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = db_path or str(base_dir / DB_FILENAME)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_profiles (
                    user_id TEXT PRIMARY KEY,
                    long_term_value_model_json TEXT NOT NULL DEFAULT '{}',
                    stated_goals_json TEXT NOT NULL DEFAULT '{"short":[],"mid":[],"long":[]}',
                    behavioral_patterns_json TEXT NOT NULL DEFAULT '[]',
                    decision_history_trace_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    decision_payload_json TEXT NOT NULL DEFAULT '{}',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_identity_decisions_user_id ON identity_decisions(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_identity_decisions_task_id ON identity_decisions(task_id)"
            )

    def ensure_profile(self, user_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO identity_profiles(user_id)
                VALUES(?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id,),
            )

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        self.ensure_profile(user_id)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM identity_profiles WHERE user_id=?",
                (user_id,),
            ).fetchone()
            if row is None:
                return {
                    "user_id": user_id,
                    "long_term_value_model": {},
                    "stated_goals": {"short": [], "mid": [], "long": []},
                    "behavioral_patterns": [],
                    "decision_history_trace": [],
                }

            return {
                "user_id": user_id,
                "long_term_value_model": json.loads(row["long_term_value_model_json"] or "{}"),
                "stated_goals": json.loads(row["stated_goals_json"] or '{"short":[],"mid":[],"long":[]}'),
                "behavioral_patterns": json.loads(row["behavioral_patterns_json"] or "[]"),
                "decision_history_trace": json.loads(row["decision_history_trace_json"] or "[]"),
            }

    def append_decision(
        self,
        *,
        user_id: str,
        task_id: str,
        decision_type: str,
        decision_payload: Dict[str, Any],
        confidence: float = 0.5,
    ) -> int:
        self.ensure_profile(user_id)
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO identity_decisions(user_id, task_id, decision_type, decision_payload_json, confidence)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    task_id,
                    decision_type,
                    json.dumps(decision_payload, ensure_ascii=False),
                    float(confidence),
                ),
            )
            decision_id = int(cur.lastrowid)

            row = conn.execute(
                "SELECT decision_history_trace_json FROM identity_profiles WHERE user_id=?",
                (user_id,),
            ).fetchone()

            trace: List[Dict[str, Any]]
            if row is None:
                trace = []
            else:
                trace = json.loads(row["decision_history_trace_json"] or "[]")

            trace.append(
                {
                    "decision_id": decision_id,
                    "task_id": task_id,
                    "decision_type": decision_type,
                    "confidence": float(confidence),
                }
            )
            trace = trace[-500:]

            conn.execute(
                """
                UPDATE identity_profiles
                SET decision_history_trace_json=?, updated_at=datetime('now')
                WHERE user_id=?
                """,
                (json.dumps(trace, ensure_ascii=False), user_id),
            )

            return decision_id


identity_store = IdentityStore()
