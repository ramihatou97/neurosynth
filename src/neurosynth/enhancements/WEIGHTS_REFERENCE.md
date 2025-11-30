# NeuroSynth Enhancement v3.1 - Weight Configuration Reference

> **Version:** 3.1
> **Status:** All weights centralized in `config.py`
> **Rule:** NEVER hardcode weights in other modules

---

## 1. Keyword Category Weights (`KeywordWeightConfig`)

**Purpose:** Score text blocks by neurosurgical relevance

**MUST SUM TO 1.0**

| Category | Weight | Rationale |
|----------|--------|-----------|
| `procedure` | **0.30** | Highest — surgical actions are most discriminative |
| `anatomy` | 0.25 | Critical anatomical structure identification |
| `pathology` | 0.25 | Disease/condition context |
| `imaging` | 0.15 | Useful but secondary |
| `instruments` | 0.05 | Lowest — present in most surgical images |
| **TOTAL** | **1.00** | ✓ |

**Context Multipliers:**
- `caption_context_boost`: 1.5× (keywords in captions worth 50% more)
- `heading_context_boost`: 1.3× (keywords in headings worth 30% more)  
- `body_context_boost`: 1.0× (standard body text)

**Usage Location:** `visual_cluster_associator.py` → `NeurosurgicalKeywordScorer`

---

## 2. Association Weights (`AssociationWeightConfig`)

**Purpose:** Score image-text associations

**MUST SUM TO 1.0**

| Component | Weight | Description |
|-----------|--------|-------------|
| `spatial_weight` | **0.50** | Physical proximity to image |
| `keyword_weight` | 0.30 | Neurosurgical keyword relevance |
| `context_weight` | 0.20 | References, demonstratives |
| **TOTAL** | **1.00** | ✓ |

**Boost Values (added after weighted sum):**
- `caption_boost`: 0.15 (if text is a caption)
- `direct_ref_boost`: 0.20 (if text directly references figure)

**Formula:**
```
total = (spatial × 0.50) + (keyword × 0.30) + (context × 0.20) + boosts
```

**Usage Location:** `visual_cluster_associator.py` → `EnhancedVisualClusterAssociator`

---

## 3. Caption Confidence Weights (`CaptionConfidenceConfig`)

**Purpose:** Score caption detection confidence

**MUST SUM TO 1.0**

| Component | Weight | Description |
|-----------|--------|-------------|
| `pattern_weight` | **0.40** | Pattern match quality (Fig X format) |
| `proximity_weight` | 0.30 | Distance from image |
| `formatting_weight` | 0.20 | Italic/bold formatting |
| `length_weight` | 0.10 | Caption text length |
| **TOTAL** | **1.00** | ✓ |

**Scoring Bonuses:**
- `standard_figure_id_bonus`: 0.10 ("Figure X" format)
- `italic_bonus`: 0.10
- `bold_bonus`: 0.05
- `close_proximity_bonus`: 0.20 (within 50px)
- `adequate_length_bonus`: 0.10 (>30 chars)

**Usage Location:** `enhanced_caption_detector.py` → `EnhancedCaptionDetector._calculate_confidence()`

---

## 4. Quick Validation

Run this to verify all weights:

```python
from config import NeuroSynthEnhancedConfig

config = NeuroSynthEnhancedConfig()
config.print_weights_summary()
```

Expected output:
```
============================================================
NEUROSYNTH WEIGHT CONFIGURATION SUMMARY
============================================================

[Keyword Category Weights] (must sum to 1.0)
  anatomy:     0.25
  pathology:   0.25
  procedure:   0.30  ← highest
  imaging:     0.15
  instruments: 0.05  ← lowest
  TOTAL:       1.00

[Association Weights] (must sum to 1.0)
  spatial:  0.50
  keyword:  0.30
  context:  0.20
  TOTAL:    1.00

[Caption Confidence Weights] (must sum to 1.0)
  pattern:    0.40
  proximity:  0.30
  formatting: 0.20
  length:     0.10
  TOTAL:      1.00
============================================================
```

---

## 5. Example: Full Scoring Trace

**Input:** Image with nearby caption text

```
Caption: "Figure 3. Pterional craniotomy approach showing the 
sylvian fissure and MCA bifurcation after dural opening."
```

### Keyword Scoring

| Keyword | Category | Weight |
|---------|----------|--------|
| craniotomy | procedure | 0.30 |
| approach | procedure | 0.30 |
| sylvian fissure | anatomy | 0.25 |
| MCA | anatomy | 0.25 |
| dural | anatomy | 0.25 |

Category scores (with diminishing returns):
- procedure: 2 keywords → 0.30 × (1 - 0.5²) = 0.30 × 0.75 = 0.225
- anatomy: 3 keywords → 0.25 × (1 - 0.5³) = 0.25 × 0.875 = 0.219

Raw score: 0.225 + 0.219 = 0.444

Context multiplier (caption): 0.444 × 1.5 = **0.666**

### Association Scoring

| Component | Score | Weight | Contribution |
|-----------|-------|--------|--------------|
| Spatial | 0.90 (very close) | 0.50 | 0.450 |
| Keyword | 0.666 | 0.30 | 0.200 |
| Context | 0.70 (has "Fig 3") | 0.20 | 0.140 |
| Caption boost | | | 0.150 |
| **TOTAL** | | | **0.940** |

---

## 6. Files Modified in v3.1

| File | Change |
|------|--------|
| `config.py` | Added `AssociationWeightConfig`, `CaptionConfidenceConfig` |
| `visual_cluster_associator.py` | Uses `config.association_weights` instead of hardcoded |
| `enhanced_caption_detector.py` | Uses `config.caption_confidence` for scoring |

---

*Last Updated: 2025-11-30*
*Version: 3.1*
