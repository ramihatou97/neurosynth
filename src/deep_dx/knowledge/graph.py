
"""
Deep-Dx Knowledge Graph Module
Extracts entities and relationships from medical text and ingests into Neo4j.
"""

import json
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from neo4j import GraphDatabase
from deep_dx.config import get_deepdx_settings
from neurosynth.config import get_settings as get_sys_settings

class DeepDxKnowledgeGraph:
    """
    Manages Knowledge Graph operations:
    1. Extraction: LLM-based entity/relationship extraction.
    2. Ingestion: Cypher queries to build the graph in Neo4j.
    """
    
    def __init__(self):
        self.settings = get_deepdx_settings()
        self.sys_settings = get_sys_settings()
        
        # 1. Setup LLM
        if not self.sys_settings.anthropic_api_key:
            raise ValueError("Anthropic API Key required for KG Extraction.")
        self.client = Anthropic(api_key=self.sys_settings.anthropic_api_key)
        self.model = "claude-3-haiku-20240307"
        
        # 2. Setup Neo4j (Lazy connection or fail-soft)
        self.driver = None
        self.connected = False
        try:
            # TODO: Move auth to config/env
            # For now default local dev creds as per plan
            uri = self.settings.neo4j_uri or "bolt://localhost:7687"
            user = self.settings.neo4j_user or "neo4j"
            pwd = self.settings.neo4j_password or "password" # usually user needs to set this
            
            self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
            self.driver.verify_connectivity()
            self.connected = True
            print("🔌 Connected to Neo4j successfully.")
        except Exception as e:
            print(f"⚠️ Neo4j Connection Failed: {e}")
            print("   -> Graph operations will run in 'Dry Run' mode (Extraction only).")

    def close(self):
        if self.driver:
            self.driver.close()

    def extract_entities(self, text: str) -> Dict[str, List[Any]]:
        """
        Extracts structured graph data from text.
        Returns: {
            "entities": [{"name": "Glioblastoma", "label": "Disease"}, ...],
            "relationships": [{"head": "Temozolomide", "type": "TREATS", "tail": "Glioblastoma"}]
        }
        """
        prompt = f"""You are a Knowledge Graph extraction engine for Neurosurgery.
Extract clinical entities and relationships from the text below.

Tx: {text[:4000]}

SCHEMA:
- Entities: [Disease, Treatment, Anatomy, Symptom, Complication]
- Relationships: [TREATS, CAUSES, LOCATED_IN, PREVENTS, DIAGNOSES]

OUTPUT FORMAT (JSON):
{{
  "entities": [
    {{"name": "Standardized Name", "label": "Label"}}
  ],
  "relationships": [
    {{"head": "Entity Name", "type": "REL_TYPE", "tail": "Entity Name"}}
  ]
}}
Extract only explicitly stated facts. Minimize duplicates.
"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Helper logic to strip markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            data = json.loads(content)
            return data
            
        except Exception as e:
            print(f"❌ Extraction Failed: {e}")
            return {"entities": [], "relationships": []}

    def ingest_chunk(self, chunk_id: str, text: str, source: str):
        """
        Extracts data from a chunk and writes 
        (Chunk)-[:MENTIONS]->(Entities) and (Entity)-[REL]->(Entity) to Neo4j.
        """
        # 1. Extract
        graph_data = self.extract_entities(text)
        if not graph_data.get("entities"):
            return # Nothing found
            
        print(f"   -> Extracted {len(graph_data['entities'])} entities, {len(graph_data['relationships'])} rels.")
        
        if not self.connected:
            return # Stop here if no DB
            
        # 2. Write to Neo4j
        with self.driver.session() as session:
            # Create Chunk Node
            session.run(
                """
                MERGE (c:Chunk {id: $chunk_id})
                SET c.text = $text, c.source = $source
                """,
                chunk_id=chunk_id, text=text, source=source
            )
            
            # Create Entities and MENTIONS
            for ent in graph_data['entities']:
                if not ent.get("name") or not ent.get("label"): continue
                
                # Dynamic cypher for Label is tricky, safer to use explicit logic or generic node with property
                # But typically we want explicit labels.
                # Here we default to :Concept and add secondary label dynamically or use prop.
                # Let's use :Concept and a property for simplicity/safety first.
                
                query = """
                MERGE (e:Concept {name: $name})
                SET e.label = $label
                WITH e
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (c)-[:MENTIONS]->(e)
                """
                session.run(query, name=ent['name'], label=ent['label'], chunk_id=chunk_id)

            # Create Intrinsic Relationships
            for rel in graph_data['relationships']:
                # Ensure both ends exist (they should from entities list, but be safe)
                query = """
                MERGE (h:Concept {name: $head})
                MERGE (t:Concept {name: $tail})
                WITH h, t
                CALL apoc.create.relationship(h, $type, {}, t) YIELD rel
                RETURN rel
                """
                # Note: APOC might not be installed. Standard cypher match is safer if types are fixed.
                # But types are dynamic from LLM.
                # Fallback: Fixed list mapping or specific queries.
                # Let's allow specific trusted types.
                
                rtype = rel['type'].upper().replace(" ", "_")
                allowed_rels = ["TREATS", "CAUSES", "LOCATED_IN", "PREVENTS", "DIAGNOSES"]
                if rtype not in allowed_rels:
                    rtype = "RELATED_TO"
                    
                # We can construct the query string safely since we whitelist rtype or sanitize
                query = f"""
                MATCH (h:Concept {{name: $head}})
                MATCH (t:Concept {{name: $tail}})
                MERGE (h)-[:{rtype}]->(t)
                """
                session.run(query, head=rel['head'], tail=rel['tail'])

