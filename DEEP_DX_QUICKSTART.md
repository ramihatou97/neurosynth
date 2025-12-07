# Deep-Dx Quick Start Guide

**Created**: 2024-12-06
**Status**: ✅ Phase 0 Infrastructure Complete

---

## 🎯 What You Have Now

Deep-Dx is now integrated into your NeuroSynth project as a modular retrieval system.

### ✅ Completed Setup

```
neurosynth/
├── src/
│   ├── neurosynth/          # Existing chapter synthesis
│   └── deep_dx/             # ✅ NEW: Quick lookup system
│       ├── __init__.py
│       ├── config.py        # Deep-Dx configuration
│       └── eval/            # Evaluation infrastructure
│           ├── README.md
│           ├── generate_eval_candidates.py
│           ├── validate_eval_dataset.py
│           └── gold_standard_eval_TEMPLATE.json
│
└── data/
    ├── sources/             # Your PDFs go here
    ├── colbert_index/       # ✅ NEW: ColBERT index (Phase 1)
    └── knowledge_graph/     # ✅ NEW: Graph data (Phase 4)
```

---

## 🚀 Phase 0: Create Evaluation Dataset (Week 1)

**Goal**: Create 100 expert-annotated query-answer pairs to evaluate Deep-Dx performance

**Time**: 8-10 hours over 7 days

---

### Option 1: Manual Curation (Recommended for Quality)

Create queries based on your actual clinical experience.

#### Day 1-2: Setup and First 10 Queries (2 hours)

```bash
# Navigate to eval directory
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval

# Copy template
cp gold_standard_eval_TEMPLATE.json gold_standard_eval.json

# Edit gold_standard_eval.json
# - Study the 10 example queries
# - Add your own queries from real cases
# - Think: "What did I look up before my last surgery?"
```

**Query creation tips**:
- **Factual**: "What is the blood supply to the facial nerve?"
- **Procedural**: "How do you identify the facial nerve in translabyrinthine approach?"
- **Contraindication**: "When should retrosigmoid NOT be used?"
- **Spatial**: "What is anterior to the facial nerve in the IAC?"
- **Comparative**: "Retrosigmoid vs translabyrinthine for 3cm VS?"

#### Day 3-6: Add 90 More Queries (6-8 hours)

Add 15-20 queries per day:
1. Review recent cases you've operated
2. What questions did residents ask on rounds?
3. What contraindications do you always warn about?
4. What spatial relationships are critical?

#### Day 7: Validate (30 minutes)

```bash
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval
python validate_eval_dataset.py gold_standard_eval.json
```

**Expected output**:
```
✅ DATASET READY
Total queries: 100
Query types: ✓
Safety-critical: 32 (32.0%) ✓
```

---

### Option 2: Semi-Automated Generation (Faster, Needs Review)

Use Claude to generate candidate queries from your PDFs.

#### Step 1: Add Your PDFs to NeuroSynth

```bash
# Copy your neurosurgical PDFs to NeuroSynth sources directory
cp ~/Documents/Neurosurgery_PDFs/*.pdf /Users/ramihatoum/neurosynth/data/sources/

# Or if PDFs are elsewhere, use absolute paths:
cp /path/to/your/pdfs/*.pdf /Users/ramihatoum/neurosynth/data/sources/
```

#### Step 2: Generate Candidate Queries

```bash
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval

# Generate 150 candidate queries (you'll keep best 100)
python generate_eval_candidates.py --num-queries 150
```

**This will**:
- Extract text chunks from your PDFs
- Use Claude to generate questions from each chunk
- Save to `generated_candidates.json`
- Take ~30-60 minutes depending on number of PDFs

#### Step 3: Review and Curate

```bash
# Open generated_candidates.json
# Review each query:
#   ✓ Is the question realistic?
#   ✓ Is the ground truth answer accurate?
#   ✓ Does it cite the correct source?
#
# Edit/fix as needed
# Keep best 100 queries
# Delete/merge the rest
```

#### Step 4: Finalize

```bash
# Rename to gold standard
mv generated_candidates.json gold_standard_eval.json

# Validate
python validate_eval_dataset.py gold_standard_eval.json
```

---

## 📊 Target Distribution (100 Queries)

| Query Type | Count | Examples |
|------------|-------|----------|
| **Factual** | 30 | "What is the blood supply to X?" |
| **Procedural** | 30 | "How do you identify X during Y approach?" |
| **Contraindication** | 15 | "When should you NOT use X?" |
| **Spatial** | 15 | "What is anterior to X?" |
| **Comparative** | 10 | "X vs Y for Z?" |

### Special Requirements

- **30%+ safety-critical** (wrong answer = patient harm)
- **10+ adversarial** queries (test negation, edge cases)
- **Ground truth**: 4-8 sentences with specific details, measurements, percentages

---

## ✅ Success Criteria (End of Week 1)

Your dataset is ready when validation shows:

- [x] **80-100 queries** total
- [x] **Query distribution** matches targets (30/30/15/15/10)
- [x] **30%+ safety-critical** queries
- [x] **10+ adversarial** queries
- [x] **No critical validation errors**
- [x] **Ground truth is detailed** (>100 characters each)

---

## 🔧 Configuration

Deep-Dx configuration is in `src/deep_dx/config.py`.

Key settings:
```python
# ColBERT (Phase 1)
colbert_checkpoint: "colbert-ir/colbertv2.0"
retrieval_top_k: 20

# Critic (Phase 2)
critic_enabled: True
confidence_threshold_high: 0.85

# RAPTOR (Phase 3 - optional)
raptor_enabled: False

# Knowledge Graph (Phase 4 - optional)
knowledge_graph_enabled: False
```

**For now**: Leave all settings at defaults. You'll enable features in later phases.

---

## 📅 Timeline: Full Deep-Dx Build

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 0** (current) | Week 1 | Evaluation dataset (100 queries) |
| **Phase 1** | Week 2-6 | ColBERT + synthesis (>85% recall) |
| **Phase 2** | Week 7-8 | Critic + confidence calibration |
| **Phase 3** (optional) | Week 9-11 | RAPTOR hierarchy |
| **Phase 4** (optional) | Week 12-16 | Knowledge graph |

---

## 🎯 Immediate Next Steps

### Today (2 hours)

**If you choose Manual Curation**:

```bash
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval
cp gold_standard_eval_TEMPLATE.json gold_standard_eval.json

# Edit gold_standard_eval.json
# Add your first 5-10 queries from real cases
```

**If you choose Semi-Automated Generation**:

```bash
# Add your PDFs
cp /path/to/your/neurosurgery/pdfs/*.pdf /Users/ramihatoum/neurosynth/data/sources/

# Generate candidates
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval
python generate_eval_candidates.py --num-queries 150
```

### This Week (6-8 more hours)

- Add queries daily (10-20 per day)
- Review and edit generated queries if using automation
- Validate frequently to check progress
- Aim for 100 queries by Day 7

### Week 2

After your evaluation dataset is validated:
- Begin Phase 1 (ColBERT indexing)
- Index your full PDF library
- Build basic retrieval system
- Evaluate on your 100-query dataset

---

## 🆘 Common Questions

**Q: Can I start with 50 queries instead of 100?**
A: Yes. 50 high-quality queries is enough to start Phase 1. Expand later.

**Q: What if I don't have specific page numbers for sources?**
A: List PDF filenames for now. You'll verify pages during Phase 1 indexing.

**Q: How detailed should ground truth answers be?**
A: 4-8 sentences with specific measurements, percentages, criteria. Study the template examples.

**Q: What if sources disagree on an answer?**
A: Perfect! Write: "Source A says X. Source B says Y. Context determines which applies."

**Q: I don't have 400 PDFs yet - can I still build this?**
A: Yes! Start with 10-20 PDFs (your most-used references). You can expand the library later.

**Q: What happens if I skip the evaluation dataset?**
A: ❌ **Don't skip this**. Without it, you have no way to validate that Deep-Dx actually works. You'll be flying blind.

---

## 📖 Additional Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| **Eval README** | `src/deep_dx/eval/README.md` | Detailed evaluation guide |
| **Template** | `gold_standard_eval_TEMPLATE.json` | 10 example queries to learn from |
| **Validation script** | `validate_eval_dataset.py` | Check dataset quality |
| **Generation script** | `generate_eval_candidates.py` | Semi-automated query generation |
| **NeuroSynth config** | `src/neurosynth/config.py` | Main project configuration |
| **Deep-Dx config** | `src/deep_dx/config.py` | Deep-Dx specific settings |

---

## 🎓 Example: Creating Your First Query

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
```json
{
  "id": "Q001",
  "query": "What is the typical position of the facial nerve in a 3cm vestibular schwannoma?",
  "ground_truth": "In vestibular schwannomas measuring 3cm, the facial nerve is typically displaced anteriorly and stretched over the anterior surface of the tumor. The nerve becomes attenuated, may be splayed across the tumor capsule, and can appear translucent, making identification challenging. In approximately 85-90% of cases >2.5cm, the nerve is displaced anteriorly rather than posteriorly.",
  "query_type": "spatial",
  "difficulty": "medium",
  "safety_critical": true,
  "required_sources": ["Samii_Vestibular_Schwannoma.pdf"],
  "negation_query": false,
  "spatial_query": true,
  "adversarial": false,
  "tags": ["vestibular_schwannoma", "facial_nerve", "anatomy"],
  "added_date": "2024-12-06",
  "notes": "Critical for surgical planning"
}
```

### 6. Validate
```bash
python validate_eval_dataset.py gold_standard_eval.json
# ✓ All required fields present
# ✓ Ground truth is detailed
```

---

## ✅ Folder Structure Verification

Verify your setup is complete:

```bash
cd /Users/ramihatoum/neurosynth

# Check Deep-Dx directories exist
ls -la src/deep_dx/
ls -la src/deep_dx/eval/
ls -la data/colbert_index/
ls -la data/knowledge_graph/

# Check evaluation files exist
ls -la src/deep_dx/eval/*.py
ls -la src/deep_dx/eval/*.json
ls -la src/deep_dx/eval/*.md
```

Expected output:
```
src/deep_dx/__init__.py
src/deep_dx/config.py
src/deep_dx/eval/README.md
src/deep_dx/eval/generate_eval_candidates.py
src/deep_dx/eval/validate_eval_dataset.py
src/deep_dx/eval/gold_standard_eval_TEMPLATE.json
```

---

## 🎯 START HERE

**Your immediate task** (choose one path):

### Path A: Manual Curation
```bash
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval
cp gold_standard_eval_TEMPLATE.json gold_standard_eval.json
# Edit and add your first 10 queries
```

### Path B: Semi-Automated
```bash
# 1. Add PDFs
cp /path/to/pdfs/*.pdf /Users/ramihatoum/neurosynth/data/sources/

# 2. Generate candidates
cd /Users/ramihatoum/neurosynth/src/deep_dx/eval
python generate_eval_candidates.py --num-queries 150
```

**Timeline**: 2 hours today → validated 100-query dataset by end of week.

---

**Status**: Phase 0 infrastructure complete. Begin evaluation dataset creation.

**Next milestone**: Validated gold standard dataset → Proceed to Phase 1 (ColBERT indexing)
