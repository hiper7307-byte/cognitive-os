from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class GraphNode:
    id: int
    user_id: str
    node_type: str
    label: str
    metadata: Dict[str, Any]
    source_memory_id: Optional[int]
    confidence: float
    created_at_epoch: int
    updated_at_epoch: int


@dataclass(frozen=True)
class GraphEdge:
    id: int
    user_id: str
    src_node_id: int
    dst_node_id: int
    edge_type: str
    weight: float
    metadata: Dict[str, Any]
    source_memory_id: Optional[int]
    created_at_epoch: int
    updated_at_epoch: int


class GraphStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    source_memory_id INTEGER,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_nodes_user_type_label
                ON memory_nodes(user_id, node_type, label)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_nodes_user_created
                ON memory_nodes(user_id, created_at_epoch DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_nodes_user_source
                ON memory_nodes(user_id, source_memory_id)
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    src_node_id INTEGER NOT NULL,
                    dst_node_id INTEGER NOT NULL,
                    edge_type TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 0.5,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    source_memory_id INTEGER,
                    created_at_epoch INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_edges_unique
                ON memory_edges(user_id, src_node_id, dst_node_id, edge_type)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_edges_user_src
                ON memory_edges(user_id, src_node_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_edges_user_dst
                ON memory_edges(user_id, dst_node_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_edges_user_source
                ON memory_edges(user_id, source_memory_id)
                """
            )

            conn.commit()

    @staticmethod
    def _safe_json_loads(raw: Any, default: Dict[str, Any]) -> Dict[str, Any]:
        if raw is None:
            return dict(default)
        if isinstance(raw, dict):
            return raw
        text = str(raw).strip()
        if not text:
            return dict(default)
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else dict(default)
        except Exception:
            return dict(default)

    @staticmethod
    def _normalize_label(label: str) -> str:
        return " ".join(label.strip().split()).lower()

    def upsert_node(
        self,
        *,
        user_id: str,
        node_type: str,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
        source_memory_id: Optional[int] = None,
        confidence: float = 0.5,
    ) -> GraphNode:
        metadata = metadata or {}
        now = int(time.time())
        norm_label = self._normalize_label(label)

        with self._connect() as conn:
            cur = conn.cursor()
            existing = cur.execute(
                """
                SELECT * FROM memory_nodes
                WHERE user_id = ? AND node_type = ? AND label = ?
                LIMIT 1
                """,
                (user_id, node_type, norm_label),
            ).fetchone()

            if existing:
                existing_meta = self._safe_json_loads(existing["metadata_json"], {})
                merged_meta = dict(existing_meta)
                merged_meta.update(metadata)
                merged_conf = max(float(existing["confidence"]), float(confidence))
                cur.execute(
                    """
                    UPDATE memory_nodes
                    SET metadata_json = ?, confidence = ?, updated_at_epoch = ?,
                        source_memory_id = COALESCE(?, source_memory_id)
                    WHERE id = ?
                    """,
                    (
                        json.dumps(merged_meta, ensure_ascii=False),
                        merged_conf,
                        now,
                        source_memory_id,
                        int(existing["id"]),
                    ),
                )
                conn.commit()
                row = cur.execute("SELECT * FROM memory_nodes WHERE id = ?", (int(existing["id"]),)).fetchone()
            else:
                cur.execute(
                    """
                    INSERT INTO memory_nodes(
                        user_id, node_type, label, metadata_json, source_memory_id, confidence,
                        created_at_epoch, updated_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        node_type,
                        norm_label,
                        json.dumps(metadata, ensure_ascii=False),
                        source_memory_id,
                        float(confidence),
                        now,
                        now,
                    ),
                )
                conn.commit()
                row = cur.execute("SELECT * FROM memory_nodes WHERE id = ?", (cur.lastrowid,)).fetchone()

        return self._row_to_node(row)

    def upsert_edge(
        self,
        *,
        user_id: str,
        src_node_id: int,
        dst_node_id: int,
        edge_type: str,
        weight: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        source_memory_id: Optional[int] = None,
    ) -> GraphEdge:
        metadata = metadata or {}
        now = int(time.time())

        with self._connect() as conn:
            cur = conn.cursor()
            existing = cur.execute(
                """
                SELECT * FROM memory_edges
                WHERE user_id = ? AND src_node_id = ? AND dst_node_id = ? AND edge_type = ?
                LIMIT 1
                """,
                (user_id, src_node_id, dst_node_id, edge_type),
            ).fetchone()

            if existing:
                existing_meta = self._safe_json_loads(existing["metadata_json"], {})
                merged_meta = dict(existing_meta)
                merged_meta.update(metadata)
                merged_weight = max(float(existing["weight"]), float(weight))
                cur.execute(
                    """
                    UPDATE memory_edges
                    SET weight = ?, metadata_json = ?, updated_at_epoch = ?,
                        source_memory_id = COALESCE(?, source_memory_id)
                    WHERE id = ?
                    """,
                    (
                        merged_weight,
                        json.dumps(merged_meta, ensure_ascii=False),
                        now,
                        source_memory_id,
                        int(existing["id"]),
                    ),
                )
                conn.commit()
                row = cur.execute("SELECT * FROM memory_edges WHERE id = ?", (int(existing["id"]),)).fetchone()
            else:
                cur.execute(
                    """
                    INSERT INTO memory_edges(
                        user_id, src_node_id, dst_node_id, edge_type, weight, metadata_json,
                        source_memory_id, created_at_epoch, updated_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        int(src_node_id),
                        int(dst_node_id),
                        edge_type,
                        float(weight),
                        json.dumps(metadata, ensure_ascii=False),
                        source_memory_id,
                        now,
                        now,
                    ),
                )
                conn.commit()
                row = cur.execute("SELECT * FROM memory_edges WHERE id = ?", (cur.lastrowid,)).fetchone()

        return self._row_to_edge(row)

    def get_node(self, *, user_id: str, node_id: int) -> Optional[GraphNode]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_nodes WHERE id = ? AND user_id = ? LIMIT 1",
                (node_id, user_id),
            ).fetchone()
        return self._row_to_node(row) if row else None

    def list_nodes(self, *, user_id: str, limit: int = 50) -> List[GraphNode]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_nodes
                WHERE user_id = ?
                ORDER BY updated_at_epoch DESC, id DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 500))),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def list_edges_for_node(self, *, user_id: str, node_id: int, limit: int = 200) -> List[GraphEdge]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memory_edges
                WHERE user_id = ? AND (src_node_id = ? OR dst_node_id = ?)
                ORDER BY weight DESC, updated_at_epoch DESC, id DESC
                LIMIT ?
                """,
                (user_id, node_id, node_id, max(1, min(limit, 1000))),
            ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_neighbors(
        self,
        *,
        user_id: str,
        node_id: int,
        edge_types: Optional[Sequence[str]] = None,
        limit: int = 100,
    ) -> List[Tuple[GraphEdge, GraphNode]]:
        params: List[Any] = [user_id, node_id]
        sql = """
            SELECT
                e.*,
                n.id AS n_id,
                n.user_id AS n_user_id,
                n.node_type AS n_node_type,
                n.label AS n_label,
                n.metadata_json AS n_metadata_json,
                n.source_memory_id AS n_source_memory_id,
                n.confidence AS n_confidence,
                n.created_at_epoch AS n_created_at_epoch,
                n.updated_at_epoch AS n_updated_at_epoch
            FROM memory_edges e
            JOIN memory_nodes n
                ON n.id = CASE
                    WHEN e.src_node_id = ? THEN e.dst_node_id
                    ELSE e.src_node_id
                END
            WHERE e.user_id = ?
              AND (e.src_node_id = ? OR e.dst_node_id = ?)
        """
        params = [node_id, user_id, node_id, node_id]

        if edge_types:
            edge_types = [e for e in edge_types if e]
            if edge_types:
                placeholders = ",".join("?" for _ in edge_types)
                sql += f" AND e.edge_type IN ({placeholders})"
                params.extend(edge_types)

        sql += " ORDER BY e.weight DESC, e.updated_at_epoch DESC, e.id DESC LIMIT ?"
        params.append(max(1, min(limit, 2000)))

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        out: List[Tuple[GraphEdge, GraphNode]] = []
        for r in rows:
            edge = self._row_to_edge(r)
            node = GraphNode(
                id=int(r["n_id"]),
                user_id=str(r["n_user_id"]),
                node_type=str(r["n_node_type"]),
                label=str(r["n_label"]),
                metadata=self._safe_json_loads(r["n_metadata_json"], {}),
                source_memory_id=int(r["n_source_memory_id"]) if r["n_source_memory_id"] is not None else None,
                confidence=float(r["n_confidence"]),
                created_at_epoch=int(r["n_created_at_epoch"]),
                updated_at_epoch=int(r["n_updated_at_epoch"]),
            )
            out.append((edge, node))
        return out

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            node_type=str(row["node_type"]),
            label=str(row["label"]),
            metadata=self._safe_json_loads(row["metadata_json"], {}),
            source_memory_id=int(row["source_memory_id"]) if row["source_memory_id"] is not None else None,
            confidence=float(row["confidence"]),
            created_at_epoch=int(row["created_at_epoch"]),
            updated_at_epoch=int(row["updated_at_epoch"]),
        )

    def _row_to_edge(self, row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            src_node_id=int(row["src_node_id"]),
            dst_node_id=int(row["dst_node_id"]),
            edge_type=str(row["edge_type"]),
            weight=float(row["weight"]),
            metadata=self._safe_json_loads(row["metadata_json"], {}),
            source_memory_id=int(row["source_memory_id"]) if row["source_memory_id"] is not None else None,
            created_at_epoch=int(row["created_at_epoch"]),
            updated_at_epoch=int(row["updated_at_epoch"]),
        )
