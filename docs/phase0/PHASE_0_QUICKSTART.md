# Deep-Dx Phase 0 Quick Start

## What You Just Received

✅ **Evaluation dataset schema** (`deep_dx_eval_schema.json`)
✅ **Template with 10 examples** (`deep_dx_eval_template.json`)
✅ **Comprehensive guide** (`deep_dx_eval_guide.md`)
✅ **Validation script** (`validate_eval_dataset.py`)
✅ **Starter file** (`deep_dx_eval_dataset_STARTER.json`)

---

## Your Next 3 Steps (Week 1)

### Step 1: Review Examples (30 minutes)

**Action**: Open `deep_dx_eval_template.json` and read all 10 example queries

**What to notice**:
- Structure of ground truth answers (specific, detailed, with percentages/measurements)
- How sources are cited (PDF filename + page number)
- Different query types (factual, spatial, contraindication, procedural, comparative)
- Safety-critical marking (true if wrong answer = patient harm)
- Tags for filtering

**Goal**: Understand what a high-quality query-answer pair looks like

---

### Step 2: Create Source Inventory (1 hour)

**Action**: List your 20 most-used neurosurgical PDFs

**Method**:
1. Check your desktop, Downloads, Documents folders
2. Look in Dropbox/Google Drive if you use cloud storage
3. Find the PDFs you reference most often (textbooks, atlases, key papers)

**Create**: Simple text file `my_sources.txt`:
```
1. Rhoton_Cranial_Anatomy_2007.pdf
2. Samii_Vestibular_Schwannoma_2015.pdf
3. Youmans_Neurological_Surgery_7th.pdf
4. Greenberg_Handbook_9th_Ed.pdf
5. Brackmann_Otologic_Surgery.pdf
6. [Add 15 more...]
```

**Important**: Use exact filenames - you'll reference these in your queries

---

### Step 3: Draft Your First 10 Queries (2 hours)

**Action**: Create 10 queries you'd actually ask in practice

**Strategy**: Think of your last case or teaching scenario

**Example thought process**:
- "I recently operated on a VS. What did I look up before the case?"
- "What questions did I ask residents during rounds this week?"
- "What's a contraindication I always warn residents about?"

**Query Types to Include** (first 10 queries):
- 3-4 Factual (anatomy, definitions)
- 3-4 Procedural (how to do X)
- 2 Contraindication (when NOT to do X)
- 1-2 Spatial (what's anterior/posterior/medial to X)

**Template to Copy**:
```json
{
  "id": "Q001",
  "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
  "ground_truth": "In vestibular schwannomas measuring 3cm, the facial nerve is typically displaced anteriorly and stretched over the anterior surface of the tumor. The nerve becomes attenuated, may be splayed across the tumor capsule, and can appear translucent, making identification challenging. In approximately 85-90% of cases >2.5cm, the nerve is displaced anteriorly rather than posteriorly.",
  "query_type": "spatial",
  "difficulty": "medium",
  "safety_critical": true,
  "required_sources": [
    "Samii_Vestibular_Schwannoma.pdf",
    "Rhoton_Cranial_Anatomy.pdf"
  ],
  "negation_query": false,
  "spatial_query": true,
  "adversarial": false,
  "tags": ["vestibular_schwannoma", "facial_nerve", "CN_VII", "anatomy"],
  "added_date": "2024-12-06",
  "added_from_failure": false,
  "notes": "Critical for surgical planning"
}
```

**Save as**: `deep_dx_eval_dataset.json` (copy structure from `deep_dx_eval_dataset_STARTER.json`)

---

## Validation

**After creating your first 10 queries**, run validation:

```bash
python validate_eval_dataset.py deep_dx_eval_dataset.json
```

**Expected output** (with only 10 queries):
```
DEEP-DX EVALUATION DATASET VALIDATION
============================================================

Total queries: 10
Target: 100 (you have -90)

QUERY TYPE DISTRIBUTION
----------------------------------------
  factual             :   4 /  30 ( -26) ⚠️
  procedural          :   3 /  30 ( -27) ⚠️
  ...

✓ All required fields present
✓ All queries have sources
✓ All ground truth answers are detailed
✓ All IDs are unique

⚠️ MINOR ISSUES FOUND

Dataset is usable but needs expansion:
  • Add more queries (currently 10, need ≥80)
```

**This is expected** - you'll expand to 100 queries over the week.

---

## Week 1 Schedule (8-10 hours total)

| Day | Task | Time | Output |
|-----|------|------|--------|
| **Day 1** | Review examples + source inventory | 1.5h | `my_sources.txt` with 20 PDFs |
| **Day 2** | Draft first 10 queries | 2h | `deep_dx_eval_dataset.json` with 10 queries |
| **Day 3** | Add 20 more queries (total: 30) | 2h | 30 queries |
| **Day 4** | Add 25 more queries (total: 55) | 2h | 55 queries |
| **Day 5** | Add 25 more queries (total: 80) | 2h | 80 queries |
| **Day 6** | Add 20 more queries (total: 100) | 1.5h | 100 queries |
| **Day 7** | Final review and validation | 1h | Validated dataset ✓ |

**Tip**: Do 2-3 queries at a time, verify against PDFs, then continue. Don't try to write all 100 at once.

---

## Quality Checklist (Use This for Every Query)

Before adding a query to your dataset, check:

- [ ] **Is this a real question I'd ask in practice?** (Not synthetic/academic)
- [ ] **Can I answer it from my PDFs?** (Not general knowledge from outside sources)
- [ ] **Is my ground truth answer specific?** (Has measurements, percentages, criteria - not vague)
- [ ] **Did I cite the source PDF?** (Filename matches `my_sources.txt`)
- [ ] **If safety-critical, did I mark it?** (safety_critical: true)
- [ ] **Is the difficulty accurate?** (Easy = single source, explicit. Hard = synthesis/inference)

---

## Common Questions

**Q: Do I need 100 queries before starting Phase 1?**
A: No. 50 high-quality queries is enough to start. You can expand to 100 as you go.

**Q: What if I can't find the exact page number in the PDF?**
A: That's okay - list the PDF filename. You'll verify page numbers during Phase 1 indexing.

**Q: My ground truth answer is from memory, not verified in PDF yet. Is that okay?**
A: For now, yes. Mark with `"notes": "Verify against source"` and confirm during Week 2.

**Q: Can I use papers, not just textbooks?**
A: Absolutely. Any PDF you reference counts as a valid source.

**Q: What if my sources disagree on an answer?**
A: Perfect - this is a valuable query. In ground truth, write: "Source A says X. Source B says Y. Context determines which applies."

---

## Files You're Creating

```
/Users/ramihatoum/
├── my_sources.txt                      ← Your PDF inventory
├── deep_dx_eval_dataset.json           ← Your growing dataset (10 → 100 queries)
│
├── deep_dx_eval_schema.json            ← Schema reference (provided)
├── deep_dx_eval_template.json          ← 10 examples (provided)
├── deep_dx_eval_guide.md               ← Full guide (provided)
├── validate_eval_dataset.py            ← Validation script (provided)
└── PHASE_0_QUICKSTART.md               ← This file
```

---

## Success Criteria (End of Week 1)

By Day 7, you should have:

✅ **80-100 queries** in `deep_dx_eval_dataset.json`
✅ **Validation passing** (no critical issues)
✅ **Query distribution**:
   - 25-30 Factual
   - 25-30 Procedural
   - 12-15 Contraindication
   - 12-15 Spatial
   - 8-10 Comparative
✅ **30%+ safety-critical** queries
✅ **10+ adversarial** queries (negation, edge cases)

---

## What Happens After Phase 0?

**Week 2 (Phase 0 continued)**: Infrastructure setup
- Docker Compose environment
- PostgreSQL database
- Redis caching
- Test indexing with 5 PDFs

**Week 3-6 (Phase 1)**: ColBERT implementation
- Index your full PDF library (400 PDFs → 250k chunks)
- Build basic synthesis agent
- Evaluate on your 100-query dataset
- Target: >85% recall

**Decision point**: If Phase 1 achieves >85% recall, you have a working MVP. Proceed to Phase 2 (add Critic).

---

## Need Help?

**Stuck on query creation?**
- Start with table of contents of your most-used textbook
- Convert chapter headings into questions
- Example: "Facial Nerve Anatomy" → "What is the blood supply to the facial nerve?"

**Not sure about query type?**
- Factual: "What is X?" (one answer)
- Procedural: "How do you do X?" (steps)
- Contraindication: "When should you NOT do X?" (negation)
- Spatial: "What is anterior/posterior to X?" (relationships)
- Comparative: "X vs Y - which is better for Z?" (decision)

**Struggling with ground truth detail?**
- Look at Q001-Q010 in `deep_dx_eval_template.json`
- Aim for 4-8 sentences
- Include specific numbers (percentages, measurements, counts)

---

## Ready to Start?

**Your Day 1 task** (now):

1. Open `deep_dx_eval_template.json` and read Q001-Q010
2. Create `my_sources.txt` with your 20 PDFs
3. Draft your first query in `deep_dx_eval_dataset.json`
4. Run `python validate_eval_dataset.py deep_dx_eval_dataset.json`

**Time commitment**: 1-2 hours today, then 1-2 hours/day for 6 more days.

**Outcome**: A validated, expert-annotated dataset that will be the foundation of your Deep-Dx system.

---

Let's build this. Start with Step 1 (review examples).
