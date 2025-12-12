# Disorder Synthesis Prompt v2.0 — Textbook Excellence Edition

> **Version**: 2.0  
> **Purpose**: Neurosurgical disorder chapters matching Youmans/Greenberg/Principles quality  
> **Architecture**: Youmans (encyclopedic depth, basic science) + Greenberg (rapid reference, drug boxes) + Principles of NS (teaching clarity, board relevance)  
> **Figure Target**: 1 per 200-250 words; 50-80 figures per chapter  
> **Key Enhancements**: Molecular genetics, validated scores, pediatric considerations, medicolegal, named trials

---

## System Context

Pipeline integration for NeuroSynth FigureIntegrationPipeline:
1. Sources include "Available Figures" catalogs (FIGURE_ID, Type, Caption)
2. Place `[FIGURE: ID]` tags at clinically relevant locations
3. Pipeline handles: placeholder resolution, semantic recovery (0.4 threshold), position optimization

---

## Variables

| Variable | Description |
|----------|-------------|
| `{{REFERENCE_MATERIALS}}` | Source documents with Available Figures |
| `{{DISORDER}}` | Disorder/pathology to synthesize |

---

## Prompt

```
You are synthesizing a neurosurgical disorder chapter matching the quality standards of:

**Youmans & Winn Neurological Surgery** (8th Edition):
- Every disorder needs molecular/genetic basis when known
- Epidemiology requires incidence, prevalence, AND temporal trends
- Pathophysiology connects molecular → cellular → tissue → clinical
- Treatment discussions cite specific trials by name (e.g., "ISAT trial," "BRAT trial")
- Controversies present both sides with evidence levels

**Greenberg's Handbook of Neurosurgery** (10th Edition):
- "Booking the case" practical details
- Drug dosing with specific mg/kg and timing
- Classification systems with clinical decision rules
- Red flags that change management urgently
- Rapid reference tables with source citations

**Principles of Neurosurgery** (Rengachary & Ellenbogen):
- "Key Points" boxes highlighting board-relevant facts
- Clear teaching progression from basic to complex
- Clinical vignettes illustrating typical presentations
- Differential diagnosis with discriminating features

# Reference Materials

<reference_materials>
{{REFERENCE_MATERIALS}}
</reference_materials>

# Target Disorder

<disorder>
{{DISORDER}}
</disorder>

---

# FIGURE INTEGRATION PROTOCOL

## Density Requirements
- **Minimum**: 1 figure per 250 words
- **Target**: 50-80 figures total
- **Every** imaging finding, classification grade, and outcome graph needs figure support

## Mandatory Figure Triggers

Place `[FIGURE: ID]` when describing:
1. Pathological appearance (gross, microscopic, imaging)
2. Classification grades (example of each grade)
3. Imaging findings (annotated MRI/CT examples)
4. Pathophysiology mechanisms (pathway diagrams)
5. Epidemiology (incidence graphs, trends)
6. Natural history (progression curves, risk stratification)
7. Treatment algorithms (decision flowcharts)
8. Outcome comparisons (forest plots, Kaplan-Meier)
9. Genetic/molecular pathways
10. Complications (recognition images)

## Figure Format
`[FIGURE: exact_figure_id_from_catalog]`

---

# CORE PRINCIPLES

## 1. Source Fidelity (Zero Hallucination)
- Every statistic traces to source
- Never fabricate data, genetic information, or trial results
- State "Not addressed in provided references" when missing
- Preserve exact numeric values with confidence intervals

## 2. Evidence Classification (AANS/CNS)

| Class | Study Type | Recommendation |
|-------|------------|----------------|
| **I** | High-quality RCT, meta-analysis | **Standard** |
| **II** | Lesser RCT, prospective cohort | **Guideline** |
| **III** | Case series, retrospective, expert opinion | **Option** |

## 3. Mandatory Callout Boxes (Use Exactly As Formatted)

### 📕 DEFINITION
> **📕 DEFINITION**
> [WHO/standard definition — precise, one sentence]
> **Source**: [Reference]

### 🎯 KEY POINT (Board-Relevant)
> **🎯 KEY POINT**
> [Single high-yield fact — the "money fact" for boards/practice]
> **Source**: [Reference]

### ⚠️ CRITICAL ALERT
> **⚠️ CRITICAL**
> [Safety-critical information that prevents errors]
> **Clinical Impact**: [What happens if missed]
> **Source**: [Reference]

### 📋 PRACTICE GUIDELINE
> **📋 GUIDELINE** — Level [I/II/III]
> **Recommendation**: [Specific guideline text]
> **Strength**: [Standard/Guideline/Option]
> **Source**: [Society, Year — e.g., "AANS/CNS Guidelines, 2023"]

### 💊 DRUG DOSING (Greenberg-Style)
> **💊 [DRUG NAME]**
> | Parameter | Value |
> |-----------|-------|
> | **Class** | [Pharmacologic class] |
> | **Indication** | [When to use for this disorder] |
> | **Adult Dose** | [mg or mg/kg, frequency, route] |
> | **Pediatric Dose** | [mg/kg/day, max dose] |
> | **Loading** | [If applicable] |
> | **Renal Adjustment** | [GFR thresholds] |
> | **Hepatic Adjustment** | [Child-Pugh guidance] |
> | **Monitoring** | [Drug levels, labs to check] |
> | **Key Interactions** | [Critical drug interactions] |
> | **Black Box Warning** | [If applicable] |
> **Source**: [Reference]

### 🔴 RED FLAG
> **🔴 RED FLAG**: [Clinical scenario]
> **Implication**: [What this finding means]
> **Immediate Action**: [Required response]
> **Source**: [Reference]

### 📊 DIFFERENTIAL DIAGNOSIS
> **📊 DIFFERENTIAL DIAGNOSIS**
>
> | Condition | Key Distinguisher | Confirmatory Test |
> |-----------|-------------------|-------------------|
> | [Dx 1] | [Discriminating feature] | [Gold standard test] |
> | [Dx 2] | [Discriminating feature] | [Gold standard test] |
>
> [FIGURE: differential_imaging_comparison]

### 👶 PEDIATRIC CONSIDERATION
> **👶 PEDIATRIC**
> [Age-specific differences in presentation, workup, or management]
> **Source**: [Reference]

### ⚖️ MEDICOLEGAL
> **⚖️ MEDICOLEGAL**
> [Documentation requirement, consent issue, or standard of care consideration]
> **Source**: [Reference]

### 📝 CLINICAL VIGNETTE
> **📝 TYPICAL PRESENTATION**
> [2-3 sentence case description for pattern recognition]
> **Teaching Point**: [What this illustrates]

### 🔬 NAMED TRIAL
> **🔬 [TRIAL NAME]** (e.g., ISAT, BRAT, ARUBA)
> - **Design**: [RCT/Prospective/etc.]
> - **N**: [Sample size]
> - **Comparison**: [What was compared]
> - **Primary Outcome**: [Result with CI]
> - **Conclusion**: [Clinical implication]
> **Source**: [Citation]

---

# CHAPTER SCHEMA

---

# [DISORDER NAME]

## Executive Summary

[FIGURE: disorder_overview_schematic]

> **📕 DEFINITION**
> [WHO/standard definition]
> **Source**: [Reference]

**30-Second Summary** (Elevator Pitch):
[2-3 sentences capturing essence for rapid communication to colleagues]

### Key Numbers

| Parameter | Value | Source |
|:----------|:------|:-------|
| Incidence | [X per 100,000/year (95% CI: X-X)] | [Source] |
| Prevalence | [X per 100,000 (95% CI)] | [Source] |
| Peak Age | [Years (range)] | [Source] |
| Sex Ratio | [M:F] | [Source] |
| Annual Event Risk | [% (95% CI)] — define event | [Source] |
| Treatment Threshold | [Specific criteria] | [Source] |
| Treatment Success | [% — define success] | [Source] |

---

## Quick Reference Card

### Rapid Facts

| Parameter | Value | Source |
|:----------|:------|:-------|
| **ICD-10** | [Code] | — |
| **Synonyms** | [Alternative names, deprecated terms] | — |
| **Inheritance** | [Pattern if genetic; sporadic %] | [Source] |
| **Pathognomonic Finding** | [If exists] | [Source] |
| **Gold Standard Dx** | [Test] | [Source] |
| **First-Line Treatment** | [Treatment] | [Source] |

> **🎯 KEY POINT**
> [Single most testable/important fact — what residents MUST know]
> **Source**: [Reference]

> **🔴 RED FLAGS**
> - [Red flag 1]: Suggests [implication] → [Action]
> - [Red flag 2]: Suggests [implication] → [Action]  
> - [Red flag 3]: Suggests [implication] → [Action]

---

## Historical Context

[Brief 2-3 sentences: Discovery, key contributors, evolution of understanding. Provides context without excessive length.]

---

## Epidemiology

[FIGURE: epidemiology_overview]

### Incidence & Prevalence

| Population | Incidence (/100,000/yr) | Prevalence | 95% CI | n | Source |
|:-----------|:------------------------|:-----------|:-------|:--|:-------|
| Overall | [Rate] | [Rate] | [CI] | [n] | [Source] |
| Male | [Rate] | — | [CI] | [n] | [Source] |
| Female | [Rate] | — | [CI] | [n] | [Source] |
| Pediatric (<18) | [Rate] | — | [CI] | [n] | [Source] |
| Elderly (>65) | [Rate] | — | [CI] | [n] | [Source] |

[FIGURE: incidence_temporal_trends]

### Temporal Trends

[Description: Is incidence truly increasing or detection bias? What's driving changes?]

### Demographics

| Factor | Distribution | Clinical Significance | Source |
|:-------|:-------------|:----------------------|:-------|
| Age | Peak: [years]; Bimodal: [if applicable] | [Why age matters for prognosis/treatment] | [Source] |
| Sex | [M:F ratio or %] | [Hormonal/genetic factors] | [Source] |
| Race/Ethnicity | [If documented differences] | [Genetic/environmental explanations] | [Source] |
| Geography | [Regional variation] | [Possible explanations] | [Source] |

[FIGURE: demographic_distribution]

### Risk Factors

| Risk Factor | OR/RR | 95% CI | p | Modifiable? | Evidence | Source |
|:------------|:------|:-------|:--|:------------|:---------|:-------|
| [Factor 1] | [Value] | [CI] | [p] | Yes/No | [Class] | [Source] |
| [Factor 2] | [Value] | [CI] | [p] | Yes/No | [Class] | [Source] |

[FIGURE: risk_factor_forest_plot]

> **👶 PEDIATRIC**
> [Pediatric-specific epidemiology if different from adults]
> **Source**: [Reference]

---

## Genetics & Molecular Biology

[FIGURE: genetic_pathway_schematic]

### Genetic Basis

| Gene | Locus | Protein | Normal Function | Mutation Type | Frequency | Source |
|:-----|:------|:--------|:----------------|:--------------|:----------|:-------|
| [Gene1] | [Chr location] | [Protein name] | [What it does] | [Germline/Somatic] | [% of cases] | [Source] |

[FIGURE: molecular_mechanism]

### Hereditary Syndromes

| Syndrome | Gene | Inheritance | Key Features | Screening Recommendation | Source |
|:---------|:-----|:------------|:-------------|:-------------------------|:-------|
| [Syndrome] | [Gene] | [AD/AR/X-linked] | [Distinguishing features] | [When/how to screen] | [Source] |

### Sporadic vs. Hereditary

| Feature | Hereditary | Sporadic | Source |
|:--------|:-----------|:---------|:-------|
| Proportion | [%] | [%] | [Source] |
| Age of Onset | [Earlier/Later] | [Typical age] | [Source] |
| Multiplicity | [Higher/Lower] | [Typical] | [Source] |
| Family Screening | [Recommendation] | [Recommendation] | [Source] |

### Molecular Markers & Prognostic Factors

| Marker | Type | Clinical Utility | Prognostic Value | Source |
|:-------|:-----|:-----------------|:-----------------|:-------|
| [Marker] | [Diagnostic/Prognostic/Predictive] | [When to test] | [HR/OR if known] | [Source] |

> **📋 GUIDELINE** — Level [II/III]
> **Recommendation**: [Genetic testing indication]
> **Source**: [Society, Year]

---

## Pathophysiology

[FIGURE: pathophysiology_overview]

### Etiology & Mechanism

[Prose: Build from Molecular → Cellular → Tissue → Organ → Clinical manifestation. Make EXPLICIT connections between each level. This is the Youmans standard — deep mechanistic understanding.]

[FIGURE: mechanism_molecular_detail]
[FIGURE: mechanism_cellular]

> **🎯 KEY POINT**
> [Core pathophysiology concept — the "WHY" behind the disease that explains everything else]
> **Source**: [Reference]

### Pathological Features

**Gross Pathology**:
- Size: [Typical dimensions, range]
- Color: [Description]
- Consistency: [Soft/firm/rubbery/calcified]
- Margins: [Well-circumscribed/infiltrative]
- Cut surface: [Description]
- Location predilection: [Where most common and why]

[FIGURE: gross_pathology_specimen]

**Histopathology**:

| Feature | Description | Diagnostic Value | Source |
|:--------|:------------|:-----------------|:-------|
| [Architecture] | [Description] | [Pathognomonic/Supportive/Non-specific] | [Source] |
| [Cell type] | [Description] | [Diagnostic value] | [Source] |
| [Special features] | [Description] | [Diagnostic value] | [Source] |

[FIGURE: histology_low_power]
[FIGURE: histology_high_power]

**Immunohistochemistry**:

| Marker | Result | Utility | Source |
|:-------|:-------|:--------|:-------|
| [IHC marker] | [+/-] | [What it confirms/excludes] | [Source] |

[FIGURE: immunohistochemistry]

### Mechanism → Clinical Correlation

| Pathophysiological Mechanism | Clinical Manifestation | Source |
|:-----------------------------|:-----------------------|:-------|
| [Mechanism 1] | [How patient presents because of this] | [Source] |
| [Mechanism 2] | [How patient presents because of this] | [Source] |

---

## Natural History

[FIGURE: natural_history_timeline]

### Disease Course (Untreated)

[Prose: What happens if you do nothing? Specific timeframes, progression patterns.]

[FIGURE: progression_stages]

### Event Rates

| Event | Annual Rate | 95% CI | Cumulative (5-yr) | Risk Period | Source |
|:------|:------------|:-------|:------------------|:------------|:-------|
| [Primary event] | [%/year] | [CI] | [%] | [When highest risk] | [Source] |
| [Secondary event] | [%/year] | [CI] | [%] | [When highest risk] | [Source] |

[FIGURE: event_rate_curves]

### Risk Stratification

| Risk Category | Criteria | Annual Event Rate | 5-Year Cumulative | Management | Source |
|:--------------|:---------|:------------------|:------------------|:-----------|:-------|
| Low | [Specific criteria] | [% (CI)] | [%] | [Approach] | [Source] |
| Intermediate | [Specific criteria] | [% (CI)] | [%] | [Approach] | [Source] |
| High | [Specific criteria] | [% (CI)] | [%] | [Approach] | [Source] |

[FIGURE: risk_stratification_schema]

### Validated Prognostic Scores

| Score Name | Components | Calculation | Risk Categories | Validation | Source |
|:-----------|:-----------|:------------|:----------------|:-----------|:-------|
| [Score] | [Variables] | [Formula or point system] | [Categories with event rates] | [External validation?] | [Source] |

[FIGURE: prognostic_score_calculator]

---

## Clinical Presentation

[FIGURE: clinical_presentation_overview]

### Typical Presentation

> **📝 TYPICAL PRESENTATION**
> [2-3 sentence clinical vignette of classic case]
> **Teaching Point**: [Pattern recognition takeaway]

### Symptom Analysis

| Symptom | Frequency (%) | Mechanism | Discriminating Value | Source |
|:--------|:--------------|:----------|:---------------------|:-------|
| [Symptom 1] | [%] | [Why it occurs] | [Helps distinguish from what?] | [Source] |
| [Symptom 2] | [%] | [Why it occurs] | [Helps distinguish from what?] | [Source] |

[FIGURE: symptom_frequency_chart]

### Physical Examination Findings

| Finding | Sensitivity (%) | Specificity (%) | LR+ | LR- | Source |
|:--------|:----------------|:----------------|:----|:----|:-------|
| [Finding 1] | [%] | [%] | [Value] | [Value] | [Source] |
| [Finding 2] | [%] | [%] | [Value] | [Value] | [Source] |

[FIGURE: physical_exam_findings]

### Presentation by Subtype/Location

| Subtype/Location | Unique Features | Frequency | Source |
|:-----------------|:----------------|:----------|:-------|
| [Subtype 1] | [Distinguishing presentation] | [%] | [Source] |
| [Subtype 2] | [Distinguishing presentation] | [%] | [Source] |

> **🔴 RED FLAG**: [Symptom/sign]
> **Implication**: [What it suggests — e.g., impending herniation]
> **Immediate Action**: [What to do NOW]
> **Source**: [Reference]

---

## Diagnostic Evaluation

[FIGURE: diagnostic_algorithm]

### Imaging

#### MRI (Gold Standard for Most)

| Sequence | Typical Findings | Sensitivity | Specificity | Source |
|:---------|:-----------------|:------------|:------------|:-------|
| T1 | [Description] | [%] | [%] | [Source] |
| T1 + Gad | [Description] | [%] | [%] | [Source] |
| T2 | [Description] | [%] | [%] | [Source] |
| FLAIR | [Description] | [%] | [%] | [Source] |
| DWI/ADC | [Description] | [%] | [%] | [Source] |
| SWI/GRE | [Description] | [%] | [%] | [Source] |
| MRS | [Metabolite ratios] | [%] | [%] | [Source] |
| Perfusion | [rCBV patterns] | [%] | [%] | [Source] |

[FIGURE: mri_t1_typical]
[FIGURE: mri_t2_typical]
[FIGURE: mri_contrast_typical]
[FIGURE: mri_advanced_sequences]

#### CT

| Protocol | Findings | When Preferred Over MRI | Source |
|:---------|:---------|:------------------------|:-------|
| Non-contrast | [Description] | [Indication] | [Source] |
| Contrast | [Description] | [Indication] | [Source] |
| CTA | [Description] | [Indication] | [Source] |

[FIGURE: ct_typical]

#### Angiography (If Applicable)

[FIGURE: angiography_findings]

### Laboratory Studies

| Test | Expected Result | Clinical Utility | Source |
|:-----|:----------------|:-----------------|:-------|
| [Test] | [Value/finding] | [What it confirms/excludes] | [Source] |

### Diagnostic Criteria

> **📕 DIAGNOSTIC CRITERIA**: [Name of Criteria Set]
>
> **Definite [Disorder]** requires ALL of:
> - [ ] [Criterion 1]
> - [ ] [Criterion 2]
> - [ ] [Criterion 3]
>
> **Probable [Disorder]** requires:
> - [ ] [Alternative criteria]
>
> **Source**: [Society/Consensus, Year]

### Differential Diagnosis

> **📊 DIFFERENTIAL DIAGNOSIS**
>
> | Condition | Key Distinguisher | Confirmatory Test |
> |:----------|:------------------|:------------------|
> | [Dx 1] | [What makes it different] | [Gold standard] |
> | [Dx 2] | [What makes it different] | [Gold standard] |
> | [Dx 3] | [What makes it different] | [Gold standard] |
> | [Dx 4] | [What makes it different] | [Gold standard] |
>
> [FIGURE: differential_imaging_comparison]

---

## Classification Systems

[FIGURE: classification_overview]

### [Primary Classification Name] (Year)

| Grade/Type | Criteria | Frequency | Prognosis | Management Implication | Source |
|:-----------|:---------|:----------|:----------|:-----------------------|:-------|
| [I] | [Criteria] | [%] | [Outcome] | [What you do] | [Source] |
| [II] | [Criteria] | [%] | [Outcome] | [What you do] | [Source] |
| [III] | [Criteria] | [%] | [Outcome] | [What you do] | [Source] |
| [IV] | [Criteria] | [%] | [Outcome] | [What you do] | [Source] |

[FIGURE: classification_grade_examples]

### Classification Decision Rules

```
CLASSIFICATION ALGORITHM:

IF [Finding A] present:
  AND [Finding B] present:
    → Grade I → Observation
  AND [Finding C] present:
    → Grade II → Consider treatment

IF [Finding D] present:
  → Grade III → Treatment indicated

IF [Finding E] present:
  → Grade IV → Urgent treatment
```

> **🎯 KEY POINT**: Classification Pitfall
> [Common misclassification error and how to avoid it]
> **Source**: [Reference]

---

## Treatment Decision Framework

[FIGURE: treatment_decision_algorithm]

### Observation Criteria (When NOT to Treat)

**Observe if ALL of the following**:
- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

**Observation Protocol**:

| Interval | Clinical Assessment | Imaging | Labs | Source |
|:---------|:--------------------|:--------|:-----|:-------|
| [3 months] | [What to check] | [Modality] | [If any] | [Source] |
| [6 months] | [What to check] | [Modality] | [If any] | [Source] |
| [Annual] | [What to check] | [Modality] | [If any] | [Source] |

### Treatment Indications

> **📋 GUIDELINE** — Level [I/II/III]
> **Treat if ANY of the following**:
> - [Indication 1]
> - [Indication 2]
> - [Indication 3]
> **Source**: [Society Guidelines, Year]

### Treatment Selection Matrix

| Clinical Scenario | First-Line | Alternative | Avoid | Evidence | Source |
|:------------------|:-----------|:------------|:------|:---------|:-------|
| [Scenario 1] | [Treatment] | [Option] | [Contraindicated] | [Class] | [Source] |
| [Scenario 2] | [Treatment] | [Option] | [Contraindicated] | [Class] | [Source] |

[FIGURE: treatment_selection_flowchart]

---

## Treatment Options

### Option 1: [Treatment Name]

[FIGURE: treatment_1_overview]

**Mechanism**: [How it works]

**Indications**: [When this treatment is preferred]

**Technique Summary**: [Brief overview — NOT detailed surgical steps; those belong in Procedural chapter]

**Key Parameters**:

| Parameter | Specification | Source |
|:----------|:--------------|:-------|
| [Parameter] | [Value] | [Source] |

**Outcomes** (from Key Trials):

> **🔬 [TRIAL NAME]** (e.g., ISAT, BRAT)
> - **Design**: [RCT/Prospective cohort]
> - **N**: [Sample size]
> - **Comparison**: [What vs. what]
> - **Primary Outcome**: [Result with 95% CI]
> - **Follow-up**: [Duration]
> - **Conclusion**: [Clinical bottom line]
> **Source**: [Full citation]

| Outcome | Rate | 95% CI | Follow-up | Source |
|:--------|:-----|:-------|:----------|:-------|
| [Primary] | [%] | [CI] | [Duration] | [Source] |
| [Secondary] | [%] | [CI] | [Duration] | [Source] |

[FIGURE: treatment_1_outcomes]

### Option 2: [Treatment Name]

[Same structure...]

### Option 3: [Treatment Name]

[Same structure...]

---

## Comparative Effectiveness

[FIGURE: comparative_effectiveness_overview]

### Treatment A vs. Treatment B

| Outcome | Treatment A | Treatment B | Comparison (95% CI) | NNT/NNH | Evidence | Source |
|:--------|:------------|:------------|:--------------------|:--------|:---------|:-------|
| [Efficacy] | [%] | [%] | [OR/RR (CI)] | [Value] | [Class] | [Source] |
| [Safety] | [%] | [%] | [OR/RR (CI)] | [Value] | [Class] | [Source] |

[FIGURE: forest_plot_comparison]
[FIGURE: kaplan_meier_comparison]

### Meta-Analysis Summary (If Available)

| Comparison | Pooled Effect | 95% CI | p | I² | Studies (n) | Source |
|:-----------|:--------------|:-------|:--|:---|:------------|:-------|
| [Comparison] | [OR/RR/HR] | [CI] | [p] | [%] | [n] | [Source] |

[FIGURE: meta_analysis_forest_plot]

> **⚠️ CRITICAL**: Treatment Selection
> [Key factor that should drive decision between options]
> **Source**: [Reference]

---

## Medical Management

[FIGURE: medical_management_algorithm]

### First-Line Agents

> **💊 [DRUG 1 NAME]**
> | Parameter | Value |
> |-----------|-------|
> | **Class** | [Pharmacologic class] |
> | **Indication** | [Specific use in this disorder] |
> | **Adult Dose** | [mg or mg/kg, frequency, route, duration] |
> | **Pediatric Dose** | [mg/kg/day divided q[X]h, max [X] mg/day] |
> | **Loading Dose** | [If applicable] |
> | **Renal Adjustment** | [CrCl thresholds and adjustments] |
> | **Hepatic Adjustment** | [Child-Pugh A/B/C guidance] |
> | **Monitoring** | [Drug levels, target range, frequency; labs to monitor] |
> | **Key Interactions** | [CYP interactions, contraindicated combinations] |
> | **Pregnancy** | [Category, specific guidance] |
> | **Black Box Warning** | [If applicable] |
> **Source**: [Reference]

### Second-Line Agents

[Same format...]

### Treatment Algorithm

```
MEDICAL MANAGEMENT ALGORITHM:

Start: [First-line drug] at [dose]
  ↓
Assess response at [timeframe]
  ↓
IF adequate response:
  → Continue, monitor [parameters]
IF inadequate response:
  → Add [second agent] OR switch to [alternative]
  ↓
IF refractory (failed [n] agents):
  → Consider surgical evaluation
```

---

## Surgical Considerations

[FIGURE: surgical_overview]

*Note: Detailed operative technique is in the Procedural Synthesis chapter. This section covers indications, approach selection, and expected outcomes.*

### Surgical Indications

[Brief list — see Treatment Decision Framework for details]

### Approach Options

| Approach | Best For | Advantage | Disadvantage | Source |
|:---------|:---------|:----------|:-------------|:-------|
| [Approach 1] | [Indication] | [Pro] | [Con] | [Source] |
| [Approach 2] | [Indication] | [Pro] | [Con] | [Source] |

### Expected Surgical Outcomes

| Outcome | Rate | Definition | Source |
|:--------|:-----|:-----------|:-------|
| [Success] | [%] | [How defined] | [Source] |
| [Morbidity] | [%] | [What counts] | [Source] |
| [Mortality] | [%] | [Timeframe] | [Source] |

> **🏥 BOOKING THE CASE** (Greenberg-style)
> | Parameter | Specification |
> |-----------|---------------|
> | **Estimated Duration** | [X-X hours] |
> | **Position** | [Specific position] |
> | **Head Fixation** | [Pins/Horseshoe/Flat] |
> | **Special Equipment** | [Navigation, microscope, etc.] |
> | **Blood Products** | [Type & screen / Crossmatch X units] |
> | **Neuromonitoring** | [SSEP/MEP/EMG/etc.] |
> | **ICU Bed** | [Required/Not required] |
> **Source**: [Reference]

---

## Outcomes

[FIGURE: outcomes_summary]

### Primary Outcomes

| Outcome | Definition | Overall Rate | 95% CI | Follow-up | Source |
|:--------|:-----------|:-------------|:-------|:----------|:-------|
| [Success/Cure] | [How defined] | [%] | [CI] | [Duration] | [Source] |
| [Recurrence] | [How defined] | [%] | [CI] | [Duration] | [Source] |

[FIGURE: primary_outcome_by_treatment]

### Survival Analysis

[FIGURE: kaplan_meier_survival]

| Metric | Value | 95% CI | Source |
|:-------|:------|:-------|:-------|
| Median Survival | [Time] | [CI] | [Source] |
| 1-Year OS | [%] | [CI] | [Source] |
| 5-Year OS | [%] | [CI] | [Source] |
| 10-Year OS | [%] | [CI] | [Source] |
| PFS (if applicable) | [Time] | [CI] | [Source] |

### Functional Outcomes

| Scale | Pre-Treatment | Post-Treatment | Change | p-value | Source |
|:------|:--------------|:---------------|:-------|:--------|:-------|
| [KPS/mRS/etc.] | [Mean ± SD] | [Mean ± SD] | [Difference] | [p] | [Source] |

[FIGURE: functional_outcome_trends]

### Prognostic Factors (Multivariate)

| Factor | HR/OR | 95% CI | p | Direction | Source |
|:-------|:------|:-------|:--|:----------|:-------|
| [Factor 1] | [Value] | [CI] | [p] | [Better/Worse] | [Source] |
| [Factor 2] | [Value] | [CI] | [p] | [Better/Worse] | [Source] |

[FIGURE: prognostic_forest_plot]

---

## Complications

[FIGURE: complications_overview]

### By Treatment Modality

| Complication | Treatment A (%) | Treatment B (%) | Treatment C (%) | Source |
|:-------------|:----------------|:----------------|:----------------|:-------|
| [Complication 1] | [%] | [%] | [%] | [Source] |
| [Complication 2] | [%] | [%] | [%] | [Source] |

[FIGURE: complication_comparison_chart]

### Complication Recognition & Management

| Complication | Incidence | Risk Factors | Recognition | Prevention | Treatment | Source |
|:-------------|:----------|:-------------|:------------|:-----------|:----------|:-------|
| [Major 1] | [%] | [Factors] | [Signs/symptoms] | [How to avoid] | [Management] | [Source] |
| [Major 2] | [%] | [Factors] | [Signs/symptoms] | [How to avoid] | [Management] | [Source] |

[FIGURE: complication_recognition]

> **⚠️ CRITICAL**: [Most Dangerous Complication]
> **Incidence**: [%]
> **Recognition**: [Key signs — what to look for]
> **Immediate Action**: [What to do in first minutes]
> **Source**: [Reference]

---

## Follow-Up Protocol

[FIGURE: followup_algorithm]

### Surveillance Schedule

| Time Point | Clinical | Imaging | Labs | Source |
|:-----------|:---------|:--------|:-----|:-------|
| [1 month] | [Assessment] | [If indicated] | [If indicated] | [Source] |
| [3 months] | [Assessment] | [Modality] | [If indicated] | [Source] |
| [6 months] | [Assessment] | [Modality] | [If indicated] | [Source] |
| [1 year] | [Assessment] | [Modality] | [If indicated] | [Source] |
| [Annual thereafter] | [Assessment] | [Modality] | [If indicated] | [Source] |

### Recurrence Detection

**Signs of Recurrence**:
- Imaging: [What to look for]
- Clinical: [Symptoms suggesting recurrence]

**Response Protocol**:
```
IF surveillance shows [finding]:
  → [Immediate action]
IF clinical [symptom]:
  → [Workup required]
```

[FIGURE: recurrence_imaging_example]

---

## Special Populations

### Pediatric

> **👶 PEDIATRIC CONSIDERATIONS**
>
> **Epidemiology**: [How different in children]
>
> **Presentation**: [Unique pediatric features]
>
> **Treatment Modifications**: [What changes]
>
> **Outcomes**: [Better/worse than adults]
>
> **Long-term Issues**: [Growth, development, late effects]
>
> **Source**: [Reference]

[FIGURE: pediatric_specific]

### Elderly (>65 or >70)

| Consideration | Modification | Rationale | Source |
|:--------------|:-------------|:----------|:-------|
| [Issue] | [What to change] | [Why] | [Source] |

### Pregnancy

| Trimester | Imaging | Treatment | Delivery Considerations | Source |
|:----------|:--------|:----------|:-----------------------|:-------|
| First | [Safe options] | [Modifications] | [If applicable] | [Source] |
| Second | [Safe options] | [Modifications] | [If applicable] | [Source] |
| Third | [Safe options] | [Modifications] | [Timing, mode] | [Source] |

---

## Controversies & Evolving Concepts

[FIGURE: controversy_overview]

### Controversy 1: [Topic]

**The Clinical Question**: [Frame as answerable question]

| Position | Argument | Key Evidence | Evidence Class | Source |
|:---------|:---------|:-------------|:---------------|:-------|
| Pro-[A] | [Rationale] | [Studies/data] | [I/II/III] | [Source] |
| Pro-[B] | [Rationale] | [Studies/data] | [I/II/III] | [Source] |

**Current Consensus** (if any): [Statement]

**Ongoing Trials**: [NCT numbers, expected completion]

**Bottom Line for Now**: [Practical guidance given uncertainty]

[FIGURE: controversy_data_comparison]

### Controversy 2: [Topic]

[Same structure...]

---

## Clinical Pearls

> **🎯 PEARL 1: [Topic]**
> [Board-relevant clinical insight]
> **Source**: [Reference]

> **🎯 PEARL 2: [Topic]**
> [Practical clinical insight]
> **Source**: [Reference]

> **🎯 PEARL 3: [Topic]**
> [Diagnostic insight]
> **Source**: [Reference]

> **🎯 PEARL 4: [Topic]**
> [Treatment insight]
> **Source**: [Reference]

> **🎯 PEARL 5: [Topic]**
> [Prognostic insight]
> **Source**: [Reference]

[Continue for 5-8 total pearls]

---

## Common Pitfalls

| Pitfall | Consequence | How to Avoid | Source |
|:--------|:------------|:-------------|:-------|
| [Diagnostic pitfall] | [What goes wrong] | [Prevention] | [Source] |
| [Treatment pitfall] | [What goes wrong] | [Prevention] | [Source] |
| [Follow-up pitfall] | [What goes wrong] | [Prevention] | [Source] |

[FIGURE: pitfall_example]

---

## Medicolegal Considerations

> **⚖️ DOCUMENTATION**
> **Required Elements**:
> - [Element 1]
> - [Element 2]
> - [Element 3]
> **Source**: [Reference]

> **⚖️ INFORMED CONSENT**
> **Must Discuss**:
> - [Risk 1]: [Incidence]
> - [Risk 2]: [Incidence]
> - [Risk 3]: [Incidence]
> - [Alternatives]
> **Source**: [Reference]

---

## Critical Information Gaps

**MANDATORY SECTION**

*The following clinically relevant parameters were NOT addressed in the provided references:*

- **Epidemiology**: [What's missing]
- **Genetics**: [What's missing]
- **Natural History**: [What's missing]
- **Treatment**: [What's missing]
- **Outcomes**: [What's missing]

---

## Quantitative Reference Tables

### All Epidemiological Data
| Parameter | Value | Source |
|:----------|:------|:-------|
| [Consolidated epidemiological statistics] | | |

### All Outcome Data
| Parameter | Value | Source |
|:----------|:------|:-------|
| [Consolidated outcome statistics] | | |

### All Risk/Prognostic Data
| Parameter | Value | Source |
|:----------|:------|:-------|
| [Consolidated prognostic statistics] | | |

---

## Figure Index

| Figure ID | Description | Section | Source |
|:----------|:------------|:--------|:-------|
| [All figures cataloged with locations] | | | |

---

## References

[Complete source list organized by section]

---

# SYNTHESIS PROCESS

## Phase 1: Figure Inventory
Map available figures to schema sections

## Phase 2: Data Extraction
- All statistics with confidence intervals and n
- All genetic/molecular data
- All named trial results
- All drug dosing parameters

## Phase 3: Evidence Grading
Classify every recommendation by AANS/CNS evidence level

## Phase 4: Figure Integration
Verify ≥1 figure per 250 words

## Phase 5: Box Integration
Place all standardized boxes (📕🎯⚠️📋💊🔴📊👶⚖️📝🔬)

## Phase 6: Completeness Check
- [ ] All sections present
- [ ] All statistics have CI and n
- [ ] All recommendations evidence-graded
- [ ] All drugs have complete dosing boxes
- [ ] Information gaps documented
- [ ] Figure density adequate
```

---

## Quality Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Figures per 1000 words | 4-5 | 3 |
| Standardized boxes per chapter | 15-25 | 10 |
| Evidence-graded recommendations | 100% | 80% |
| Statistics with CI | 100% | 90% |
| Named trials cited | All major | Key trials |
| Drug boxes complete | 100% | 80% |
