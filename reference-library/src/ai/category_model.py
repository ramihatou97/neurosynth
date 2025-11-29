"""Category definitions and models."""
from dataclasses import dataclass
from typing import Optional

from src import config


@dataclass
class CategoryResult:
    """Result of AI categorization with hierarchical group support."""
    group: str          # "Surgical/Anatomical" or "Theoretical"
    category: str       # Specific subcategory
    confidence: float
    reasoning: str
    cached: bool = False

    @property
    def color(self) -> str:
        """Get color for this category."""
        return config.CATEGORY_COLORS.get(self.category, config.CATEGORY_COLORS["Other"])

    @property
    def group_color(self) -> str:
        """Get color for the parent group."""
        group_data = config.CATEGORY_GROUPS.get(self.group)
        return group_data["color"] if group_data else "#95a5a6"

    @property
    def confidence_label(self) -> str:
        """Human-readable confidence label."""
        if self.confidence >= 0.8:
            return "High"
        elif self.confidence >= 0.5:
            return "Medium"
        else:
            return "Low"

    @property
    def display_label(self) -> str:
        """Full display label with group prefix."""
        return f"{self.group}: {self.category}"


# Category descriptions for UI tooltips (updated for hierarchical system)
CATEGORY_DESCRIPTIONS = {
    # Surgical/Anatomical subcategories
    "Preoperative Planning": "Image review, approach selection, equipment preparation",
    "Anesthetic Considerations": "Airway, positioning concerns, neuromonitoring setup",
    "Patient Positioning": "Supine, prone, lateral, park bench, head fixation",
    "Surgical Approach": "Incision, soft tissue dissection, craniotomy/laminectomy, dural opening",
    "Anatomical Landmarks": "Surface anatomy, vascular landmarks, neural identification",
    "Surgical Technique": "Primary maneuver - resection, decompression, clipping, tumor removal",
    "Reconstruction": "Fusion, instrumentation, grafting, dural repair",
    "Closure": "Layer-by-layer closure, drain placement, wound management",
    "Intraoperative Monitoring": "SSEP, MEP, EMG, ECoG, vascular monitoring",
    "Technical Pitfalls": "Common errors, avoidance strategies, bailout procedures",

    # Theoretical subcategories
    "Definition & Classification": "Terminology, grading systems, ICD codes, nomenclature",
    "Epidemiology": "Incidence, prevalence, risk factors, demographics, natural history",
    "Pathophysiology": "Disease mechanisms, molecular/cellular changes, histopathology",
    "Clinical Presentation": "Symptoms, signs, neurological examination findings",
    "Diagnostic Evaluation": "Imaging, labs, electrodiagnostics, tissue diagnosis",
    "Differential Diagnosis": "Clinical mimics, imaging differentials, diagnostic algorithms",
    "Treatment Options": "Conservative management, indications for surgery, alternatives",
    "Postoperative Management": "ICU care, floor care, rehabilitation, discharge",
    "Complications": "Intraoperative, early postoperative, late complications",
    "Outcomes": "Short-term, long-term, quality of life, prognostic factors",
    "Future Directions": "Emerging technologies, ongoing research, controversies",

    "Other": "Content not fitting other categories"
}
