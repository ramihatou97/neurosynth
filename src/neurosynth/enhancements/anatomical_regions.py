"""
Anatomical Region Taxonomy for NeuroSynth
==========================================
Hierarchical classification of neuroanatomical regions, vascular territories,
spinal segments, cranial nerves, and surgical corridors.

This module provides the taxonomy used for automatic region tagging
of extracted medical images.

Version: 1.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RegionCategory(str, Enum):
    """Top-level anatomical region categories."""

    BRAIN = "brain"
    SPINE = "spine"
    VASCULAR = "vascular"
    CRANIAL_NERVE = "cranial_nerve"
    SURGICAL_CORRIDOR = "surgical_corridor"
    SKULL_BASE = "skull_base"
    VENTRICULAR = "ventricular"


@dataclass
class AnatomicalRegion:
    """Definition of an anatomical region with keywords and hierarchy."""

    id: str  # Standardized identifier (e.g., "MCA_territory")
    name: str  # Human-readable name (e.g., "Middle Cerebral Artery Territory")
    category: RegionCategory
    parent_id: str | None = None  # Hierarchical parent
    keywords: list[str] = field(default_factory=list)  # Detection keywords
    aliases: list[str] = field(default_factory=list)  # Alternative names


# =============================================================================
# BRAIN REGIONS
# =============================================================================

BRAIN_REGIONS = [
    # Frontal Lobe
    AnatomicalRegion(
        id="frontal_lobe",
        name="Frontal Lobe",
        category=RegionCategory.BRAIN,
        keywords=["frontal", "prefrontal", "orbitofrontal"],
        aliases=["frontal cortex"],
    ),
    AnatomicalRegion(
        id="superior_frontal_gyrus",
        name="Superior Frontal Gyrus",
        category=RegionCategory.BRAIN,
        parent_id="frontal_lobe",
        keywords=["superior frontal", "sfg"],
    ),
    AnatomicalRegion(
        id="middle_frontal_gyrus",
        name="Middle Frontal Gyrus",
        category=RegionCategory.BRAIN,
        parent_id="frontal_lobe",
        keywords=["middle frontal", "mfg", "dlpfc"],
    ),
    AnatomicalRegion(
        id="inferior_frontal_gyrus",
        name="Inferior Frontal Gyrus",
        category=RegionCategory.BRAIN,
        parent_id="frontal_lobe",
        keywords=["inferior frontal", "ifg", "broca"],
    ),
    AnatomicalRegion(
        id="precentral_gyrus",
        name="Precentral Gyrus (Motor Cortex)",
        category=RegionCategory.BRAIN,
        parent_id="frontal_lobe",
        keywords=["precentral", "motor cortex", "primary motor", "m1"],
    ),
    # Temporal Lobe
    AnatomicalRegion(
        id="temporal_lobe",
        name="Temporal Lobe",
        category=RegionCategory.BRAIN,
        keywords=["temporal", "mesial temporal"],
        aliases=["temporal cortex"],
    ),
    AnatomicalRegion(
        id="superior_temporal_gyrus",
        name="Superior Temporal Gyrus",
        category=RegionCategory.BRAIN,
        parent_id="temporal_lobe",
        keywords=["superior temporal", "stg", "wernicke"],
    ),
    AnatomicalRegion(
        id="hippocampus",
        name="Hippocampus",
        category=RegionCategory.BRAIN,
        parent_id="temporal_lobe",
        keywords=["hippocampal", "hippocampus", "ca1", "ca2", "ca3", "dentate gyrus"],
    ),
    AnatomicalRegion(
        id="amygdala",
        name="Amygdala",
        category=RegionCategory.BRAIN,
        parent_id="temporal_lobe",
        keywords=["amygdala", "amygdaloid"],
    ),
    # Parietal Lobe
    AnatomicalRegion(
        id="parietal_lobe",
        name="Parietal Lobe",
        category=RegionCategory.BRAIN,
        keywords=["parietal"],
        aliases=["parietal cortex"],
    ),
    AnatomicalRegion(
        id="postcentral_gyrus",
        name="Postcentral Gyrus (Sensory Cortex)",
        category=RegionCategory.BRAIN,
        parent_id="parietal_lobe",
        keywords=["postcentral", "sensory cortex", "primary sensory", "s1"],
    ),
    # Occipital Lobe
    AnatomicalRegion(
        id="occipital_lobe",
        name="Occipital Lobe",
        category=RegionCategory.BRAIN,
        keywords=["occipital", "visual cortex", "calcarine"],
        aliases=["occipital cortex"],
    ),
    # Insula
    AnatomicalRegion(
        id="insula",
        name="Insula",
        category=RegionCategory.BRAIN,
        keywords=["insula", "insular", "sylvian"],
    ),
    # Deep Structures
    AnatomicalRegion(
        id="basal_ganglia",
        name="Basal Ganglia",
        category=RegionCategory.BRAIN,
        keywords=["basal ganglia", "striatum", "putamen", "caudate", "globus pallidus"],
    ),
    AnatomicalRegion(
        id="thalamus",
        name="Thalamus",
        category=RegionCategory.BRAIN,
        keywords=["thalamus", "thalamic"],
    ),
    AnatomicalRegion(
        id="hypothalamus",
        name="Hypothalamus",
        category=RegionCategory.BRAIN,
        keywords=["hypothalamus", "hypothalamic"],
    ),
    # Brainstem
    AnatomicalRegion(
        id="brainstem",
        name="Brainstem",
        category=RegionCategory.BRAIN,
        keywords=["brainstem", "brain stem"],
    ),
    AnatomicalRegion(
        id="midbrain",
        name="Midbrain",
        category=RegionCategory.BRAIN,
        parent_id="brainstem",
        keywords=["midbrain", "mesencephalon", "cerebral peduncle", "substantia nigra"],
    ),
    AnatomicalRegion(
        id="pons",
        name="Pons",
        category=RegionCategory.BRAIN,
        parent_id="brainstem",
        keywords=["pons", "pontine", "basis pontis"],
    ),
    AnatomicalRegion(
        id="medulla",
        name="Medulla Oblongata",
        category=RegionCategory.BRAIN,
        parent_id="brainstem",
        keywords=["medulla", "medullary", "olive", "pyramid"],
    ),
    # Cerebellum
    AnatomicalRegion(
        id="cerebellum",
        name="Cerebellum",
        category=RegionCategory.BRAIN,
        keywords=[
            "cerebellum",
            "cerebellar",
            "vermis",
            "cerebellar hemisphere",
            "dentate nucleus",
        ],
    ),
    # Corpus Callosum
    AnatomicalRegion(
        id="corpus_callosum",
        name="Corpus Callosum",
        category=RegionCategory.BRAIN,
        keywords=["corpus callosum", "genu", "splenium", "body of corpus callosum"],
    ),
]

# =============================================================================
# VASCULAR TERRITORIES
# =============================================================================

VASCULAR_REGIONS = [
    # General vascular category (matches book titles)
    AnatomicalRegion(
        id="vascular_general",
        name="Vascular/Angiography (General)",
        category=RegionCategory.VASCULAR,
        keywords=[
            "angiography",
            "neuroangiography",
            "angiogram",
            "vascular",
            "vessels",
            "arteries",
            "veins",
        ],
    ),
    # Anterior Circulation
    AnatomicalRegion(
        id="ica",
        name="Internal Carotid Artery",
        category=RegionCategory.VASCULAR,
        keywords=[
            "internal carotid",
            "ica",
            "cavernous ica",
            "petrous ica",
            "supraclinoid",
        ],
    ),
    AnatomicalRegion(
        id="mca",
        name="Middle Cerebral Artery",
        category=RegionCategory.VASCULAR,
        keywords=[
            "middle cerebral",
            "mca",
            "m1",
            "m2",
            "m3",
            "m4",
            "mca bifurcation",
            "mca trifurcation",
        ],
    ),
    AnatomicalRegion(
        id="aca",
        name="Anterior Cerebral Artery",
        category=RegionCategory.VASCULAR,
        keywords=[
            "anterior cerebral",
            "aca",
            "a1",
            "a2",
            "pericallosal",
            "callosomarginal",
        ],
    ),
    AnatomicalRegion(
        id="acom",
        name="Anterior Communicating Artery",
        category=RegionCategory.VASCULAR,
        keywords=["anterior communicating", "acom", "a-com"],
    ),
    # Posterior Circulation
    AnatomicalRegion(
        id="vertebral",
        name="Vertebral Artery",
        category=RegionCategory.VASCULAR,
        keywords=["vertebral artery", "v1", "v2", "v3", "v4"],
    ),
    AnatomicalRegion(
        id="basilar",
        name="Basilar Artery",
        category=RegionCategory.VASCULAR,
        keywords=["basilar", "basilar trunk", "basilar tip"],
    ),
    AnatomicalRegion(
        id="pca",
        name="Posterior Cerebral Artery",
        category=RegionCategory.VASCULAR,
        keywords=["posterior cerebral", "pca", "p1", "p2", "p3"],
    ),
    AnatomicalRegion(
        id="pcom",
        name="Posterior Communicating Artery",
        category=RegionCategory.VASCULAR,
        keywords=["posterior communicating", "pcom", "p-com"],
    ),
    AnatomicalRegion(
        id="sca",
        name="Superior Cerebellar Artery",
        category=RegionCategory.VASCULAR,
        keywords=["superior cerebellar", "sca"],
    ),
    AnatomicalRegion(
        id="aica",
        name="Anterior Inferior Cerebellar Artery",
        category=RegionCategory.VASCULAR,
        keywords=["anterior inferior cerebellar", "aica"],
    ),
    AnatomicalRegion(
        id="pica",
        name="Posterior Inferior Cerebellar Artery",
        category=RegionCategory.VASCULAR,
        keywords=["posterior inferior cerebellar", "pica"],
    ),
    # Venous
    AnatomicalRegion(
        id="superior_sagittal_sinus",
        name="Superior Sagittal Sinus",
        category=RegionCategory.VASCULAR,
        keywords=["superior sagittal", "sss", "sagittal sinus"],
    ),
    AnatomicalRegion(
        id="transverse_sinus",
        name="Transverse Sinus",
        category=RegionCategory.VASCULAR,
        keywords=["transverse sinus", "lateral sinus"],
    ),
    AnatomicalRegion(
        id="sigmoid_sinus",
        name="Sigmoid Sinus",
        category=RegionCategory.VASCULAR,
        keywords=["sigmoid sinus", "sigmoid"],
    ),
    AnatomicalRegion(
        id="cavernous_sinus",
        name="Cavernous Sinus",
        category=RegionCategory.VASCULAR,
        keywords=["cavernous sinus", "cavernous"],
    ),
]

# =============================================================================
# SPINAL SEGMENTS
# =============================================================================

SPINAL_REGIONS = [
    # Cervical
    AnatomicalRegion(
        id="cervical_spine",
        name="Cervical Spine",
        category=RegionCategory.SPINE,
        keywords=["cervical", "c-spine", "neck"],
    ),
    *[
        AnatomicalRegion(
            id=f"c{i}",
            name=f"C{i} Vertebra",
            category=RegionCategory.SPINE,
            parent_id="cervical_spine",
            keywords=[f"c{i}", f"c-{i}"],
        )
        for i in range(1, 8)
    ],
    AnatomicalRegion(
        id="c5_c6",
        name="C5-C6 Disc Level",
        category=RegionCategory.SPINE,
        parent_id="cervical_spine",
        keywords=["c5-c6", "c5/c6", "c5 c6"],
    ),
    AnatomicalRegion(
        id="c6_c7",
        name="C6-C7 Disc Level",
        category=RegionCategory.SPINE,
        parent_id="cervical_spine",
        keywords=["c6-c7", "c6/c7", "c6 c7"],
    ),
    # Thoracic
    AnatomicalRegion(
        id="thoracic_spine",
        name="Thoracic Spine",
        category=RegionCategory.SPINE,
        keywords=["thoracic", "t-spine", "dorsal spine"],
    ),
    # Lumbar
    AnatomicalRegion(
        id="lumbar_spine",
        name="Lumbar Spine",
        category=RegionCategory.SPINE,
        keywords=["lumbar", "l-spine", "lower back"],
    ),
    AnatomicalRegion(
        id="l4_l5",
        name="L4-L5 Disc Level",
        category=RegionCategory.SPINE,
        parent_id="lumbar_spine",
        keywords=["l4-l5", "l4/l5", "l4 l5"],
    ),
    AnatomicalRegion(
        id="l5_s1",
        name="L5-S1 Disc Level",
        category=RegionCategory.SPINE,
        parent_id="lumbar_spine",
        keywords=["l5-s1", "l5/s1", "l5 s1", "lumbosacral"],
    ),
    # Sacral
    AnatomicalRegion(
        id="sacral_spine",
        name="Sacral Spine",
        category=RegionCategory.SPINE,
        keywords=["sacral", "sacrum", "s-spine"],
    ),
]

# =============================================================================
# CRANIAL NERVES
# =============================================================================

CRANIAL_NERVE_REGIONS = [
    # General cranial nerve category (matches book titles)
    AnatomicalRegion(
        id="cranial_nerves",
        name="Cranial Nerves (General)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["cranial nerve", "cranial nerves", "cranial-nerve", "cranial-nerves"],
    ),
    AnatomicalRegion(
        id="cn_i",
        name="Olfactory Nerve (CN I)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["olfactory nerve", "cn i", "cn1", "olfactory"],
    ),
    AnatomicalRegion(
        id="cn_ii",
        name="Optic Nerve (CN II)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["optic nerve", "cn ii", "cn2", "optic chiasm", "optic tract"],
    ),
    AnatomicalRegion(
        id="cn_iii",
        name="Oculomotor Nerve (CN III)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["oculomotor", "cn iii", "cn3", "third nerve"],
    ),
    AnatomicalRegion(
        id="cn_iv",
        name="Trochlear Nerve (CN IV)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["trochlear", "cn iv", "cn4", "fourth nerve"],
    ),
    AnatomicalRegion(
        id="cn_v",
        name="Trigeminal Nerve (CN V)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["trigeminal", "cn v", "cn5", "v1", "v2", "v3", "gasserian", "meckel"],
    ),
    AnatomicalRegion(
        id="cn_vi",
        name="Abducens Nerve (CN VI)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["abducens", "cn vi", "cn6", "sixth nerve"],
    ),
    AnatomicalRegion(
        id="cn_vii",
        name="Facial Nerve (CN VII)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["facial nerve", "cn vii", "cn7", "seventh nerve", "geniculate"],
    ),
    AnatomicalRegion(
        id="cn_viii",
        name="Vestibulocochlear Nerve (CN VIII)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=[
            "vestibulocochlear",
            "cn viii",
            "cn8",
            "acoustic",
            "auditory",
            "vestibular",
        ],
    ),
    AnatomicalRegion(
        id="cn_ix",
        name="Glossopharyngeal Nerve (CN IX)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["glossopharyngeal", "cn ix", "cn9", "ninth nerve"],
    ),
    AnatomicalRegion(
        id="cn_x",
        name="Vagus Nerve (CN X)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["vagus", "cn x", "cn10", "tenth nerve"],
    ),
    AnatomicalRegion(
        id="cn_xi",
        name="Accessory Nerve (CN XI)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["accessory nerve", "cn xi", "cn11", "spinal accessory"],
    ),
    AnatomicalRegion(
        id="cn_xii",
        name="Hypoglossal Nerve (CN XII)",
        category=RegionCategory.CRANIAL_NERVE,
        keywords=["hypoglossal", "cn xii", "cn12", "twelfth nerve"],
    ),
]

# =============================================================================
# SURGICAL CORRIDORS
# =============================================================================

SURGICAL_CORRIDOR_REGIONS = [
    AnatomicalRegion(
        id="pterional",
        name="Pterional Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["pterional", "frontotemporal", "sylvian"],
    ),
    AnatomicalRegion(
        id="retrosigmoid",
        name="Retrosigmoid Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["retrosigmoid", "lateral suboccipital"],
    ),
    AnatomicalRegion(
        id="far_lateral",
        name="Far-Lateral Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["far lateral", "far-lateral", "transcondylar"],
    ),
    AnatomicalRegion(
        id="transsphenoidal",
        name="Transsphenoidal Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["transsphenoidal", "endonasal", "transnasal", "sellar"],
    ),
    AnatomicalRegion(
        id="supracerebellar_infratentorial",
        name="Supracerebellar Infratentorial",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["supracerebellar", "infratentorial", "scit"],
    ),
    AnatomicalRegion(
        id="interhemispheric",
        name="Interhemispheric Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["interhemispheric", "transcallosal", "callosal"],
    ),
    AnatomicalRegion(
        id="subtemporal",
        name="Subtemporal Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["subtemporal", "temporal base"],
    ),
    AnatomicalRegion(
        id="orbitozygomatic",
        name="Orbitozygomatic Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["orbitozygomatic", "orbito-zygomatic", "oz"],
    ),
    AnatomicalRegion(
        id="suboccipital_midline",
        name="Suboccipital Midline Approach",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["suboccipital", "midline suboccipital", "telovelar"],
    ),
    AnatomicalRegion(
        id="anterior_petrosectomy",
        name="Anterior Petrosectomy (Kawase)",
        category=RegionCategory.SURGICAL_CORRIDOR,
        keywords=["anterior petrosectomy", "kawase", "rhomboid"],
    ),
]

# =============================================================================
# SKULL BASE REGIONS
# =============================================================================

SKULL_BASE_REGIONS = [
    AnatomicalRegion(
        id="anterior_fossa",
        name="Anterior Cranial Fossa",
        category=RegionCategory.SKULL_BASE,
        keywords=[
            "anterior fossa",
            "anterior cranial",
            "cribriform",
            "planum sphenoidale",
        ],
    ),
    AnatomicalRegion(
        id="middle_fossa",
        name="Middle Cranial Fossa",
        category=RegionCategory.SKULL_BASE,
        keywords=["middle fossa", "middle cranial", "sphenoid wing", "temporal fossa"],
    ),
    AnatomicalRegion(
        id="posterior_fossa",
        name="Posterior Cranial Fossa",
        category=RegionCategory.SKULL_BASE,
        keywords=["posterior fossa", "posterior cranial", "foramen magnum"],
    ),
    AnatomicalRegion(
        id="clivus",
        name="Clivus",
        category=RegionCategory.SKULL_BASE,
        keywords=["clivus", "clival"],
    ),
    AnatomicalRegion(
        id="petrous_apex",
        name="Petrous Apex",
        category=RegionCategory.SKULL_BASE,
        keywords=["petrous apex", "petrous bone", "petrous"],
    ),
    AnatomicalRegion(
        id="cerebellopontine_angle",
        name="Cerebellopontine Angle",
        category=RegionCategory.SKULL_BASE,
        keywords=["cerebellopontine", "cpa", "cp angle"],
    ),
]

# =============================================================================
# ALL REGIONS COMBINED
# =============================================================================

ALL_REGIONS: list[AnatomicalRegion] = (
    BRAIN_REGIONS
    + VASCULAR_REGIONS
    + SPINAL_REGIONS
    + CRANIAL_NERVE_REGIONS
    + SURGICAL_CORRIDOR_REGIONS
    + SKULL_BASE_REGIONS
)

# Build lookup dictionaries
REGION_BY_ID: dict[str, AnatomicalRegion] = {r.id: r for r in ALL_REGIONS}
REGION_BY_CATEGORY: dict[RegionCategory, list[AnatomicalRegion]] = {}
for region in ALL_REGIONS:
    if region.category not in REGION_BY_CATEGORY:
        REGION_BY_CATEGORY[region.category] = []
    REGION_BY_CATEGORY[region.category].append(region)
