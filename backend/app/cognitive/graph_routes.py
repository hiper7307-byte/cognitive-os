from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..tenant import resolve_user_id
from .graph_runtime import graph_service, graph_store

router = APIRouter(prefix="/cognitive/graph", tags=["cognitive-graph"])


class GraphNodeUpsertRequest(BaseModel):
    node_type: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=256)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_memory_id: Optional[int] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class GraphEdgeUpsertRequest(BaseModel):
    src_node_id: int = Field(ge=1)
    dst_node_id: int = Field(ge=1)
    edge_type: str = Field(min_length=1, max_length=64)
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_memory_id: Optional[int] = None


class GraphIngestRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    source_memory_id: Optional[int] = None


class GraphTraverseRequest(BaseModel):
    start_node_id: int = Field(ge=1)
    max_hops: int = Field(default=2, ge=1, le=5)
    edge_types: Optional[List[str]] = None
    per_hop_limit: int = Field(default=50, ge=1, le=500)


@router.put("/nodes")
def upsert_node(req: GraphNodeUpsertRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    node = graph_service.upsert_node(
        user_id=user_id,
        node_type=req.node_type,
        label=req.label,
        metadata=req.metadata,
        source_memory_id=req.source_memory_id,
        confidence=req.confidence,
    )
    return {
        "ok": True,
        "node": {
            "id": node.id,
            "node_type": node.node_type,
            "label": node.label,
            "metadata": node.metadata,
            "source_memory_id": node.source_memory_id,
            "confidence": node.confidence,
            "created_at_epoch": node.created_at_epoch,
            "updated_at_epoch": node.updated_at_epoch,
        },
    }


@router.put("/edges")
def upsert_edge(req: GraphEdgeUpsertRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    edge = graph_service.upsert_edge(
        user_id=user_id,
        src_node_id=req.src_node_id,
        dst_node_id=req.dst_node_id,
        edge_type=req.edge_type,
        weight=req.weight,
        metadata=req.metadata,
        source_memory_id=req.source_memory_id,
    )
    return {
        "ok": True,
        "edge": {
            "id": edge.id,
            "src_node_id": edge.src_node_id,
            "dst_node_id": edge.dst_node_id,
            "edge_type": edge.edge_type,
            "weight": edge.weight,
            "metadata": edge.metadata,
            "source_memory_id": edge.source_memory_id,
            "created_at_epoch": edge.created_at_epoch,
            "updated_at_epoch": edge.updated_at_epoch,
        },
    }


@router.post("/ingest")
def ingest(req: GraphIngestRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    return graph_service.ingest_memory(
        user_id=user_id,
        content=req.content,
        memory_id=req.source_memory_id,
    )


@router.post("/query")
def traverse(req: GraphTraverseRequest, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    return graph_service.traverse(
        user_id=user_id,
        start_node_id=req.start_node_id,
        max_hops=req.max_hops,
        edge_types=req.edge_types,
        per_hop_limit=req.per_hop_limit,
    )


@router.get("/nodes")
def list_nodes(limit: int = 50, user_id: str = Depends(resolve_user_id)) -> Dict[str, Any]:
    rows = graph_store.list_nodes(user_id=user_id, limit=limit)
    return {
        "ok": True,
        "count": len(rows),
        "nodes": [
            {
                "id": n.id,
                "node_type": n.node_type,
                "label": n.label,
                "metadata": n.metadata,
                "source_memory_id": n.source_memory_id,
                "confidence": n.confidence,
                "created_at_epoch": n.created_at_epoch,
                "updated_at_epoch": n.updated_at_epoch,
            }
            for n in rows
        ],
    }
