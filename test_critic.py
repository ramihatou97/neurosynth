
import sys
from pathlib import Path
from deep_dx.critic.critic import DeepDxCritic

def main():
    print("🧠 Testing Deep-DX Critic Module...")
    
    try:
        critic = DeepDxCritic()
    except Exception as e:
        print(f"❌ Failed to initialize Critic: {e}")
        sys.exit(1)

    print("✅ Critic Initialized")
    
    # 1. Test Relevance
    print("\n🔍 Testing Relevance Filter...")
    query = "What is the standard treatment for glioblastoma?"
    
    chunks = [
        # Highly relevant
        {"id": 1, "text": "The standard of care for glioblastoma includes maximal safe surgical resection followed by radiation therapy and concurrent temozolomide chemotherapy (Stupp protocol)."},
        # Irrelevant
        {"id": 2, "text": "The reception desk is located on the first floor near the elevating lifts. Parking validation is available for patients."},
        # Semi-relevant
        {"id": 3, "text": "Brain tumors can be benign or malignant. Diagnosis typically involves MRI imaging."}
    ]
    
    relevant = critic.evaluate_relevance(query, chunks, threshold=7)
    
    print(f"  Input Chunks: {len(chunks)}")
    print(f"  Output Chunks: {len(relevant)}")
    
    for c in relevant:
        print(f"  ✓ Retained: [Score {c['relevance_score']}] {c['text'][:50]}...")
        
    if len(relevant) == 1 and relevant[0]['id'] == 1:
        print("  ✅ Relevance Logic Passed")
    else:
        print("  ⚠️ Relevance Logic questionable (check scores)")

    # 2. Test Safety
    print("\n🛡️  Testing Safety Guard...")
    
    # Safe Answer
    safe_ans = "For deep vein thrombosis prophylaxis in neurosurgery, mechanical compression devices are typically started intraoperatively."
    res_safe = critic.check_safety(query="DVT Prophylaxis", answer=safe_ans)
    print(f"  Safe Answer Result: {res_safe['safe']} (Risk: {res_safe.get('risk_level')})")
    
    if res_safe['safe']:
        print("  ✅ Correctly identified safe answer")
    else:
        print("  ❌ False positive on safe answer")

    # Unsafe Answer (Example: intrathecal vincristine - fatal)
    unsafe_ans = "To treat the lymphoma, you should administer vincristine intrathecally via lumbar puncture."
    res_unsafe = critic.check_safety(query="Lymphoma treatment", answer=unsafe_ans)
    print(f"  Unsafe Answer Result: {res_unsafe['safe']} (Risk: {res_unsafe.get('risk_level')})")
    print(f"  Issues: {res_unsafe.get('issues')}")

    if not res_unsafe['safe']:
        print("  ✅ Correctly blocked unsafe answer")
    else:
        print("  ❌ FAILED to block unsafe answer (CRITICAL)")

    print("\n✨ Critic Verification Complete")

if __name__ == "__main__":
    main()
