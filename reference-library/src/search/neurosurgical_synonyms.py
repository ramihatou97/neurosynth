"""Neurosurgical terminology synonym dictionary for query expansion.

This module provides comprehensive synonym mappings for neurosurgical terms
to improve search recall by expanding queries with related terminology.
"""

from typing import Dict, List, Set


# Tumor/Pathology Synonyms
TUMOR_SYNONYMS: Dict[str, List[str]] = {
    "acoustic neuroma": ["vestibular schwannoma", "VS", "cerebellopontine angle tumor", "CPA tumor"],
    "vestibular schwannoma": ["acoustic neuroma", "VS", "cerebellopontine angle tumor"],
    "glioblastoma": ["GBM", "glioblastoma multiforme", "grade IV astrocytoma", "high-grade glioma"],
    "meningioma": ["meningeal tumor", "dural tumor"],
    "pituitary adenoma": ["pituitary tumor", "sellar mass", "pituitary macroadenoma", "pituitary microadenoma"],
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
    "stroke": ["cerebrovascular accident", "CVA", "ischemic stroke", "hemorrhagic stroke"],
    "SAH": ["subarachnoid hemorrhage", "aneurysmal hemorrhage"],
    "ICH": ["intracerebral hemorrhage", "intraparenchymal hemorrhage"],
    "SDH": ["subdural hematoma", "subdural hemorrhage"],
    "EDH": ["epidural hematoma", "extradural hematoma"],
}

# Spinal Pathology Synonyms
SPINAL_SYNONYMS: Dict[str, List[str]] = {
    "herniated disc": ["disc herniation", "HNP", "herniated nucleus pulposus", "ruptured disc"],
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
    "aneurysm clipping": ["microsurgical clipping", "clip ligation", "aneurysm obliteration"],
    "tumor resection": ["tumor removal", "excision", "gross total resection", "GTR", "subtotal resection"],
    "microvascular decompression": ["MVD", "Jannetta procedure", "neurovascular decompression"],
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

# Combine all synonym dictionaries
ALL_SYNONYMS: Dict[str, List[str]] = {
    **TUMOR_SYNONYMS,
    **VASCULAR_SYNONYMS,
    **SPINAL_SYNONYMS,
    **APPROACH_SYNONYMS,
    **PROCEDURE_SYNONYMS,
    **ANATOMY_SYNONYMS,
    **CLINICAL_SYNONYMS,
    **IMAGING_SYNONYMS,
}


def expand_query(query: str, max_expansions: int = 3) -> List[str]:
    """
    Expand a query with neurosurgical synonyms.

    Args:
        query: Original search query
        max_expansions: Maximum number of synonym expansions to add

    Returns:
        List of query variations including original
    """
    query_lower = query.lower()
    expanded = [query]  # Always include original

    # Find matching terms and add their synonyms
    for term, synonyms in ALL_SYNONYMS.items():
        if term.lower() in query_lower:
            # Add up to max_expansions synonyms
            for synonym in synonyms[:max_expansions]:
                # Replace the term with synonym in the query
                expanded_query = query_lower.replace(term.lower(), synonym.lower())
                if expanded_query not in [e.lower() for e in expanded]:
                    expanded.append(expanded_query)

    return expanded[:max_expansions + 1]  # Limit total expansions


def get_all_terms_for_query(query: str) -> Set[str]:
    """
    Get all related terms (original + all synonyms) for a query.

    Useful for comprehensive keyword search across all variations.

    Args:
        query: Search query

    Returns:
        Set of all related terms
    """
    query_lower = query.lower()
    terms = {query_lower}

    # Find all matching terms and their synonyms
    for term, synonyms in ALL_SYNONYMS.items():
        if term.lower() in query_lower:
            terms.add(term.lower())
            terms.update(s.lower() for s in synonyms)

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

    return False

