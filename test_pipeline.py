
from src.deep_dx.retrieval.colbert_client import ColBERTClient

def main():
    # Note: Search requires an index to exist. 
    # If this is a fresh run, search might fail unless we point to an index.
    # We will test rerank first as it doesn't need an index.
    
    client = ColBERTClient()

    print("\n-----------------------")
    print("Testing Rerank...")
    print("-----------------------")
    docs = [
        "The facial nerve is anterior to the tumor.",
        "The patient liked the soup.",
        "Cranial nerve VII runs through the internal auditory canal."
    ]
    reranked = client.rerank("facial nerve location", docs)
    # The output format of rerank in ragatouille is usually a list of dicts with 'content', 'score', 'rank'
    # The client returns this list directly.
    if reranked:
        print(f"Top rerank: {reranked[0]}") 
        # Should be index 0 or 2, definitely not 1
    else:
        print("❌ Rerank returned no results.")

    print("\n-----------------------")
    print("Testing Indexing...")
    try:
        # Create a small index so search works
        docs = [
            "Glioblastoma multiforme is a grade IV astrocytoma.",
            "The facial nerve (CN VII) exits the skull via the stylomastoid foramen.",
            "Treatment for hydrocephalus often involves a ventriculoperitoneal shunt."
        ]
        client.index(index_name="neurosynth_v1", documents=docs)
    except Exception as e:
        print(f"Indexing failed: {e}")

    print("\n-----------------------")
    print("Testing Search...")
    print("-----------------------")
    try:
        # We need to make sure the client uses the correct path.
        # The default in search.py is /app/data/colbert_index/...
        # Checking where index.py outputs... it outputs to default ragatouille location?
        # index.py sets index_root, but ragatouille default logic applies. 
        # Typically .ragatouille/colbert/indexes/{index_name} relative to CWD.
        # Inside docker CWD is /app.
        # So it should be /app/.ragatouille/colbert/indexes/neurosynth_v1
        # But search.py default is /app/data/colbert_index/.ragatouille...
        # We need to override index_path in client.
        
        # Override client index path to match where we likely built it
        # If we ran index.py in /app, it created /app/.ragatouille/...
        client.index_path = "/app/.ragatouille/colbert/indexes/neurosynth_v1"
        
        results = client.search("facial nerve")
        print(f"Found {len(results)} results.")
        if results:
            print(f"Top result: {results[0]['content'][:100]}...")
    except Exception as e:
        print(f"Search test encounterd error: {e}")

if __name__ == "__main__":
    main()
