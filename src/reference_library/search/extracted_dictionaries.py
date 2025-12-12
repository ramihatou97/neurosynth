"""
Extracted Dictionaries from Neurosurgical Procedural Framework
===============================================================
These dictionaries complement the existing ANATOMICAL_REGIONS, APPROACH_EXPANSIONS,
and ACRONYM_CONTEXT dictionaries for enhanced query expansion in the Reference Library.

Extracted from: src/neurosynth/Untitled-3.ini (Procedural Chapter Architecture)
"""

from typing import Dict, List

# =============================================================================
# 1. INSTRUMENT_SYNONYMS - Surgical instruments and equipment
# =============================================================================
INSTRUMENT_SYNONYMS: dict[str, list[str]] = {
    # Head Fixation
    "mayfield": [
        "skull clamp",
        "head holder",
        "three-pin fixation",
        "pin fixation",
        "head frame",
    ],
    "skull clamp": ["mayfield", "head holder", "pin fixation"],
    # Bone Instruments
    "kerrison": ["kerrison rongeur", "rongeur", "bone biter"],
    "rongeur": ["kerrison", "bone biter", "pituitary rongeur"],
    "craniotome": ["bone saw", "cranial perforator", "high-speed drill"],
    "perforator": ["burr", "drill bit", "cranial drill"],
    "high-speed drill": ["craniotome", "matchstick burr", "cutting burr"],
    "osteotome": ["bone chisel", "bone cutter"],
    # Dissection Instruments
    "penfield": ["penfield dissector", "dural elevator", "dissector"],
    "microdissector": ["micro-dissector", "dissector", "nerve hook"],
    "cottonoid": ["patty", "cottonoid patty", "neurosurgical patty"],
    # Retractors
    "self-retaining retractor": [
        "weitlaner",
        "cerebellar retractor",
        "brain retractor",
    ],
    "army-navy": ["army navy retractor", "handheld retractor"],
    "cerebellar retractor": ["brain retractor", "fixed arm retractor"],
    # Cutting Instruments
    "microscissors": ["micro-scissors", "microsurgical scissors", "dural scissors"],
    "microscalpel": ["micro-scalpel", "#11 blade", "#15 blade"],
    # Forceps
    "bipolar": ["bipolar forceps", "bipolar cautery", "bipolar coagulation"],
    "adson": ["adson forceps", "tissue forceps"],
    "debakey": ["debakey forceps", "vascular forceps"],
    "tumor forceps": ["biopsy forceps", "grasping forceps"],
    # Aspiration/Debulking
    "cusa": ["cavitron", "ultrasonic aspirator", "ultrasonic surgical aspirator"],
    "suction": ["sucker", "frazier suction", "neurosurgical suction"],
    # Clips and Ligatures
    "raney clips": ["scalp clips", "hemostatic clips"],
    "aneurysm clip": ["yasargil clip", "sugita clip", "vascular clip"],
    "micro-clip": ["microclip", "temporary clip", "vessel clip"],
    # Cautery
    "monopolar": ["monopolar cautery", "bovie", "electrocautery"],
    "electrocautery": ["cautery", "bovie", "monopolar"],
    # Visualization
    "operating microscope": ["surgical microscope", "microscope"],
    "endoscope": ["neuroendoscope", "ventricular scope"],
    "c-arm": ["fluoroscopy", "image intensifier", "fluoro"],
}

# =============================================================================
# 2. POSITIONING_TERMS - Patient positioning terminology
# =============================================================================
POSITIONING_TERMS: dict[str, list[str]] = {
    # Major Positions
    "park bench": ["lateral decubitus", "lateral position", "three-quarter prone"],
    "lateral decubitus": ["park bench", "lateral position", "side-lying"],
    "prone": ["prone position", "face down", "ventral decubitus"],
    "supine": ["supine position", "dorsal decubitus", "face up"],
    "sitting": ["sitting position", "semi-sitting", "beach chair"],
    # Position Components
    "axillary roll": ["chest roll", "axilla support", "brachial plexus protection"],
    "chest roll": ["thoracic roll", "body support"],
    "head holder": ["mayfield", "skull clamp", "pin fixation"],
    "arm board": ["arm support", "arm rest"],
    # Position Modifications
    "reverse trendelenburg": ["head up", "anti-trendelenburg"],
    "trendelenburg": ["head down", "feet elevated"],
    "neck flexion": ["chin tuck", "cervical flexion"],
    "neck extension": ["cervical extension", "head back"],
    "head rotation": ["head turn", "cervical rotation"],
    # Pressure Points
    "pressure point": ["bony prominence", "weight-bearing area"],
    "gel pad": ["foam pad", "pressure relief", "positioning pad"],
}

# =============================================================================
# 3. NEUROMONITORING_TERMS - Intraoperative monitoring vocabulary
# =============================================================================
NEUROMONITORING_TERMS: dict[str, dict] = {
    "BAER": {
        "full": "brainstem auditory evoked responses",
        "synonyms": [
            "ABR",
            "auditory brainstem response",
            "brainstem auditory evoked potentials",
        ],
        "context": ["posterior fossa", "acoustic neuroma", "CN VIII", "brainstem"],
    },
    "SSEP": {
        "full": "somatosensory evoked potentials",
        "synonyms": ["somatosensory evoked responses", "sensory evoked potentials"],
        "context": ["spinal cord", "sensory pathway", "dorsal column"],
    },
    "MEP": {
        "full": "motor evoked potentials",
        "synonyms": [
            "motor evoked responses",
            "transcranial motor evoked potentials",
            "TcMEP",
        ],
        "context": ["motor pathway", "corticospinal tract", "spinal cord"],
    },
    "EMG": {
        "full": "electromyography",
        "synonyms": ["electromyogram", "muscle monitoring", "nerve monitoring"],
        "context": ["facial nerve", "cranial nerve", "nerve root", "triggered EMG"],
    },
    "EEG": {
        "full": "electroencephalography",
        "synonyms": ["electroencephalogram", "brain wave monitoring"],
        "context": ["seizure", "cortical function", "depth of anesthesia"],
    },
    "triggered EMG": {
        "full": "triggered electromyography",
        "synonyms": ["stimulated EMG", "pedicle screw testing"],
        "context": ["pedicle screw", "nerve proximity", "XLIF", "lateral approach"],
    },
}

# =============================================================================
# 4. HEMOSTATIC_AGENTS - Hemostasis materials and techniques
# =============================================================================
HEMOSTATIC_AGENTS: dict[str, list[str]] = {
    # Topical Agents
    "gelfoam": ["gelatin sponge", "absorbable gelatin", "gelatin foam"],
    "surgicel": ["oxidized cellulose", "oxidized regenerated cellulose", "ORC"],
    "floseal": ["gelatin-thrombin matrix", "flowable hemostatic", "thrombin matrix"],
    "tisseel": ["fibrin glue", "fibrin sealant", "fibrinogen-thrombin"],
    "thrombin": ["topical thrombin", "bovine thrombin", "recombinant thrombin"],
    # Bone Hemostasis
    "bone wax": ["bone hemostasis", "beeswax", "ostene"],
    # Dural Sealants
    "duraseal": ["dural sealant", "PEG sealant", "polyethylene glycol sealant"],
    "fibrin glue": ["tisseel", "fibrin sealant", "biological glue"],
    # Techniques
    "bipolar coagulation": ["bipolar cautery", "bipolar hemostasis", "electrocautery"],
    "cottonoid tamponade": ["patty pressure", "cottonoid pressure", "gentle tamponade"],
    "direct pressure": ["manual compression", "pressure hemostasis"],
}

# =============================================================================
# 5. COMPLICATION_TERMS - Surgical complications and adverse events
# =============================================================================
COMPLICATION_TERMS: dict[str, dict] = {
    # Vascular Complications
    "hematoma": {
        "synonyms": ["blood collection", "hemorrhage", "bleeding"],
        "types": [
            "epidural hematoma",
            "subdural hematoma",
            "intracerebral hematoma",
            "posterior fossa hematoma",
            "wound hematoma",
        ],
    },
    "hemorrhage": {
        "synonyms": ["bleeding", "blood loss", "exsanguination"],
        "types": ["arterial bleeding", "venous bleeding", "parenchymal bleeding"],
    },
    "venous air embolism": {
        "synonyms": ["VAE", "air embolism", "gas embolism"],
        "context": ["sitting position", "park bench", "negative venous pressure"],
    },
    "sinus injury": {
        "synonyms": ["venous sinus injury", "sinus tear", "sinus laceration"],
        "types": ["transverse sinus", "sigmoid sinus", "sagittal sinus", "torcula"],
    },
    # Neural Complications
    "nerve injury": {
        "synonyms": ["nerve damage", "neuropraxia", "axonotmesis", "neurotmesis"],
        "types": [
            "cranial nerve injury",
            "nerve root injury",
            "peripheral nerve injury",
        ],
    },
    "brachial plexus injury": {
        "synonyms": ["plexopathy", "arm weakness", "positioning injury"],
        "context": ["lateral position", "park bench", "axillary roll"],
    },
    "peroneal nerve palsy": {
        "synonyms": ["foot drop", "peroneal neuropathy", "fibular nerve injury"],
        "context": ["lateral position", "knee compression", "fibular head"],
    },
    "facial palsy": {
        "synonyms": ["facial weakness", "CN VII injury", "facial nerve injury"],
        "context": ["CPA tumor", "acoustic neuroma", "parotid surgery"],
    },
    # CSF-Related
    "CSF leak": {
        "synonyms": ["cerebrospinal fluid leak", "CSF fistula", "pseudomeningocele"],
        "context": ["dural tear", "wound leak", "rhinorrhea", "otorrhea"],
    },
    "dural tear": {
        "synonyms": ["durotomy", "dural laceration", "incidental durotomy"],
        "context": ["CSF leak", "dural repair", "dural patch"],
    },
    # Positioning Complications
    "POVL": {
        "full": "perioperative vision loss",
        "synonyms": [
            "postoperative blindness",
            "ischemic optic neuropathy",
            "retinal artery occlusion",
        ],
        "context": ["prone position", "eye pressure", "long surgery"],
    },
    "pressure ulcer": {
        "synonyms": ["decubitus ulcer", "pressure sore", "bedsore", "pressure injury"],
        "context": ["bony prominence", "long surgery", "positioning"],
    },
    # Neurological Deficits
    "paresis": {
        "synonyms": ["weakness", "motor deficit", "hemiparesis", "monoparesis"],
        "types": ["hemiparesis", "paraparesis", "quadriparesis", "monoparesis"],
    },
    "ataxia": {
        "synonyms": ["incoordination", "cerebellar dysfunction", "gait instability"],
        "context": ["cerebellar injury", "posterior fossa", "vermis"],
    },
    "dysphagia": {
        "synonyms": ["swallowing difficulty", "deglutition disorder"],
        "context": ["lower cranial nerve", "brainstem", "CN IX", "CN X"],
    },
}

# =============================================================================
# 6. TISSUE_DESCRIPTORS - Tissue characteristics and anatomical layers
# =============================================================================
TISSUE_DESCRIPTORS: dict[str, list[str]] = {
    # Meningeal Layers
    "dura": ["dura mater", "dural", "pachymeninx"],
    "arachnoid": ["arachnoid mater", "arachnoid membrane", "leptomeninges"],
    "pia": ["pia mater", "pial", "leptomeninges"],
    # Brain Tissue
    "cortex": ["cortical", "gray matter", "cerebral cortex", "cerebellar cortex"],
    "white matter": ["subcortical", "fiber tracts", "corona radiata"],
    "parenchyma": ["brain tissue", "neural tissue", "brain parenchyma"],
    # Tumor Characteristics
    "tumor capsule": ["capsule", "tumor margin", "pseudocapsule"],
    "cleavage plane": ["dissection plane", "tumor-brain interface", "surgical plane"],
    "feeding artery": ["tumor feeder", "arterial supply", "vascular pedicle"],
    "draining vein": ["venous drainage", "tumor vein"],
    # Scalp Layers
    "scalp": [
        "SCALP layers",
        "skin-connective tissue-aponeurosis-loose CT-pericranium",
    ],
    "galea": ["galea aponeurotica", "epicranial aponeurosis"],
    "pericranium": ["periosteum", "outer periosteum"],
    # Spinal Layers
    "ligamentum flavum": ["yellow ligament", "flavum"],
    "posterior longitudinal ligament": ["PLL", "posterior ligament"],
    "anterior longitudinal ligament": ["ALL", "anterior ligament"],
    "annulus fibrosus": ["annulus", "disc annulus", "outer disc"],
    "nucleus pulposus": ["nucleus", "disc nucleus", "inner disc"],
    # Fascia
    "thoracolumbar fascia": ["lumbodorsal fascia", "posterior fascia"],
    "prevertebral fascia": ["anterior cervical fascia", "deep cervical fascia"],
    "platysma": ["platysma muscle", "superficial cervical muscle"],
}

# =============================================================================
# 7. IMAGING_INTRAOP - Intraoperative imaging modalities
# =============================================================================
IMAGING_INTRAOP: dict[str, list[str]] = {
    # Fluoroscopy
    "fluoroscopy": ["fluoro", "C-arm", "image intensifier", "live X-ray"],
    "c-arm": ["C-arm fluoroscopy", "mobile fluoroscopy", "image intensifier"],
    "AP view": ["anteroposterior", "frontal view"],
    "lateral view": ["lateral fluoroscopy", "side view"],
    # Navigation
    "neuronavigation": [
        "navigation",
        "image guidance",
        "stereotactic navigation",
        "BrainLab",
        "Stealth",
    ],
    "stereotactic": ["stereotaxy", "frame-based", "frameless navigation"],
    # Ultrasound
    "intraoperative ultrasound": ["IOUS", "surgical ultrasound", "neurosonography"],
    "ultrasound": ["sonography", "US", "ultrasonography"],
    # Vascular Imaging
    "ICG": ["indocyanine green", "ICG angiography", "fluorescence angiography"],
    "intraoperative angiography": ["IOA", "surgical angiography"],
    "micro-Doppler": ["microvascular Doppler", "vessel Doppler"],
    # Advanced Imaging
    "intraoperative MRI": ["iMRI", "surgical MRI", "intraoperative magnetic resonance"],
    "intraoperative CT": ["iCT", "surgical CT", "O-arm"],
    "O-arm": ["cone beam CT", "intraoperative CT", "3D fluoroscopy"],
}

# =============================================================================
# 8. SURGICAL_PHASES - Procedural phase terminology
# =============================================================================
SURGICAL_PHASES: dict[str, list[str]] = {
    # Preparation
    "positioning": ["patient positioning", "surgical position", "operative position"],
    "prep and drape": ["surgical prep", "sterile preparation", "draping"],
    "timeout": ["surgical timeout", "time out", "safety pause"],
    # Exposure
    "incision": ["skin incision", "surgical incision", "approach"],
    "dissection": ["tissue dissection", "surgical dissection", "exposure"],
    "craniotomy": ["bone flap", "craniectomy", "bone removal"],
    "laminectomy": ["lamina removal", "decompression", "laminotomy"],
    # Core Procedure
    "dural opening": ["durotomy", "dural incision", "opening dura"],
    "tumor resection": ["tumor removal", "excision", "debulking"],
    "decompression": [
        "neural decompression",
        "cord decompression",
        "root decompression",
    ],
    "fusion": ["arthrodesis", "spinal fusion", "instrumented fusion"],
    # Closure
    "dural closure": ["dural repair", "duraplasty", "watertight closure"],
    "bone flap replacement": ["cranioplasty", "bone replacement"],
    "wound closure": ["layered closure", "skin closure", "fascial closure"],
    "hemostasis": ["bleeding control", "coagulation", "hemostatic control"],
}

# =============================================================================
# 9. ORTHOGRAPHIC_VARIATIONS - British/American spelling variants
# =============================================================================
ORTHOGRAPHIC_VARIATIONS: dict[str, str] = {
    # -our/-or variations
    "tumour": "tumor",
    "colour": "color",
    "behaviour": "behavior",
    "favour": "favor",
    "honour": "honor",
    "labour": "labor",
    "neighbour": "neighbor",
    "odour": "odor",
    "vapour": "vapor",
    # -ise/-ize variations
    "anaesthetise": "anesthetize",
    "cauterise": "cauterize",
    "immobilise": "immobilize",
    "localise": "localize",
    "mobilise": "mobilize",
    "stabilise": "stabilize",
    "visualise": "visualize",
    # -ae-/-e- variations
    "anaemia": "anemia",
    "anaesthesia": "anesthesia",
    "anaesthetic": "anesthetic",
    "haematoma": "hematoma",
    "haemorrhage": "hemorrhage",
    "haemostasis": "hemostasis",
    "oedema": "edema",
    "oesophagus": "esophagus",
    "paediatric": "pediatric",
    # -re/-er variations
    "centre": "center",
    "fibre": "fiber",
    "litre": "liter",
    "metre": "meter",
    # Other variations
    "disc": "disk",
    "grey": "gray",
    "programme": "program",
    "catalogue": "catalog",
    "analogue": "analog",
    "orthopaedic": "orthopedic",
    "foetus": "fetus",
    "manoeuvre": "maneuver",
    "defence": "defense",
    "offence": "offense",
    "licence": "license",
    "practise": "practice",
    "aluminium": "aluminum",
    "sulphur": "sulfur",
    "syphon": "siphon",
    "plough": "plow",
    "mould": "mold",
    "axe": "ax",
    "cheque": "check",
    "draught": "draft",
    "gaol": "jail",
    "jewellery": "jewelry",
    "kerb": "curb",
    "pyjamas": "pajamas",
    "sceptic": "skeptic",
    "storey": "story",
    "tyre": "tire",
    "waggon": "wagon",
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_all_synonyms() -> dict[str, list[str]]:
    """Combine all simple synonym dictionaries into one."""
    combined = {}
    combined.update(INSTRUMENT_SYNONYMS)
    combined.update(POSITIONING_TERMS)
    combined.update(HEMOSTATIC_AGENTS)
    combined.update(TISSUE_DESCRIPTORS)
    combined.update(IMAGING_INTRAOP)
    combined.update(SURGICAL_PHASES)
    return combined


def get_orthographic_variants(term: str) -> list[str]:
    """Get both British and American spellings for a term.

    Handles:
    1. Exact matches (tumour → tumor)
    2. Compound words containing variant roots (discectomy → diskectomy)
    """
    term_lower = term.lower()
    variants = [term]

    # Check if term is an exact British spelling
    if term_lower in ORTHOGRAPHIC_VARIATIONS:
        variants.append(ORTHOGRAPHIC_VARIATIONS[term_lower])

    # Check if term is an exact American spelling (reverse lookup)
    for british, american in ORTHOGRAPHIC_VARIATIONS.items():
        if term_lower == american:
            variants.append(british)
            break

    # FIX: Handle compound words containing variant roots
    # e.g., "discectomy" contains "disc" → generate "diskectomy"
    # e.g., "haematoma" is already in dict, but "subdural haematoma" needs expansion
    compound_roots = [
        ("disc", "disk"),  # discectomy/diskectomy, disc herniation/disk herniation
        ("tumour", "tumor"),  # tumour resection/tumor resection
        ("haem", "hem"),  # haematoma/hematoma, haemorrhage/hemorrhage
        ("anaesth", "anesth"),  # anaesthesia/anesthesia
        ("oedem", "edem"),  # oedema/edema
        ("paed", "ped"),  # paediatric/pediatric
        ("centre", "center"),  # centre of mass/center of mass
        ("fibre", "fiber"),  # nerve fibre/nerve fiber
        ("grey", "gray"),  # grey matter/gray matter
    ]

    for british_root, american_root in compound_roots:
        # British → American
        if british_root in term_lower:
            american_variant = term_lower.replace(british_root, american_root)
            if american_variant != term_lower:
                variants.append(american_variant)
        # American → British
        if american_root in term_lower:
            british_variant = term_lower.replace(american_root, british_root)
            if british_variant != term_lower:
                variants.append(british_variant)

    return list(set(variants))


def expand_with_monitoring_context(term: str) -> list[str]:
    """Expand neuromonitoring terms with full names and context."""
    term_upper = term.upper()
    expansions = [term]

    if term_upper in NEUROMONITORING_TERMS:
        entry = NEUROMONITORING_TERMS[term_upper]
        expansions.append(entry.get("full", ""))
        expansions.extend(entry.get("synonyms", []))
        expansions.extend(entry.get("context", []))

    return [e for e in expansions if e]


def expand_with_complication_context(term: str) -> list[str]:
    """Expand complication terms with synonyms and types."""
    term_lower = term.lower()
    expansions = [term]

    for key, entry in COMPLICATION_TERMS.items():
        if term_lower == key.lower() or term_lower in [
            s.lower() for s in entry.get("synonyms", [])
        ]:
            expansions.extend(entry.get("synonyms", []))
            expansions.extend(entry.get("types", []))
            expansions.extend(entry.get("context", []))
            if "full" in entry:
                expansions.append(entry["full"])

    return list(set([e for e in expansions if e]))


# Export all dictionaries for easy import
__all__ = [
    "INSTRUMENT_SYNONYMS",
    "POSITIONING_TERMS",
    "NEUROMONITORING_TERMS",
    "HEMOSTATIC_AGENTS",
    "COMPLICATION_TERMS",
    "TISSUE_DESCRIPTORS",
    "IMAGING_INTRAOP",
    "SURGICAL_PHASES",
    "ORTHOGRAPHIC_VARIATIONS",
    "get_all_synonyms",
    "get_orthographic_variants",
    "expand_with_monitoring_context",
    "expand_with_complication_context",
]
