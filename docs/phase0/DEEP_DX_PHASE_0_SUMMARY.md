# Deep-Dx Phase 0: Complete Evaluation Infrastructure

**Created**: 2024-12-06
**Status**: ✅ Ready to begin dataset creation

---

## 📦 What You Have

### Core Files (Created)

| File | Purpose | Size | Status |
|------|---------|------|--------|
| **PHASE_0_QUICKSTART.md** | Start here - your immediate next steps | Quick read | ✅ Ready |
| **deep_dx_eval_guide.md** | Comprehensive guide for dataset creation | Full guide | ✅ Ready |
| **deep_dx_eval_template.json** | 10 example queries to learn from | 10 examples | ✅ Ready |
| **deep_dx_eval_schema.json** | JSON schema specification | Reference | ✅ Ready |
| **validate_eval_dataset.py** | Automated validation script | Executable | ✅ Tested |
| **deep_dx_eval_dataset_STARTER.json** | Template to begin populating | Starter | ✅ Ready |

---

## 🎯 Your Immediate Next Steps

### Step 1: Read the Quick Start (15 minutes)

```bash
# Open this file first
open /Users/ramihatoum/PHASE_0_QUICKSTART.md
```

This gives you the 3 immediate actions to take today.

---

### Step 2: Review Example Queries (30 minutes)

```bash
# Study the 10 example queries
open /Users/ramihatoum/deep_dx_eval_template.json
```

**What to learn**:
- How ground truth answers are written (specific, detailed, with measurements)
- How sources are cited (PDF filename + page number)
- Different query types and when to use each
- Safety-critical marking criteria

---

### Step 3: Create Your Source Inventory (1 hour)

Create a file listing your 20 most-used PDFs:

```bash
# Create source list
cat > /Users/ramihatoum/my_sources.txt << 'EOF'
1. Rhoton_Cranial_Anatomy_2007.pdf
2. Samii_Vestibular_Schwannoma_2015.pdf
3. Youmans_Neurological_Surgery_7th.pdf
4. [Add your actual PDFs here...]
EOF
```

**Important**: Use exact filenames - you'll reference these in your evaluation queries.

---

### Step 4: Draft Your First Query (30 minutes)

```bash
# Copy the starter template
cp /Users/ramihatoum/deep_dx_eval_dataset_STARTER.json /Users/ramihatoum/deep_dx_eval_dataset.json

# Edit with your favorite editor
# Add your first query using the template structure
```

**Query Template**:
```json
{
  "id": "Q001",
  "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
  "ground_truth": "In vestibular schwannomas measuring 3cm, the facial nerve is typically displaced anteriorly...",
  "query_type": "spatial",
  "difficulty": "medium",
  "safety_critical": true,
  "required_sources": ["Samii_Vestibular_Schwannoma.pdf"],
  "negation_query": false,
  "spatial_query": true,
  "adversarial": false,
  "tags": ["vestibular_schwannoma", "facial_nerve"],
  "added_date": "2024-12-06",
  "added_from_failure": false,
  "notes": ""
}
```

---

### Step 5: Validate Your Work

After adding each query (or batch of queries):

```bash
python /Users/ramihatoum/validate_eval_dataset.py /Users/ramihatoum/deep_dx_eval_dataset.json
```

**Expected output** (for first query):
```
Total queries: 1
Target: 100 (you have -99)

✓ All required fields present
✓ All queries have sources
⚠️ Add more queries (currently 1, need ≥80)
```

---

## 📊 Week 1 Progress Tracker

Track your progress as you build the dataset:

```
Day 1: [ ] Review examples + create source inventory
       Target: my_sources.txt with 20 PDFs

Day 2: [ ] Draft first 10 queries
       Target: deep_dx_eval_dataset.json with 10 queries

Day 3: [ ] Add 20 more queries (total: 30)
       Target: 30 queries, validation shows structure is correct

Day 4: [ ] Add 25 more queries (total: 55)
       Target: 55 queries, halfway done

Day 5: [ ] Add 25 more queries (total: 80)
       Target: 80 queries, minimum viable dataset

Day 6: [ ] Add 20 more queries (total: 100)
       Target: 100 queries, balanced distribution

Day 7: [ ] Final review and validation
       Target: ✅ Validation passes with no critical issues
```

---

## ✅ Success Criteria (End of Week 1)

Your dataset is ready for Phase 1 when validation shows:

### Quantitative Requirements

- [x] **Total queries**: 80-100 (minimum 80)
- [x] **Factual**: ~30 queries
- [x] **Procedural**: ~30 queries
- [x] **Contraindication**: ~15 queries
- [x] **Spatial**: ~15 queries
- [x] **Comparative**: ~10 queries
- [x] **Safety-critical**: ≥30% of total
- [x] **Adversarial**: ≥10 queries
- [x] **No critical validation errors**

### Qualitative Requirements

- [x] Ground truth answers are detailed (100+ characters)
- [x] All queries are from real clinical scenarios
- [x] Sources are accurately cited
- [x] Difficulty levels are appropriate

---

## 🛠️ Validation Command Reference

### Basic Validation
```bash
python /Users/ramihatoum/validate_eval_dataset.py /Users/ramihatoum/deep_dx_eval_dataset.json
```

### What It Checks

1. **Structure**: All required fields present, valid JSON
2. **Distribution**: Query types match targets (30/30/15/15/10)
3. **Quality**: Ground truth is detailed, sources are listed
4. **Safety**: 30%+ queries are safety-critical
5. **IDs**: Unique, following Q### format
6. **Special types**: Adequate adversarial/negation/spatial queries

### Exit Codes

- `0`: Validation passed (ready for Phase 1)
- `1`: Critical issues found (must fix before proceeding)

---

## 📖 Documentation Reference

### Quick Reference
- **PHASE_0_QUICKSTART.md**: Start here, 3 immediate steps
- **deep_dx_eval_template.json**: 10 examples to copy from

### Detailed Reference
- **deep_dx_eval_guide.md**: Comprehensive guide (8,000+ words)
  - Query creation methodology
  - Quality checklist
  - Common mistakes
  - Expansion strategy

### Technical Reference
- **deep_dx_eval_schema.json**: JSON schema for validation
- **validate_eval_dataset.py**: Validation script source code

---

## 🔍 Example Workflow (Your First Query)

### 1. Think of a Real Scenario
*"Last week I operated on a VS. I looked up facial nerve anatomy before the case."*

### 2. Convert to Natural Query
*"What is the typical position of the facial nerve in a 3cm vestibular schwannoma?"*

### 3. Answer from Memory
*"The facial nerve is usually displaced anteriorly in larger tumors..."*

### 4. Verify in Sources
- Open `Samii_Vestibular_Schwannoma.pdf`, page 147
- Find: "facial nerve displaced anteriorly in 87% of cases >2.5cm"

### 5. Write Expert-Level Ground Truth
```
In vestibular schwannomas measuring 3cm, the facial nerve is typically
displaced anteriorly and stretched over the anterior surface of the tumor.
The nerve becomes attenuated, may be splayed across the tumor capsule,
and can appear translucent, making identification challenging. In
approximately 85-90% of cases >2.5cm, the nerve is displaced anteriorly
rather than posteriorly.
```

### 6. Add Metadata
- `query_type`: "spatial" (involves anatomical position)
- `difficulty`: "medium" (requires synthesis from 2 sources)
- `safety_critical`: true (wrong expectation → nerve injury)
- `required_sources`: ["Samii_Vestibular_Schwannoma.pdf", "Rhoton_Cranial_Anatomy.pdf"]

### 7. Validate
```bash
python validate_eval_dataset.py deep_dx_eval_dataset.json
# ✓ All required fields present
# ✓ Ground truth is detailed
```

---

## 🚀 After Phase 0 (Week 2+)

Once your evaluation dataset passes validation:

### Week 2: Infrastructure Setup
- Docker Compose environment
- PostgreSQL + Redis
- Test PDF ingestion with 5 PDFs

### Week 3-6: Phase 1 (ColBERT MVP)
- Index full library (400 PDFs)
- Build synthesis agent
- **Evaluate on your 100-query dataset**
- Target: Recall@20 > 85%

### The dataset you create this week becomes the measuring stick for all future development.

---

## 💡 Tips for Success

### Start Small, Expand
- Day 1: Get 5 queries perfect
- Day 2: Add 5 more
- Day 3-6: Scale up to 100

### Use Your Real Work
- Recent cases you've operated
- Questions residents asked
- Complications you've seen
- Teaching points you emphasize

### Don't Overthink Difficulty
- Easy: Answer is in one place, explicitly stated
- Medium: Need to look at 2-3 sources and synthesize
- Hard: Requires inference or spatial reasoning

### Mark Safety Generously
If wrong answer could lead to:
- Wrong approach selected → safety_critical: true
- Structure injured → safety_critical: true
- Contraindication missed → safety_critical: true

---

## ❓ Common Questions

**Q: Can I start with 50 queries instead of 100?**
A: Yes. 50 high-quality queries is enough to start Phase 1. Expand later.

**Q: What if I don't have exact page numbers?**
A: List the PDF filename for now. Verify pages during Phase 1 indexing.

**Q: Can I use papers, not just textbooks?**
A: Absolutely. Any PDF you reference is valid.

**Q: What if sources disagree?**
A: Perfect query! In ground truth: "Source A says X (context). Source B says Y (context)."

**Q: How long should this take?**
A: 8-10 hours over one week. Don't rush - quality > speed.

---

## 📞 Next Steps

**Today** (1-2 hours):
1. ✅ Read PHASE_0_QUICKSTART.md
2. ✅ Review example queries in template
3. ✅ Create source inventory (my_sources.txt)
4. ✅ Draft first query

**This Week** (remaining 6-8 hours):
- Day 2-6: Add 10-20 queries per day
- Day 7: Final validation

**Week 2**:
- Set up infrastructure (Docker, PostgreSQL)
- Begin Phase 1 (ColBERT indexing)

---

## ✅ You're Ready to Begin

All files are created. The infrastructure is in place.

**Your first action**: Open `PHASE_0_QUICKSTART.md` and follow Step 1.

**Timeline**: By end of Week 1, you'll have a validated 100-query evaluation dataset.

**This dataset is the foundation of everything else.** Take the time to do it right.

---

## File Locations

All files are in: `/Users/ramihatoum/`

```
/Users/ramihatoum/
├── PHASE_0_QUICKSTART.md              ← START HERE
├── DEEP_DX_PHASE_0_SUMMARY.md         ← This file
├── deep_dx_eval_guide.md              ← Full guide
├── deep_dx_eval_template.json         ← 10 examples
├── deep_dx_eval_schema.json           ← Schema reference
├── deep_dx_eval_dataset_STARTER.json  ← Template
├── validate_eval_dataset.py           ← Validation script
│
└── [You will create]:
    ├── my_sources.txt                 ← Your PDF inventory
    └── deep_dx_eval_dataset.json      ← Your growing dataset
```

**Begin with**: `open /Users/ramihatoum/PHASE_0_QUICKSTART.md`
