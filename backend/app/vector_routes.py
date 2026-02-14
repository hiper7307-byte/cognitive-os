from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from .embedding_provider import embedding_provider
from .memory import memory_service
from .schemas import VectorSearchRequest, VectorSearchResponse

router = APIRouter(tags=["vector"])


def _require_user_id(x_user_id: str | None) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    return user_id


@router.post("/vector/search", response_model=VectorSearchResponse)
def vector_search(
    req: VectorSearchRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    user_id = _require_user_id(x_user_id)
    query = (req.query or "").strip()
    if not query:
        return VectorSearchResponse(ok=True, count=0, query=req.query, model=embedding_provider.model_name, results=[])

    qvec = embedding_provider.embed(query)
    ranked = memory_service.vector_store.search(
        user_id=user_id,
        query_vector=qvec,
        namespace=memory_service.namespace,
        model=memory_service.embedding_model_name,
        top_k=req.top_k,
        memory_types=req.memory_types,
    )

    results = []
    for memory_id, score in ranked:
        row = memory_service.get(user_id=user_id, memory_id=memory_id)
        if row is None:
            continue
        row["vector_score"] = score
        results.append(row)

    return VectorSearchResponse(
        ok=True,
        count=len(results),
        query=req.query,
        model=embedding_provider.model_name,
        results=results,
    )
