
import math
import re
from collections import Counter
from typing import List, Dict, Any

class BM25Retriever:
    """
    Lightweight in-memory BM25 implementation for Hybrid Search.
    Ideal for < 100,000 chunks.
    """
    
    def __init__(self, chunks: List[Dict[str, Any]]):
        """
        Initialize with a list of chunks/docs.
        chunks: List of dicts, must have 'content' and 'id' fields.
        """
        self.chunks = chunks
        self.corpus_size = len(chunks)
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.tokenized_corpus = []
        
        # Hyperparameters
        self.k1 = 1.5
        self.b = 0.75
        
        self._index_corpus()
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple regex analyzer."""
        return [w.lower() for w in re.findall(r'\b\w\w+\b', text)]
        
    def _index_corpus(self):
        """Builds stats for BM25."""
        if not self.chunks: return
        
        print(f"Index: Building BM25 for {self.corpus_size} chunks...")
        total_len = 0
        
        for chunk in self.chunks:
            tokens = self._tokenize(chunk.get('content', ''))
            self.tokenized_corpus.append(tokens)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            
            # Count frequencies
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)
            
            for token in freqs.keys():
                self.idf[token] = self.idf.get(token, 0) + 1
                
        self.avgdl = total_len / self.corpus_size
        
        # Calculate IDF
        for token, freq in self.idf.items():
            self.idf[token] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
            
    def _get_score(self, query_tokens: List[str], index: int) -> float:
        score = 0.0
        doc_tokens = self.doc_freqs[index]
        doc_len = self.doc_len[index]
        
        for token in query_tokens:
            if token not in doc_tokens: continue
            
            freq = doc_tokens[token]
            numerator = self.idf.get(token, 0) * freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += numerator / denominator
            
        return score
        
    def search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        Search the corpus.
        Returns list of (chunk, score).
        """
        if not self.chunks: return []
        
        query_tokens = self._tokenize(query)
        scores = []
        
        for i in range(self.corpus_size):
            score = self._get_score(query_tokens, i)
            if score > 0:
                scores.append((self.chunks[i], score))
                
        # Sort desc
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
