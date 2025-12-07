"""
Study Package - Universal Neurosurgical Knowledge System
=========================================================

Enhances BROAD mode search to include foundational knowledge
(anatomy, biomechanics, pathophysiology) for any neurosurgical topic.

Usage:
    from src.search.study_package import enhance_broad_results, analyze_query

    # In BROAD mode search:
    enhanced_results, report = enhance_broad_results(
        searcher, query, direct_results, semantic_results
    )

    # Check for library gaps
    if report.has_gaps:
        print(f"Missing topics: {report.missing_topics}")

    # Or analyze query alone:
    analysis = analyze_query("lumbar discectomy")
    print(analysis.region_tags)  # {'spine', 'lumbar'}
"""

from src.search.study_package.analyzer import (
    QueryAnalysis,
    QueryAnalyzer,
    analyze_query,
    get_analyzer,
    get_foundations_for_query,
)
from src.search.study_package.assembler import (
    StudyPackage,
    StudyPackageAssembler,
    StudyPackageResult,
    enhance_broad_results,
)
from src.search.study_package.report import StudyModeReport, TopicSource
from src.search.study_package.taxonomy import (
    KNOWLEDGE_CATEGORIES,
    NEUROSURGICAL_REGIONS,
    PROCEDURE_TO_REGION,
    REGION_FOUNDATIONS,
)

__all__ = [
    # Taxonomy
    "NEUROSURGICAL_REGIONS",
    "KNOWLEDGE_CATEGORIES",
    "PROCEDURE_TO_REGION",
    "REGION_FOUNDATIONS",
    # Analyzer
    "QueryAnalyzer",
    "QueryAnalysis",
    "get_analyzer",
    "analyze_query",
    "get_foundations_for_query",
    # Assembler
    "StudyPackageAssembler",
    "StudyPackage",
    "StudyPackageResult",
    "enhance_broad_results",
    # Report
    "StudyModeReport",
    "TopicSource",
]
