"""
GraphRAG: Graph-based Retrieval Augmented Generation
=====================================================
extracts entities and relationships to build a semantic knowledge graph.
Enables "Reasoning" queries by traversing relationships.

1. Extract: LLM -> (Entity, Relation, Entity)
2. Build: NetworkX Graph
3. Traverse: Find paths between entities
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import networkx as nx

from src.ai.client import AIClient
from src.models import Chunk

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name: str
    type: str  # e.g. "Drug", "Disease", "Anatomy"
    description: str = ""


@dataclass
class Relation:
    source: str
    target: str
    type: str  # e.g. "TREATS", "CAUSES", "LOCATED_IN"
    description: str = ""


class KnowledgeGraphBuilder:
    """
    Builds and queries a Knowledge Graph from chunks.
    """

    def __init__(self, ai_client: AIClient):
        self.ai = ai_client
        self.graph = nx.DiGraph()

    async def process_chunks(self, chunks: list[Chunk]):
        """
        Extract triples from chunks and update the graph.
        """
        for chunk in chunks:
            try:
                triples = await self._extract_triples(chunk.content)
                self._update_graph(triples, source_chunk_id=chunk.id)
            except Exception as e:
                logger.error(f"Graph extraction failed for chunk {chunk.id}: {e}")

    async def _extract_triples(self, text: str) -> list[dict[str, Any]]:
        """
        Use LLM to extract (Subject, Predicate, Object) triples.
        Returns JSON list of triples.
        """
        prompt = (
            "Extract knowledge triples from the text below.\n"
            "Format: JSON list of objects with keys: 'head', 'relation', 'tail', 'head_type', 'tail_type'.\n"
            "Entities should be atomic (e.g. 'Glioblastoma', not 'The Glioblastoma tumor').\n"
            "Relations should be specific (e.g. 'LOCATED_IN', 'CAUSES', 'TREATED_BY').\n\n"
            f"Text: {text[:4000]}"
        )

        try:
            response = await self.ai.synthesize(
                prompt, max_tokens=2000, temperature=0.0
            )
            # Parse JSON (assuming client returns string)
            # This depends on AIClient implementation.
            # If it returns raw text, we need to parse it.
            # Let's assume response is the JSON string.
            import re

            # Simple heuristic cleaning if markdown code blocks exist
            cleaned = re.sub(r"```json|```", "", response).strip()
            data = json.loads(cleaned)
            return data.get("triples", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.warning(f"Triple extraction failed: {e}")
            return []

    def _update_graph(self, triples: list[dict[str, Any]], source_chunk_id: str):
        """
        Add triples to NetworkX graph.
        """
        for t in triples:
            head = t.get("head")
            tail = t.get("tail")
            rel = t.get("relation")

            if not head or not tail or not rel:
                continue

            # Add Nodes
            self.graph.add_node(head, type=t.get("head_type", "Unknown"))
            self.graph.add_node(tail, type=t.get("tail_type", "Unknown"))

            # Add Edge
            self.graph.add_edge(head, tail, relation=rel, source_chunk=source_chunk_id)

    def search(self, query_entities: list[str], depth: int = 1) -> list[str]:
        """
        Return text description of graph neighborhood for query entities.
        """
        subgraph_nodes = set()

        for entity in query_entities:
            # Fuzzy match? For MVP, assume exact match or simple case-insensitive
            # Real implementation needs generic entity resolution/linking.
            matches = [n for n in self.graph.nodes if entity.lower() in n.lower()]

            for match in matches:
                # Get neighbors
                k_hop = nx.single_source_shortest_path_length(
                    self.graph, match, cutoff=depth
                )
                subgraph_nodes.update(k_hop.keys())

        if not subgraph_nodes:
            return []

        # Serialize subgraph to text for the LLM
        context = []
        subgraph = self.graph.subgraph(subgraph_nodes)
        for u, v, data in subgraph.edges(data=True):
            context.append(f"{u} --[{data['relation']}]--> {v}")

        return context
