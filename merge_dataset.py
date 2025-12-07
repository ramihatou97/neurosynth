
import json
from pathlib import Path

GOLD_PATH = Path("src/deep_dx/eval/gold_standard_eval.json")
CANDIDATES_PATH = Path("generated_candidates.json")

def main():
    if not CANDIDATES_PATH.exists():
        print("❌ Candidates file not found")
        return

    # Load existing
    if GOLD_PATH.exists():
        with open(GOLD_PATH, 'r') as f:
            gold_data = json.load(f)
            existing_queries = gold_data.get('queries', [])
            next_id = len(existing_queries) + 1
    else:
        gold_data = {"version": "1.0.0", "metadata": {}, "queries": []}
        existing_queries = []
        next_id = 1

    print(f"📉 Existing queries: {len(existing_queries)}")

    # Load candidates
    candidates = []
    
    # Standard candidates
    if CANDIDATES_PATH.exists():
        with open(CANDIDATES_PATH, 'r') as f:
            cand_data = json.load(f)
            candidates.extend(cand_data.get('queries', []))
        print(f"📈 Standard candidates: {len(cand_data.get('queries', []))}")
            
    # Adversarial candidates
    adv_path = Path("adversarial_candidates.json")
    if adv_path.exists():
        with open(adv_path, 'r') as f:
            adv_data = json.load(f)
            adv_queries = adv_data.get('queries', [])
            candidates.extend(adv_queries)
        print(f"😈 Adversarial candidates: {len(adv_queries)}")

    print(f"Total candidates to merge: {len(candidates)}")

    # Merge
    added_count = 0
    for q in candidates:
        # Re-ID to ensure continuity
        q['id'] = f"Q{next_id:03d}"
        q['added_date'] = "2024-12-06"
        
        # Ensure required fields
        if 'difficulty' not in q: q['difficulty'] = 'medium'
        if 'safety_critical' not in q: q['safety_critical'] = False
        
        # Add to list
        existing_queries.append(q)
        next_id += 1
        added_count += 1

    # Update metadata
    gold_data['metadata']['total_queries'] = len(existing_queries)
    gold_data['metadata']['last_updated'] = "2024-12-06"
    gold_data['queries'] = existing_queries

    # Save
    with open(GOLD_PATH, 'w') as f:
        json.dump(gold_data, f, indent=2)

    print(f"✅ Merged {added_count} queries. Total: {len(existing_queries)}")

if __name__ == "__main__":
    main()
