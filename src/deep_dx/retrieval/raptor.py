
"""
Deep-Dx RAPTOR Module
Recursive Abstractive Processing for Tree-Organized Retrieval
"""

import numpy as np
import faiss
from typing import List, Dict, Tuple
from sklearn.cluster import KMeans # Robust alternative
from anthropic import Anthropic
from deep_dx.retrieval.indexer import DeepDxIndexer
from neurosynth.config import get_settings as get_sys_settings

class RaptorIndexer:
    """
    Builds a hierarchical tree of summaries on top of base chunks.
    1. Clusters chunks.
    2. Summarizes clusters.
    3. Recursively clusters summaries until root.
    """
    
    def __init__(self, base_indexer: DeepDxIndexer):
        self.indexer = base_indexer
        self.sys_settings = get_sys_settings()
        
        if not self.sys_settings.anthropic_api_key:
            raise ValueError("Anthropic API Key required for RAPTOR summarization.")
            
        self.client = Anthropic(api_key=self.sys_settings.anthropic_api_key)
        self.model = "claude-3-haiku-20240307"

    def cluster_embeddings(self, embeddings: np.ndarray, max_cluster_size: int = 10) -> List[List[int]]:
        """
        Clusters embeddings using Sklearn KMeans (Faiss can be brittle with small N).
        Returns list of lists (indices of items in each cluster).
        """
        n_samples = embeddings.shape[0]
        if n_samples <= max_cluster_size:
            return [list(range(n_samples))] # Single cluster
            
        n_clusters = max(1, n_samples // max_cluster_size)
        
        # Scikit-learn KMeans
        kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        kmeans.fit(embeddings)
        labels = kmeans.labels_
        
        clusters = [[] for _ in range(n_clusters)]
        for i, label in enumerate(labels):
            clusters[label].append(i)
            
        # Filter empty clusters
        return [c for c in clusters if c]

    def summarize_cluster(self, cluster_text: str) -> str:
        """Generates a summary of the cluster text using Claude."""
        prompt = f"""You are an expert medical summarizer.
Summarize the following group of text chunks into a comprehensive abstract.
Focus on clinical protocols, treatments, and key anatomical details.
Preserve specific medical terminology.

TEXT TO SUMMARIZE:
{cluster_text[:20000]}  # Truncate to avoid context overflow if huge

SUMMARY:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"⚠️ Summarization failed: {e}")
            return "Summary generation failed."

    def build_tree(self, chunks: List[Dict], distinct_layer_name: str = "raptor") -> List[Dict]:
        """
        Recursive function to build layers.
        Returns ALL nodes (original chunks + summaries).
        """
        all_nodes = chunks.copy() # Level 0
        current_layer_nodes = chunks
        
        level = 1
        while len(current_layer_nodes) > 5: # Stop when we have few summary nodes
            print(f"🦖 RAPTOR Level {level}: Processing {len(current_layer_nodes)} nodes...")
            
            # 1. Embed current layer
            embeddings = self.indexer.encode_chunks(current_layer_nodes)
            
            # 2. Cluster
            clusters = self.cluster_embeddings(embeddings)
            print(f"   -> Formed {len(clusters)} clusters.")
            
            next_layer_nodes = []
            
            # 3. Summarize each cluster
            for i, cluster_indices in enumerate(clusters):
                # Concatenate texts
                cluster_texts = [current_layer_nodes[idx]['text'] for idx in cluster_indices]
                full_text = "\n---\n".join(cluster_texts)
                
                print(f"   -> Summarizing Cluster {i+1}/{len(clusters)} ({len(cluster_texts)} chunks)...")
                summary = self.summarize_cluster(full_text)
                
                # Create Summary Node
                node = {
                    "text": summary,
                    "metadata": {
                        "source": f"RAPTOR_Layer_{level}_Cluster_{i}",
                        "is_summary": True,
                        "level": level,
                        "child_count": len(cluster_indices)
                    }
                }
                next_layer_nodes.append(node)
                
            # Add to collection and recurse
            all_nodes.extend(next_layer_nodes)
            current_layer_nodes = next_layer_nodes
            level += 1
            
        return all_nodes

    def run(self, source_dir: Path, index_name: str = "deep_dx_raptor"):
        """Execution pipeline."""
        # 1. Load base PDFs (Level 0)
        print("📂 Loading Level 0 (Base Chunks)...")
        level_0_chunks = []
        pdf_files = list(source_dir.glob("*.pdf"))
        # Limit for demo/testing to avoid huge token costs on full library immediately?
        # User asked to proceed with RAPTOR. We should probably do a subset or full?
        # Let's do FULL as requested, but warning: it might be slow.
        # Update: To be safe, let's limit to 5 PDFs for the 'build' to prove it works first validation step.
        # Actually user said "Index 20 PDFs" in Phase 1. 
        # For RAPTOR, let's start with a subset in the test, but the class should handle all.
        
        for pdf_file in pdf_files:
            level_0_chunks.extend(self.indexer.load_and_chunk_pdf(pdf_file))
            
        print(f"📚 Total Base Chunks: {len(level_0_chunks)}")
        
        # 2. Build Tree
        all_nodes = self.build_tree(level_0_chunks)
        
        # 3. Save Final Index
        print(f"💾 Saving RAPTOR Index ({len(all_nodes)} nodes)...")
        embeddings = self.indexer.encode_chunks(all_nodes)
        self.indexer.save_index(embeddings, all_nodes, index_name)
