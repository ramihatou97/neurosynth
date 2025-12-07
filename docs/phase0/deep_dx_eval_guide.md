# Deep-Dx Evaluation Dataset Creation Guide

## Overview

This guide helps you create the 100-query evaluation dataset that is the foundation of the Deep-Dx system.

**Timeline**: 8-10 hours over 1 week
**Deliverable**: `deep_dx_eval_dataset.json` with 100 expert-annotated queries

---

## Why This Matters

**Without this dataset, you cannot:**
- Validate retrieval performance (Recall@20 > 85%)
- Measure improvement between phases
- Identify failure modes
- Know if the system is safe to use

**This dataset is the single source of truth for system evaluation.**

---

## Query Distribution (Target: 100 Queries)

| Query Type | Count | Purpose |
|------------|-------|---------|
| **Factual** | 30 | Basic knowledge retrieval (anatomy, definitions) |
| **Procedural** | 30 | Step-by-step technique queries |
| **Contraindication** | 15 | Safety-critical negation queries |
| **Spatial** | 15 | Anatomical relationships (anterior/posterior/medial/lateral) |
| **Comparative** | 10 | "X vs Y" decision-making queries |

### Difficulty Distribution

- **Easy** (30%): Answer found in single source, explicit statement
- **Medium** (50%): Requires synthesis from 2-3 sources
- **Hard** (20%): Requires inference, spatial reasoning, or rare information

### Safety-Critical Queries

- **Target**: 30% of queries marked as safety-critical
- **Definition**: Incorrect answer could lead to patient harm
- **Examples**: Contraindications, critical anatomical relationships, surgical warnings

---

## Step-by-Step Process

### Week 1, Day 1-2: Gather Source Material (2 hours)

1. **Identify your 20 most-used PDFs**
   - Textbooks you reference weekly
   - Operative atlases (Rhoton, Samii, etc.)
   - Key papers you've saved
   - Clinical guidelines

2. **Create source inventory** (`source_inventory.txt`):
   ```
   1. Rhoton_Cranial_Anatomy_2007.pdf
   2. Samii_Vestibular_Schwannoma_2015.pdf
   3. Youmans_Neurological_Surgery_7th_Ed.pdf
   4. Greenberg_Handbook_9th_Ed.pdf
   5. Brackmann_Otologic_Surgery_4th_Ed.pdf
   ...
   ```

3. **Verify PDF text extractability**:
   - Open each PDF and try to copy/paste text
   - If it's a scanned image, note "NEEDS OCR" next to filename
   - PDFs that are pure images will require special handling in Phase 1

---

### Week 1, Day 2-4: Generate Query Candidates (3 hours)

**Method 1: From Teaching Cases**
- Think of 10 cases you've presented at rounds or taught residents
- What questions did you ask them?
- What key concepts did you emphasize?

**Method 2: From Your Notes**
- Review your OR notes, case preparations, study notes
- What did you need to look up recently?
- What warnings did you highlight?

**Method 3: From Table of Contents**
- Scan TOCs of your top 5 textbooks
- Convert chapter sections into questions
- Example: Chapter section "Facial Nerve Anatomy in VS" → "What is the typical position of the facial nerve in vestibular schwannoma?"

**Method 4: From Mistakes/Near-Misses**
- What have you or colleagues looked up incorrectly?
- What assumptions turned out wrong?
- These make excellent adversarial queries

**Target**: Generate 150 candidate queries (you'll select best 100)

**Format** (simple text file initially):
```
CANDIDATE QUERIES (Raw)
=======================

FACTUAL:
- What is the blood supply to CN VII?
- Where is Meckel's cave located?
- What is the normal diameter of the IAC?
...

PROCEDURAL:
- How do you identify the facial nerve in translabyrinthine approach?
- What are the steps of retrosigmoid craniotomy?
...

CONTRAINDICATION:
- When should you NOT use sitting position?
- What are contraindications to retrosigmoid approach?
...

SPATIAL:
- What is anterior to the facial nerve in the IAC?
- Where is the AICA relative to the facial nerve?
...

COMPARATIVE:
- Retrosigmoid vs translabyrinthine for large VS?
- Middle fossa vs translabyrinthine for small IAC tumor?
...
```

---

### Week 1, Day 4-6: Write Ground Truth Answers (4 hours)

**This is the most important step.**

For each query:

1. **Answer from memory first** (2-3 sentences)
2. **Verify against sources** - open the PDFs and find the actual text
3. **Write expert-level answer** (4-8 sentences with specific details)
4. **Note source citations** (filename + page number)

**Quality checklist for ground truth answers**:
- ✅ Contains specific details (measurements, percentages, criteria)
- ✅ Cites source material you can point to
- ✅ Written at level of "what you'd tell a senior resident"
- ✅ Includes relevant caveats/exceptions
- ✅ For safety queries: includes explicit warnings
- ❌ Does NOT include information you're not certain about
- ❌ Does NOT synthesize beyond what sources state

**Example - GOOD ground truth**:
```json
{
  "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
  "ground_truth": "In vestibular schwannomas measuring 3cm, the facial nerve is typically displaced anteriorly and stretched over the anterior surface of the tumor. The nerve becomes attenuated, may be splayed across the tumor capsule, and can appear translucent, making identification challenging. In approximately 85-90% of cases >2.5cm, the nerve is displaced anteriorly rather than posteriorly.",
  "required_sources": ["Samii_Vestibular_Schwannoma.pdf", "Rhoton_Cranial_Anatomy.pdf"]
}
```

**Example - BAD ground truth** (too vague):
```json
{
  "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
  "ground_truth": "The facial nerve is usually displaced by the tumor.",
  "required_sources": ["Some textbook"]
}
```

---

### Week 1, Day 6-7: Format and Validate (1 hour)

1. **Convert to JSON format** using template structure

2. **Run validation script** (see below)

3. **Fix any errors**

4. **Review distribution**:
   ```
   Total queries: 100
   - Factual: 30 ✓
   - Procedural: 28 ⚠️ (need 2 more)
   - Contraindication: 15 ✓
   - Spatial: 15 ✓
   - Comparative: 12 ⚠️ (have 2 extra, can keep or redistribute)

   Safety-critical: 32 ✓ (>30%)
   Negation queries: 18 ✓
   Spatial queries: 20 ✓
   ```

---

## Special Query Types

### Adversarial Queries (Target: 10-15)

**Purpose**: Test edge cases and potential failure modes

**Examples**:
1. **Negation**: "Do NOT cut the arachnoid before..." (system must not return "cut" instructions)
2. **Opposite spatial**: "What is POSTERIOR to X?" (when most sources discuss what's anterior)
3. **Rare contraindication**: Obscure but critical warning buried in text
4. **Conflicting sources**: Query where you know sources disagree slightly
5. **Multi-hop reasoning**: "Given X and Y, what approach is preferred?" (requires combining two pieces of information)

### Safety-Critical Queries (Target: 30)

**Must include**:
- All contraindication queries (15)
- Critical anatomical relationships (10)
- Surgical warnings/complications (5)

**Marking criteria**:
- `"safety_critical": true` if wrong answer could lead to:
  - Wrong surgical approach selected
  - Critical structure injured
  - Contraindication missed
  - Incorrect spatial expectation in OR

---

## Quality Assurance

### Self-Review Checklist

Before finalizing, review random sample of 10 queries:

**For each query**:
- [ ] Would I actually ask this question in practice?
- [ ] Is the ground truth answer something I'm confident about?
- [ ] Can I point to specific pages in sources that support the answer?
- [ ] Is the difficulty level accurate? (easy/medium/hard)
- [ ] Are the tags helpful for filtering?

**For the dataset overall**:
- [ ] Query distribution matches targets (30/30/15/15/10)
- [ ] 30%+ queries are safety-critical
- [ ] Mix of difficulty levels (30% easy, 50% medium, 20% hard)
- [ ] At least 15 adversarial/edge-case queries
- [ ] Sources are listed accurately (filenames match your library)

---

## Common Mistakes to Avoid

| Mistake | Example | Fix |
|---------|---------|-----|
| **Ground truth too vague** | "The nerve is usually displaced" | "The nerve is displaced anteriorly in 85-90% of cases >2.5cm" |
| **Query too specific** | "What did Samii report in 2015 about..." | "What is the typical facial nerve outcome after VS surgery?" |
| **Missing source** | Answer provided but no source cited | Always list the PDFs that contain the answer |
| **Synthetic query** | Question no one would actually ask | Use real clinical scenarios |
| **Answer includes opinion** | "The best approach is..." | "Outcomes data shows X vs Y: [data]" |

---

## Expansion Strategy (Living Dataset)

**After Phase 1 evaluation**:
- Identify queries where system failed
- Add those failure cases to dataset (mark `"added_from_failure": true`)
- Target: Add 10-20 queries after each phase

**By Phase 4**:
- Dataset will grow to 140-150 queries
- Includes all discovered edge cases
- Represents realistic use patterns

---

## Validation Script

Run this after completing dataset to check quality:

```python
# Save as: validate_eval_dataset.py

import json
from collections import Counter

def validate_dataset(filepath):
    """Validate evaluation dataset structure and distribution"""

    with open(filepath, 'r') as f:
        data = json.load(f)

    queries = data['queries']
    total = len(queries)

    print(f"\n{'='*60}")
    print(f"EVALUATION DATASET VALIDATION")
    print(f"{'='*60}\n")

    print(f"Total queries: {total}")
    print(f"Target: 100 (you have {total - 100:+d})\n")

    # Query type distribution
    print("QUERY TYPE DISTRIBUTION")
    print("-" * 40)
    type_counts = Counter(q['query_type'] for q in queries)
    targets = {
        'factual': 30,
        'procedural': 30,
        'contraindication': 15,
        'spatial': 15,
        'comparative': 10
    }
    for qtype, target in targets.items():
        actual = type_counts.get(qtype, 0)
        status = "✓" if abs(actual - target) <= 2 else "⚠️"
        print(f"  {qtype:20s}: {actual:3d} / {target:3d} {status}")

    # Difficulty distribution
    print("\nDIFFICULTY DISTRIBUTION")
    print("-" * 40)
    diff_counts = Counter(q['difficulty'] for q in queries)
    print(f"  Easy:   {diff_counts.get('easy', 0):3d} (target: ~30)")
    print(f"  Medium: {diff_counts.get('medium', 0):3d} (target: ~50)")
    print(f"  Hard:   {diff_counts.get('hard', 0):3d} (target: ~20)")

    # Safety-critical count
    safety_count = sum(1 for q in queries if q.get('safety_critical', False))
    safety_pct = (safety_count / total) * 100
    safety_status = "✓" if safety_pct >= 30 else "⚠️"
    print(f"\nSAFETY-CRITICAL QUERIES")
    print("-" * 40)
    print(f"  Count: {safety_count} ({safety_pct:.1f}%) {safety_status}")
    print(f"  Target: ≥30%")

    # Special query flags
    negation_count = sum(1 for q in queries if q.get('negation_query', False))
    spatial_count = sum(1 for q in queries if q.get('spatial_query', False))
    adversarial_count = sum(1 for q in queries if q.get('adversarial', False))

    print(f"\nSPECIAL QUERY TYPES")
    print("-" * 40)
    print(f"  Negation queries:    {negation_count}")
    print(f"  Spatial queries:     {spatial_count}")
    print(f"  Adversarial queries: {adversarial_count} (target: ≥10)")

    # Quality checks
    print(f"\nQUALITY CHECKS")
    print("-" * 40)

    missing_sources = [q['id'] for q in queries if not q.get('required_sources')]
    if missing_sources:
        print(f"  ⚠️  Missing sources: {', '.join(missing_sources)}")
    else:
        print(f"  ✓  All queries have sources")

    short_ground_truth = [q['id'] for q in queries if len(q.get('ground_truth', '')) < 100]
    if short_ground_truth:
        print(f"  ⚠️  Short ground truth (<100 chars): {', '.join(short_ground_truth)}")
    else:
        print(f"  ✓  All ground truth answers are detailed")

    vague_queries = [q['id'] for q in queries if len(q.get('query', '')) < 20]
    if vague_queries:
        print(f"  ⚠️  Vague queries (<20 chars): {', '.join(vague_queries)}")
    else:
        print(f"  ✓  All queries are specific")

    # ID uniqueness
    ids = [q['id'] for q in queries]
    duplicate_ids = [id for id in ids if ids.count(id) > 1]
    if duplicate_ids:
        print(f"  ⚠️  Duplicate IDs: {set(duplicate_ids)}")
    else:
        print(f"  ✓  All IDs are unique")

    print(f"\n{'='*60}\n")

    # Final verdict
    critical_issues = (
        bool(missing_sources) or
        bool(duplicate_ids) or
        safety_pct < 25 or
        total < 80
    )

    if critical_issues:
        print("❌ CRITICAL ISSUES FOUND - Fix before proceeding")
        return False
    elif short_ground_truth or adversarial_count < 10:
        print("⚠️  MINOR ISSUES - Dataset usable but could be improved")
        return True
    else:
        print("✅ DATASET READY - Proceed to Phase 1")
        return True

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validate_eval_dataset.py <path_to_dataset.json>")
        sys.exit(1)

    filepath = sys.argv[1]
    validate_dataset(filepath)
```

**Usage**:
```bash
python validate_eval_dataset.py deep_dx_eval_dataset.json
```

---

## Example Workflow

**Day 1** (2 hours):
- Create source inventory (20 PDFs)
- Review table of contents
- List 50 candidate queries from TOCs

**Day 2** (2 hours):
- Review recent cases/teaching scenarios
- Add 50 more candidate queries
- Review list, remove duplicates/low-quality
- Select 100 best queries

**Day 3-5** (4 hours):
- Write ground truth for 30 queries/day
- Verify against actual PDF pages
- Mark difficulty, safety-critical, query type

**Day 6** (1 hour):
- Convert to JSON format
- Run validation script
- Fix errors

**Day 7** (1 hour):
- Final review of random sample
- Ensure adversarial queries included
- Commit dataset

---

## Next Steps After Dataset Creation

Once you have `deep_dx_eval_dataset.json` validated:

1. **Baseline benchmark** (Phase 0, Week 2):
   - Index your 20 PDFs with simple embedding model
   - Test retrieval on your 100 queries
   - Record baseline performance (likely 40-60% recall)

2. **Phase 1 kickoff**:
   - Use dataset to guide development
   - After each code change, re-run evaluation
   - Track improvement over time

3. **Living dataset maintenance**:
   - Add failures as you discover them
   - Grow to 120-150 queries by Phase 4
   - Version the dataset (1.0 → 1.1 → 2.0)

---

## Questions?

If you get stuck:
1. Start with 50 queries instead of 100 (can expand later)
2. Focus on query types you use most (e.g., if you never do comparative queries, make fewer of those)
3. Ground truth can be iterative (start with 80% confidence, refine as you verify sources)

The goal is a **usable, real-world dataset**, not perfection.
