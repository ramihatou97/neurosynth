"""Prompt templates for AI categorization."""

CATEGORIZATION_PROMPT = """You are a neurosurgical content analyst. Analyze this textbook excerpt and categorize it according to standard neurosurgical textbook chapter structure.

SEARCH CONTEXT:
- Search Term: "{search_term}"
- Source: {book_title}
- Chapter: {chapter_title}
- Page: {page_number}

TEXT EXCERPT:
---
{context}
---

CATEGORY SYSTEM (Choose ONE):

## SURGICAL/ANATOMICAL (Procedural content showing how to do something)
- Preoperative Planning: Image review, approach selection, equipment preparation
- Anesthetic Considerations: Airway, positioning concerns, neuromonitoring setup
- Patient Positioning: Supine, prone, lateral, park bench, head fixation
- Surgical Approach: Incision, exposure, access procedures - craniotomy, laminectomy, laminotomy, discectomy approach, foraminotomy, corpectomy approach, soft tissue dissection, dural opening
- Anatomical Landmarks: Surface anatomy, vascular landmarks, neural identification, microsurgical anatomy
- Surgical Technique: Target manipulation AFTER access - tumor resection, aneurysm clipping, AVM obliteration, nerve decompression, microdissection of pathology, hemostasis
- Reconstruction: Fusion, instrumentation, grafting, dural repair
- Closure: Layer-by-layer closure, drain placement, wound management
- Intraoperative Monitoring: SSEP, MEP, EMG, ECoG, vascular monitoring
- Technical Pitfalls: Common errors, avoidance strategies, bailout procedures

## THEORETICAL (Knowledge content about a condition)
- Definition & Classification: Terminology, grading systems, ICD codes, nomenclature
- Epidemiology: Incidence, prevalence, risk factors, demographics, natural history
- Pathophysiology: Disease mechanisms, molecular/cellular changes, histopathology
- Clinical Presentation: Symptoms, signs, neurological examination findings
- Diagnostic Evaluation: Imaging, labs, electrodiagnostics, tissue diagnosis
- Differential Diagnosis: Clinical mimics, imaging differentials, diagnostic algorithms
- Treatment Options: Conservative management, indications for surgery, alternatives
- Postoperative Management: ICU care, floor care, rehabilitation, discharge
- Complications: Intraoperative, early postoperative, late complications
- Outcomes: Short-term, long-term, quality of life, prognostic factors
- Future Directions: Emerging technologies, ongoing research, controversies

- Other: Content that doesn't fit the above categories

INSTRUCTIONS:
1. Determine if content is primarily PROCEDURAL (how-to) or KNOWLEDGE-BASED (what/why)
2. Assign the SINGLE most specific subcategory
3. Provide confidence 0.0-1.0 (0.8+ clear, 0.5-0.8 reasonable, <0.5 uncertain)
4. Give brief reasoning

Respond with JSON only:
{{"group": "<Surgical/Anatomical|Theoretical>", "category": "<subcategory>", "confidence": <float>, "reasoning": "<1 sentence>"}}"""


BATCH_CATEGORIZATION_PROMPT = """You are a neurosurgical content analyst. Categorize each excerpt according to standard neurosurgical textbook chapter structure.

Search Term: "{search_term}"

EXCERPTS TO CATEGORIZE:
{excerpts}

GROUPS AND CATEGORIES:
SURGICAL/ANATOMICAL: Preoperative Planning, Anesthetic Considerations, Patient Positioning, Surgical Approach, Anatomical Landmarks, Surgical Technique, Reconstruction, Closure, Intraoperative Monitoring, Technical Pitfalls
THEORETICAL: Definition & Classification, Epidemiology, Pathophysiology, Clinical Presentation, Diagnostic Evaluation, Differential Diagnosis, Treatment Options, Postoperative Management, Complications, Outcomes, Future Directions

For each excerpt, respond with JSON array:
[
  {{"id": 1, "group": "<group>", "category": "<subcategory>", "confidence": <float>, "reasoning": "<brief>"}},
  ...
]"""
