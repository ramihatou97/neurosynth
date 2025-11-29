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

DECISION TREE (Apply in order):

1. VOICE & VERB ANALYSIS
   - Contains IMPERATIVE verbs (position, make, identify, dissect, resect, place, insert)?
     → Likely SURGICAL/ANATOMICAL
   - Contains DESCRIPTIVE language (the patient presents, studies show, incidence is)?
     → Likely THEORETICAL

2. CONTENT STRUCTURE
   - Describes STEP-BY-STEP actions with anatomical landmarks?
     → Likely SURGICAL/ANATOMICAL (Surgical Approach or Technique)
   - Describes WHAT a condition is, WHY it occurs, or HOW to diagnose?
     → Likely THEORETICAL (Pathophysiology, Clinical Presentation, etc.)

3. SPECIFIC INDICATORS

   SURGICAL/ANATOMICAL Indicators:
   - Imperative voice: "Position the patient in lateral decubitus"
   - Anatomical navigation: "Identify the sigmoid sinus medially"
   - Instrument mentions: "Use bipolar cautery to coagulate..."
   - Sequential procedural steps: "After dural opening, inspect the cerebellum"
   - Positioning details: "Place the head in three-point fixation"
   - Incision descriptions: "Make a curvilinear incision..."
   - Dissection planes: "Develop the subgaleal plane..."

   THEORETICAL Indicators:
   - Descriptive voice: "The tumor typically presents with..."
   - Statistical data: "Incidence is 1 per 100,000"
   - Diagnostic criteria: "MRI shows enhancement on T1..."
   - Outcome data: "5-year survival is approximately..."
   - Disease mechanisms: "The pathophysiology involves..."
   - Clinical signs: "Patients commonly experience..."
   - Treatment paradigms: "Management options include..."

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
1. Apply the DECISION TREE above to determine group (Surgical/Anatomical vs Theoretical)
2. Look for specific indicators (imperative verbs, anatomical navigation, etc.)
3. Assign the SINGLE most specific subcategory within that group
4. Provide confidence 0.0-1.0:
   - 0.9-1.0: Very clear indicators, unambiguous
   - 0.7-0.9: Clear category with strong evidence
   - 0.5-0.7: Reasonable assignment with some ambiguity
   - <0.5: Uncertain, mixed signals
5. Give brief reasoning citing specific indicators

IMPORTANT DISTINCTIONS:
- "Surgical Approach" = ACCESS (incision, exposure, craniotomy, laminectomy)
- "Surgical Technique" = TARGET MANIPULATION (tumor resection, aneurysm clipping, decompression)
- "Complications" = Problems that can occur (intraoperative, postoperative)
- "Postoperative Management" = Care after surgery (ICU, floor, rehabilitation)

Respond with JSON only:
{{"group": "<Surgical/Anatomical|Theoretical>", "category": "<subcategory>", "confidence": <float>, "reasoning": "<1 sentence citing specific indicators>"}}"""


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
