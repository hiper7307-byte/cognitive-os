from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, Optional


def _utc_epoch() -> int:
    return int(time.time())


class IdentityAlignmentStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_tables()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_profiles (
                    user_id TEXT PRIMARY KEY,
                    values_json TEXT NOT NULL DEFAULT '[]',
                    goals_json TEXT NOT NULL DEFAULT '[]',
                    constraints_json TEXT NOT NULL DEFAULT '[]',
                    risk_tolerance REAL NOT NULL DEFAULT 0.5,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at_epoch INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identity_alignment_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    candidate_action TEXT,
                    score REAL NOT NULL,
                    components_json TEXT NOT NULL DEFAULT '{}',
                    matched_json TEXT NOT NULL DEFAULT '{}',
                    trace_json TEXT NOT NULL DEFAULT '{}',
                    created_at_epoch INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_profile(
        self,
        *,
        user_id: str,
        values: list[str],
        goals: list[str],
        constraints: list[str],
        risk_tolerance: float,
        metadata: Dict[str, str],
    ) -> Dict[str, Any]:
        now = _utc_epoch()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO identity_profiles (
                    user_id, values_json, goals_json, constraints_json,
                    risk_tolerance, metadata_json, updated_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    values_json=excluded.values_json,
                    goals_json=excluded.goals_json,
                    constraints_json=excluded.constraints_json,
                    risk_tolerance=excluded.risk_tolerance,
                    metadata_json=excluded.metadata_json,
                    updated_at_epoch=excluded.updated_at_epoch
                """,
                (
                    user_id,
                    json.dumps(values, ensure_ascii=False),
                    json.dumps(goals, ensure_ascii=False),
                    json.dumps(constraints, ensure_ascii=False),
                    float(risk_tolerance),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT user_id, values_json, goals_json, constraints_json,
                       risk_tolerance, metadata_json, updated_at_epoch
                FROM identity_profiles
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
            conn.commit()
        return self._decode_profile_row(dict(row)) if row else {}

    def get_profile(self, *, user_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT user_id, values_json, goals_json, constraints_json,
                       risk_tolerance, metadata_json, updated_at_epoch
                FROM identity_profiles
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self._decode_profile_row(dict(row))

    def log_alignment_event(
        self,
        *,
        user_id: str,
        text: str,
        candidate_action: Optional[str],
        score: float,
        components: Dict[str, float],
        matched: Dict[str, Any],
        trace: Dict[str, str],
    ) -> int:
        now = _utc_epoch()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO identity_alignment_events (
                    user_id, text, candidate_action, score,
                    components_json, matched_json, trace_json, created_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    text,
                    candidate_action,
                    float(score),
                    json.dumps(components, ensure_ascii=False),
                    json.dumps(matched, ensure_ascii=False),
                    json.dumps(trace, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _decode_profile_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": row["user_id"],
            "values": self._safe_json_list(row.get("values_json")),
            "goals": self._safe_json_list(row.get("goals_json")),
            "constraints": self._safe_json_list(row.get("constraints_json")),
            "risk_tolerance": float(row.get("risk_tolerance") or 0.5),
            "metadata": self._safe_json_dict(row.get("metadata_json")),
            "updated_at_epoch": int(row.get("updated_at_epoch") or 0),
        }

    @staticmethod
    def _safe_json_list(raw: Any) -> list[str]:
        try:
            data = json.loads(raw or "[]")
            if isinstance(data, list):
                return [str(x) for x in data]
            return []
        except Exception:
            return []

    @staticmethod
    def _safe_json_dict(raw: Any) -> Dict[str, str]:
        try:
            data = json.loads(raw or "{}")
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            return {}
        except Exception:
            return {}
