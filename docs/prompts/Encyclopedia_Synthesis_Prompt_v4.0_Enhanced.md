# Neurosurgical Encyclopedia Synthesis Prompt v4.0 — Ultimate Textbook Edition

> **Version**: 4.0  
> **Purpose**: Comprehensive single-topic reference combining Disorder + Anatomy + Procedure  
> **Architecture**: Youmans (encyclopedic) + Schmidek (operative) + Rhoton (anatomical) + Greenberg (rapid reference)  
> **Figure Target**: 1 figure per 150 words; 120-180 figures per encyclopedia entry  
> **Key Enhancement**: Integrated decision-making, complete surgical planning, outcome optimization

---

## System Context

This prompt generates comprehensive encyclopedia entries for the NeuroSynth FigureIntegrationPipeline:
1. Sources include "Available Figures" catalogs (FIGURE_ID, Type, Caption)
2. Place `[FIGURE: ID]` tags throughout all sections
3. Pipeline handles: placeholder resolution, cross-section correlation, position optimization

**Your role**: Create the definitive single reference for a neurosurgical topic—everything a surgeon needs from diagnosis through long-term follow-up.

---

## Variables

| Variable | Description | Options |
|----------|-------------|---------|
| `{{REFERENCE_MATERIALS}}` | Source documents with Available Figures | Required |
| `{{TOPIC}}` | Encyclopedia topic | Required |
| `{{ANATOMY_DEPTH}}` | Anatomical detail level | MINIMAL / STANDARD / COMPREHENSIVE |
| `{{CONTENT_EMPHASIS}}` | Weight distribution | DISORDER / SURGICAL / BALANCED |

---

## Prompt

```
You are creating the definitive neurosurgical encyclopedia entry for {{TOPIC}}. This entry must serve as a complete reference integrating:

1. **Disease Understanding** (Youmans depth) — Pathophysiology, natural history, evidence-based treatment selection
2. **Surgical Technique** (Schmidek precision) — Step-by-step operative technique with decision points
3. **Microsurgical Anatomy** (Rhoton quality) — Surgically-relevant anatomical detail
4. **Rapid Reference** (Greenberg utility) — Boxes, algorithms, and quick-lookup tables

The output should allow a neurosurgery resident to:
- Understand the disease completely
- Select appropriate treatment
- Plan and execute surgery safely
- Manage complications
- Counsel patients on outcomes

CRITICAL TEXTBOOK STANDARDS INTEGRATION:

**From Youmans & Winn**:
- Molecular/genetic basis of disease
- Named clinical trials for treatment evidence
- Comprehensive natural history data
- Systematic review of treatment outcomes

**From Schmidek & Sweet**:
- Numbered surgical steps with endpoints
- Equipment specifications
- Complication prevention and management
- Results with statistical detail

**From Rhoton**:
- Layer-by-layer anatomical progression
- All measurements: Mean ± SD (range; n)
- Variations with prevalence percentages
- Multiple viewing angles

**From Greenberg**:
- Quick reference boxes (📕📋💊🔴⚠️)
- Drug dosing tables
- Classification systems with management implications
- Red flags and emergency protocols

# Reference Materials

<reference_materials>
{{REFERENCE_MATERIALS}}
</reference_materials>

# Encyclopedia Topic

<topic>
{{TOPIC}}
</topic>

<anatomy_depth>
{{ANATOMY_DEPTH}}
</anatomy_depth>

<content_emphasis>
{{CONTENT_EMPHASIS}}
</content_emphasis>

---

# FIGURE INTEGRATION PROTOCOL

## Density Requirements
- **Minimum**: 1 figure per 150 words
- **Target**: 120-180 figures for comprehensive encyclopedia entry
- **Integration**: Figures link disease, anatomy, and procedure

## Figure Triggers by Section

### Part I (Disorder)
- Pathophysiology mechanisms
- Classification grade examples
- Imaging findings (all modalities)
- Treatment algorithms
- Outcome graphs

### Part II (Anatomy)
- Every named structure
- Multiple viewing angles
- Surgical corridors
- Variations

### Part III (Procedure)
- Every surgical step (2-4 figures each)
- Instrument positioning
- Anatomical relationships during surgery
- Complications

## Figure Format
`[FIGURE: exact_figure_id_from_catalog]`

---

# CORE PRINCIPLES

## 1. Evidence Classification

| Class | Study Design | Recommendation Level |
|-------|--------------|---------------------|
| **I** | High-quality RCT, meta-analysis | **Standard** |
| **II** | Lesser RCT, prospective cohort | **Guideline** |
| **III** | Case series, retrospective | **Option** |

## 2. Measurement Standards

- Anatomical: Mean ± SD (range; n)
- Variations: Prevalence % (95% CI; n)
- Outcomes: Rate % (95% CI)
- Comparisons: OR/RR (95% CI), p-value

## 3. Integrated Callout System

### 📕 DEFINITION
> **📕 DEFINITION**
> [Precise WHO/standard definition]
> **Source**: [Reference]

### 🎯 KEY POINT (Board-Relevant)
> **🎯 KEY POINT**
> [High-yield testable fact]
> **Source**: [Reference]

### 📋 PRACTICE GUIDELINE
> **📋 GUIDELINE** — Level [I/II/III]
> **Recommendation**: [Specific guidance]
> **Strength**: [Standard/Guideline/Option]
> **Source**: [Society, Year]

### 💊 DRUG DOSING
> **💊 [DRUG NAME]**
> - **Class**: [Category]
> - **Indication**: [Use]
> - **Adult**: [Dose, frequency]
> - **Pediatric**: [mg/kg]
> - **Monitoring**: [Labs/levels]
> - **Cautions**: [Warnings]
> **Source**: [Reference]

### 🔴 RED FLAG
> **🔴 RED FLAG**: [Clinical finding]
> **Means**: [Diagnosis/condition]
> **Action**: [Required response]
> **Source**: [Reference]

### ⚠️ HAZARD WARNING (Surgical)
> **⚠️ HAZARD**: [Risk]
> **Recognition**: [Signs]
> **Prevention**: [Technique]
> **Bailout**: [If occurs]
> [FIGURE: hazard_illustration]

### 🔴 CRITICAL ANATOMY
> **🔴 STRUCTURE AT RISK**: [Name]
> **Location**: [Position]
> **Consequence**: [If injured]
> **Protection**: [Strategy]
> [FIGURE: anatomy_at_risk]

### 🔀 DECISION POINT
> **🔀 DECISION**
> ```
> IF [finding A]:
>   → [Action A]
> IF [finding B]:
>   → [Action B]
> ```

### 💡 PEARL
> **💡 PEARL**: [Topic]
> [Expert insight]
> **Source**: [Reference]

### 🚫 PITFALL
> **🚫 PITFALL**: [Mistake]
> **Consequence**: [Result]
> **Prevention**: [How to avoid]

### 🏥 BOOKING THE CASE
> **🏥 OPERATIVE SETUP**
> - **Duration**: [Hours]
> - **Position**: [Position]
> - **Equipment**: [Key items]
> - **Monitoring**: [Modalities]
> - **Blood**: [Products needed]
> [FIGURE: or_setup]

### 📐 KEY MEASUREMENT
> **📐 MEASUREMENT**: [Parameter]
> **Value**: [Mean ± SD (range; n)]
> **Surgical Use**: [Application]
> [FIGURE: measurement_illustration]

### 🔺 ANATOMICAL TRIANGLE
> **🔺 TRIANGLE**: [Name]
> **Boundaries**: [Three structures]
> **Contents**: [What's inside]
> **Surgical Use**: [Access provided]
> [FIGURE: triangle_detail]

---

# ENCYCLOPEDIA SCHEMA

---

# [TOPIC] — Comprehensive Neurosurgical Reference

## Executive Summary

[FIGURE: topic_comprehensive_overview]

> **📕 DEFINITION**
> [One-sentence authoritative definition]
> **Source**: [Reference]

### The Complete Picture (60-Second Brief)

[3-4 sentences capturing: What is it → Who gets it → How it presents → How we treat it → What outcomes to expect]

### Essential Numbers

| Category | Parameter | Value | Source |
|:---------|:----------|:------|:-------|
| **Epidemiology** | Incidence | [/100,000/year (95% CI)] | [Source] |
| **Natural History** | Annual event rate | [% (95% CI)] | [Source] |
| **Treatment** | Success rate | [% (definition)] | [Source] |
| **Surgery** | Major complication | [%] | [Source] |
| **Anatomy** | Key dimension | [Mean ± SD mm] | [Source] |

---

## Quick Reference Card

### At-a-Glance Table

| Parameter | Value | Source |
|:----------|:------|:-------|
| **ICD-10** | [Code] | — |
| **Synonyms** | [Names] | — |
| **Incidence** | [Rate] | [Source] |
| **Peak Age** | [Years] | [Source] |
| **M:F** | [Ratio] | [Source] |
| **Pathognomonic** | [Finding] | [Source] |
| **Gold Standard Dx** | [Test] | [Source] |
| **First-Line Rx** | [Treatment] | [Source] |
| **Surgical Approach** | [Approach] | [Source] |
| **Success Rate** | [%] | [Source] |

> **🎯 KEY POINT**
> [Single most important fact]
> **Source**: [Reference]

> **🔴 RED FLAGS**
> - [Flag 1] → [Action]
> - [Flag 2] → [Action]
> - [Flag 3] → [Action]

[FIGURE: quick_reference_visual]

---

# PART I: THE DISORDER

---

## 1.1 Disease Definition & Classification

[FIGURE: classification_overview]

### WHO/Standard Definition

> **📕 DEFINITION**
> [Precise pathological definition from authoritative source]
> **Source**: [WHO/Reference]

### Classification Systems

#### [Primary Classification Name]

| Grade/Type | Criteria | Clinical Implication | Source |
|:-----------|:---------|:---------------------|:-------|
| [I] | [Features] | [Management] | [Source] |
| [II] | [Features] | [Management] | [Source] |
| [III] | [Features] | [Management] | [Source] |
| [IV] | [Features] | [Management] | [Source] |

[FIGURE: classification_each_grade]

### Classification Application Algorithm

```
IF [Finding A] AND [Finding B]:
  → Grade I → [Management path]
IF [Finding C]:
  → Grade II → [Management path]
...
```

[FIGURE: classification_algorithm]

---

## 1.2 Epidemiology

[FIGURE: epidemiology_overview]

### Incidence & Prevalence

| Population | Incidence | Prevalence | 95% CI | n | Source |
|:-----------|:----------|:-----------|:-------|:--|:-------|
| Overall | [/100,000/yr] | [/100,000] | [CI] | [n] | [Source] |
| Male | [Rate] | [Rate] | [CI] | [n] | [Source] |
| Female | [Rate] | [Rate] | [CI] | [n] | [Source] |
| Pediatric | [Rate] | [Rate] | [CI] | [n] | [Source] |

[FIGURE: incidence_trends]
[FIGURE: demographic_distribution]

### Risk Factors

| Factor | OR/RR | 95% CI | Modifiable | Evidence | Source |
|:-------|:------|:-------|:-----------|:---------|:-------|
| [Factor] | [Value] | [CI] | Yes/No | [Class] | [Source] |

[FIGURE: risk_factors_forest_plot]

---

## 1.3 Genetics & Molecular Biology

[FIGURE: molecular_pathway]

### Genetic Basis

| Gene | Locus | Protein | Mutation Type | Frequency | Source |
|:-----|:------|:--------|:--------------|:----------|:-------|
| [Gene] | [Chr] | [Protein] | [Germline/Somatic] | [%] | [Source] |

[FIGURE: genetic_pathway_schematic]

### Hereditary Syndromes

| Syndrome | Gene | Inheritance | Features | Screening | Source |
|:---------|:-----|:------------|:---------|:----------|:-------|
| [Syndrome] | [Gene] | [Pattern] | [Features] | [Recommendation] | [Source] |

> **📋 GUIDELINE** — Level [II/III]
> **Genetic Testing**: [Indication]
> **Source**: [Society, Year]

---

## 1.4 Pathophysiology

[FIGURE: pathophysiology_overview]

### Mechanism: Molecular → Clinical

[Prose connecting basic science to clinical manifestations]

[FIGURE: mechanism_molecular]
[FIGURE: mechanism_cellular]
[FIGURE: mechanism_tissue]

### Pathological Features

**Gross Pathology**:
[FIGURE: gross_specimen]

**Histopathology**:
| Feature | Description | Significance | Source |
|:--------|:------------|:-------------|:-------|
| [Feature] | [Description] | [Diagnostic value] | [Source] |

[FIGURE: histology_low_power]
[FIGURE: histology_high_power]

> **🎯 KEY POINT**: Pathophysiology Core Concept
> [The essential "why" of this disease]
> **Source**: [Reference]

---

## 1.5 Natural History

[FIGURE: natural_history_timeline]

### Untreated Course

[Description with timeframes]

### Event Rates

| Event | Annual Rate | 95% CI | Risk Period | Source |
|:------|:------------|:-------|:------------|:-------|
| [Event] | [%/year] | [CI] | [When highest] | [Source] |

[FIGURE: event_rate_curves]

### Risk Stratification

| Risk | Criteria | Annual Rate | Management | Source |
|:-----|:---------|:------------|:-----------|:-------|
| Low | [Criteria] | [%] | [Approach] | [Source] |
| High | [Criteria] | [%] | [Approach] | [Source] |

[FIGURE: risk_stratification_schema]

### Validated Prognostic Scores

| Score | Components | Interpretation | Source |
|:------|:-----------|:---------------|:-------|
| [Score] | [Variables] | [Categories] | [Source] |

[FIGURE: prognostic_nomogram]

---

## 1.6 Clinical Presentation

[FIGURE: presentation_overview]

### Typical Presentation

> **📝 CLINICAL VIGNETTE**
> [2-3 sentence classic presentation]

### Symptom Analysis

| Symptom | Frequency | Mechanism | Source |
|:--------|:----------|:----------|:-------|
| [Symptom] | [%] | [Why occurs] | [Source] |

[FIGURE: symptom_distribution]

### Physical Examination

| Finding | Sensitivity | Specificity | LR+ | Source |
|:--------|:------------|:------------|:----|:-------|
| [Finding] | [%] | [%] | [Value] | [Source] |

[FIGURE: exam_findings]

> **🔴 RED FLAG**: [Finding]
> **Means**: [Diagnosis]
> **Action**: [Response]
> **Source**: [Reference]

---

## 1.7 Diagnostic Evaluation

[FIGURE: diagnostic_algorithm]

### Imaging

#### MRI Protocol

| Sequence | Findings | Sensitivity | Specificity | Source |
|:---------|:---------|:------------|:------------|:-------|
| T1 | [Findings] | [%] | [%] | [Source] |
| T2 | [Findings] | [%] | [%] | [Source] |
| FLAIR | [Findings] | [%] | [%] | [Source] |
| T1+Gad | [Findings] | [%] | [%] | [Source] |
| DWI | [Findings] | [%] | [%] | [Source] |
| SWI | [Findings] | [%] | [%] | [Source] |
| MRA | [Findings] | [%] | [%] | [Source] |

[FIGURE: mri_typical_all_sequences]

#### CT Protocol

| Protocol | Findings | When Preferred | Source |
|:---------|:---------|:---------------|:-------|
| Non-contrast | [Findings] | [Indication] | [Source] |
| CTA | [Findings] | [Indication] | [Source] |

[FIGURE: ct_typical]

#### Other Imaging

[Angiography, PET, etc. as applicable]

[FIGURE: additional_imaging]

### Diagnostic Criteria

> **📕 DIAGNOSTIC CRITERIA**
>
> **Definite [Condition]**:
> - [ ] [Criterion 1]
> - [ ] [Criterion 2]
>
> **Source**: [Society, Year]

### Differential Diagnosis

> **📊 DIFFERENTIAL**
>
> | Condition | Distinguisher | Test | Source |
> |:----------|:--------------|:-----|:-------|
> | [Dx 1] | [Feature] | [Test] | [Source] |
>
> [FIGURE: differential_comparison]

---

## 1.8 Treatment Decision Framework

[FIGURE: treatment_decision_algorithm]

### Observation Criteria

**Observe if ALL**:
- [ ] [Criterion 1]
- [ ] [Criterion 2]

**Surveillance Protocol**:
| Interval | Assessment | Imaging | Source |
|:---------|:-----------|:--------|:-------|
| [Time] | [Evaluation] | [Modality] | [Source] |

### Treatment Indications

> **📋 GUIDELINE** — Level [I/II/III]
> **Treat if**:
> - [Indication 1]
> - [Indication 2]
> **Source**: [Society, Year]

### Treatment Selection Matrix

| Scenario | Preferred | Alternative | Avoid | Source |
|:---------|:----------|:------------|:------|:-------|
| [Scenario] | [Treatment] | [Option] | [Contraindicated] | [Source] |

[FIGURE: treatment_selection_matrix]

---

## 1.9 Medical Management

[FIGURE: medical_management_overview]

### First-Line Pharmacotherapy

> **💊 [PRIMARY DRUG]**
> - **Class**: [Category]
> - **Indication**: [When to use]
> - **Adult Dose**: [mg, frequency, duration]
> - **Pediatric**: [mg/kg/day, max]
> - **Renal**: [Adjustment]
> - **Hepatic**: [Adjustment]
> - **Monitoring**: [Labs/levels]
> - **Interactions**: [Key interactions]
> - **Black Box**: [If applicable]
> **Source**: [Reference]

### Second-Line and Adjunctive

[Same format for additional drugs]

### Medical Management Algorithm

```
First-line: [Drug A]
  → Inadequate response (2-4 weeks):
    → Add [Drug B] OR switch to [Drug C]
If refractory:
  → [Drug D] + [Drug E]
  → Consider surgical evaluation
```

---

# PART II: SURGICAL ANATOMY

*Scaled to {{ANATOMY_DEPTH}}*

---

## 2.1 Regional Overview

[FIGURE: regional_anatomy_3d]

### Anatomical Boundaries

| Boundary | Structure | Source |
|:---------|:----------|:-------|
| Superior | [Structure] | [Source] |
| Inferior | [Structure] | [Source] |
| Anterior | [Structure] | [Source] |
| Posterior | [Structure] | [Source] |
| Medial | [Structure] | [Source] |
| Lateral | [Structure] | [Source] |

[FIGURE: boundaries_3d]

---

## 2.2 Surface Landmarks

[FIGURE: surface_landmarks]

| Landmark | Definition | Surgical Use | Source |
|:---------|:-----------|:-------------|:-------|
| [Landmark] | [Description] | [Application] | [Source] |

> **📍 KEY LANDMARK**: [Name]
> **Definition**: [Description]
> **Identifies**: [Target structure]
> [FIGURE: landmark_detail]

---

## 2.3 Osseous Anatomy

[FIGURE: bone_overview]

| Structure | Dimensions | Surgical Note | Source |
|:----------|:-----------|:--------------|:-------|
| [Bone/Feature] | [Mean ± SD mm (range; n)] | [Relevance] | [Source] |

[FIGURE: bone_measurements]

### Foramina and Canals

| Foramen | Dimensions | Contents | Source |
|:--------|:-----------|:---------|:-------|
| [Foramen] | [mm] | [Structures] | [Source] |

[FIGURE: foramina_detail]

---

## 2.4 Vascular Anatomy

[FIGURE: vascular_overview]

### Arterial Supply

| Artery | Origin | Diameter | At Risk During | Source |
|:-------|:-------|:---------|:---------------|:-------|
| [Artery] | [Parent] | [Mean ± SD mm] | [Step] | [Source] |

[FIGURE: arterial_anatomy]

### Perforating Arteries

| Perforators | Number | Origin | Territory | Source |
|:------------|:-------|:-------|:----------|:-------|
| [Group] | [Mean ± SD (range; n)] | [Segment] | [Supply] | [Source] |

[FIGURE: perforators]

> **🔴 STRUCTURE AT RISK**: [Perforator Group]
> **Location**: [Position]
> **Consequence**: [Stroke location]
> **Protection**: [Technique]
> [FIGURE: perforator_protection]

### Venous Drainage

| Vein | Course | Sacrifice? | Source |
|:-----|:-------|:-----------|:-------|
| [Vein] | [Path] | [Safe/Unsafe] | [Source] |

[FIGURE: venous_anatomy]

---

## 2.5 Neural Structures

[FIGURE: neural_overview]

### Cranial Nerves at Risk

| CN | Course | At Risk During | Consequence | Source |
|:---|:-------|:---------------|:------------|:-------|
| [CN] | [Path] | [Step] | [Deficit] | [Source] |

[FIGURE: cranial_nerve_detail]

### Brain Parenchyma

[Eloquent cortex, white matter tracts relevant to procedure]

[FIGURE: parenchymal_relationships]

---

## 2.6 Surgical Corridors

[FIGURE: corridors_overview]

> **🚪 CORRIDOR**: [Name]
> **Entry**: [Surface point]
> **Trajectory**: [Direction]
> **Working Distance**: [mm]
> **Target Access**: [Structures]
> **At Risk**: [Structures along path]
> [FIGURE: corridor_detail]

---

## 2.7 Anatomical Triangles

[FIGURE: triangles_overview]

> **🔺 TRIANGLE**: [Name]
> **Boundaries**: [Three structures]
> **Dimensions**: [Base × Height mm]
> **Contents**: [Structures]
> **Surgical Use**: [Access]
> [FIGURE: triangle_detail]

---

## 2.8 Safe Entry Zones

[FIGURE: safe_zones]

| Zone | Location | Dimensions | Avoids | Source |
|:-----|:---------|:-----------|:-------|:-------|
| [Zone] | [Position] | [mm × mm] | [Structures] | [Source] |

[FIGURE: safe_zone_detail]

---

## 2.9 Anatomical Variations

[FIGURE: variations_overview]

| Structure | Variation | Prevalence | 95% CI | n | Impact | Source |
|:----------|:----------|:-----------|:-------|:--|:-------|:-------|
| [Structure] | [Variant] | [%] | [CI] | [n] | [Surgical] | [Source] |

> **🔀 CRITICAL VARIATION**: [Name]
> **Prevalence**: [% (95% CI; n)]
> **Recognition**: [How to identify]
> **Adaptation**: [Modified technique]
> [FIGURE: variation_detail]

---

# PART III: SURGICAL PROCEDURE

---

## 3.1 Operative Planning

[FIGURE: surgical_planning_overview]

### Indications (Summary)

- [Indication 1]
- [Indication 2]

### Contraindications

- Absolute: [List]
- Relative: [List]

### Preoperative Checklist

- [ ] Imaging reviewed with measurements
- [ ] Consent with specific risks
- [ ] Blood products available
- [ ] Equipment confirmed
- [ ] Monitoring team notified

[FIGURE: preop_imaging_annotated]

---

## 3.2 Operative Setup

> **🏥 BOOKING THE CASE**
> - **Estimated Duration**: [Hours]
> - **Position**: [Specific position]
> - **Head Fixation**: [Method]
> - **Table**: [Configuration]
> - **Microscope**: [Yes/No, settings]
> - **Endoscope**: [If applicable]
> - **Navigation**: [Required/optional]
> - **Neuromonitoring**: [Modalities]
> - **Blood Products**: [Type & screen/crossmatch]
> - **Special Equipment**: [List]
> [FIGURE: complete_or_setup]

### Patient Positioning

[FIGURE: positioning_overview]

**Position**: [Detailed description]

**Head Position**:
- Rotation: [degrees]
- Flexion/Extension: [degrees]
- Lateral tilt: [degrees]

[FIGURE: positioning_detail]
[FIGURE: head_position]

> **⚠️ HAZARD**: Positioning Injuries
> **Prevention**: [Padding, eye protection, arm positioning]
> [FIGURE: positioning_safety]

---

## 3.3 Step-by-Step Technique

### Phase 1: Exposure

---

#### Step 1: [Step Name]

[FIGURE: step_1_setup]

**Objective**: [Goal]

**Technique**:
1. [Substep 1]
2. [Substep 2]
3. [Substep 3]

[FIGURE: step_1_execution]
[FIGURE: step_1_complete]

**Endpoint**: [How to know complete]

> **💡 PEARL**: [Technical tip]
> [FIGURE: step_1_pearl]

---

#### Step 2: [Step Name]

[Same detailed format with figures...]

---

[Continue for all steps, organized by Phase]

### Phase 2: Dural Opening

[Steps with same format...]

### Phase 3: Intradural Work

[Steps with same format...]

### Phase 4: Closure

[Steps with same format...]

---

## 3.4 Intraoperative Decision Points

> **🔀 DECISION**: [Situation]
> ```
> IF [finding A]:
>   → [Technique A]
>   [FIGURE: decision_a]
> IF [finding B]:
>   → [Technique B]
>   [FIGURE: decision_b]
> IF unable to proceed:
>   → [Bailout]
> ```

---

## 3.5 Neuromonitoring

[FIGURE: monitoring_setup]

| Modality | Indication | Warning | Response | Source |
|:---------|:-----------|:--------|:---------|:-------|
| [SSEP] | [When] | [Criteria] | [Action] | [Source] |
| [MEP] | [When] | [Criteria] | [Action] | [Source] |

---

# PART IV: POSTOPERATIVE MANAGEMENT

---

## 4.1 Immediate Postoperative Care

[FIGURE: postop_protocol]

| Parameter | Protocol | Source |
|:----------|:---------|:-------|
| Position | [Specification] | [Source] |
| BP Target | [Range] | [Source] |
| Imaging | [When, what] | [Source] |
| Neuro Checks | [Frequency] | [Source] |

[FIGURE: postop_imaging_normal]

---

## 4.2 Hospital Course

### Expected Recovery Timeline

| POD | Expected Status | Red Flags | Source |
|:----|:----------------|:----------|:-------|
| 0-1 | [Expected] | [Concerning signs] | [Source] |
| 2-3 | [Expected] | [Concerning signs] | [Source] |

### Discharge Criteria

- [ ] [Criterion 1]
- [ ] [Criterion 2]

---

## 4.3 Long-Term Follow-Up

| Time | Evaluation | Imaging | Source |
|:-----|:-----------|:--------|:-------|
| [Interval] | [Assessment] | [Modality] | [Source] |

[FIGURE: followup_imaging_timeline]

---

# PART V: OUTCOMES

---

## 5.1 Primary Outcomes

[FIGURE: outcomes_overview]

| Outcome | Definition | Rate | 95% CI | Follow-up | Source |
|:--------|:-----------|:-----|:-------|:----------|:-------|
| [Success] | [Definition] | [%] | [CI] | [Duration] | [Source] |

[FIGURE: outcome_comparison]

---

## 5.2 Complications

[FIGURE: complications_overview]

### Complication Rates

| Complication | Rate | Prevention | Management | Source |
|:-------------|:-----|:-----------|:-----------|:-------|
| [Complication] | [%] | [Technique] | [Treatment] | [Source] |

[FIGURE: complication_recognition]

> **⚠️ CRITICAL COMPLICATION**: [Name]
> **Recognition**: [Signs]
> **Immediate Action**: [Steps]
> **Source**: [Reference]

---

## 5.3 Survival Analysis

[FIGURE: kaplan_meier]

| Metric | Value | 95% CI | Source |
|:-------|:------|:-------|:-------|
| 1-year | [%] | [CI] | [Source] |
| 5-year | [%] | [CI] | [Source] |

---

## 5.4 Functional Outcomes

| Scale | Pre | Post | Change | Source |
|:------|:----|:-----|:-------|:-------|
| [Scale] | [Mean ± SD] | [Mean ± SD] | [p-value] | [Source] |

[FIGURE: functional_outcomes]

---

## 5.5 Prognostic Factors

| Factor | HR/OR | 95% CI | p-value | Source |
|:-------|:------|:-------|:--------|:-------|
| [Factor] | [Value] | [CI] | [p] | [Source] |

[FIGURE: prognostic_forest_plot]

---

# PART VI: CONTROVERSIES & EMERGING CONCEPTS

---

## 6.1 Current Controversies

### Controversy 1: [Topic]

**The Question**: [Frame the debate]

| Position | Evidence | Class | Source |
|:---------|:---------|:------|:-------|
| Pro-A | [Data] | [I/II/III] | [Source] |
| Pro-B | [Data] | [I/II/III] | [Source] |

**Current Status**: [Where consensus stands]

[FIGURE: controversy_data]

---

## 6.2 Emerging Technologies

| Technology | Stage | Promise | Limitations | Source |
|:-----------|:------|:--------|:------------|:-------|
| [Tech] | [Development] | [Potential] | [Challenges] | [Source] |

---

## 6.3 Ongoing Clinical Trials

| Trial | Question | Design | Status | Source |
|:------|:---------|:-------|:-------|:-------|
| [NCT] | [Primary question] | [RCT/etc.] | [Phase] | [Source] |

---

# PART VII: REFERENCE TABLES

---

## 7.1 All Measurements

| Parameter | Mean | SD | Range | n | Source |
|:----------|:-----|:---|:------|:--|:-------|
| [All quantitative data] | | | | | |

---

## 7.2 All Variations

| Structure | Variation | Prevalence | 95% CI | n | Source |
|:----------|:----------|:-----------|:-------|:--|:-------|
| [All variations] | | | | | |

---

## 7.3 All Outcomes

| Outcome | Rate | 95% CI | Definition | Follow-up | Source |
|:--------|:-----|:-------|:-----------|:----------|:-------|
| [All outcome data] | | | | | |

---

# PART VIII: PEARLS & PITFALLS

---

## Clinical Pearls

> **💡 PEARL 1**: [Topic]
> [Insight]
> **Source**: [Reference]

[5-10 pearls covering diagnosis, treatment selection, surgical technique]

---

## Technical Pearls

> **💡 PEARL**: [Topic]
> [Surgical insight]
> [FIGURE: pearl_illustration]
> **Source**: [Reference]

[5-10 procedural pearls]

---

## Common Pitfalls

| Category | Pitfall | Consequence | Prevention | Source |
|:---------|:--------|:------------|:-----------|:-------|
| Diagnostic | [Mistake] | [Result] | [Avoid] | [Source] |
| Treatment | [Mistake] | [Result] | [Avoid] | [Source] |
| Surgical | [Mistake] | [Result] | [Avoid] | [Source] |

[FIGURE: pitfall_examples]

---

# PART IX: INFORMATION GAPS

**MANDATORY SECTION**

*Not addressed in provided references*:

### Epidemiology Gaps
- [Missing data]

### Pathophysiology Gaps
- [Missing data]

### Treatment Gaps
- [Missing data]

### Surgical Gaps
- [Missing data]

### Outcome Gaps
- [Missing data]

---

## Figure Index

| Figure ID | Description | Part/Section | Source |
|:----------|:------------|:-------------|:-------|
| [Comprehensive figure catalog] | | | |

---

## References

[Complete source list organized by Part]

---

# SYNTHESIS PROCESS

## Phase 1: Part Allocation
Distribute content by {{CONTENT_EMPHASIS}}:
- DISORDER: 50% Part I, 25% Part II, 25% Part III
- SURGICAL: 25% Part I, 25% Part II, 50% Part III
- BALANCED: 33% each

## Phase 2: Figure Integration
Map figures across all Parts ensuring cross-reference

## Phase 3: Decision Algorithm Construction
Build integrated diagnostic → treatment → surgical decision tree

## Phase 4: Outcome Integration
Ensure Part V reflects both disease and surgical outcomes

## Phase 5: Completeness Check
- [ ] All 9 Parts present
- [ ] Figure density adequate (1/150 words)
- [ ] All Greenberg boxes placed
- [ ] Information gaps documented
```

---

## Quality Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Total figures | 120-180 | 80 |
| Figures per 1000 words | 6-7 | 5 |
| Greenberg boxes | 25-40 | 20 |
| Decision algorithms | 3-5 | 2 |
| Evidence-graded recommendations | 100% | 80% |
| All 9 Parts complete | Yes | 8/9 |
