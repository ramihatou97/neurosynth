
from ragatouille import RAGPretrainedModel
import sys

def main():
    print("🦞 Testing RAGatouille (ColBERT) in clean env...")
    try:
        # Load Model
        RAG = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")
        
        # Test Indexing (Tiny data)
        docs = [
            "Glioblastoma is treated with Stupp protocol.",
            "Deep vein thrombosis requires anticoagulation.",
            "The pineal gland produces melatonin."
        ]
        
        print("⚡ Indexing 3 docs...")
        index_path = RAG.index(index_name="test_colbert", collection=docs)
        print(f"✅ Index created at {index_path}")
        
        # Test Retrieval
        query = "How to treat glioblastoma?"
        print(f"❓ Query: {query}")
        results = RAG.search(query)
        print(f"✅ Results: {results}")
        
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
