from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .graph_store import GraphEdge, GraphNode, GraphStore

_EDGE_HINT_PATTERNS: Sequence[Tuple[str, str]] = (
    (r"\bdepends on\b", "depends_on"),
    (r"\bblocked by\b", "blocked_by"),
    (r"\bsupports?\b", "supports"),
    (r"\bcontradicts?\b", "contradicts"),
    (r"\binspired by\b", "inspired_by"),
    (r"\blearned from\b", "learned_from"),
    (r"\bcaused by\b", "caused_by"),
    (r"\brelated to\b", "related_to"),
)

# terms that should never become standalone concept nodes
_VERB_NOISE = {
    "depends", "support", "supports", "contradict", "contradicts", "caused",
    "inspired", "learned", "blocked", "related", "create", "created", "run",
    "executed", "enqueue", "enqueued", "saved", "save", "check", "final",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "it", "this", "that", "at", "as", "by", "from", "about",
    "into", "over", "under", "after", "before", "between", "during", "within",
}


@dataclass(frozen=True)
class ProposedNode:
    node_type: str
    label: str
    confidence: float
    metadata: Dict[str, object]


@dataclass(frozen=True)
class ProposedEdge:
    src_label: str
    dst_label: str
    edge_type: str
    weight: float
    metadata: Dict[str, object]


class GraphLinker:
    def __init__(self, store: GraphStore) -> None:
        self.store = store

    @staticmethod
    def _sentences(text: str) -> List[str]:
        chunks = re.split(r"(?<=[\.\!\?])\s+", text.strip())
        return [c.strip() for c in chunks if c.strip()]

    @staticmethod
    def _normalize_label(label: str) -> str:
        return " ".join(label.strip().split()).lower()

    def _is_noise_label(self, label: str) -> bool:
        t = self._normalize_label(label)
        if not t:
            return True
        if t in _VERB_NOISE:
            return True
        if len(t) <= 2:
            return True
        if all(ch in "-_:[]{}()'\"." for ch in t):
            return True
        return False

    def _extract_phrases(self, sentence: str) -> List[str]:
        s = sentence.strip()

        # 1) Quoted phrases
        quoted = re.findall(r'"([^"]{2,120})"|\'([^\']{2,120})\'', s)
        quoted_vals = [self._normalize_label(a or b) for a, b in quoted if (a or b).strip()]

        # 2) Title-case entities (AI Task OS, Memory Governance)
        title_entities = re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,5})\b", s)
        title_vals = [self._normalize_label(x) for x in title_entities]

        # 3) Hyphen-aware noun-ish chunks
        chunk_vals: List[str] = []
        for m in re.finditer(r"\b([a-zA-Z][a-zA-Z0-9\-]{2,})(?:\s+([a-zA-Z][a-zA-Z0-9\-]{2,})){0,3}\b", s):
            phrase = self._normalize_label(m.group(0))
            words = phrase.split()
            if not words:
                continue
            if words[0] in _STOPWORDS:
                continue
            # reject chunks that are mostly stopwords
            stop_count = sum(1 for w in words if w in _STOPWORDS)
            if stop_count >= len(words):
                continue
            chunk_vals.append(phrase)

        merged = quoted_vals + title_vals + chunk_vals

        # de-dup + clean
        out: List[str] = []
        seen: Set[str] = set()
        for p in merged:
            if p in seen:
                continue
            if self._is_noise_label(p):
                continue
            # remove very generic single words
            if len(p.split()) == 1 and (p in _STOPWORDS or p in _VERB_NOISE):
                continue
            seen.add(p)
            out.append(p)

        # keep best first
        return out[:12]

    def _guess_node_type(self, label: str) -> str:
        t = label.lower()
        if any(x in t for x in ("project", "repo", "app", "platform", "system", "os")):
            return "project"
        if any(x in t for x in ("goal", "milestone", "target", "objective", "roadmap")):
            return "goal"
        if any(x in t for x in ("risk", "constraint", "blocker", "issue")):
            return "constraint"
        if len(t.split()) >= 2:
            return "concept"
        if re.match(r"^[0-9a-f]{8}-[0-9a-f\-]{27,}$", t):
            return "fact"
        return "concept"

    def _edge_type_for_sentence(self, sentence: str) -> str:
        for pattern, e_type in _EDGE_HINT_PATTERNS:
            if re.search(pattern, sentence, flags=re.IGNORECASE):
                return e_type
        return "related_to"

    def propose(self, *, text: str) -> Tuple[List[ProposedNode], List[ProposedEdge]]:
        sentences = self._sentences(text)
        nodes: List[ProposedNode] = []
        edges: List[ProposedEdge] = []

        for s in sentences:
            phrases = self._extract_phrases(s)
            if not phrases:
                continue

            for p in phrases:
                nodes.append(
                    ProposedNode(
                        node_type=self._guess_node_type(p),
                        label=p,
                        confidence=0.62,
                        metadata={"source": "graph_linker_v2", "sentence": s[:300]},
                    )
                )

            edge_type = self._edge_type_for_sentence(s)

            # chain edges over all adjacent phrases: p0->p1, p1->p2, ...
            if len(phrases) >= 2:
                for i in range(len(phrases) - 1):
                    src = phrases[i]
                    dst = phrases[i + 1]
                    if src == dst:
                        continue
                    edges.append(
                        ProposedEdge(
                            src_label=src,
                            dst_label=dst,
                            edge_type=edge_type,
                            weight=0.68 if edge_type != "related_to" else 0.58,
                            metadata={"source": "graph_linker_v2", "sentence": s[:300], "index": i},
                        )
                    )
                    # For relation types that are usually symmetric in memory browsing, add reverse weak edge
                    if edge_type in {"related_to", "supports"}:
                        edges.append(
                            ProposedEdge(
                                src_label=dst,
                                dst_label=src,
                                edge_type=edge_type,
                                weight=0.51,
                                metadata={"source": "graph_linker_v2", "sentence": s[:300], "reverse": True},
                            )
                        )

        # de-dup nodes
        dedup_nodes: Dict[Tuple[str, str], ProposedNode] = {}
        for n in nodes:
            key = (n.node_type, n.label)
            prev = dedup_nodes.get(key)
            if prev is None or n.confidence > prev.confidence:
                dedup_nodes[key] = n

        # de-dup edges
        dedup_edges: Dict[Tuple[str, str, str], ProposedEdge] = {}
        for e in edges:
            key = (e.src_label, e.dst_label, e.edge_type)
            prev = dedup_edges.get(key)
            if prev is None or e.weight > prev.weight:
                dedup_edges[key] = e

        return list(dedup_nodes.values()), list(dedup_edges.values())

    def ingest_text(
        self,
        *,
        user_id: str,
        text: str,
        source_memory_id: Optional[int] = None,
    ) -> Dict[str, object]:
        proposed_nodes, proposed_edges = self.propose(text=text)

        label_to_node: Dict[str, GraphNode] = {}
        created_nodes: List[GraphNode] = []
        created_edges: List[GraphEdge] = []

        for n in proposed_nodes:
            node = self.store.upsert_node(
                user_id=user_id,
                node_type=n.node_type,
                label=n.label,
                metadata=n.metadata,
                source_memory_id=source_memory_id,
                confidence=n.confidence,
            )
            label_to_node[n.label] = node
            created_nodes.append(node)

        for e in proposed_edges:
            src = label_to_node.get(e.src_label)
            dst = label_to_node.get(e.dst_label)
            if src is None or dst is None or src.id == dst.id:
                continue
            edge = self.store.upsert_edge(
                user_id=user_id,
                src_node_id=src.id,
                dst_node_id=dst.id,
                edge_type=e.edge_type,
                weight=e.weight,
                metadata=e.metadata,
                source_memory_id=source_memory_id,
            )
            created_edges.append(edge)

        return {
            "ok": True,
            "nodes_upserted": len(created_nodes),
            "edges_upserted": len(created_edges),
            "node_ids": [n.id for n in created_nodes],
            "edge_ids": [e.id for e in created_edges],
        }
