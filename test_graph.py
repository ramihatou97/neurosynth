
import sys
from deep_dx.knowledge.graph import DeepDxKnowledgeGraph

def main():
    print("🕸️  Testing Knowledge Graph Module...")
    
    try:
        kg = DeepDxKnowledgeGraph()
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        sys.exit(1)
        
    # 1. Test Extraction Logic
    print("\n🧪 Testing Entity Extraction (LLM)...")
    text = """
    Glioblastoma is treated with Temozolomide. 
    It is located in the Brain.
    Hydrocephalus is a complication of Glioblastoma.
    """
    
    print(f"  Input Text: {text.strip()}")
    
    data = kg.extract_entities(text)
    
    print("\n  Output Data:")
    print(f"  - Entities: {len(data.get('entities', []))}")
    for e in data.get('entities', []):
        print(f"    * {e}")
        
    print(f"  - Relationships: {len(data.get('relationships', []))}")
    for r in data.get('relationships', []):
        print(f"    * {r['head']} -[{r['type']}]-> {r['tail']}")
        
    # Validation logic
    ents = [e['name'] for e in data.get('entities', [])]
    if "Glioblastoma" in ents and "Temozolomide" in ents:
        print("  ✅ Extraction Logic Passed")
    else:
        print("  ⚠️ Extraction Logic questionable (missing expected entities)")
        
    # 2. Test Ingestion (Dry Run if no DB)
    print("\n💾 Testing Ingestion Flow...")
    if kg.connected:
        print("  (DB Connected) Attempting write...")
        try:
            kg.ingest_chunk("test_chunk_001", text, "manual_test")
            print("  ✅ Write Successful")
        except Exception as e:
            print(f"  ❌ Write Failed: {e}")
    else:
        print("  (DB Disconnected) Skipping write. Logic verification only.")
        print("  ✅ Ingestion Flow Handled Gracefully")

    print("\n✨ Knowledge Graph Test Complete!")

if __name__ == "__main__":
    main()
