"""Comprehensive tests for figure integration pipeline components.

These tests verify the figure-text integration system including:
- Data models (PlacementType, MatchMethod, PositionedFigure, FigureLibrary)
- FigurePlaceholderResolver
- SemanticImageMatcher
- ProceduralStepCorrelator
- PositionOptimizer
- FigureIntegrationPipeline

All tests mock external dependencies (Qdrant, LLM) per coding guidelines.
"""

from unittest.mock import MagicMock

import pytest

from neurosynth.models.visual import ImageType, VisualElement
from neurosynth.synthesis.figure_integration import (
    ChapterFigureResolution,
    FigureIntegrationConfig,
    FigureIntegrationPipeline,
)
from neurosynth.synthesis.figure_resolver import FigurePlaceholderResolver
from neurosynth.synthesis.position_optimizer import (
    PositionOptimizer,
    PositionOptimizerConfig,
)
from neurosynth.synthesis.positioned_figure import (
    FigureLibrary,
    MatchMethod,
    PlaceholderMatch,
    PlacementType,
    PositionedFigure,
    ProceduralMatch,
    SectionFigureResolution,
)
from neurosynth.synthesis.procedural_correlator import ProceduralStepCorrelator
from neurosynth.synthesis.semantic_matcher import (
    SemanticImageMatcher,
    SemanticMatcherConfig,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_visual_surgical():
    """Create a sample surgical step VisualElement."""
    return VisualElement(
        id="vis_surgical_001",
        format="png",
        caption="Step 1: Initial incision through the fascia",
        image_type=ImageType.SURGICAL_STEP,
        is_procedural=True,
        sequence_id="seq_approach",
        sequence_position=1,
        step_label="Step 1",
        keywords_matched=["incision", "fascia", "surgical"],
        context_text="The surgeon makes the initial incision",
    )


@pytest.fixture
def sample_visual_anatomical():
    """Create a sample anatomical VisualElement."""
    return VisualElement(
        id="vis_anat_001",
        format="png",
        caption="Anatomical relationship of the facial nerve",
        image_type=ImageType.ANATOMICAL,
        is_procedural=False,
        keywords_matched=["facial nerve", "anatomy", "relationship"],
        context_text="Critical anatomy for safe dissection",
    )


@pytest.fixture
def sample_visual_imaging():
    """Create a sample imaging VisualElement."""
    return VisualElement(
        id="vis_img_001",
        format="png",
        caption="T2-weighted MRI showing tumor extent",
        image_type=ImageType.IMAGING,
        is_procedural=False,
        keywords_matched=["MRI", "T2", "tumor"],
        context_text="Preoperative imaging assessment",
    )


@pytest.fixture
def sample_visual_list(
    sample_visual_surgical, sample_visual_anatomical, sample_visual_imaging
):
    """Create a list of sample VisualElements."""
    return [sample_visual_surgical, sample_visual_anatomical, sample_visual_imaging]


@pytest.fixture
def procedural_sequence():
    """Create a sequence of procedural images."""
    return [
        VisualElement(
            id=f"vis_step_{i}",
            format="png",
            caption=f"Step {i}: Surgical procedure step {i}",
            image_type=ImageType.SURGICAL_STEP,
            is_procedural=True,
            sequence_id="main_procedure",
            sequence_position=i,
            step_label=f"Step {i}",
            keywords_matched=["surgical", "step", "procedure"],
        )
        for i in range(1, 5)
    ]


# =============================================================================
# PlacementType and MatchMethod Enum Tests
# =============================================================================


class TestPlacementTypeEnum:
    """Tests for PlacementType enumeration."""

    def test_placement_type_values(self):
        """Verify all PlacementType values."""
        assert PlacementType.INLINE_AFTER.value == "inline_after"
        assert PlacementType.FLOAT_TOP.value == "float_top"
        assert PlacementType.SUBFIGURE.value == "subfigure"
        assert PlacementType.PLATE.value == "plate"
        assert PlacementType.UNASSIGNED.value == "unassigned"

    def test_placement_type_is_str_enum(self):
        """PlacementType should be a string enum."""
        assert isinstance(PlacementType.INLINE_AFTER, str)
        assert PlacementType.INLINE_AFTER == "inline_after"


class TestMatchMethodEnum:
    """Tests for MatchMethod enumeration."""

    def test_match_method_values(self):
        """Verify all MatchMethod values."""
        assert MatchMethod.ID_MATCH.value == "id_match"
        assert MatchMethod.SEMANTIC.value == "semantic"
        assert MatchMethod.PROCEDURAL.value == "procedural"
        assert MatchMethod.KEYWORD.value == "keyword"
        assert MatchMethod.PRIORITY.value == "priority"

    def test_match_method_is_str_enum(self):
        """MatchMethod should be a string enum."""
        assert isinstance(MatchMethod.SEMANTIC, str)
        assert MatchMethod.SEMANTIC == "semantic"


# =============================================================================
# PositionedFigure and SectionFigureResolution Tests
# =============================================================================


class TestPositionedFigure:
    """Tests for PositionedFigure dataclass."""

    def test_positioned_figure_creation(self, sample_visual_surgical):
        """Test basic PositionedFigure creation."""
        pf = PositionedFigure(
            visual=sample_visual_surgical,
            anchor_paragraph_index=2,
            placement_type=PlacementType.INLINE_AFTER,
            match_method=MatchMethod.ID_MATCH,
            match_confidence=0.95,
        )

        assert pf.visual.id == "vis_surgical_001"
        assert pf.anchor_paragraph_index == 2
        assert pf.placement_type == PlacementType.INLINE_AFTER
        assert pf.match_method == MatchMethod.ID_MATCH
        assert pf.match_confidence == 0.95

    def test_positioned_figure_with_subfigure(self, sample_visual_surgical):
        """Test PositionedFigure with subfigure grouping."""
        pf = PositionedFigure(
            visual=sample_visual_surgical,
            anchor_paragraph_index=0,
            placement_type=PlacementType.SUBFIGURE,
            match_method=MatchMethod.PROCEDURAL,
            match_confidence=0.85,
            subfigure_group_id="proc_1_3",
            subfigure_label="a",
        )

        assert pf.subfigure_group_id == "proc_1_3"
        assert pf.subfigure_label == "a"
        assert pf.placement_type == PlacementType.SUBFIGURE

    def test_positioned_figure_defaults(self, sample_visual_surgical):
        """Test PositionedFigure default values."""
        pf = PositionedFigure(visual=sample_visual_surgical)

        assert pf.anchor_paragraph_index is None
        assert pf.placement_type == PlacementType.PLATE
        assert pf.match_method == MatchMethod.PRIORITY
        assert pf.match_confidence == 0.0
        assert pf.resolved_placeholder is None
        assert pf.subfigure_group_id is None
        assert pf.subfigure_label is None


class TestSectionFigureResolution:
    """Tests for SectionFigureResolution dataclass."""

    def test_section_resolution_empty(self):
        """Test empty SectionFigureResolution."""
        resolution = SectionFigureResolution(
            section_title="Test Section",
            raw_text="Some raw text",
            resolved_text="Some resolved text",
        )

        assert resolution.inline_count == 0
        assert resolution.plate_count == 0
        assert resolution.total_positioned == 0
        assert len(resolution.positioned_figures) == 0

    def test_section_resolution_with_figures(
        self, sample_visual_surgical, sample_visual_anatomical
    ):
        """Test SectionFigureResolution with positioned figures."""
        pf_inline = PositionedFigure(
            visual=sample_visual_surgical,
            placement_type=PlacementType.INLINE_AFTER,
        )
        pf_plate = PositionedFigure(
            visual=sample_visual_anatomical,
            placement_type=PlacementType.PLATE,
        )

        resolution = SectionFigureResolution(
            section_title="Test Section",
            raw_text="Raw",
            resolved_text="Resolved",
            positioned_figures=[pf_inline, pf_plate],
        )

        assert resolution.inline_count == 1
        assert resolution.plate_count == 1
        assert resolution.total_positioned == 2

    def test_section_resolution_subfigures_count_inline(self, procedural_sequence):
        """Subfigures should count as inline figures."""
        pf_subfig = PositionedFigure(
            visual=procedural_sequence[0],
            placement_type=PlacementType.SUBFIGURE,
        )

        resolution = SectionFigureResolution(
            section_title="Test",
            raw_text="",
            resolved_text="",
            positioned_figures=[pf_subfig],
        )

        assert resolution.inline_count == 1
        assert resolution.plate_count == 0


# =============================================================================
# FigureLibrary Tests
# =============================================================================


class TestFigureLibrary:
    """Tests for FigureLibrary class."""

    def test_figure_library_empty(self):
        """Test empty FigureLibrary."""
        lib = FigureLibrary()

        assert lib.unused_count == 0
        assert lib.used_count == 0
        assert len(lib.unused_figures) == 0
        assert len(lib.used_figures) == 0

    def test_figure_library_with_figures(self, sample_visual_list):
        """Test FigureLibrary with figures."""
        lib = FigureLibrary(all_figures=sample_visual_list)

        assert lib.unused_count == 3
        assert lib.used_count == 0
        assert len(lib.unused_figures) == 3

    def test_figure_library_mark_used(self, sample_visual_list):
        """Test marking figures as used."""
        lib = FigureLibrary(all_figures=sample_visual_list)

        lib.mark_used("vis_surgical_001")

        assert lib.used_count == 1
        assert lib.unused_count == 2
        assert "vis_surgical_001" in lib.used_figure_ids
        assert len(lib.used_figures) == 1
        assert lib.used_figures[0].id == "vis_surgical_001"

    def test_figure_library_get_unused_by_type(self, sample_visual_list):
        """Test filtering unused figures by type."""
        lib = FigureLibrary(all_figures=sample_visual_list)

        surgical = lib.get_unused_by_type("surgical_step")
        anatomical = lib.get_unused_by_type("anatomical")
        imaging = lib.get_unused_by_type("imaging")

        assert len(surgical) == 1
        assert len(anatomical) == 1
        assert len(imaging) == 1

    def test_figure_library_get_unused_by_type_after_mark(self, sample_visual_list):
        """Test filtering excludes used figures."""
        lib = FigureLibrary(all_figures=sample_visual_list)
        lib.mark_used("vis_surgical_001")

        surgical = lib.get_unused_by_type("surgical_step")

        assert len(surgical) == 0

    def test_figure_library_mark_used_idempotent(self, sample_visual_list):
        """Marking same figure twice should be idempotent."""
        lib = FigureLibrary(all_figures=sample_visual_list)

        lib.mark_used("vis_surgical_001")
        lib.mark_used("vis_surgical_001")

        assert lib.used_count == 1


# =============================================================================
# FigurePlaceholderResolver Tests
# =============================================================================


class TestFigurePlaceholderResolver:
    """Tests for FigurePlaceholderResolver class."""

    def test_resolver_init(self, sample_visual_list):
        """Test resolver initialization."""
        resolver = FigurePlaceholderResolver(sample_visual_list)

        assert len(resolver.visuals) == 3
        assert "vis_surgical_001" in resolver.visuals_by_id
        assert "surgical_step" in resolver.visuals_by_type

    def test_resolve_figure_id_placeholder(self, sample_visual_list):
        """Test resolving [FIGURE: ID] placeholders."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = "The incision is shown in [FIGURE: vis_surgical_001] below."

        matches, unresolved = resolver.resolve_placeholders(text)

        assert len(matches) == 1
        assert len(unresolved) == 0
        assert matches[0].resolved_visual.id == "vis_surgical_001"
        assert matches[0].match_method == MatchMethod.ID_MATCH
        assert matches[0].confidence == 1.0

    def test_resolve_figure_id_not_found(self, sample_visual_list):
        """Test unresolved [FIGURE: ID] placeholder."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = "See [FIGURE: nonexistent_id] for details."

        matches, unresolved = resolver.resolve_placeholders(text)

        assert len(matches) == 0
        assert len(unresolved) == 1
        assert "[FIGURE: nonexistent_id]" in unresolved[0]

    def test_resolve_image_desc_placeholder(self, sample_visual_list):
        """Test resolving [IMAGE: Type - Description] placeholders."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = "The anatomy is illustrated in [IMAGE: anatomical - facial nerve relationship]."

        matches, unresolved = resolver.resolve_placeholders(text)

        # Should find a match based on description keywords
        assert len(matches) == 1
        assert matches[0].match_method == MatchMethod.SEMANTIC

    def test_resolve_multiple_placeholders(self, sample_visual_list):
        """Test resolving multiple placeholders in text."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = """
        First, examine the MRI [FIGURE: vis_img_001].
        Then, note the anatomy [FIGURE: vis_anat_001].
        """

        matches, unresolved = resolver.resolve_placeholders(text)

        assert len(matches) == 2
        assert len(unresolved) == 0

    def test_strip_placeholders(self, sample_visual_list):
        """Test stripping all placeholders from text."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = "See [FIGURE: vis_surgical_001] and [IMAGE: anatomical - nerve] here."

        stripped = resolver.strip_placeholders(text)

        assert "[FIGURE:" not in stripped
        assert "[IMAGE:" not in stripped
        assert "See" in stripped
        assert "here" in stripped

    def test_get_placeholder_count(self, sample_visual_list):
        """Test counting placeholders by type."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = """
        [FIGURE: id1] [FIGURE: id2]
        [IMAGE: type - desc1] [IMAGE: type - desc2] [IMAGE: type - desc3]
        """

        counts = resolver.get_placeholder_count(text)

        assert counts["figure_id"] == 2
        assert counts["image_desc"] == 3

    def test_paragraph_index_calculation(self, sample_visual_list):
        """Test correct paragraph index calculation."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = """First paragraph here.

Second paragraph with [FIGURE: vis_surgical_001] placeholder.

Third paragraph here."""

        matches, _ = resolver.resolve_placeholders(text)

        assert len(matches) == 1
        assert matches[0].paragraph_index == 1  # Second paragraph (0-indexed)

    def test_case_insensitive_patterns(self, sample_visual_list):
        """Test that patterns are case-insensitive."""
        resolver = FigurePlaceholderResolver(sample_visual_list)
        text = "[figure: vis_surgical_001] and [FIGURE: vis_anat_001] and [Figure: vis_img_001]"

        matches, _ = resolver.resolve_placeholders(text)

        assert len(matches) == 3


# =============================================================================
# SemanticImageMatcher Tests
# =============================================================================


class TestSemanticImageMatcher:
    """Tests for SemanticImageMatcher class."""

    def test_matcher_init_default_config(self):
        """Test matcher initialization with default config."""
        matcher = SemanticImageMatcher()

        assert matcher.config.similarity_threshold == 0.4
        assert matcher.config.caption_weight == 0.40
        assert matcher.config.keyword_weight == 0.35

    def test_matcher_init_custom_config(self):
        """Test matcher initialization with custom config."""
        config = SemanticMatcherConfig(
            similarity_threshold=0.6,
            caption_weight=0.5,
        )
        matcher = SemanticImageMatcher(config)

        assert matcher.config.similarity_threshold == 0.6
        assert matcher.config.caption_weight == 0.5

    def test_match_paragraph_to_relevant_image(self, sample_visual_list):
        """Test matching a paragraph to a semantically relevant image."""
        # Use a lower threshold for this test
        config = SemanticMatcherConfig(similarity_threshold=0.2, min_paragraph_words=5)
        matcher = SemanticImageMatcher(config)
        # Use more keywords that match the visual's caption and keywords_matched
        paragraphs = [
            "The initial incision through the fascia is critical for proper exposure. "
            "This surgical step requires careful technique and precision."
        ]

        matches = matcher.match_paragraphs_to_images(paragraphs, sample_visual_list)

        # Should match an image based on keyword overlap
        assert len(matches) >= 1
        assert matches[0].paragraph_index == 0
        assert matches[0].score > 0.0

    def test_match_skip_short_paragraphs(self, sample_visual_list):
        """Test that short paragraphs are skipped."""
        config = SemanticMatcherConfig(min_paragraph_words=15)
        matcher = SemanticImageMatcher(config)
        paragraphs = ["Too short to match."]  # Only 4 words

        matches = matcher.match_paragraphs_to_images(paragraphs, sample_visual_list)

        assert len(matches) == 0

    def test_match_respects_threshold(self, sample_visual_list):
        """Test that matches below threshold are excluded."""
        config = SemanticMatcherConfig(similarity_threshold=0.99)
        matcher = SemanticImageMatcher(config)
        paragraphs = [
            "This paragraph has completely unrelated content about weather patterns."
        ]

        matches = matcher.match_paragraphs_to_images(paragraphs, sample_visual_list)

        assert len(matches) == 0

    def test_match_excludes_already_matched(self, sample_visual_list):
        """Test that already-matched IDs are excluded."""
        matcher = SemanticImageMatcher()
        paragraphs = [
            "The incision through the fascia is the first step of the surgical approach."
        ]
        already_matched = {"vis_surgical_001"}

        matches = matcher.match_paragraphs_to_images(
            paragraphs, sample_visual_list, already_matched
        )

        # Should not match the surgical image since it's already matched
        for m in matches:
            assert m.visual.id != "vis_surgical_001"

    def test_match_signals_populated(self, sample_visual_list):
        """Test that match signals are populated."""
        matcher = SemanticImageMatcher()
        paragraphs = [
            "The initial incision through the fascia requires careful technique."
        ]

        matches = matcher.match_paragraphs_to_images(paragraphs, sample_visual_list)

        if matches:
            assert "caption" in matches[0].match_signals
            assert "keyword" in matches[0].match_signals
            assert "type" in matches[0].match_signals
            assert "context" in matches[0].match_signals


# =============================================================================
# ProceduralStepCorrelator Tests
# =============================================================================


class TestProceduralStepCorrelator:
    """Tests for ProceduralStepCorrelator class."""

    def test_correlator_init(self):
        """Test correlator initialization."""
        correlator = ProceduralStepCorrelator()

        assert len(correlator.STEP_PATTERNS) > 0
        assert correlator.ORDINAL_MAP["first"] == 1

    def test_correlate_numbered_steps(self, procedural_sequence):
        """Test correlating numbered steps with procedural images."""
        correlator = ProceduralStepCorrelator()
        text = """
Step 1: Make the initial incision.

Step 2: Retract the muscle layer.

Step 3: Identify the target structure.
"""

        matches = correlator.correlate_steps(text, procedural_sequence)

        assert len(matches) >= 1
        # Steps should be correlated to images by position/label

    def test_correlate_dotted_steps(self, procedural_sequence):
        """Test correlating '1. ' '2. ' format steps."""
        correlator = ProceduralStepCorrelator()
        text = """
1. Make the initial incision.

2. Retract the muscle layer.

3. Identify the target structure.
"""

        matches = correlator.correlate_steps(text, procedural_sequence)

        assert len(matches) >= 1

    def test_correlate_ordinal_steps(self, procedural_sequence):
        """Test correlating ordinal word steps (First, Second, etc.)."""
        correlator = ProceduralStepCorrelator()
        text = """
First, make the initial incision.

Second, retract the muscle layer.

Third, identify the target structure.
"""

        matches = correlator.correlate_steps(text, procedural_sequence)

        assert len(matches) >= 1

    def test_correlate_empty_procedural_list(self):
        """Test with empty procedural visuals list."""
        correlator = ProceduralStepCorrelator()
        text = "Step 1: Some step."

        matches = correlator.correlate_steps(text, [])

        assert len(matches) == 0

    def test_correlate_no_steps_in_text(self, procedural_sequence):
        """Test with text containing no steps."""
        correlator = ProceduralStepCorrelator()
        text = "This text has no numbered or labeled steps whatsoever."

        matches = correlator.correlate_steps(text, procedural_sequence)

        assert len(matches) == 0

    def test_correlate_confidence_scores(self, procedural_sequence):
        """Test that confidence scores are assigned."""
        correlator = ProceduralStepCorrelator()
        text = """
Step 1: Make the initial incision.

Step 2: Retract the muscle layer.
"""

        matches = correlator.correlate_steps(text, procedural_sequence)

        for match in matches:
            assert 0.0 < match.confidence <= 1.0
            assert match.step_number > 0

    def test_correlate_paragraph_index(self, procedural_sequence):
        """Test paragraph index tracking."""
        correlator = ProceduralStepCorrelator()
        text = """Introduction paragraph.

Step 1: First step content.

Step 2: Second step content."""

        matches = correlator.correlate_steps(text, procedural_sequence)

        # Steps should have correct paragraph indices
        for match in matches:
            assert match.paragraph_index >= 0


# =============================================================================
# PositionOptimizer Tests
# =============================================================================


class TestPositionOptimizer:
    """Tests for PositionOptimizer class."""

    def test_optimizer_init_default_config(self):
        """Test optimizer initialization with default config."""
        optimizer = PositionOptimizer()

        assert optimizer.config.max_inline_per_section == 5
        assert optimizer.config.max_inline_per_paragraph == 2
        assert optimizer.config.group_subfigures is True

    def test_optimizer_init_custom_config(self):
        """Test optimizer initialization with custom config."""
        config = PositionOptimizerConfig(
            max_inline_per_section=10,
            max_inline_per_paragraph=3,
        )
        optimizer = PositionOptimizer(config)

        assert optimizer.config.max_inline_per_section == 10
        assert optimizer.config.max_inline_per_paragraph == 3

    def test_optimize_placeholder_matches(self, sample_visual_surgical):
        """Test optimizing placeholder matches (highest priority)."""
        optimizer = PositionOptimizer()

        placeholder_match = PlaceholderMatch(
            placeholder_text="[FIGURE: vis_surgical_001]",
            position=50,
            paragraph_index=1,
            resolved_visual=sample_visual_surgical,
            match_method=MatchMethod.ID_MATCH,
            confidence=1.0,
        )

        positioned = optimizer.optimize(
            placeholder_matches=[placeholder_match],
            semantic_matches=[],
            procedural_matches=[],
            section_word_count=500,
            available_visuals=[sample_visual_surgical],
        )

        assert len(positioned) == 1
        assert positioned[0].match_method == MatchMethod.ID_MATCH
        assert positioned[0].placement_type == PlacementType.INLINE_AFTER

    def test_optimize_respects_paragraph_limit(self, sample_visual_list):
        """Test that paragraph figure limit is respected."""
        config = PositionOptimizerConfig(max_inline_per_paragraph=1)
        optimizer = PositionOptimizer(config)

        # Two matches for same paragraph
        matches = [
            PlaceholderMatch(
                placeholder_text=f"[FIGURE: {v.id}]",
                position=i * 50,
                paragraph_index=0,  # Same paragraph
                resolved_visual=v,
                match_method=MatchMethod.ID_MATCH,
                confidence=1.0,
            )
            for i, v in enumerate(sample_visual_list[:2])
        ]

        positioned = optimizer.optimize(
            placeholder_matches=matches,
            semantic_matches=[],
            procedural_matches=[],
            section_word_count=500,
            available_visuals=sample_visual_list,
        )

        # Only one should be inline due to limit
        inline_count = sum(
            1 for p in positioned if p.placement_type == PlacementType.INLINE_AFTER
        )
        assert inline_count <= 1

    def test_optimize_groups_procedural_subfigures(self, procedural_sequence):
        """Test grouping consecutive procedural matches as subfigures."""
        config = PositionOptimizerConfig(
            group_subfigures=True,
            min_subfigure_group_size=2,
        )
        optimizer = PositionOptimizer(config)

        # Create procedural matches for consecutive steps
        procedural_matches = [
            ProceduralMatch(
                step_number=i + 1,
                paragraph_index=i,
                visual=procedural_sequence[i],
                sequence_id="main_procedure",
                confidence=0.85,
            )
            for i in range(3)
        ]

        positioned = optimizer.optimize(
            placeholder_matches=[],
            semantic_matches=[],
            procedural_matches=procedural_matches,
            section_word_count=1000,
            available_visuals=procedural_sequence,
        )

        # Should have subfigures
        subfigure_count = sum(
            1 for p in positioned if p.placement_type == PlacementType.SUBFIGURE
        )
        assert subfigure_count >= 2

    def test_optimize_adds_high_priority_to_plate(self, sample_visual_surgical):
        """Test that unused high-priority images go to plate."""
        config = PositionOptimizerConfig(include_high_priority_unused=True)
        optimizer = PositionOptimizer(config)

        positioned = optimizer.optimize(
            placeholder_matches=[],
            semantic_matches=[],
            procedural_matches=[],
            section_word_count=500,
            available_visuals=[sample_visual_surgical],
        )

        # Surgical step is high priority, should be in plate
        plate_count = sum(
            1 for p in positioned if p.placement_type == PlacementType.PLATE
        )
        assert plate_count >= 1

    def test_optimize_updates_visual_output_fields(self, sample_visual_surgical):
        """Test that visual output fields are updated."""
        optimizer = PositionOptimizer()

        placeholder_match = PlaceholderMatch(
            placeholder_text="[FIGURE: vis_surgical_001]",
            position=50,
            paragraph_index=2,
            resolved_visual=sample_visual_surgical,
            match_method=MatchMethod.ID_MATCH,
            confidence=0.95,
        )

        optimizer.optimize(
            placeholder_matches=[placeholder_match],
            semantic_matches=[],
            procedural_matches=[],
            section_word_count=500,
            available_visuals=[sample_visual_surgical],
        )

        # Check that visual's output fields were updated
        assert sample_visual_surgical.output_anchor_paragraph == 2
        assert sample_visual_surgical.output_placement == "inline_after"
        assert sample_visual_surgical.output_match_method == "id_match"
        assert sample_visual_surgical.output_match_confidence == 0.95


# =============================================================================
# FigureIntegrationPipeline Tests
# =============================================================================


class TestFigureIntegrationPipeline:
    """Tests for FigureIntegrationPipeline class."""

    def test_pipeline_init(self, sample_visual_list):
        """Test pipeline initialization."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)

        assert len(pipeline.visuals) == 3
        assert pipeline.placeholder_resolver is not None
        assert pipeline.semantic_matcher is not None
        assert pipeline.procedural_correlator is not None
        assert pipeline.position_optimizer is not None

    def test_pipeline_init_custom_config(self, sample_visual_list):
        """Test pipeline initialization with custom config."""
        config = FigureIntegrationConfig(
            semantic_threshold=0.6,
            enable_semantic_matching=False,
        )
        pipeline = FigureIntegrationPipeline(sample_visual_list, config)

        assert pipeline.config.semantic_threshold == 0.6
        assert pipeline.config.enable_semantic_matching is False

    def test_pipeline_get_figure_library(self, sample_visual_list):
        """Test getting the figure library."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        library = pipeline.get_figure_library()

        assert isinstance(library, FigureLibrary)
        assert library.unused_count == 3

    def test_pipeline_split_paragraphs(self, sample_visual_list):
        """Test paragraph splitting."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        text = """First paragraph here.

Second paragraph here.

Third paragraph here."""

        paragraphs = pipeline._split_paragraphs(text)

        assert len(paragraphs) == 3
        assert "First" in paragraphs[0]
        assert "Second" in paragraphs[1]
        assert "Third" in paragraphs[2]

    def test_pipeline_split_paragraphs_filters_empty(self, sample_visual_list):
        """Test that empty paragraphs are filtered."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        text = """First paragraph.



Second paragraph."""

        paragraphs = pipeline._split_paragraphs(text)

        assert len(paragraphs) == 2


class TestFigureIntegrationPipelineResolveSection:
    """Tests for FigureIntegrationPipeline.resolve_section method."""

    @pytest.fixture
    def mock_section(self):
        """Create a mock Section object."""
        section = MagicMock()
        section.title = "Surgical Technique"
        section.content = """
Introduction paragraph about surgical technique.

[FIGURE: vis_surgical_001]

The incision is made through the fascia layer carefully.

Step 1: Make the initial incision through skin.

Step 2: Retract the muscle layer gently.
"""
        section.word_count = 50
        return section

    def test_resolve_section_with_placeholders(self, sample_visual_list, mock_section):
        """Test resolving a section with figure placeholders."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        used_ids: set[str] = set()

        resolution = pipeline.resolve_section(mock_section, used_ids)

        assert resolution.section_title == "Surgical Technique"
        assert "[FIGURE:" not in resolution.resolved_text
        # Should have resolved the placeholder
        assert len(resolution.positioned_figures) >= 1

    def test_resolve_section_marks_used(self, sample_visual_list, mock_section):
        """Test that resolved figures are marked as used."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        used_ids: set[str] = set()

        resolution = pipeline.resolve_section(mock_section, used_ids)

        # used_ids should be updated
        assert len(used_ids) > 0
        # Library should reflect usage
        assert pipeline.figure_library.used_count > 0
        # Resolution should have content
        assert resolution.section_title == "Surgical Technique"

    def test_resolve_section_empty_content(self, sample_visual_list):
        """Test resolving a section with empty content."""
        pipeline = FigureIntegrationPipeline(sample_visual_list)
        section = MagicMock()
        section.title = "Empty Section"
        section.content = ""
        section.word_count = 0

        resolution = pipeline.resolve_section(section, set())

        assert resolution.section_title == "Empty Section"
        assert resolution.resolved_text == ""
        assert len(resolution.positioned_figures) == 0

    def test_resolve_section_respects_disabled_features(
        self, sample_visual_list, mock_section
    ):
        """Test that disabled features are skipped."""
        config = FigureIntegrationConfig(
            enable_semantic_matching=False,
            enable_procedural_correlation=False,
            enable_placeholder_resolution=True,
        )
        pipeline = FigureIntegrationPipeline(sample_visual_list, config)

        resolution = pipeline.resolve_section(mock_section, set())

        # Should still work, just with fewer match sources
        assert resolution.section_title == "Surgical Technique"


class TestChapterFigureResolution:
    """Tests for ChapterFigureResolution dataclass."""

    def test_chapter_resolution_empty(self):
        """Test empty ChapterFigureResolution."""
        resolution = ChapterFigureResolution()

        assert len(resolution.section_resolutions) == 0
        assert resolution.total_positioned == 0
        assert resolution.total_unresolved_placeholders == 0
        assert resolution.unused_count == 0

    def test_chapter_resolution_unused_count_from_library(self, sample_visual_list):
        """Test unused_count property uses library."""
        library = FigureLibrary(all_figures=sample_visual_list)
        library.mark_used("vis_surgical_001")

        resolution = ChapterFigureResolution(
            figure_library=library,
            total_positioned=1,
        )

        assert resolution.unused_count == 2
