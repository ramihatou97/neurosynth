# Master Neuroanatomy Synthesis Prompt v2.0 — Rhoton Excellence Edition

> **Version**: 2.0  
> **Purpose**: Microsurgical anatomy chapters matching Rhoton's Cranial Anatomy standards  
> **Architecture**: Rhoton (microsurgical precision) + Seven Aneurysms (surgical application) + Operative Cranial Neurosurgical Anatomy (Fukushima)  
> **Figure Target**: 1 figure per 150-200 words; 100-150 figures per region  
> **Key Enhancement**: Multi-angle visualization, surgical corridor integration, 3D relationships

---

## System Context

This prompt generates neuroanatomy chapters for the NeuroSynth FigureIntegrationPipeline:
1. Sources include "Available Figures" catalogs (FIGURE_ID, Type, Caption)
2. Place `[FIGURE: ID]` tags at every anatomical structure, relationship, and surgical view
3. Pipeline handles: placeholder resolution, multi-angle correlation, position optimization

**Your role**: Create Rhoton-quality microsurgical anatomy with explicit surgical application.

---

## Variables

| Variable | Description | Options |
|----------|-------------|---------|
| `{{REFERENCE_MATERIALS}}` | Source documents with Available Figures | Required |
| `{{ANATOMICAL_REGION}}` | Region to synthesize | Required |
| `{{REGION_TYPE}}` | Cranial vs Spinal | CRANIAL / SPINAL / CRANIOCERVICAL |

---

## Prompt

```
You are synthesizing a microsurgical anatomy chapter matching the quality of Rhoton's Cranial Anatomy and the Microsurgical Anatomy of the Brain (encyclopedic anatomical detail), Seven Aneurysms (surgical anatomy application), and Operative Cranial Neurosurgical Anatomy (Fukushima's 3D understanding).

CRITICAL STANDARDS FROM TEXTBOOK ANALYSIS:

**From Rhoton's Cranial Anatomy**:
- Systematic layer-by-layer description: Surface → Osseous → Meningeal → Cisternal → Vascular → Neural
- All measurements in Mean ± SD (range; n) format
- Terminologia Anatomica (TA) as primary nomenclature
- Multiple viewing angles (superior, lateral, anterior, posterior, inferior)
- Anatomical variations with prevalence percentages and sample sizes
- Surgical significance stated for every structure

**From Seven Aneurysms (Lawton)**:
- Anatomy organized by surgical corridor
- "Working distance" and "angle of attack" concepts
- Structure-at-risk identification for each approach
- Bailout options when anatomy unfavorable

**From Fukushima's Operative Anatomy**:
- Three-dimensional relationships emphasized
- Photographic documentation from surgical perspective
- Anatomical triangles and safe zones defined
- Critical distances for surgical planning

# Reference Materials

<reference_materials>
{{REFERENCE_MATERIALS}}
</reference_materials>

# Target Region

<anatomical_region>
{{ANATOMICAL_REGION}}
</anatomical_region>

<region_type>
{{REGION_TYPE}}
</region_type>

---

# FIGURE INTEGRATION PROTOCOL

## Density Requirements
- **Minimum**: 1 figure per 200 words
- **Target**: 100-150 figures for comprehensive regional anatomy
- **Every structure needs multiple angles**: Superior, lateral, surgical view minimum

## Mandatory Figure Triggers

Place `[FIGURE: ID]` when describing:
1. **Every named structure** — First mention gets figure
2. **Spatial relationships** — Structure A relative to B
3. **Measurements** — Distance, diameter, angle
4. **Surgical views** — As seen during approach
5. **Variations** — Each variant type
6. **Boundaries** — Limits of regions/spaces
7. **Entry zones** — Safe surgical entries
8. **Triangles** — Named anatomical triangles
9. **Corridors** — Surgical access pathways
10. **3D relationships** — Multiple angles for complex areas

## Multi-Angle Protocol

Every major structure requires:
```
[FIGURE: structure_superior_view]
[FIGURE: structure_lateral_view]  
[FIGURE: structure_surgical_view]
[FIGURE: structure_relationships]
```

## Figure Format
`[FIGURE: exact_figure_id_from_catalog]`

---

# CORE PRINCIPLES

## 1. Rhoton Anatomical Standards

### Measurement Format
All measurements: **Mean ± SD (range; n)**
- Example: "The optic canal measures 8.5 ± 1.2 mm (range: 6-12 mm; n=100)"

### Nomenclature Priority
1. **Primary**: Terminologia Anatomica (TA) / Terminologia Neuroanatomica (TNA)
2. **Secondary**: Common clinical/eponymous terms in parentheses
- Example: "Arteriae cerebri anterior (anterior cerebral artery, ACA)"

### Variation Documentation
All variations: **Prevalence % (95% CI; n)**
- Example: "Fetal PCA: 15% (95% CI: 12-18%; n=500)"

## 2. Layer-by-Layer Progression

For cranial anatomy, always progress:
1. **Surface** — Scalp, landmarks, skin incisions
2. **Osseous** — Bones, foramina, sutures
3. **Meningeal** — Dura, sinuses, reflections
4. **Cisternal** — Arachnoid, cisterns, CSF spaces
5. **Arterial** — Arteries by segment
6. **Venous** — Veins and sinuses
7. **Neural** — Cranial nerves, brain parenchyma
8. **Surgical** — Corridors, safe zones, triangles

## 3. Mandatory Callout Boxes

### 🔴 CRITICAL ANATOMY
> **🔴 STRUCTURE**: [Name]
> **Surgical Significance**: [Why critical]
> **At Risk During**: [Procedures/approaches]
> **Injury Consequence**: [Deficit]
> **Protection Strategy**: [How to avoid]
> [FIGURE: critical_anatomy_detail]

### 📐 KEY MEASUREMENT
> **📐 MEASUREMENT**: [What]
> **Value**: [Mean ± SD (range; n)]
> **Surgical Relevance**: [How used in planning]
> **Source**: [Reference]

### 🔀 ANATOMICAL VARIATION
> **🔀 VARIATION**: [Name]
> **Prevalence**: [% (95% CI; n)]
> **Recognition**: [How identified]
> **Surgical Adaptation**: [What to do differently]
> [FIGURE: variation_example]

### 📍 SURGICAL LANDMARK
> **📍 LANDMARK**: [Name]
> **Definition**: [Precise description]
> **Identifies**: [What it leads to]
> **Distance to Target**: [mm]
> [FIGURE: landmark_detail]

### ⚠️ DANGER ZONE
> **⚠️ DANGER ZONE**
> **Location**: [Precise boundaries]
> **Contents**: [Structures at risk]
> **Approaches Affected**: [Which procedures]
> **Safe Alternative**: [How to avoid]
> [FIGURE: danger_zone]

### 🔺 ANATOMICAL TRIANGLE
> **🔺 TRIANGLE**: [Name (Eponym)]
> **Boundaries**:
> - Superior: [Structure]
> - Inferior: [Structure]  
> - Medial/Lateral: [Structure]
> **Contents**: [What's inside]
> **Dimensions**: [Base × Height mm]
> **Surgical Use**: [Access to what]
> [FIGURE: triangle_boundaries]
> [FIGURE: triangle_contents]

### 🚪 SURGICAL CORRIDOR
> **🚪 CORRIDOR**: [Name]
> **Entry Point**: [Surface location]
> **Trajectory**: [Direction]
> **Working Distance**: [mm]
> **Angle of Attack**: [degrees]
> **Target Access**: [What structures reached]
> **Structures at Risk**: [Along trajectory]
> [FIGURE: corridor_trajectory]

---

# CHAPTER SCHEMA

---

# [ANATOMICAL REGION] — Microsurgical Anatomy

## Executive Summary

[FIGURE: region_overview_3d]

**Region Definition**: [One sentence defining boundaries]

**Surgical Importance**: [Why this region matters to neurosurgeons]

**Key Numbers**:
| Parameter | Value | Source |
|:----------|:------|:-------|
| [Key dimension 1] | [Mean ± SD mm] | [Source] |
| [Key dimension 2] | [Mean ± SD mm] | [Source] |
| [Key relationship] | [Value] | [Source] |

---

## Quick Reference Card

### Critical Measurements

| Structure | Measurement | Value | Source |
|:----------|:------------|:------|:-------|
| [Structure] | [Parameter] | [Mean ± SD (range; n)] | [Source] |

### Structures at Risk by Approach

| Approach | Critical Structures | Source |
|:---------|:--------------------|:-------|
| [Approach] | [Structures] | [Source] |

### Key Landmarks

| Landmark | Leads to | Distance | Source |
|:---------|:---------|:---------|:-------|
| [Landmark] | [Target] | [mm] | [Source] |

[FIGURE: quick_reference_overview]

---

## Regional Boundaries

[FIGURE: boundaries_3d]

### Definition of Boundaries

| Boundary | Structure | Notes | Source |
|:---------|:----------|:------|:-------|
| Superior | [Structure] | [Details] | [Source] |
| Inferior | [Structure] | [Details] | [Source] |
| Anterior | [Structure] | [Details] | [Source] |
| Posterior | [Structure] | [Details] | [Source] |
| Medial | [Structure] | [Details] | [Source] |
| Lateral | [Structure] | [Details] | [Source] |

[FIGURE: boundaries_coronal]
[FIGURE: boundaries_sagittal]
[FIGURE: boundaries_axial]

### Neighboring Regions

| Direction | Adjacent Region | Communication | Source |
|:----------|:----------------|:--------------|:-------|
| [Direction] | [Region] | [Via what structure] | [Source] |

[FIGURE: neighboring_regions]

---

## Surface Anatomy

[FIGURE: surface_landmarks_overview]

### Scalp and Soft Tissue Layers

| Layer | Thickness | Contents | Surgical Note | Source |
|:------|:----------|:---------|:--------------|:-------|
| Skin | [mm] | [Description] | [Note] | [Source] |
| Subcutaneous | [mm] | [Vessels/nerves] | [Note] | [Source] |
| Galea | [mm] | [Description] | [Note] | [Source] |
| Subgaleal | [mm] | [Description] | [Note] | [Source] |
| Pericranium | [mm] | [Description] | [Note] | [Source] |

[FIGURE: scalp_layers]

### Surface Landmarks and Craniometric Points

| Point/Landmark | Definition | Coordinates from Reference | Surgical Use | Source |
|:---------------|:-----------|:---------------------------|:-------------|:-------|
| [Point] | [Precise definition] | [Distance from bregma/nasion/etc.] | [What it localizes] | [Source] |

[FIGURE: craniometric_points_lateral]
[FIGURE: craniometric_points_superior]

### Surface Projections of Deep Structures

| Structure | Surface Projection | Accuracy | Source |
|:----------|:-------------------|:---------|:-------|
| [Deep structure] | [Surface location] | [± mm] | [Source] |

[FIGURE: surface_projections]

> **📍 LANDMARK**: [Key Landmark]
> **Definition**: [Precise description]
> **Identifies**: [Deep structure]
> **Reliability**: [Consistent/Variable]
> [FIGURE: key_landmark_detail]

---

## Osseous Anatomy

[FIGURE: bone_overview_3d]

### Bones of the Region

#### [Bone Name 1]

[FIGURE: bone_1_external]
[FIGURE: bone_1_internal]

**General Description**: [Shape, position, relationships]

**Components**:
| Part | Dimensions | Features | Source |
|:-----|:-----------|:---------|:-------|
| [Part] | [Mean ± SD mm] | [Notable features] | [Source] |

**Thickness**:
| Location | Thickness | Range | n | Source |
|:---------|:----------|:------|:--|:-------|
| [Site] | [Mean ± SD mm] | [Range] | [n] | [Source] |

[FIGURE: bone_1_thickness_map]

#### [Bone Name 2]

[Same detailed format...]

### Sutures

| Suture | Bones Joined | Fusion Age | Surgical Note | Source |
|:-------|:-------------|:-----------|:--------------|:-------|
| [Suture] | [Bones] | [Age range] | [Relevant for] | [Source] |

[FIGURE: sutures_overview]

### Foramina and Canals

| Foramen/Canal | Location | Dimensions | Contents | Source |
|:--------------|:---------|:-----------|:---------|:-------|
| [Foramen] | [Precise location] | [Mean ± SD mm] | [What passes through] | [Source] |

[FIGURE: foramina_locations]
[FIGURE: foramina_contents]

> **📐 KEY MEASUREMENT**: [Critical Foramen]
> **Diameter**: [Mean ± SD mm (range; n)]
> **Distance to [Reference]**: [mm]
> **Surgical Relevance**: [Why matters]
> [FIGURE: critical_foramen_detail]

### Pneumatization

| Structure | Pneumatization Pattern | Prevalence | Surgical Impact | Source |
|:----------|:-----------------------|:-----------|:----------------|:-------|
| [Sinus/cell] | [Description] | [%] | [Consideration] | [Source] |

[FIGURE: pneumatization_variants]

---

## Meningeal Anatomy

[FIGURE: meninges_overview]

### Dural Layers and Reflections

**Dural Architecture**:
- Periosteal layer: [Description]
- Meningeal layer: [Description]
- Separations: [Where layers split]

[FIGURE: dural_layers]

### Dural Reflections (Folds)

| Reflection | Attachments | Separates | Contains | Source |
|:-----------|:------------|:----------|:---------|:-------|
| [Fold name] | [Attachment sites] | [Compartments] | [Venous sinuses] | [Source] |

[FIGURE: dural_reflections_sagittal]
[FIGURE: dural_reflections_coronal]

### Venous Sinuses

| Sinus | Course | Receives | Drains To | Dimensions | Source |
|:------|:-------|:---------|:----------|:-----------|:-------|
| [Sinus] | [Path] | [Tributaries] | [Outlet] | [Mean ± SD mm] | [Source] |

[FIGURE: venous_sinuses_overview]
[FIGURE: venous_sinuses_detail]

> **🔴 CRITICAL ANATOMY**: [Major Sinus]
> **Location**: [Precise position]
> **At Risk During**: [Approaches/procedures]
> **Injury Consequence**: [Bleeding, venous infarction, etc.]
> **Protection**: [Technique]
> [FIGURE: sinus_protection]

### Meningeal Vessels

| Vessel | Origin | Course | Significance | Source |
|:-------|:-------|:-------|:-------------|:-------|
| [Artery/vein] | [Parent] | [Path] | [Surgical relevance] | [Source] |

[FIGURE: meningeal_vessels]

---

## Cisternal Anatomy

[FIGURE: cisterns_overview_3d]

### Arachnoid Cisterns

| Cistern | Location | Boundaries | Contents | CSF Volume | Source |
|:--------|:---------|:-----------|:---------|:-----------|:-------|
| [Cistern name] | [Position] | [Limits] | [Vessels, nerves] | [mL] | [Source] |

[FIGURE: cistern_1_boundaries]
[FIGURE: cistern_1_contents]

### Cisternal Contents Detail

#### [Cistern Name] Cistern

[FIGURE: cistern_detail_overview]

**Boundaries**:
- Superior: [Structure]
- Inferior: [Structure]
- Anterior: [Structure]
- Posterior: [Structure]
- Lateral: [Structure]

**Neural Contents**:
| Structure | Course Through Cistern | Source |
|:----------|:-----------------------|:-------|
| [Nerve/tract] | [Description] | [Source] |

**Vascular Contents**:
| Vessel | Relationship | Source |
|:-------|:-------------|:-------|
| [Artery/vein] | [Position in cistern] | [Source] |

[FIGURE: cistern_neural_contents]
[FIGURE: cistern_vascular_contents]

### Arachnoid Membranes and Trabeculations

| Membrane | Location | Attachment | Surgical Note | Source |
|:---------|:---------|:-----------|:--------------|:-------|
| [Membrane name] | [Where found] | [What it connects] | [When to divide] | [Source] |

[FIGURE: arachnoid_membranes]

> **📍 SURGICAL LANDMARK**: Cisternal Opening
> **Key Cistern**: [Name]
> **Opening Point**: [Location]
> **CSF Released**: [Approximate volume]
> **Effect**: [Brain relaxation, etc.]
> [FIGURE: cisternal_opening_technique]

---

## Arterial Anatomy

[FIGURE: arterial_overview_3d]

### Arterial Supply Overview

**Primary Arterial System**: [Circle of Willis component/Vertebrobasilar/etc.]

[FIGURE: arterial_tree_schematic]

### Arteries by Segment

#### [Major Artery Name]

[FIGURE: artery_course_overview]

**Segments**:

| Segment | Boundaries | Length | Diameter | Source |
|:--------|:-----------|:-------|:---------|:-------|
| [Segment name] | [From-to landmarks] | [Mean ± SD mm] | [Mean ± SD mm] | [Source] |

[FIGURE: artery_segments_labeled]

**Branches**:

| Branch | Origin | Course | Territory | Diameter | Source |
|:-------|:-------|:-------|:----------|:---------|:-------|
| [Branch] | [Segment] | [Direction] | [Supply area] | [mm] | [Source] |

[FIGURE: arterial_branches]

**Perforating Arteries**:

| Perforator Group | Number | Origin | Course | Territory | Source |
|:-----------------|:-------|:-------|:-------|:----------|:-------|
| [Group name] | [Mean ± SD (range; n)] | [Parent segment] | [Direction] | [Supply] | [Source] |

[FIGURE: perforators_detail]

> **🔴 CRITICAL ANATOMY**: [Perforator Group]
> **Number**: [Mean ± SD (range; n)]
> **Origin Zone**: [mm from landmark]
> **At Risk During**: [Procedure]
> **Injury Consequence**: [Stroke type/location]
> **Protection**: [Technique]
> [FIGURE: perforator_protection]

### Arterial Variations

| Variation | Prevalence | Description | Surgical Impact | Source |
|:----------|:-----------|:------------|:----------------|:-------|
| [Variant name] | [% (95% CI; n)] | [What's different] | [How affects surgery] | [Source] |

[FIGURE: arterial_variations]

> **🔀 VARIATION**: [Important Variant]
> **Prevalence**: [% (95% CI; n)]
> **Recognition**: [How to identify]
> **Surgical Adaptation**: [What to do]
> [FIGURE: variation_detail]

### Collateral Circulation

| Collateral | Between | Opens When | Significance | Source |
|:-----------|:--------|:-----------|:-------------|:-------|
| [Pathway] | [Territories] | [Condition] | [Surgical relevance] | [Source] |

[FIGURE: collateral_pathways]

---

## Venous Anatomy

[FIGURE: venous_overview_3d]

### Superficial Venous System

| Vein | Course | Drainage | Variations | Source |
|:-----|:-------|:---------|:-----------|:-------|
| [Vein name] | [Path] | [Into what] | [Prevalence of variants] | [Source] |

[FIGURE: superficial_veins]

### Deep Venous System

| Vein | Course | Drainage | Surgical Significance | Source |
|:-----|:-------|:---------|:----------------------|:-------|
| [Vein name] | [Path] | [Into what] | [Why matters] | [Source] |

[FIGURE: deep_veins]

### Venous Variations

| Variation | Prevalence | Description | Impact | Source |
|:----------|:-----------|:------------|:-------|:-------|
| [Variant] | [% (95% CI; n)] | [Description] | [Surgical impact] | [Source] |

[FIGURE: venous_variations]

> **🔴 CRITICAL ANATOMY**: [Major Vein]
> **Location**: [Position]
> **Sacrifice Tolerance**: [Safe to sacrifice? Conditions]
> **Injury Consequence**: [Infarction, swelling, etc.]
> [FIGURE: vein_critical_anatomy]

---

## Neural Anatomy

[FIGURE: neural_overview_3d]

### Cranial Nerves

#### CN [Number]: [Name] ([Latin])

[FIGURE: cn_X_overview]

**Origin**: [Nucleus/brainstem location]

**Course**:
| Segment | Course | Length | Relationships | Source |
|:--------|:-------|:-------|:--------------|:-------|
| [Segment] | [Description] | [mm] | [Adjacent structures] | [Source] |

[FIGURE: cn_X_course_detail]

**Key Relationships**:
| Location | Relationship To | Distance | Source |
|:---------|:----------------|:---------|:-------|
| [Where] | [Structure] | [mm] | [Source] |

[FIGURE: cn_X_relationships]

**Exit Point**: [Foramen/fissure]

**Function**: [Motor/sensory/autonomic]

**Surgical Vulnerability**:
| Approach | Risk Level | Mechanism | Source |
|:---------|:-----------|:----------|:-------|
| [Approach] | [High/Moderate/Low] | [How injured] | [Source] |

[FIGURE: cn_X_surgical_risk]

> **🔴 CRITICAL ANATOMY**: CN [X]
> **Most Vulnerable Point**: [Location]
> **During**: [Which procedures]
> **Consequence**: [Deficit]
> **Monitoring**: [Technique]
> [FIGURE: cn_X_protection]

### Brain Parenchyma

| Structure | Location | Function | Surgical Landmark | Source |
|:----------|:---------|:---------|:------------------|:-------|
| [Structure] | [Position] | [Function] | [Why matters] | [Source] |

[FIGURE: parenchymal_structures]

### White Matter Tracts

| Tract | Course | Function | Safe Distance | Source |
|:------|:-------|:---------|:--------------|:-------|
| [Tract] | [Path] | [Function] | [mm from surface] | [Source] |

[FIGURE: white_matter_tracts]

---

## Surgical Corridors

[FIGURE: corridors_overview]

### Corridor 1: [Name]

[FIGURE: corridor_1_trajectory]

> **🚪 CORRIDOR**: [Name]
>
> **Entry Point**: [Surface location]
>
> **Trajectory**: [Direction, angle]
>
> **Working Distance**: [mm from surface to target]
>
> **Angle of Attack**: [degrees from perpendicular]
>
> **Structures Traversed**:
> | Layer | Structure | Action | Source |
> |:------|:----------|:-------|:-------|
> | 1 | [Structure] | [Incise/retract/preserve] | [Source] |
> | 2 | [Structure] | [Action] | [Source] |
>
> **Target Access**: [What structures reached]
>
> **Structures at Risk**:
> | Structure | Location in Corridor | Risk Level | Source |
> |:----------|:---------------------|:-----------|:-------|
> | [Structure] | [Position] | [High/Mod/Low] | [Source] |
>
> **Approach Angle Limits**: [Degrees of freedom]
>
> [FIGURE: corridor_1_detail]
> [FIGURE: corridor_1_target_view]

### Corridor 2: [Name]

[Same detailed format...]

---

## Anatomical Triangles

[FIGURE: triangles_overview]

### Triangle 1: [Name (Eponym)]

> **🔺 TRIANGLE**: [Name]
>
> **Boundaries**:
> - Superior: [Structure]
> - Inferior/Base: [Structure]
> - Medial: [Structure] (OR Third side)
>
> **Dimensions**:
> | Parameter | Value | Source |
> |:----------|:------|:-------|
> | Base | [Mean ± SD mm] | [Source] |
> | Height | [Mean ± SD mm] | [Source] |
> | Area | [Mean ± SD mm²] | [Source] |
>
> **Contents**:
> | Structure | Position in Triangle | Source |
> |:----------|:---------------------|:-------|
> | [Structure] | [Where located] | [Source] |
>
> **Surgical Application**: [What access it provides]
>
> [FIGURE: triangle_1_boundaries]
> [FIGURE: triangle_1_contents]
> [FIGURE: triangle_1_surgical_view]

### Triangle 2: [Name]

[Same detailed format...]

---

## Safe Entry Zones

[FIGURE: safe_zones_overview]

### Zone 1: [Name]

> **🟢 SAFE ENTRY ZONE**: [Name]
>
> **Location**: [Precise anatomical position]
>
> **Boundaries**:
> - Superior: [Limit]
> - Inferior: [Limit]
> - Medial: [Limit]
> - Lateral: [Limit]
>
> **Dimensions**: [Length × Width mm]
>
> **What It Avoids**: [Structures not injured]
>
> **Access To**: [Target structures]
>
> **Depth Limits**: [How far can safely go]
>
> [FIGURE: safe_zone_1_boundaries]
> [FIGURE: safe_zone_1_depth]

---

## Anatomical Variations Summary

[FIGURE: variations_overview]

### Systematic Variation Table

| Structure | Variation | Prevalence | 95% CI | n | Surgical Impact | Source |
|:----------|:----------|:-----------|:-------|:--|:----------------|:-------|
| [Structure] | [Variant] | [%] | [CI] | [n] | [Impact] | [Source] |

[FIGURE: variation_examples_compilation]

### High-Impact Variations

> **🔀 CRITICAL VARIATION**: [Variant Name]
> **Prevalence**: [% (95% CI; n)]
> **Structure Affected**: [What's different]
> **Recognition**: [How to identify preoperatively/intraoperatively]
> **Surgical Adaptation**: [Modified technique]
> **Consequence if Missed**: [Complication risk]
> [FIGURE: critical_variation_detail]

---

## Imaging Correlation

[FIGURE: imaging_overview]

### MRI Correlation

| Sequence | Key Structures Visualized | Optimal Parameters | Source |
|:---------|:--------------------------|:-------------------|:-------|
| T1 | [Structures] | [Settings] | [Source] |
| T2 | [Structures] | [Settings] | [Source] |
| FLAIR | [Structures] | [Settings] | [Source] |
| DWI | [Structures] | [Settings] | [Source] |
| MRA | [Vessels] | [Settings] | [Source] |

[FIGURE: mri_t1_annotated]
[FIGURE: mri_t2_annotated]

### CT Correlation

| Window | Key Structures | Measurements | Source |
|:-------|:---------------|:-------------|:-------|
| Bone | [Structures] | [What to measure] | [Source] |
| Soft tissue | [Structures] | [What to measure] | [Source] |

[FIGURE: ct_bone_annotated]
[FIGURE: ct_soft_tissue_annotated]

### Angiographic Correlation

[FIGURE: angiography_correlation]

---

## Quantitative Summary Tables

### All Measurements

| Structure | Parameter | Mean | SD | Range | n | Source |
|:----------|:----------|:-----|:---|:------|:--|:-------|
| [All anatomical measurements from chapter] | | | | | | |

### All Variations

| Structure | Variation | Prevalence | 95% CI | n | Source |
|:----------|:----------|:-----------|:-------|:--|:-------|
| [All variations from chapter] | | | | | |

---

## Clinical Pearls

> **💡 ANATOMICAL PEARL 1**: [Topic]
> [Key anatomical insight for surgery]
> [FIGURE: pearl_1]
> **Source**: [Reference]

> **💡 ANATOMICAL PEARL 2**: [Topic]
> [Key insight]
> [FIGURE: pearl_2]
> **Source**: [Reference]

[5-10 pearls]

---

## Critical Anatomy Summary

### Structures at Risk by Approach

| Approach | Critical Structure | Risk | Consequence | Source |
|:---------|:-------------------|:-----|:------------|:-------|
| [Approach] | [Structure] | [Level] | [Deficit] | [Source] |

[FIGURE: critical_anatomy_summary]

---

## Information Gaps

**MANDATORY SECTION**

*Not addressed in provided references*:

- **Measurements**: [Missing quantitative data]
- **Variations**: [Missing variation prevalence]
- **Relationships**: [Unclear spatial relationships]
- **Imaging**: [Missing correlation data]

---

## Figure Index

| Figure ID | Description | View/Angle | Section | Source |
|:----------|:------------|:-----------|:--------|:-------|
| [All figures with viewing angle specified] | | | | |

---

## References

[Complete source list organized anatomically]

---

# SYNTHESIS PROCESS

## Phase 1: Figure Inventory by Anatomical Layer
Map all figures to layer-by-layer structure

## Phase 2: Measurement Extraction  
Extract all measurements in Mean ± SD (range; n) format

## Phase 3: Variation Compilation
Document all variations with prevalence (95% CI; n)

## Phase 4: Multi-Angle Integration
Ensure major structures have multiple viewing angles

## Phase 5: Surgical Application
Link anatomy to surgical corridors and safe zones

## Phase 6: Completeness Verification
- [ ] All layers documented (8 standard layers)
- [ ] All measurements formatted correctly
- [ ] All variations with prevalence
- [ ] Multiple angles for major structures
- [ ] Figure density adequate
```

---

## Quality Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Figures per 1000 words | 5-7 | 4 |
| Measurements with SD | 100% | 90% |
| Variations with prevalence | 100% | 80% |
| Multi-angle structures | 80% | 60% |
| Surgical correlation | All structures | Major structures |
