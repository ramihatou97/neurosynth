# Procedural Synthesis Prompt v3.0 — Textbook Excellence Edition

> **Version**: 3.0  
> **Purpose**: Operative technique chapters matching Schmidek/Rhoton/Operative Neurosurgery quality  
> **Architecture**: Schmidek (systematic structure) + Rhoton (microsurgical anatomy) + Connolly (decision-making) + Quinones-Hinojosa (technical pearls)  
> **Figure Target**: 1 per 100-150 words; 80-120 figures per chapter  
> **Key Enhancements**: Two-surgeon perspective, bailout procedures, complication avoidance matrix, step endpoints

---

## System Context

Pipeline integration for NeuroSynth FigureIntegrationPipeline:
1. Sources include "Available Figures" catalogs (FIGURE_ID, Type, Caption)
2. Place `[FIGURE: ID]` tags at EVERY surgical step, anatomical structure, and decision point
3. Pipeline handles: placeholder resolution, procedural step correlation, temporal sequencing

---

## Variables

| Variable | Description | Options |
|----------|-------------|---------|
| `{{REFERENCE_MATERIALS}}` | Source documents with Available Figures | Required |
| `{{PROCEDURE}}` | Surgical procedure to synthesize | Required |
| `{{ANATOMY_DEPTH}}` | Anatomical detail level | MINIMAL / STANDARD / COMPREHENSIVE |

---

## Prompt

```
You are synthesizing an operative technique chapter matching the quality standards of:

**Schmidek & Sweet Operative Neurosurgical Techniques** (6th Edition):
- Systematic chapter structure: Indications → Preop → Technique → Complications → Results
- Each step explicitly numbered with clear ENDPOINTS (how you know it's done)
- Equipment specifications with sizes and model recommendations
- Pearls and Pitfalls boxes throughout
- Alternative techniques for common variations

**Rhoton's Cranial Anatomy & Surgical Approaches**:
- All measurements in Mean ± SD (range; n) format
- Layer-by-layer dissection sequence (surface → deep)
- Multiple viewing angles for complex anatomy
- Safe entry zones with precise boundaries (mm)
- Anatomical variations with prevalence percentages

**Operative Neurosurgery** (Connolly & McKhann):
- Two-surgeon perspective where applicable
- Decision points explicitly marked with IF/THEN logic
- Bailout procedures when things go wrong
- Intraoperative problem-solving algorithms
- Complication avoidance strategies

**Quinones-Hinojosa Operative Neurosurgical Techniques**:
- Technical pearls from master surgeons
- Common mistakes and how to avoid them
- Instrument positioning details
- Tissue handling principles

# Reference Materials

<reference_materials>
{{REFERENCE_MATERIALS}}
</reference_materials>

# Target Procedure

<procedure>
{{PROCEDURE}}
</procedure>

<anatomy_depth>
{{ANATOMY_DEPTH}}
</anatomy_depth>

**ANATOMY_DEPTH Options**:
- **MINIMAL** (~200 words): Context + critical structures only
- **STANDARD** (~800 words): Regional overview + landmarks + neurovascular tables + key distances
- **COMPREHENSIVE** (~2,500 words): Full Rhoton-style 12-subsection anatomical documentation

---

# FIGURE INTEGRATION PROTOCOL

## Density Requirements
- **Minimum**: 1 figure per 150 words
- **Target**: 80-120 figures total
- **Every surgical step needs 2-4 figures**: Setup → Execution → Completion → Anatomy

## Mandatory Figure Triggers

Place `[FIGURE: ID]` when describing:
1. **Patient positioning** — Setup, fixation, final position
2. **Surface landmarks** — Incision planning
3. **Each surgical step** — Setup, execution, completion views
4. **Anatomical structures encountered** — As they appear
5. **Instrument positioning** — Specific tool in use
6. **Decision points** — What you see that determines next action
7. **Anatomical variations** — Recognition images
8. **Complications** — What they look like, how to manage
9. **Closure** — Each layer separately
10. **Critical anatomy at risk** — Multiple angles

## Step Figure Template

Every major step requires this sequence:
```
[FIGURE: step_N_setup]      — Preparation/positioning for the step
[FIGURE: step_N_execution]  — Active surgical maneuver
[FIGURE: step_N_complete]   — Verification view before proceeding
[FIGURE: step_N_anatomy]    — Relevant anatomy visible at this point
```

## Figure Format
`[FIGURE: exact_figure_id_from_catalog]`

---

# CORE PRINCIPLES

## 1. Schmidek Structure
Every chapter follows this sequence:
1. **Indications/Contraindications**
2. **Preoperative Planning**
3. **Positioning & Setup**
4. **Surgical Anatomy** (scaled to {{ANATOMY_DEPTH}})
5. **Step-by-Step Technique** (numbered, with endpoints)
6. **Complications** (prevention, recognition, management)
7. **Results/Outcomes**

## 2. Rhoton Anatomical Standards
- All measurements: **Mean ± SD (range; n)**
- Terminologia Anatomica as primary terms
- Layer-by-layer: superficial → deep progression
- Multiple angles for 3D relationships
- Variations with **prevalence % (95% CI; n)**

## 3. Step Documentation Standards

Each step MUST include:
- **Step Number & Title**
- **Objective**: What this step accomplishes
- **Landmarks/Orientation**: How to know you're in the right place
- **Technique**: How to perform (with instrument specifics)
- **ENDPOINT**: How you know this step is complete
- **Anatomy at This Step**: Structures visible/at risk
- **Figures**: 2-4 per step

## 4. Mandatory Callout Boxes

### ⚠️ HAZARD WARNING
> **⚠️ HAZARD**: [Specific Risk]
> **When**: [At what step/situation]
> **Recognition**: [How to identify the problem]
> **Prevention**: [Technique to avoid]
> **Bailout**: [What to do if it occurs]
> [FIGURE: hazard_illustration]

### 🔴 CRITICAL ANATOMY AT RISK
> **🔴 STRUCTURE**: [Structure Name]
> **Location**: [Where in surgical field]
> **Step(s) at Risk**: [Which steps]
> **Consequence if Injured**: [Deficit/outcome]
> **Protection Strategy**: [Specific technique]
> [FIGURE: anatomy_at_risk]

### 🔀 DECISION POINT
> **🔀 DECISION POINT**: [Situation]
> ```
> IF [finding/condition A]:
>   → [Technique modification A]
>   [FIGURE: variation_a]
> IF [finding/condition B]:
>   → [Technique modification B]
>   [FIGURE: variation_b]
> IF unable to proceed safely:
>   → [Bailout option]
> ```

### 🔀 ANATOMICAL VARIATION
> **🔀 VARIATION**: [Variation Name]
> **Prevalence**: [% (95% CI; n)]
> **Recognition**: [How to identify intraoperatively]
> **Adaptation**: [Modified technique]
> [FIGURE: variation_recognition]
> **Source**: [Reference]

### 💡 TECHNICAL PEARL
> **💡 PEARL**: [Topic]
> [Expert insight that improves outcomes or efficiency]
> [FIGURE: pearl_demonstration]
> **Source**: [Reference]

### 🚫 PITFALL
> **🚫 PITFALL**: [Common Mistake]
> **Consequence**: [What goes wrong]
> **Recognition**: [How to know you've done it]
> **Avoidance**: [How to prevent]
> **Recovery**: [How to fix if it happens]
> [FIGURE: pitfall_illustration]

### 🏥 BOOKING THE CASE
> **🏥 OPERATIVE REQUIREMENTS**
> | Parameter | Specification |
> |-----------|---------------|
> | **Duration** | [X-X hours] |
> | **Position** | [Specific position] |
> | **Head Fixation** | [Pins: configuration / Horseshoe / None] |
> | **Table** | [Type, rotation capability] |
> | **Microscope** | [Required/Optional; settings] |
> | **Endoscope** | [If applicable; angle] |
> | **Navigation** | [Required/Optional; type] |
> | **Neuromonitoring** | [SSEP/MEP/EMG/D-wave/etc.] |
> | **Blood Products** | [Type & screen / Crossmatch X units] |
> | **Cell Saver** | [Required/Optional] |
> | **Special Equipment** | [List specific items] |
> | **Implants** | [If applicable] |
> [FIGURE: or_setup]

### 👥 TWO-SURGEON TECHNIQUE
> **👥 ASSISTANT ROLE** (This Step)
> **Primary surgeon**: [What they're doing]
> **Assistant**: [What they should be doing]
> **Communication**: [Key callouts]
> [FIGURE: two_surgeon_view]

### 📊 COMPLICATION AVOIDANCE MATRIX
> **📊 PREVENTING [Complication]**
> | Step | Risk | Prevention | Recognition | Recovery |
> |------|------|------------|-------------|----------|
> | [Step #] | [Specific risk] | [Technique] | [Signs] | [Action] |

---

# CHAPTER SCHEMA

---

# [PROCEDURE NAME]

## Executive Summary

[FIGURE: procedure_overview_schematic]

**Procedure Definition**: [One sentence — what this procedure accomplishes]

**Primary Indications**: [Brief list]

**Key Statistics**:
| Parameter | Value | Source |
|:----------|:------|:-------|
| Duration | [Mean ± SD hours (range)] | [Source] |
| Blood Loss | [Mean ± SD mL (range)] | [Source] |
| Success Rate | [% (95% CI)] — define success | [Source] |
| Major Complication | [%] — define major | [Source] |
| Mortality | [%] | [Source] |

---

## Quick Reference Card

### Rapid Facts

| Parameter | Value | Source |
|:----------|:------|:-------|
| **Position** | [Position] | [Source] |
| **Incision** | [Type, length] | [Source] |
| **Key Landmark** | [Primary landmark] | [Source] |
| **Critical Structure** | [Main structure at risk] | [Source] |
| **Duration** | [Hours] | [Source] |
| **Blood Loss** | [mL] | [Source] |

> **🔴 CRITICAL ANATOMY AT RISK**
> - **[Structure 1]**: [Location] → [Injury consequence]
> - **[Structure 2]**: [Location] → [Injury consequence]
> - **[Structure 3]**: [Location] → [Injury consequence]
> [FIGURE: critical_anatomy_overview]

> **💡 KEY PEARL**
> [Single most important technical insight for this procedure]
> **Source**: [Reference]

---

## Indications

[FIGURE: indication_algorithm]

### Absolute Indications
- [Indication 1]
- [Indication 2]

### Relative Indications
- [Indication]: [Context when appropriate]

### Patient Selection Factors

| Factor | Favorable | Unfavorable | Source |
|:-------|:----------|:------------|:-------|
| [Factor] | [Good prognostic feature] | [Poor prognostic feature] | [Source] |

> **📋 GUIDELINE** — Level [I/II/III]
> **Surgical Indication**: [Specific recommendation]
> **Source**: [Society, Year]

---

## Contraindications

### Absolute
- [Contraindication 1]: [Rationale]
- [Contraindication 2]: [Rationale]

### Relative
- [Contraindication]: [Risk-benefit consideration]

---

## Preoperative Planning

[FIGURE: preop_workup_algorithm]

### Required Imaging

| Study | Key Features to Assess | Source |
|:------|:-----------------------|:-------|
| MRI | [Specific sequences; what to measure] | [Source] |
| CT | [Windows; specific measurements] | [Source] |
| Angiography | [If applicable; what to look for] | [Source] |

[FIGURE: preop_mri_annotated]
[FIGURE: preop_ct_annotated]

### Surgical Planning Measurements

| Measurement | Value | Significance | Source |
|:------------|:------|:-------------|:-------|
| [Distance/angle] | [From imaging] | [How it affects approach] | [Source] |

### Preoperative Checklist

- [ ] Imaging reviewed with key measurements documented
- [ ] Surgical plan documented (approach, extent, goals)
- [ ] Informed consent with specific risks discussed
- [ ] Blood products available: [Type]
- [ ] Equipment confirmed available: [List]
- [ ] Neuromonitoring team notified: [Modalities]
- [ ] [Procedure-specific items]

### Approach Selection

> **🔀 DECISION POINT**: Approach Selection
> ```
> IF [anatomy finding A]:
>   → [Approach 1] preferred because [rationale]
> IF [anatomy finding B]:
>   → [Approach 2] preferred because [rationale]
> IF [unfavorable anatomy C]:
>   → Consider [alternative] or staged approach
> ```

[FIGURE: approach_selection_algorithm]

---

## Instrumentation

[FIGURE: instrument_tray_complete]

### Standard Instruments

| Category | Instrument | Size/Specifications | Source |
|:---------|:-----------|:--------------------|:-------|
| **Retractors** | [Name] | [Size] | [Source] |
| **Dissectors** | [Name] | [Type, size] | [Source] |
| **Scissors** | [Name] | [Type] | [Source] |
| **Forceps** | [Name] | [Type, tip] | [Source] |
| **Suction** | [Type] | [French size] | [Source] |
| **Bipolar** | [Type] | [Tip size, settings] | [Source] |
| **Drill** | [Type] | [Bit sizes] | [Source] |

### Specialized Equipment

| Equipment | Purpose | Specifications | Source |
|:----------|:--------|:---------------|:-------|
| [Equipment] | [Why needed] | [Settings/details] | [Source] |

[FIGURE: specialized_instruments_detail]

> **🏥 BOOKING THE CASE**
> | Parameter | Specification |
> |-----------|---------------|
> | **Duration** | [X-X hours] |
> | **Position** | [Position] |
> | **Head Fixation** | [Method, pin sites] |
> | **Microscope** | [Required/Optional] |
> | **Navigation** | [Required/Optional] |
> | **Neuromonitoring** | [Modalities] |
> | **Blood Products** | [Requirements] |
> | **Special Equipment** | [List] |
> [FIGURE: complete_or_setup]

---

## Patient Positioning

[FIGURE: positioning_overview]

### Position Setup

**Position**: [Detailed description]

**Setup Sequence**:
1. [Step 1 with specifics]
2. [Step 2 with specifics]
3. [Step 3 with specifics]

[FIGURE: positioning_sequence]

### Head Fixation

**Pin Configuration**:
- Single pin: [Anatomical location, rationale]
- Double pins: [Anatomical location, rationale]
- Avoid: [Where NOT to place, why]

[FIGURE: pin_placement_detail]

**Head Position Parameters**:
| Parameter | Specification | Rationale | Source |
|:----------|:--------------|:----------|:-------|
| Rotation | [X° from midline] | [Why this angle] | [Source] |
| Flexion/Extension | [X°] | [Why this angle] | [Source] |
| Lateral Tilt | [X°] | [Why this angle] | [Source] |
| Vertex Position | [Up/down/toward surgeon] | [Why] | [Source] |
| Height | [Relative to surgeon] | [Ergonomics] | [Source] |

[FIGURE: head_position_angles]

### Final Position Verification

**Checklist before draping**:
- [ ] Eyes protected and not compressed
- [ ] All pressure points padded
- [ ] Arms secured, no stretch on brachial plexus
- [ ] Head position verified with [navigation/fluoro]
- [ ] IV access and monitoring accessible
- [ ] Surgeon can operate ergonomically

[FIGURE: final_position_verification]

> **⚠️ HAZARD**: Positioning Injuries
> **Risks**: [Pressure injuries, nerve compression, venous congestion, VAE]
> **Prevention**:
> - Eye protection: [Method]
> - Pressure points: [Where to pad]
> - Arms: [Position, padding]
> - Head: [Avoid excessive rotation/flexion]
> **Source**: [Reference]
> [FIGURE: positioning_hazards]

---

## Surgical Anatomy

*Scaled to {{ANATOMY_DEPTH}}*

---

### MINIMAL ANATOMY (~200 words)

[FIGURE: anatomy_overview]

**Regional Context**:
[Brief paragraph on relevant regional anatomy for this approach]

**Critical Structures**:

| Structure | Location in Surgical Field | Surgical Significance | Source |
|:----------|:---------------------------|:----------------------|:-------|
| [Structure 1] | [Where encountered] | [Why it matters, what happens if injured] | [Source] |
| [Structure 2] | [Where encountered] | [Why it matters] | [Source] |
| [Structure 3] | [Where encountered] | [Why it matters] | [Source] |

[FIGURE: critical_structures_labeled]

---

### STANDARD ANATOMY (~800 words)

[FIGURE: regional_anatomy_overview]

#### Surface Landmarks

| Landmark | Definition | Relationship to Target | Source |
|:---------|:-----------|:-----------------------|:-------|
| [Landmark 1] | [Description] | [Distance/direction to key structure] | [Source] |
| [Landmark 2] | [Description] | [Distance/direction to key structure] | [Source] |

[FIGURE: surface_landmarks]

#### Osseous Anatomy

| Structure | Dimensions | Surgical Relevance | Source |
|:----------|:-----------|:-------------------|:-------|
| [Bone feature] | [Mean ± SD mm (range; n)] | [Drilling/exposure consideration] | [Source] |

[FIGURE: bone_anatomy]

#### Neurovascular Anatomy

**Arterial**:

| Artery | Origin | Course | Diameter | At-Risk Step | Source |
|:-------|:-------|:-------|:---------|:-------------|:-------|
| [Artery] | [Parent] | [Path] | [Mean ± SD mm] | [Step #] | [Source] |

[FIGURE: arterial_anatomy]

**Venous**:

| Vein | Course | Drains To | At-Risk Step | Source |
|:-----|:-------|:----------|:-------------|:-------|
| [Vein] | [Path] | [Drainage] | [Step #] | [Source] |

[FIGURE: venous_anatomy]

**Neural**:

| Nerve | Course | Function | At-Risk Step | Source |
|:------|:-------|:---------|:-------------|:-------|
| [Nerve] | [Path] | [Motor/sensory function] | [Step #] | [Source] |

[FIGURE: neural_anatomy]

#### Key Measurements

| Parameter | Value | Clinical Significance | Source |
|:----------|:------|:----------------------|:-------|
| [Distance A to B] | [Mean ± SD mm (range; n)] | [How it guides surgery] | [Source] |

[FIGURE: anatomical_measurements]

#### Anatomical Variations

| Variation | Prevalence | Recognition | Surgical Adaptation | Source |
|:----------|:-----------|:------------|:--------------------|:-------|
| [Variant] | [% (95% CI; n)] | [How to identify] | [What to do differently] | [Source] |

[FIGURE: anatomical_variations]

---

### COMPREHENSIVE ANATOMY (~2,500 words)

*Full Rhoton-style 12-subsection anatomical documentation*

[See Master_Neuroanatomy_Synthesis for complete template]

#### 1. Regional Overview and Boundaries
#### 2. Surface Landmarks and Craniometric Points  
#### 3. Osseous Anatomy
#### 4. Meningeal Layers
#### 5. Cisternal Anatomy
#### 6. Arterial Anatomy (with perforators)
#### 7. Venous Anatomy
#### 8. Neural Anatomy
#### 9. Surgical Corridors
#### 10. Safe Entry Zones
#### 11. Anatomical Variations
#### 12. Imaging Correlation

[Each with figures, measurements, and tables per Rhoton standards]

---

## Step-by-Step Surgical Technique

### Phase 1: Exposure

---

#### Step 1: Skin Incision

[FIGURE: step_1_planning]

**Objective**: Create access for [craniotomy/exposure]

**Landmarks**:
- Start: [Anatomical point]
- End: [Anatomical point]
- Length: [X cm]
- Shape: [Linear/curvilinear/etc.]

**Technique**:
1. Mark incision with [marking pen/skin scribe]
2. Infiltrate with [lidocaine 1% with 1:100,000 epinephrine], [X mL], wait [X minutes]
3. Incise skin with [#10 or #15 blade] to [depth]
4. [Additional details]

[FIGURE: step_1_marking]
[FIGURE: step_1_incision]

**ENDPOINT**: [How you know this step is complete — e.g., "Full-thickness skin incision with visible galea throughout"]

> **💡 PEARL**: Scalp Hemostasis
> [Specific technique for this incision]
> **Source**: [Reference]

---

#### Step 2: Soft Tissue Dissection

[FIGURE: step_2_overview]

**Objective**: [What this accomplishes]

**Technique**:
1. [Substep with specifics]
2. [Substep with specifics]
3. [Substep with specifics]

[FIGURE: step_2_layer_1]
[FIGURE: step_2_layer_2]

**Anatomy at This Step**:

| Structure | Location | Significance | Source |
|:----------|:---------|:-------------|:-------|
| [Structure] | [Where visible] | [Risk/importance] | [Source] |

[FIGURE: step_2_anatomy]

**ENDPOINT**: [Specific verification]

> **🔴 STRUCTURE AT RISK**: [Structure]
> **Location**: [Where in field]
> **Consequence**: [If injured]
> **Protection**: [Technique to avoid]
> [FIGURE: step_2_structure_at_risk]

> **👥 ASSISTANT ROLE**
> Maintain retraction on [structure]
> Provide hemostasis with [method]
> [FIGURE: step_2_two_surgeon]

---

#### Step 3: Bone Exposure

[FIGURE: step_3_overview]

**Objective**: [Goal]

**Technique**:
1. [Detailed substep]
2. [Detailed substep]

[FIGURE: step_3_execution]

**ENDPOINT**: [Verification]

---

#### Step 4: Craniotomy/Bone Work

[FIGURE: step_4_overview]

**Burr Holes**:

| Hole # | Location | Purpose | Source |
|:-------|:---------|:--------|:-------|
| 1 | [Precise anatomical location] | [Why here] | [Source] |
| 2 | [Precise anatomical location] | [Why here] | [Source] |

[FIGURE: burr_hole_placement]

**Craniotomy Technique**:
- Dimensions: [X cm × Y cm]
- Boundaries: [Anatomical limits]
- Craniotome: [Type, settings]
- Bone flap: [Free/pedicled]

[FIGURE: craniotomy_execution]
[FIGURE: craniotomy_complete]

**ENDPOINT**: [Verification — e.g., "Bone flap elevated, dura intact, margins expose [structures]"]

> **⚠️ HAZARD**: Dural/Venous Sinus Injury
> **Recognition**: [What you see]
> **Prevention**: [Technique — e.g., stay in epidural plane]
> **Bailout**: [What to do — e.g., repair technique, hemostatic agents]
> [FIGURE: craniotomy_hazard_management]

> **🔀 DECISION POINT**: Adherent Dura
> ```
> IF dura adherent to bone:
>   → Dissect with #4 Penfield, staying in epidural plane
>   → Consider leaving inner table and drilling away
>   [FIGURE: adherent_dura_technique]
> IF sinus encountered:
>   → Immediately pack with [hemostatic agent]
>   → Control with [specific technique]
>   [FIGURE: sinus_repair_technique]
> ```

---

### Phase 2: Dural Opening

---

#### Step 5: Dural Incision

[FIGURE: step_5_overview]

**Objective**: Expose intradural contents while preserving [cortical veins/other structures]

**Dural Opening Pattern**: [C-shaped/cruciate/linear/other]

**Technique**:
1. Tack-up sutures at [locations] with [4-0 Nurolon/other]
2. Initial dural nick with [#11 blade/microscissors]
3. Open dura with [Metzenbaum scissors], extending [direction]
4. Preserve [specific veins/sinuses]

[FIGURE: dural_incision_pattern]
[FIGURE: dural_tack_up]
[FIGURE: dural_opening_complete]

**ENDPOINT**: [Verification — e.g., "Dura opened completely, cortical surface visible, bridging veins preserved"]

> **🔴 STRUCTURE AT RISK**: [Bridging Vein/Sinus]
> **Location**: [Where]
> **Consequence**: [Venous infarct, bleeding]
> **Protection**: [Open away from, coagulate before cutting, etc.]
> [FIGURE: venous_protection]

---

### Phase 3: Intradural Work

---

#### Step 6: Brain Relaxation & Initial Exposure

[FIGURE: step_6_overview]

**Objective**: Achieve adequate relaxation for safe retraction/dissection

**Techniques** (use in combination):
- CSF drainage: Open [cistern] → drain [X mL]
- Mannitol: [Dose], given [timing relative to opening]
- Hyperventilation: [Target PaCO2]
- Position optimization: [Head elevation, venous drainage]

[FIGURE: cisternal_opening]
[FIGURE: brain_relaxation_result]

**ENDPOINT**: [Brain relaxed, easily retractable without pressure]

> **💡 PEARL**: Brain Relaxation
> [Optimal sequencing: Mannitol 30 min before open, head up, CSF drainage last]
> **Source**: [Reference]

---

#### Step 7: Approach to Target

[FIGURE: step_7_overview]

**Corridor**: [Anatomical corridor used]

**Technique**:
1. Retract [structure] [direction] with [retractor type]
2. Open arachnoid over [cistern] sharply
3. Identify landmarks: [structure 1], [structure 2]
4. Dissect toward target following [anatomical plane]

[FIGURE: corridor_entry]
[FIGURE: arachnoid_dissection]
[FIGURE: target_approach]

**Anatomy at This Depth**:

| Structure | Relationship to Target | Source |
|:----------|:-----------------------|:-------|
| [Structure] | [Anterior/posterior/medial/lateral] | [Source] |

[FIGURE: deep_anatomy_relationships]

**ENDPOINT**: [Target visualized, surrounding structures identified]

> **🔀 DECISION POINT**: Anatomical Variant
> ```
> IF [variant A present — e.g., anomalous vessel]:
>   → [Modified approach: work around, sacrifice if small, etc.]
>   [FIGURE: variant_a_management]
> IF [standard anatomy]:
>   → Continue standard approach
> IF [unfavorable finding — e.g., unexpected tumor invasion]:
>   → Consider: abort vs. debulk vs. biopsy
>   → Communicate with team
> ```

---

#### Steps 8-N: [Procedure-Specific Core Steps]

[Continue same detailed format for each step...]

Each step includes:
- Objective
- Landmarks/Orientation
- Technique (numbered substeps)
- Figures (3-4 per step)
- ENDPOINT
- Relevant callout boxes

---

### Phase 4: Hemostasis & Inspection

---

#### Step N-2: Final Hemostasis

[FIGURE: hemostasis_overview]

**Technique**:
1. Irrigate thoroughly with [warm saline]
2. Inspect systematically: [specific areas to check]
3. Bipolar any oozing points at [low settings]
4. Apply [hemostatic agents] to [specific areas]
5. Perform Valsalva maneuver (anesthesia raises to [X cmH2O])
6. Wait [X minutes], reinspect

[FIGURE: hemostasis_technique]
[FIGURE: final_field_inspection]

**ENDPOINT**: [Dry field on Valsalva, no active bleeding after X minutes]

---

### Phase 5: Closure

---

#### Step N-1: Dural Closure

[FIGURE: dural_closure_overview]

**Closure Type**: [Primary/Graft — indicate when each used]

**Materials**:
| Material | Indication | Source |
|:---------|:-----------|:-------|
| [4-0 Nurolon] | [Primary closure] | [Source] |
| [Pericranium graft] | [If defect > X cm] | [Source] |
| [DuraGen/other] | [Onlay reinforcement] | [Source] |

**Technique**:
1. [Closure technique details]
2. [Test for watertightness: Valsalva to X cmH2O]

[FIGURE: dural_closure_technique]
[FIGURE: dural_closure_complete]

**ENDPOINT**: [Watertight closure on Valsalva]

> **💡 PEARL**: Watertight Closure
> [Specific technique tips — e.g., start at corners, continuous vs. interrupted, use of sealant]
> **Source**: [Reference]

---

#### Step N: Bone Replacement & Soft Tissue Closure

[FIGURE: layered_closure_overview]

**Bone Flap Fixation**:
| Method | Material | Specifications | Source |
|:-------|:---------|:---------------|:-------|
| [Plates/screws] | [Titanium] | [Size] | [Source] |

[FIGURE: bone_flap_fixation]

**Soft Tissue Closure by Layer**:

| Layer | Material | Technique | Source |
|:------|:---------|:----------|:-------|
| [Muscle/fascia] | [2-0 Vicryl] | [Interrupted/figure-8] | [Source] |
| [Galea] | [2-0 Vicryl] | [Interrupted/running] | [Source] |
| [Skin] | [Staples/3-0 nylon] | [Evert edges] | [Source] |

[FIGURE: muscle_closure]
[FIGURE: galea_closure]
[FIGURE: skin_closure]

**ENDPOINT**: [Skin edges everted, approximated without tension]

---

## Intraoperative Monitoring

[FIGURE: monitoring_setup]

### Modality Selection

| Modality | Indication | Structures Monitored | Source |
|:---------|:-----------|:---------------------|:-------|
| SSEP | [When used] | [Structures] | [Source] |
| MEP | [When used] | [Structures] | [Source] |
| EMG | [When used] | [Specific nerves] | [Source] |
| D-wave | [When used] | [Structures] | [Source] |
| BAEP | [When used] | [Structures] | [Source] |

### Alert Criteria & Response

| Change | Significance | Immediate Action | Source |
|:-------|:-------------|:-----------------|:-------|
| SSEP amplitude ↓ >50% | [Interpretation] | [Response protocol] | [Source] |
| MEP loss | [Interpretation] | [Response protocol] | [Source] |
| EMG train | [Interpretation] | [Response protocol] | [Source] |

[FIGURE: monitoring_waveforms_normal]
[FIGURE: monitoring_waveforms_alert]

> **⚠️ MONITORING ALERT PROTOCOL**
> ```
> IF [SSEP amplitude drops >50%]:
>   1. Announce to team, STOP dissection
>   2. Release any retractors
>   3. Irrigate with warm saline
>   4. Check: BP adequate? Temp ok? Anesthetic depth?
>   5. Raise MAP to [target]
>   6. Wait [X minutes] for recovery
> IF no recovery after [X minutes]:
>   → Consider terminating resection
>   → Document baseline and changes
> ```

---

## Postoperative Care

[FIGURE: postop_protocol]

### Immediate Postoperative (0-24 hours)

| Parameter | Target/Protocol | Source |
|:----------|:----------------|:-------|
| Position | [HOB elevation, positioning] | [Source] |
| BP | [SBP target range] | [Source] |
| Neuro checks | q[X] hours | [Source] |
| Imaging | [CT/MRI at X hours] | [Source] |
| DVT prophylaxis | Start at [X hours] post-op | [Source] |
| Steroids | [Taper protocol] | [Source] |
| Antibiotics | [Duration] | [Source] |
| Pain | [Protocol] | [Source] |

[FIGURE: postop_ct_expected]

### Disposition

| Condition | Disposition | Source |
|:----------|:------------|:-------|
| Uncomplicated | [Floor/step-down at X hours] | [Source] |
| High-risk | [ICU for X hours] | [Source] |

### Discharge Criteria

- [ ] Neurologically at baseline or improved
- [ ] Adequate oral intake
- [ ] Pain controlled with oral medications
- [ ] Wound clean and dry
- [ ] [Procedure-specific criteria]

### Follow-Up Schedule

| Time | Evaluation | Imaging | Source |
|:-----|:-----------|:--------|:-------|
| [2 weeks] | [Wound check] | [None] | [Source] |
| [6 weeks] | [Neuro exam] | [MRI] | [Source] |
| [3 months] | [Full evaluation] | [MRI] | [Source] |

---

## Complications

[FIGURE: complications_overview]

### Complication Prevention Matrix

> **📊 COMPLICATION AVOIDANCE**
>
> | Complication | Incidence | At-Risk Steps | Prevention Strategy | Source |
> |:-------------|:----------|:--------------|:--------------------|:-------|
> | [CSF leak] | [%] | [Steps X-Y] | [Watertight closure, sealants] | [Source] |
> | [Infection] | [%] | [All] | [Sterile technique, prophylaxis] | [Source] |
> | [Hematoma] | [%] | [Steps X-Y] | [Meticulous hemostasis] | [Source] |
> | [Neuro deficit] | [%] | [Steps X-Y] | [Monitoring, gentle technique] | [Source] |

### Recognition & Management

#### [Complication 1]: CSF Leak

**Incidence**: [%]

**Risk Factors**:
- [Factor 1]
- [Factor 2]

**Prevention**:
- [Technique 1]
- [Technique 2]

**Recognition**:
- Intraoperative: [Signs]
- Postoperative: [Signs]

**Management**:
```
IF recognized intraoperatively:
  → [Immediate repair technique]

IF recognized postoperatively:
  Mild (positional headache only):
    → Bedrest, hydration, caffeine
    → If no improvement in [X days] → lumbar drain
  Moderate (wound drainage):
    → Lumbar drain [X mL/hr for X days]
  Severe (meningitis risk):
    → Return to OR for wound exploration and repair
```

[FIGURE: csf_leak_recognition]
[FIGURE: csf_leak_repair]

[Repeat structure for each major complication...]

---

## Results

[FIGURE: outcomes_summary]

### Primary Outcomes

| Outcome | Definition | Rate | 95% CI | Source |
|:--------|:-----------|:-----|:-------|:-------|
| Success | [How defined] | [%] | [CI] | [Source] |
| Failure | [How defined] | [%] | [CI] | [Source] |

[FIGURE: outcome_graph]

### Outcomes by Subgroup

| Subgroup | Success Rate | p-value | Source |
|:---------|:-------------|:--------|:-------|
| [Subgroup 1] | [%] | [p] | [Source] |
| [Subgroup 2] | [%] | [p] | [Source] |

### Learning Curve

[If applicable: data on case volume and outcomes]

[FIGURE: learning_curve_graph]

---

## Technical Pearls Summary

> **💡 PEARL 1**: [Positioning]
> [Detailed insight]
> [FIGURE: pearl_1]
> **Source**: [Reference]

> **💡 PEARL 2**: [Exposure]
> [Detailed insight]
> [FIGURE: pearl_2]
> **Source**: [Reference]

> **💡 PEARL 3**: [Core Technique]
> [Detailed insight]
> [FIGURE: pearl_3]
> **Source**: [Reference]

> **💡 PEARL 4**: [Complication Avoidance]
> [Detailed insight]
> [FIGURE: pearl_4]
> **Source**: [Reference]

> **💡 PEARL 5**: [Closure]
> [Detailed insight]
> [FIGURE: pearl_5]
> **Source**: [Reference]

[5-10 pearls total, covering each phase]

---

## Common Pitfalls

| Pitfall | Step | Consequence | Avoidance | Recovery | Source |
|:--------|:-----|:------------|:----------|:---------|:-------|
| [Mistake 1] | [#] | [Result] | [Prevention] | [Fix] | [Source] |
| [Mistake 2] | [#] | [Result] | [Prevention] | [Fix] | [Source] |

[FIGURE: pitfall_examples]

---

## Alternative Techniques

### Variation 1: [Alternative Approach/Technique Name]

**When to Use**: [Specific indication for this variation]

**Key Differences**:
- [Difference 1]
- [Difference 2]

**Technique**: [Brief description]

[FIGURE: alternative_technique_1]

**Outcomes vs. Standard**: [If data available]

---

## Information Gaps

**MANDATORY SECTION**

*Not addressed in provided references*:

- **Technique**: [Missing details]
- **Anatomy**: [Missing measurements]
- **Outcomes**: [Missing data]
- **Complications**: [Missing data]

---

## Quantitative Reference Tables

### Surgical Parameters
| Parameter | Value | Source |
|:----------|:------|:-------|
| [All surgical specifications consolidated] | | |

### Anatomical Measurements  
| Structure | Measurement | Source |
|:----------|:------------|:-------|
| [All anatomical measurements consolidated] | | |

---

## Figure Index

| Figure ID | Description | Step/Section | Source |
|:----------|:------------|:-------------|:-------|
| [All figures with step assignments] | | | |

---

## References

[Complete source list]

---

# SYNTHESIS PROCESS

## Phase 1: Figure Inventory by Surgical Phase
Map all figures to specific steps and phases

## Phase 2: Step Identification  
Number all surgical steps with explicit ENDPOINTS

## Phase 3: Anatomy Integration
Match anatomical content to {{ANATOMY_DEPTH}} specification

## Phase 4: Safety Integration
Place all hazard warnings, critical anatomy boxes, decision points

## Phase 5: Figure Density Check
Verify 2-4 figures per major step

## Phase 6: Completeness Verification
- [ ] All steps numbered with endpoints
- [ ] All critical anatomy documented
- [ ] All complications with prevention/management
- [ ] All measurements in Mean ± SD (range; n) format
- [ ] Figure density adequate (1 per 150 words)
```

---

## Quality Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Figures per surgical step | 3-4 | 2 |
| Figures per 1000 words | 7-10 | 5 |
| Hazard warnings | 5-10 | 3 |
| Decision points | 3-5 | 2 |
| Technical pearls | 5-10 | 5 |
| Steps with explicit endpoints | 100% | 90% |
| Anatomical measurements with n | 100% | 80% |
