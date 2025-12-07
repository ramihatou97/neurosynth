
import sys
from pathlib import Path
from deep_dx.retrieval.indexer import DeepDxIndexer
from deep_dx.retrieval.raptor import RaptorIndexer

def main():
    print("🦖 Testing RAPTOR Pipeline...")
    
    # 1. Setup
    try:
        base_indexer = DeepDxIndexer()
        raptor = RaptorIndexer(base_indexer)
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        sys.exit(1)
        
    # 2. Mock Data (or load small subset)
    # We'll mock chunks to avoid heavy PDF loading for this test
    print("\n🧪 Creating Mock Data...")
    mock_chunks = [
        {"text": "Glioblastoma multiforme (GBM) is the most common primary malignant brain tumor. Standard treatment involves surgery, radiation, and temozolomide.", "metadata": {"source": "doc1"}},
        {"text": "The Stupp protocol for GBM consists of radiotherapy with concomitant temozolomide followed by adjuvant temozolomide.", "metadata": {"source": "doc1"}},
        {"text": "Meningiomas are typically benign tumors arising from the arachnoid cap cells. they are often cured by surgical resection.", "metadata": {"source": "doc2"}},
        {"text": "Simpson Grade I resection of meningioma involves complete removal of tumor and dural attachment. This offers best recurrence-free survival.", "metadata": {"source": "doc2"}},
        {"text": "Deep vein thrombosis (DVT) is a significant risk in neurosurgical patients. Prophylaxis includes mechanical compression and chemical anticoagulation.", "metadata": {"source": "doc3"}},
        {"text": "Unfractionated heparin or low-molecular-weight heparin are used for chemical DVT prophylaxis. Timing depends on hemorrhage risk.", "metadata": {"source": "doc3"}},
        {"text": "Pineal region tumors include germinomas, pineocytomas, and pineoblastomas. Parinaud's syndrome is a common presentation.", "metadata": {"source": "doc4"}},
        {"text": "Surgical approaches to the pineal region include the supracerebellar infratentorial approach and the occipital transtentorial approach.", "metadata": {"source": "doc4"}},
    ]
    
    # We need enough mock data to trigger clustering (max_cluster_size is logic dependent)
    # Let's force small clusters for test
    
    print(f"  Input Chunks: {len(mock_chunks)}")
    
    # 3. Build Tree
    print("\n🌳 Building RAPTOR Tree...")
    # We patch cluster_embeddings to force small clusters for this test if needed, 
    # or just rely on the mock data being distinct enough.
    # RaptorIndexer uses max_cluster_size=10 by default. We have 8 chunks. 
    # It might just make 1 cluster. Let's override the method or create a subclass for test?
    # Easier: Just pass more chunks or duplicate them to trigger logic.
    mock_chunks = mock_chunks * 3 # 24 chunks -> should trigger clustering (24 > 10)
    
    try:
        all_nodes = raptor.build_tree(mock_chunks)
        print(f"\n✅ Tree Built. Total Nodes: {len(all_nodes)}")
        
        # Verify we have summaries
        summaries = [n for n in all_nodes if n['metadata'].get('is_summary')]
        print(f"  - Original Chunks: {len(mock_chunks)}")
        print(f"  - Generated Summaries: {len(summaries)}")
        
        if summaries:
            print(f"\n📄 Sample Summary:\n{summaries[0]['text'][:150]}...")
        else:
            print("⚠️ No summaries generated (did clustering happen?)")
            
        # 4. Indexing Integration (Dry Run)
        print("\n💾 Testing Indexing Integration...")
        # We won't actually save to disk to avoid polluting real index, 
        # but we'll encode to verify compatibility.
        embeddings = base_indexer.encode_chunks(all_nodes)
        print(f"  - Embeddings Shape: {embeddings.shape}")
        
    except Exception as e:
        print(f"\n❌ RAPTOR Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✨ RAPTOR Test Complete!")

if __name__ == "__main__":
    main()
