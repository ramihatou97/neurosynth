
import json
import random
from pathlib import Path

GOLD_PATH = Path("src/deep_dx/eval/gold_standard_eval.json")
ADVERSARIAL_PATH = Path("adversarial_candidates.json")

TARGETS = {
    'factual': 15,
    'procedural': 15,
    'contraindication': 15,
    'spatial': 15,
    'comparative': 10
}

def main():
    # Load all available queries
    if GOLD_PATH.exists():
        with open(GOLD_PATH, 'r') as f:
            data = json.load(f)
            pool = data.get('queries', [])
    else:
        pool = []

    # Add fresh targeted ones
    for p in ['adversarial_candidates.json', 'spatial_candidates.json', 'contraindication_candidates.json', 'comparative_candidates.json']:
        pp = Path(p)
        if pp.exists():
            with open(pp, 'r') as f:
                d = json.load(f)
                pool.extend(d.get('queries', []))
            print(f"Loaded {pp}: {len(d.get('queries', []))} queries")

    print(f"Total pool size: {len(pool)}")

    # Deduplicate by query text
    unique_pool = {}
    for q in pool:
        if q['query'] not in unique_pool:
            unique_pool[q['query']] = q
    
    pool = list(unique_pool.values())
    print(f"Unique queries: {len(pool)}")

    # Categorize
    buckets = {k: [] for k in TARGETS.keys()}
    adversarial_queries = []
    
    for q in pool:
        # Check adversarial tag
        if q.get('adversarial', False):
            adversarial_queries.append(q)
        
        qtype = q.get('query_type', 'factual')
        if qtype in buckets:
            buckets[qtype].append(q)
        else:
            # Fallback for unknown types
            buckets['factual'].append(q)

    # Selection
    final_selection = []
    
    # Prioritize Adversarial (Need 10)
    # Ensure we include adversarial queries regardless of their type bucket
    # But we also need to respect type distribution.
    # We'll pre-fill buckets with adversarial ones first.
    
    selected_queries = set()
    
    # 1. Take all adversarial (up to 15 to be safe)
    for q in adversarial_queries[:15]:
        final_selection.append(q)
        selected_queries.add(q['query'])
        print(f"Selected Adversarial: {q['query'][:30]}... ({q['query_type']})")

    # 2. Fill buckets to targets
    for qtype, target in TARGETS.items():
        # Count how many of this type we already have from step 1
        current_count = sum(1 for q in final_selection if q.get('query_type') == qtype)
        needed = target - current_count
        
        if needed > 0:
            candidates = [q for q in buckets[qtype] if q['query'] not in selected_queries]
            # Take needed
            take = candidates[:needed]
            final_selection.extend(take)
            for q in take:
                selected_queries.add(q['query'])
            
            print(f"Filled {qtype}: added {len(take)} (Target {target})")

    # 3. If still short, fill with any valid queries (prioritizing hard ones)
    remaining_needed = 100 - len(final_selection)
    if remaining_needed > 0:
        leftovers = [q for q in pool if q['query'] not in selected_queries]
        # Sort by difficulty if possible, or just random
        take = leftovers[:remaining_needed]
        final_selection.extend(take)
        print(f"Filled remaining {remaining_needed} with leftovers")

    # 4. Re-ID
    final_selection = final_selection[:100] # Cap at 100
    for i, q in enumerate(final_selection):
        q['id'] = f"Q{i+1:03d}"

    # Verify counts
    print("\nFinal Counts:")
    for qtype in TARGETS:
        c = sum(1 for q in final_selection if q.get('query_type') == qtype)
        print(f"  {qtype}: {c}")
    
    adv_count = sum(1 for q in final_selection if q.get('adversarial', False))
    print(f"  Adversarial: {adv_count}")

    # Save
    output = {
        "version": "1.0.0",
        "metadata": {
            "total_queries": len(final_selection),
            "generated": True
        },
        "queries": final_selection
    }
    
    with open(GOLD_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Saved clean 100 queries to {GOLD_PATH}")

if __name__ == "__main__":
    main()
