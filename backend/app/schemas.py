from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Core task ----------

class TaskRequest(BaseModel):
    text: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    task_id: str
    intent: str
    ok: bool
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


# ---------- Memory ----------

class MemoryWriteRequest(BaseModel):
    memory_type: Literal["episodic", "semantic", "procedural", "reflective"]
    content: str = Field(..., min_length=1)
    source_task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    retention_until: Optional[str] = None
    embed: bool = True


class MemoryWriteResponse(BaseModel):
    ok: bool
    memory_id: int


class MemoryRecentResponse(BaseModel):
    ok: bool
    count: int
    results: List[Dict[str, Any]]


class MemoryQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    types: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)


class MemoryQueryResponse(BaseModel):
    ok: bool
    count: int
    results: List[Dict[str, Any]]


# ---------- Vector ----------

class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=100)
    memory_types: Optional[List[str]] = None
    namespace: str = "memory"


class VectorSearchResponse(BaseModel):
    ok: bool
    count: int
    query: str
    model: str
    results: List[Dict[str, Any]]


class VectorStatsResponse(BaseModel):
    ok: bool
    namespace: str
    model: str
    total_vectors: int
    by_memory_type: Dict[str, int]


# ---------- LLM / Arbitration ----------

class ArbitrationMeta(BaseModel):
    mode: str = "hybrid"  # memory_only | llm_only | hybrid
    confidence: float = 0.0
    scores: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class LLMChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    use_memory: bool = True
    memory_limit: int = Field(default=8, ge=1, le=50)


class LLMChatResponse(BaseModel):
    ok: bool
    message: str
    memory_used: int = 0
    arbitration: Optional[ArbitrationMeta] = None

# Backward-compatible aliases in case other modules use old casing
LlmChatRequest = LLMChatRequest
LlmChatResponse = LLMChatResponse


# ---------- Temporal ----------
# ---------- Temporal ----------

class TemporalTaskCreateRequest(BaseModel):
    kind: str
    run_at_epoch: int
    payload: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None


class TemporalTaskCreateResponse(BaseModel):
    ok: bool
    temporal_task_id: int
    status: str


class TemporalRunDueResponse(BaseModel):
    ok: bool
    processed: int


class TemporalTasksResponse(BaseModel):
    ok: bool
    count: int
    results: List[Dict[str, Any]]


# Backward compatibility (if any older imports still use old names)
TemporalCreateRequest = TemporalTaskCreateRequest
TemporalCreateResponse = TemporalTaskCreateResponse

# ---------- Identity ----------

class IdentityDecisionRequest(BaseModel):
    task_id: str
    decision_type: str
    decision_payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class IdentityDecisionResponse(BaseModel):
    ok: bool
    decision_id: int


class IdentityProfileResponse(BaseModel):
    ok: bool
    profile: Dict[str, Any]


# ---------- Health ----------

class HealthResponse(BaseModel):
    ok: bool
    service: str
    llm_enabled: bool

