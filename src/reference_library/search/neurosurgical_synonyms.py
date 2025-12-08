"""Neurosurgical terminology synonym dictionary for query expansion.

This module provides comprehensive synonym mappings for neurosurgical terms
to improve search recall by expanding queries with related terminology.

Enhanced with extracted dictionaries from the Neurosurgical Procedural Framework.
"""

from typing import Dict, List, Optional, Set

# Import extracted dictionaries
from .extracted_dictionaries import (
    COMPLICATION_TERMS,
    HEMOSTATIC_AGENTS,
    IMAGING_INTRAOP,
    INSTRUMENT_SYNONYMS,
    NEUROMONITORING_TERMS,
    ORTHOGRAPHIC_VARIATIONS,
    POSITIONING_TERMS,
    SURGICAL_PHASES,
    TISSUE_DESCRIPTORS,
    expand_with_complication_context,
    expand_with_monitoring_context,
    get_orthographic_variants,
)

# =============================================================================
# ORIGINAL SYNONYM DICTIONARIES (Enhanced)
# =============================================================================

# Tumor/Pathology Synonyms
TUMOR_SYNONYMS: Dict[str, List[str]] = {
    "acoustic neuroma": [
        "vestibular schwannoma",
        "VS",
        "cerebellopontine angle tumor",
        "CPA tumor",
    ],
    "vestibular schwannoma": ["acoustic neuroma", "VS", "cerebellopontine angle tumor"],
    "glioblastoma": [
        "GBM",
        "glioblastoma multiforme",
        "grade IV astrocytoma",
        "high-grade glioma",
    ],
    "meningioma": ["meningeal tumor", "dural tumor"],
    "pituitary adenoma": [
        "pituitary tumor",
        "sellar mass",
        "pituitary macroadenoma",
        "pituitary microadenoma",
    ],
    "craniopharyngioma": ["suprasellar tumor", "Rathke's pouch tumor"],
    "medulloblastoma": ["posterior fossa tumor", "cerebellar tumor"],
    "ependymoma": ["ventricular tumor", "fourth ventricle tumor"],
    "oligodendroglioma": ["oligodendroglial tumor", "low-grade glioma"],
    "astrocytoma": ["glial tumor", "glioma"],
    "metastasis": ["metastatic tumor", "brain metastases", "secondary tumor"],
    "hemangioblastoma": ["cerebellar hemangioblastoma", "von Hippel-Lindau tumor"],
}

# Vascular Pathology Synonyms
VASCULAR_SYNONYMS: Dict[str, List[str]] = {
    "aneurysm": ["cerebral aneurysm", "intracranial aneurysm", "berry aneurysm"],
    "AVM": ["arteriovenous malformation", "cerebral AVM", "brain AVM"],
    "cavernoma": ["cavernous malformation", "cavernous angioma", "cerebral cavernoma"],
    "dural fistula": ["dural arteriovenous fistula", "DAVF", "dural AVF"],
    "stroke": [
        "cerebrovascular accident",
        "CVA",
        "ischemic stroke",
        "hemorrhagic stroke",
    ],
    "SAH": ["subarachnoid hemorrhage", "aneurysmal hemorrhage"],
    "ICH": ["intracerebral hemorrhage", "intraparenchymal hemorrhage"],
    "SDH": ["subdural hematoma", "subdural hemorrhage"],
    "EDH": ["epidural hematoma", "extradural hematoma"],
}

# Spinal Pathology Synonyms
SPINAL_SYNONYMS: Dict[str, List[str]] = {
    "herniated disc": [
        "disc herniation",
        "HNP",
        "herniated nucleus pulposus",
        "ruptured disc",
    ],
    "spinal stenosis": ["canal stenosis", "central stenosis", "foraminal stenosis"],
    "spondylolisthesis": ["vertebral slip", "degenerative spondylolisthesis"],
    "chiari malformation": ["Chiari I", "Chiari II", "tonsillar herniation"],
    "syringomyelia": ["syrinx", "spinal cord cyst"],
    "spinal cord injury": ["SCI", "traumatic myelopathy", "cord trauma"],
    "myelopathy": ["spinal cord compression", "cervical myelopathy"],
}

# Surgical Approach Synonyms
APPROACH_SYNONYMS: Dict[str, List[str]] = {
    "pterional": ["frontotemporal", "pterional craniotomy", "frontotemporal approach"],
    "retrosigmoid": ["lateral suboccipital", "retromastoid", "retrosigmoid approach"],
    "orbitozygomatic": ["OZ approach", "orbitozygomatic craniotomy"],
    "transsphenoidal": ["endoscopic endonasal", "transsphenoidal approach", "TSS"],
    "far lateral": ["extreme lateral", "transcondylar"],
    "midline suboccipital": ["posterior fossa craniotomy", "suboccipital craniectomy"],
    "anterior cervical": ["ACDF", "anterior cervical discectomy", "Smith-Robinson"],
    "posterior cervical": ["laminectomy", "laminoplasty", "posterior decompression"],
    "TLIF": ["transforaminal lumbar interbody fusion", "transforaminal fusion"],
    "PLIF": ["posterior lumbar interbody fusion", "posterior fusion"],
    "ALIF": ["anterior lumbar interbody fusion", "anterior fusion"],
}

# Surgical Procedure Synonyms
PROCEDURE_SYNONYMS: Dict[str, List[str]] = {
    "craniotomy": ["cranial opening", "bone flap", "skull opening"],
    "craniectomy": ["decompressive craniectomy", "bone removal", "DC"],
    "aneurysm clipping": [
        "microsurgical clipping",
        "clip ligation",
        "aneurysm obliteration",
    ],
    "tumor resection": [
        "tumor removal",
        "excision",
        "gross total resection",
        "GTR",
        "subtotal resection",
    ],
    "microvascular decompression": [
        "MVD",
        "Jannetta procedure",
        "neurovascular decompression",
    ],
    "ventriculostomy": ["EVD", "external ventricular drain", "ventricular catheter"],
    "VP shunt": ["ventriculoperitoneal shunt", "CSF shunt", "shunt placement"],
    "laminectomy": ["decompression", "posterior decompression", "laminotomy"],
    "discectomy": ["disc removal", "microdiscectomy", "disc excision"],
    "spinal fusion": ["arthrodesis", "instrumented fusion", "spinal stabilization"],
    "endoscopic third ventriculostomy": ["ETV", "third ventriculostomy"],
}

# Anatomical Structure Synonyms
ANATOMY_SYNONYMS: Dict[str, List[str]] = {
    "sylvian fissure": ["lateral sulcus", "Sylvian cistern"],
    "circle of Willis": ["cerebral arterial circle", "Willis polygon"],
    "foramen magnum": ["FM", "craniocervical junction"],
    "sella turcica": ["pituitary fossa", "sellar region"],
    "cavernous sinus": ["CS", "lateral sellar compartment"],
    "internal carotid artery": ["ICA", "carotid artery"],
    "middle cerebral artery": ["MCA", "M1", "M2"],
    "anterior communicating artery": ["ACoA", "AComm"],
    "posterior communicating artery": ["PCoA", "PComm"],
    "basilar artery": ["BA", "basilar trunk"],
}

# Clinical Condition Synonyms
CLINICAL_SYNONYMS: Dict[str, List[str]] = {
    "hydrocephalus": ["ventriculomegaly", "enlarged ventricles", "CSF accumulation"],
    "trigeminal neuralgia": ["TN", "tic douloureux", "facial pain"],
    "hemifacial spasm": ["HFS", "facial spasm"],
    "epilepsy": ["seizure disorder", "seizures", "intractable epilepsy"],
    "Parkinson's disease": ["PD", "parkinsonism", "movement disorder"],
    "essential tremor": ["ET", "benign tremor"],
    "normal pressure hydrocephalus": ["NPH", "communicating hydrocephalus"],
}

# Diagnostic/Imaging Synonyms
IMAGING_SYNONYMS: Dict[str, List[str]] = {
    "MRI": ["magnetic resonance imaging", "brain MRI", "MR imaging"],
    "CT": ["computed tomography", "CAT scan", "CT scan"],
    "angiography": ["DSA", "digital subtraction angiography", "cerebral angiogram"],
    "CTA": ["CT angiography", "computed tomography angiography"],
    "MRA": ["MR angiography", "magnetic resonance angiography"],
}

# =============================================================================
# COMBINED SYNONYM DICTIONARIES
# =============================================================================

# Original domain-specific synonyms
DOMAIN_SYNONYMS: Dict[str, List[str]] = {
    **TUMOR_SYNONYMS,
    **VASCULAR_SYNONYMS,
    **SPINAL_SYNONYMS,
    **APPROACH_SYNONYMS,
    **PROCEDURE_SYNONYMS,
    **ANATOMY_SYNONYMS,
    **CLINICAL_SYNONYMS,
    **IMAGING_SYNONYMS,
}

# Extracted procedural/technical synonyms
PROCEDURAL_SYNONYMS: Dict[str, List[str]] = {
    **INSTRUMENT_SYNONYMS,
    **POSITIONING_TERMS,
    **HEMOSTATIC_AGENTS,
    **TISSUE_DESCRIPTORS,
    **IMAGING_INTRAOP,
    **SURGICAL_PHASES,
}

# Combine all synonym dictionaries (for backward compatibility)
ALL_SYNONYMS: Dict[str, List[str]] = {
    **DOMAIN_SYNONYMS,
    **PROCEDURAL_SYNONYMS,
}


# =============================================================================
# ENHANCED QUERY EXPANSION FUNCTIONS
# =============================================================================


def expand_query(
    query: str,
    max_expansions: int = 5,
    include_orthographic: bool = True,
    include_monitoring: bool = True,
    include_complications: bool = True,
) -> List[str]:
    """
    Expand a query with neurosurgical synonyms (enhanced version).

    This enhanced function includes:
    - Standard synonym expansion
    - Orthographic variations (British/American spellings)
    - Neuromonitoring term expansion with context
    - Complication term expansion with types and context

    Args:
        query: Original search query
        max_expansions: Maximum number of synonym expansions to add
        include_orthographic: Include British/American spelling variants
        include_monitoring: Expand neuromonitoring acronyms with context
        include_complications: Expand complication terms with context

    Returns:
        List of query variations including original
    """
    query_lower = query.lower()
    expanded = [query]  # Always include original
    seen_lower = {query_lower}

    def add_expansion(exp: str) -> None:
        """Helper to add unique expansions."""
        exp_lower = exp.lower()
        if exp_lower not in seen_lower and exp.strip():
            expanded.append(exp)
            seen_lower.add(exp_lower)

    # 1. Apply orthographic variations first (disc/disk, tumour/tumor, etc.)
    if include_orthographic:
        for word in query_lower.split():
            variants = get_orthographic_variants(word)
            for variant in variants:
                if variant.lower() != word:
                    orthographic_query = query_lower.replace(word, variant.lower())
                    add_expansion(orthographic_query)

    # 2. Expand neuromonitoring terms (BAER, SSEP, MEP, EMG)
    if include_monitoring:
        for word in query.upper().split():
            if word in NEUROMONITORING_TERMS:
                monitoring_expansions = expand_with_monitoring_context(word)
                for exp in monitoring_expansions[1:]:  # Skip original
                    # Replace the acronym with full name or context term
                    monitoring_query = query_lower.replace(word.lower(), exp.lower())
                    add_expansion(monitoring_query)

    # 3. Expand complication terms
    if include_complications:
        complication_expansions = expand_with_complication_context(query)
        for exp in complication_expansions[1:]:  # Skip original
            if exp.lower() != query_lower:
                add_expansion(exp)

    # 4. Standard synonym expansion
    for term, synonyms in ALL_SYNONYMS.items():
        if term.lower() in query_lower:
            for synonym in synonyms[:max_expansions]:
                synonym_query = query_lower.replace(term.lower(), synonym.lower())
                add_expansion(synonym_query)

    return expanded[: max_expansions + 1]  # Limit total expansions


def expand_query_simple(query: str, max_expansions: int = 3) -> List[str]:
    """
    Simple query expansion (original behavior for backward compatibility).

    Args:
        query: Original search query
        max_expansions: Maximum number of synonym expansions to add

    Returns:
        List of query variations including original
    """
    query_lower = query.lower()
    expanded = [query]

    for term, synonyms in ALL_SYNONYMS.items():
        if term.lower() in query_lower:
            for synonym in synonyms[:max_expansions]:
                expanded_query = query_lower.replace(term.lower(), synonym.lower())
                if expanded_query not in [e.lower() for e in expanded]:
                    expanded.append(expanded_query)

    return expanded[: max_expansions + 1]


def get_all_terms_for_query(query: str, include_orthographic: bool = True) -> Set[str]:
    """
    Get all related terms (original + all synonyms) for a query.

    Useful for comprehensive keyword search across all variations.

    Args:
        query: Search query
        include_orthographic: Include spelling variants

    Returns:
        Set of all related terms
    """
    query_lower = query.lower()
    terms = {query_lower}

    # Add orthographic variants
    if include_orthographic:
        for word in query_lower.split():
            terms.update(v.lower() for v in get_orthographic_variants(word))

    # Find all matching terms and their synonyms
    for term, synonyms in ALL_SYNONYMS.items():
        if term.lower() in query_lower:
            terms.add(term.lower())
            terms.update(s.lower() for s in synonyms)

    # Add neuromonitoring expansions
    for word in query.upper().split():
        if word in NEUROMONITORING_TERMS:
            terms.update(e.lower() for e in expand_with_monitoring_context(word))

    # Add complication expansions
    terms.update(e.lower() for e in expand_with_complication_context(query))

    return terms


def is_neurosurgical_term(term: str) -> bool:
    """
    Check if a term is a known neurosurgical term.

    Args:
        term: Term to check

    Returns:
        True if term is in synonym dictionary
    """
    term_lower = term.lower()

    # Check if it's a key
    if term_lower in [k.lower() for k in ALL_SYNONYMS.keys()]:
        return True

    # Check if it's a synonym
    for synonyms in ALL_SYNONYMS.values():
        if term_lower in [s.lower() for s in synonyms]:
            return True

    # Check neuromonitoring terms
    if term.upper() in NEUROMONITORING_TERMS:
        return True

    # Check complication terms
    if term_lower in [k.lower() for k in COMPLICATION_TERMS.keys()]:
        return True

    return False


def get_orthographic_expansion(query: str) -> List[str]:
    """
    Get only orthographic (spelling) variations of a query.

    Handles British/American spelling differences like:
    - disc/disk
    - tumour/tumor
    - haematoma/hematoma

    Args:
        query: Original search query

    Returns:
        List of spelling variations including original
    """
    query_lower = query.lower()
    expansions = [query]
    seen = {query_lower}

    for word in query_lower.split():
        variants = get_orthographic_variants(word)
        for variant in variants:
            if variant.lower() != word:
                new_query = query_lower.replace(word, variant.lower())
                if new_query not in seen:
                    expansions.append(new_query)
                    seen.add(new_query)

    return expansions


def get_instrument_synonyms(instrument: str) -> List[str]:
    """Get synonyms for a surgical instrument."""
    instrument_lower = instrument.lower()
    if instrument_lower in INSTRUMENT_SYNONYMS:
        return [instrument] + INSTRUMENT_SYNONYMS[instrument_lower]
    return [instrument]


def get_monitoring_expansion(acronym: str) -> Dict:
    """
    Get full expansion for a neuromonitoring acronym.

    Returns dict with 'full', 'synonyms', and 'context' keys.
    """
    acronym_upper = acronym.upper()
    if acronym_upper in NEUROMONITORING_TERMS:
        return {"term": acronym, **NEUROMONITORING_TERMS[acronym_upper]}
    return {"term": acronym, "full": None, "synonyms": [], "context": []}
