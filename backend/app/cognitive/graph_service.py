from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .graph_linker import GraphLinker
from .graph_store import GraphEdge, GraphNode, GraphStore


class GraphService:
    def __init__(self, store: GraphStore, linker: GraphLinker) -> None:
        self.store = store
        self.linker = linker

    def ingest_memory(
        self,
        *,
        user_id: str,
        content: str,
        memory_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self.linker.ingest_text(
            user_id=user_id,
            text=content,
            source_memory_id=memory_id,
        )

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
        return self.store.upsert_node(
            user_id=user_id,
            node_type=node_type,
            label=label,
            metadata=metadata,
            source_memory_id=source_memory_id,
            confidence=confidence,
        )

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
        return self.store.upsert_edge(
            user_id=user_id,
            src_node_id=src_node_id,
            dst_node_id=dst_node_id,
            edge_type=edge_type,
            weight=weight,
            metadata=metadata,
            source_memory_id=source_memory_id,
        )

    def traverse(
        self,
        *,
        user_id: str,
        start_node_id: int,
        max_hops: int = 2,
        edge_types: Optional[Sequence[str]] = None,
        per_hop_limit: int = 50,
    ) -> Dict[str, Any]:
        max_hops = max(1, min(max_hops, 5))
        per_hop_limit = max(1, min(per_hop_limit, 500))

        start = self.store.get_node(user_id=user_id, node_id=start_node_id)
        if start is None:
            return {"ok": False, "error": "start node not found"}

        visited_nodes: Set[int] = {start.id}
        visited_edges: Set[int] = set()

        node_map: Dict[int, GraphNode] = {start.id: start}
        edges_out: List[GraphEdge] = []

        q: deque[Tuple[int, int]] = deque()
        q.append((start.id, 0))

        while q:
            node_id, depth = q.popleft()
            if depth >= max_hops:
                continue

            neighbors = self.store.get_neighbors(
                user_id=user_id,
                node_id=node_id,
                edge_types=edge_types,
                limit=per_hop_limit,
            )

            for edge, node in neighbors:
                if edge.id not in visited_edges:
                    visited_edges.add(edge.id)
                    edges_out.append(edge)

                if node.id not in visited_nodes:
                    visited_nodes.add(node.id)
                    node_map[node.id] = node
                    q.append((node.id, depth + 1))

        return {
            "ok": True,
            "start_node_id": start.id,
            "nodes": [self._node_to_dict(n) for n in node_map.values()],
            "edges": [self._edge_to_dict(e) for e in edges_out],
            "hops": max_hops,
            "counts": {"nodes": len(node_map), "edges": len(edges_out)},
        }

    @staticmethod
    def _node_to_dict(n: GraphNode) -> Dict[str, Any]:
        return {
            "id": n.id,
            "user_id": n.user_id,
            "node_type": n.node_type,
            "label": n.label,
            "metadata": n.metadata,
            "source_memory_id": n.source_memory_id,
            "confidence": n.confidence,
            "created_at_epoch": n.created_at_epoch,
            "updated_at_epoch": n.updated_at_epoch,
        }

    @staticmethod
    def _edge_to_dict(e: GraphEdge) -> Dict[str, Any]:
        return {
            "id": e.id,
            "user_id": e.user_id,
            "src_node_id": e.src_node_id,
            "dst_node_id": e.dst_node_id,
            "edge_type": e.edge_type,
            "weight": e.weight,
            "metadata": e.metadata,
            "source_memory_id": e.source_memory_id,
            "created_at_epoch": e.created_at_epoch,
            "updated_at_epoch": e.updated_at_epoch,
        }
