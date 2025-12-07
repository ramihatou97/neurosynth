"""
Universal Neurosurgical Study Package System
=============================================

Provides comprehensive search results by including foundational knowledge
(anatomy, biomechanics, pathophysiology) for any neurosurgical topic.

Universal design - works for spine, cranial, vascular, peripheral, functional.
"""

from typing import Dict, List, Any

# =============================================================================
# NEUROSURGICAL REGIONAL TAXONOMY
# =============================================================================
# Hierarchical organization of neurosurgical anatomy
# Used to infer region from query and find relevant foundations

NEUROSURGICAL_REGIONS: Dict[str, Dict[str, Any]] = {
    "spine": {
        "keywords": [
            "spine", "spinal", "vertebr", "disc", "disk", "lumbar", "cervical",
            "thoracic", "sacral", "cord", "radiculop", "myelop", "spondyl",
            "laminect", "discect", "diskect", "fusion", "decompress", "stenosis",
            "herniat", "foramin", "corpect", "kyphoplast", "vertebroplast",
        ],
        "subregions": {
            "cervical": {
                "keywords": ["cervical", "c-spine", "neck", "odontoid", "atlas", "axis", "subaxial", "acdf", "pcdf"],
                "anatomy_terms": ["cervical spine anatomy", "cervical vertebrae", "cervical cord"],
            },
            "thoracic": {
                "keywords": ["thoracic", "t-spine", "dorsal", "thoracolumbar", "rib"],
                "anatomy_terms": ["thoracic spine anatomy", "thoracic vertebrae", "thoracic cord"],
            },
            "lumbar": {
                "keywords": ["lumbar", "l-spine", "low back", "cauda equina", "conus"],
                "anatomy_terms": ["lumbar spine anatomy", "lumbar vertebrae", "cauda equina"],
            },
            "sacral": {
                "keywords": ["sacr", "coccyx", "sacroiliac"],
                "anatomy_terms": ["sacral anatomy", "sacral plexus"],
            },
        },
        "foundations": {
            "anatomy": ["spinal anatomy", "surgical anatomy spine", "vertebral anatomy"],
            "biomechanics": ["spine biomechanics", "spinal biomechanics", "motion segment"],
            "pathophysiology": ["disc degeneration", "degenerative disc disease"],
            "diagnostic": ["spine imaging", "spinal imaging", "spine MRI"],
            "examination": ["spine examination", "neurological examination"],
        },
    },

    "cranial": {
        "keywords": [
            "brain", "cerebr", "cranio", "intracranial", "cortex", "cortical",
            "glioma", "glioblastoma", "meningioma", "tumor", "neoplasm",
            "craniotomy", "craniectomy", "resection", "awake", "eloquent",
            "ventricle", "hydrocephalus", "shunt", "endoscop",
        ],
        "subregions": {
            "supratentorial": {
                "keywords": ["frontal", "temporal", "parietal", "occipital", "convexity", "insula", "supratentorial"],
                "anatomy_terms": ["cerebral anatomy", "cortical anatomy", "white matter tracts"],
            },
            "infratentorial": {
                "keywords": ["posterior fossa", "cerebell", "brainstem", "fourth ventricle", "infratentorial"],
                "anatomy_terms": ["posterior fossa anatomy", "cerebellar anatomy", "brainstem anatomy"],
            },
            "skull_base": {
                "keywords": ["skull base", "anterior fossa", "middle fossa", "cpa", "petrous", "clivus", "cavernous", "sella", "pituitary", "acoustic", "vestibular schwannoma"],
                "anatomy_terms": ["skull base anatomy", "cranial nerves", "cavernous sinus"],
            },
            "ventricular": {
                "keywords": ["ventricle", "hydrocephalus", "csf", "shunt", "etv", "choroid"],
                "anatomy_terms": ["ventricular anatomy", "CSF pathways", "choroid plexus"],
            },
        },
        "foundations": {
            "anatomy": ["cerebral anatomy", "brain anatomy", "surgical neuroanatomy"],
            "approaches": ["craniotomy approaches", "surgical approaches brain"],
            "pathophysiology": ["brain tumor biology", "cerebral edema"],
            "diagnostic": ["brain imaging", "brain MRI", "neuroimaging"],
            "monitoring": ["neuromonitoring", "intraoperative monitoring"],
        },
    },

    "vascular": {
        "keywords": [
            "aneurysm", "avm", "arteriovenous", "cavernoma", "cavernous malformation",
            "hemorrhage", "subarachnoid", "sah", "intracerebral", "ich",
            "stroke", "ischemi", "clipping", "coiling", "bypass", "ec-ic",
            "moyamoya", "dural fistula", "davf",
        ],
        "subregions": {
            "anterior_circulation": {
                "keywords": ["ica", "mca", "aca", "acom", "pcom", "anterior circulation", "carotid"],
                "anatomy_terms": ["anterior circulation anatomy", "circle of Willis"],
            },
            "posterior_circulation": {
                "keywords": ["vertebral", "basilar", "pica", "aica", "sca", "posterior circulation", "vertebrobasilar"],
                "anatomy_terms": ["posterior circulation anatomy", "vertebrobasilar anatomy"],
            },
        },
        "foundations": {
            "anatomy": ["cerebrovascular anatomy", "circle of Willis", "intracranial arteries"],
            "pathophysiology": ["aneurysm pathophysiology", "SAH pathophysiology", "vasospasm"],
            "diagnostic": ["cerebral angiography", "CTA brain", "vascular imaging"],
            "management": ["SAH management", "vasospasm management"],
        },
    },

    "peripheral": {
        "keywords": [
            "nerve", "plexus", "peripheral", "entrapment", "neuropathy",
            "carpal tunnel", "cubital", "tarsal", "peroneal", "ulnar",
            "neuroma", "neurolysis", "nerve transfer", "nerve repair",
            "brachial", "lumbosacral", "sciatic",
        ],
        "subregions": {
            "brachial_plexus": {
                "keywords": ["brachial plexus", "upper extremity", "arm", "shoulder", "erb", "klumpke"],
                "anatomy_terms": ["brachial plexus anatomy", "upper limb nerves"],
            },
            "lumbosacral_plexus": {
                "keywords": ["lumbosacral", "lower extremity", "leg", "sciatic", "femoral"],
                "anatomy_terms": ["lumbosacral plexus anatomy", "lower limb nerves"],
            },
            "entrapment": {
                "keywords": ["carpal tunnel", "cubital tunnel", "tarsal tunnel", "entrapment"],
                "anatomy_terms": ["peripheral nerve anatomy", "tunnel anatomy"],
            },
        },
        "foundations": {
            "anatomy": ["peripheral nerve anatomy", "nerve microanatomy"],
            "physiology": ["nerve physiology", "nerve conduction"],
            "diagnostic": ["electrodiagnostics", "EMG", "nerve conduction studies"],
            "pathophysiology": ["nerve injury classification", "wallerian degeneration"],
        },
    },

    "functional": {
        "keywords": [
            "dbs", "deep brain stimulation", "stimulator", "neuromodulation",
            "parkinson", "tremor", "dystonia", "movement disorder",
            "epilepsy", "seizure", "temporal lobe", "callosotomy",
            "pain", "neuralgia", "trigeminal", "spinal cord stimulation", "scs",
            "mvd", "microvascular decompression", "rhizotomy",
        ],
        "subregions": {
            "movement_disorders": {
                "keywords": ["parkinson", "tremor", "dystonia", "dbs", "deep brain", "gpi", "stn", "vim"],
                "anatomy_terms": ["basal ganglia anatomy", "thalamus anatomy", "subthalamic nucleus"],
            },
            "epilepsy": {
                "keywords": ["epilepsy", "seizure", "temporal lobe", "hippocampus", "amygdala", "callosotomy"],
                "anatomy_terms": ["temporal lobe anatomy", "limbic anatomy", "hippocampal anatomy"],
            },
            "pain": {
                "keywords": ["pain", "neuralgia", "trigeminal", "glossopharyngeal", "crps", "neuropathic"],
                "anatomy_terms": ["pain pathways", "trigeminal anatomy"],
            },
        },
        "foundations": {
            "anatomy": ["functional neuroanatomy", "basal ganglia", "thalamus anatomy"],
            "physiology": ["neurophysiology", "neural circuitry"],
            "diagnostic": ["functional imaging", "video EEG", "SEEG"],
            "pathophysiology": ["epileptogenesis", "movement disorder pathophysiology"],
        },
    },

    "oncology": {
        "keywords": [
            "tumor", "cancer", "neoplasm", "mass", "lesion", "malignant", "benign",
            "glioma", "glioblastoma", "astrocytoma", "oligodendroglioma",
            "meningioma", "schwannoma", "neuroma", "metastas", "metastatic",
            "chordoma", "craniopharyngioma", "pituitary adenoma", "ependymoma",
        ],
        "subregions": {
            "intra_axial": {
                "keywords": ["glioma", "glioblastoma", "astrocytoma", "oligodendroglioma", "intra-axial", "intraaxial"],
                "anatomy_terms": ["white matter anatomy", "eloquent cortex"],
            },
            "extra_axial": {
                "keywords": ["meningioma", "schwannoma", "extra-axial", "extraaxial", "dural"],
                "anatomy_terms": ["meninges anatomy", "dural anatomy"],
            },
            "sellar": {
                "keywords": ["pituitary", "adenoma", "sellar", "suprasellar", "craniopharyngioma", "rathke"],
                "anatomy_terms": ["sellar anatomy", "pituitary anatomy", "optic chiasm"],
            },
        },
        "foundations": {
            "pathology": ["brain tumor pathology", "WHO classification", "tumor grading"],
            "biology": ["tumor biology", "molecular markers", "IDH", "MGMT"],
            "diagnostic": ["tumor imaging", "MR spectroscopy", "perfusion imaging"],
            "treatment": ["adjuvant therapy", "radiation therapy", "chemotherapy"],
        },
    },
}



# =============================================================================
# KNOWLEDGE CATEGORIES
# =============================================================================
# Categories of knowledge with detection patterns and priorities

KNOWLEDGE_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "anatomy": {
        "priority": 1,  # Highest priority - foundational
        "patterns": [
            r"\banatomy\b", r"\banatomical\b", r"\bsurgical anatomy\b",
            r"\btopograph", r"\bmorpholog", r"\bstructur",
        ],
        "search_boost": 1.3,
        "description": "Structural knowledge of the region",
    },
    "biomechanics": {
        "priority": 2,
        "patterns": [
            r"\bbiomechanic", r"\bmotion segment\b", r"\bstability\b",
            r"\bkinematic", r"\bloading\b", r"\bforces\b", r"\bstress\b",
        ],
        "search_boost": 1.2,
        "description": "Mechanical principles",
    },
    "pathophysiology": {
        "priority": 2,
        "patterns": [
            r"\bpathophysiology\b", r"\bpathology\b", r"\bpathogenesis\b",
            r"\bdisease\b", r"\bdegenerat", r"\bherniat", r"\bruptur",
            r"\betiology\b", r"\bmechanism\b",
        ],
        "search_boost": 1.2,
        "description": "Disease mechanisms",
    },
    "diagnostic": {
        "priority": 3,
        "patterns": [
            r"\bimaging\b", r"\bdiagnos", r"\bevaluation\b",
            r"\bexamination\b", r"\bworkup\b", r"\bhistory\b",
            r"\bmri\b", r"\bct\b", r"\belectrophysiol", r"\bemg\b",
        ],
        "search_boost": 1.1,
        "description": "Diagnostic workup",
    },
    "surgical_technique": {
        "priority": 1,
        "patterns": [
            r"\btechnique\b", r"\bapproach\b", r"\bprocedure\b",
            r"\bsurgery\b", r"\bsurgical\b", r"\boperative\b",
            r"\bstep", r"\bmethod\b",
        ],
        "search_boost": 1.0,  # No boost - direct matches
        "description": "Surgical procedures",
    },
    "complications": {
        "priority": 4,
        "patterns": [
            r"\bcomplication", r"\brisk\b", r"\bfailure\b",
            r"\brevisio", r"\bmorbidity\b", r"\bmortality\b",
            r"\badverse\b", r"\bpseudarthrosis\b",
        ],
        "search_boost": 1.0,
        "description": "Complications and risks",
    },
    "outcomes": {
        "priority": 5,
        "patterns": [
            r"\boutcome", r"\bresult", r"\bprognosis\b",
            r"\bfollow.?up\b", r"\blong.?term\b", r"\bsurvival\b",
        ],
        "search_boost": 1.0,
        "description": "Results and prognosis",
    },
    "instrumentation": {
        "priority": 4,
        "patterns": [
            r"\binstrument", r"\bhardware\b", r"\bimplant\b",
            r"\bscrew\b", r"\brod\b", r"\bcage\b", r"\bplate\b",
        ],
        "search_boost": 1.0,
        "description": "Surgical instrumentation",
    },
}


# =============================================================================
# PROCEDURE KEYWORDS TO REGION MAPPING
# =============================================================================
# Maps procedure-specific keywords to their anatomical region
# Used when region isn't explicit in query

PROCEDURE_TO_REGION: Dict[str, str] = {
    # Spine procedures
    "discectomy": "spine",
    "diskectomy": "spine",
    "laminectomy": "spine",
    "laminoplasty": "spine",
    "foraminotomy": "spine",
    "corpectomy": "spine",
    "fusion": "spine",
    "acdf": "cervical",
    "pcdf": "cervical",
    "tlif": "lumbar",
    "plif": "lumbar",
    "alif": "lumbar",
    "xlif": "lumbar",
    "olif": "lumbar",
    "kyphoplasty": "spine",
    "vertebroplasty": "spine",

    # Cranial procedures
    "craniotomy": "cranial",
    "craniectomy": "cranial",
    "awake craniotomy": "cranial",
    "tumor resection": "cranial",
    "glioma": "cranial",
    "meningioma": "cranial",
    "shunt": "ventricular",
    "ventriculostomy": "ventricular",
    "etv": "ventricular",

    # Skull base
    "acoustic neuroma": "skull_base",
    "vestibular schwannoma": "skull_base",
    "pituitary": "skull_base",
    "transsphenoidal": "skull_base",
    "petrosal": "skull_base",

    # Vascular
    "aneurysm": "vascular",
    "clipping": "vascular",
    "coiling": "vascular",
    "avm": "vascular",
    "bypass": "vascular",
    "ec-ic": "vascular",
    "carotid": "vascular",

    # Peripheral
    "carpal tunnel": "peripheral",
    "cubital tunnel": "peripheral",
    "nerve repair": "peripheral",
    "nerve transfer": "peripheral",
    "neurolysis": "peripheral",

    # Functional
    "dbs": "functional",
    "deep brain stimulation": "functional",
    "scs": "functional",
    "spinal cord stimulation": "functional",
    "mvd": "functional",
    "microvascular decompression": "functional",
    "rhizotomy": "functional",
    "epilepsy surgery": "functional",
    "temporal lobectomy": "functional",
}


# =============================================================================
# FOUNDATIONAL SEARCH TERMS BY REGION
# =============================================================================
# For each region, define search terms that find foundational chapters
# These are used to supplement BROAD mode results

REGION_FOUNDATIONS: Dict[str, Dict[str, List[str]]] = {
    "spine": {
        "anatomy": [
            "spinal anatomy",
            "surgical anatomy spine",
            "vertebral anatomy",
            "spine surgical anatomy",
        ],
        "biomechanics": [
            "spine biomechanics",
            "spinal biomechanics",
            "motion segment biomechanics",
            "spinal stability",
        ],
        "pathophysiology": [
            "disc degeneration",
            "degenerative disc disease",
            "spinal pathology",
        ],
        "diagnostic": [
            "spine imaging",
            "spinal imaging",
            "spine MRI interpretation",
        ],
    },
    "cervical": {
        "anatomy": [
            "cervical spine anatomy",
            "cervical vertebrae anatomy",
            "neck anatomy surgery",
        ],
        "biomechanics": [
            "cervical spine biomechanics",
            "cervical stability",
        ],
        "approaches": [
            "cervical approaches",
            "anterior cervical approach",
            "posterior cervical approach",
        ],
    },
    "lumbar": {
        "anatomy": [
            "lumbar spine anatomy",
            "lumbar vertebrae anatomy",
            "cauda equina anatomy",
        ],
        "biomechanics": [
            "lumbar biomechanics",
            "lumbar spine biomechanics",
        ],
        "approaches": [
            "lumbar approaches",
            "posterior lumbar approach",
            "lateral lumbar approach",
        ],
    },
    "cranial": {
        "anatomy": [
            "cerebral anatomy",
            "brain anatomy",
            "surgical neuroanatomy",
            "cortical anatomy",
        ],
        "approaches": [
            "craniotomy approaches",
            "surgical approaches brain",
            "neurosurgical approaches",
        ],
        "diagnostic": [
            "brain imaging",
            "neuroimaging",
            "brain MRI",
        ],
    },
    "skull_base": {
        "anatomy": [
            "skull base anatomy",
            "cranial nerve anatomy",
            "cavernous sinus anatomy",
        ],
        "approaches": [
            "skull base approaches",
            "anterior skull base approach",
            "lateral skull base approach",
        ],
    },
    "vascular": {
        "anatomy": [
            "cerebrovascular anatomy",
            "circle of Willis",
            "intracranial arteries",
        ],
        "pathophysiology": [
            "aneurysm pathophysiology",
            "SAH pathophysiology",
            "vasospasm",
        ],
        "diagnostic": [
            "cerebral angiography",
            "CTA brain",
            "vascular imaging",
        ],
    },
    "peripheral": {
        "anatomy": [
            "peripheral nerve anatomy",
            "brachial plexus anatomy",
            "nerve microanatomy",
        ],
        "physiology": [
            "nerve physiology",
            "nerve conduction",
        ],
        "diagnostic": [
            "electrodiagnostics",
            "EMG",
            "nerve conduction studies",
        ],
    },
    "functional": {
        "anatomy": [
            "basal ganglia anatomy",
            "thalamus anatomy",
            "functional neuroanatomy",
        ],
        "physiology": [
            "neurophysiology",
            "neural circuits",
        ],
    },
    "oncology": {
        "pathology": [
            "brain tumor pathology",
            "WHO tumor classification",
            "tumor grading",
        ],
        "biology": [
            "tumor biology",
            "molecular markers",
        ],
    },
}

