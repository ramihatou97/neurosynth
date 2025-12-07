# Deep-Dx Evaluation Dataset

This directory contains the evaluation infrastructure for Deep-Dx.

## Phase 0: Creating the Gold Standard Dataset

The evaluation dataset is the **foundation** of Deep-Dx. Without it, you cannot:
- Validate retrieval performance (Recall@20 > 85%)
- Measure improvement between phases
- Identify failure modes
- Know if the system is safe to use

## Quick Start

### Option 1: Manual Curation (Recommended for Quality)

Create 100 expert-annotated query-answer pairs using your clinical experience:

```bash
# 1. Copy the starter template
cp gold_standard_eval_TEMPLATE.json gold_standard_eval.json

# 2. Edit and add your queries
# Use queries from actual clinical scenarios

# 3. Validate
python validate_eval_dataset.py gold_standard_eval.json
```

### Option 2: Semi-Automated Generation

Use Claude to help generate candidate queries from your PDFs:

```bash
# 1. Generate candidate queries from processed documents
python generate_eval_candidates.py --num-queries 150

# 2. Review and edit generated_candidates.json
# Keep best 100, fix any errors

# 3. Rename to gold standard
mv generated_candidates.json gold_standard_eval.json

# 4. Validate
python validate_eval_dataset.py gold_standard_eval.json
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `gold_standard_eval_TEMPLATE.json` | Empty template with 10 examples |
| `gold_standard_eval.json` | **YOUR DATASET** (create this) |
| `generate_eval_candidates.py` | Semi-automated query generation |
| `validate_eval_dataset.py` | Quality validation script |
| `eval_schema.json` | JSON schema for validation |
| `README.md` | This file |

## Dataset Structure

```json
{
  "version": "1.0.0",
  "metadata": {
    "created_date": "2024-12-06",
    "total_queries": 100,
    "curator": "Your Name"
  },
  "queries": [
    {
      "id": "Q001",
      "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
      "ground_truth": "In vestibular schwannomas measuring 3cm...",
      "query_type": "spatial",
      "difficulty": "medium",
      "safety_critical": true,
      "required_sources": ["Samii_VS.pdf"],
      "tags": ["facial_nerve", "VS", "anatomy"]
    }
  ]
}
```

## Query Type Distribution (Target: 100 queries)

- **Factual (30)**: "What is the blood supply to X?"
- **Procedural (30)**: "How to identify X during Y approach?"
- **Contraindication (15)**: "When should you NOT use X?"
- **Spatial (15)**: "What is anterior to X?"
- **Comparative (10)**: "X vs Y for Z?"

## Quality Checklist

Before finalizing your dataset:

- [ ] 80-100 queries total
- [ ] Query distribution matches targets
- [ ] 30%+ queries are safety-critical
- [ ] 10+ adversarial queries (negation, edge cases)
- [ ] Ground truth answers are detailed (100+ characters)
- [ ] All queries are from real clinical scenarios
- [ ] No critical validation errors

## Validation

Run validation after adding queries:

```bash
python validate_eval_dataset.py gold_standard_eval.json
```

Expected output:
```
✅ DATASET READY
Total queries: 100
Query types: ✓
Safety-critical: 32 (32.0%) ✓
No critical issues found
```

## Next Steps

Once your dataset passes validation:

1. **Week 2 (Phase 1)**: Build ColBERT index
2. **Week 3**: Implement basic synthesis
3. **Week 4**: Evaluate on this dataset
4. **Target**: Recall@20 > 85%

The dataset you create here is how you'll measure success in every subsequent phase.
