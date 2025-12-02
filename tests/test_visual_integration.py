"""Tests for visual integration modules.

These tests verify that the visual processing pipeline components
can be imported and instantiated correctly.
"""

# ============================================================================
# Model Import Tests
# ============================================================================


class TestVisualModelsImport:
    """Test that visual model classes can be imported."""

    def test_image_type_enum_import(self):
        """Test ImageType enum import and values."""
        from neurosynth.models.visual import ImageType

        assert ImageType.SURGICAL_STEP == "surgical_step"
        assert ImageType.ANATOMICAL == "anatomical"
        assert ImageType.IMAGING == "imaging"
        assert ImageType.TABLE == "table"
        assert ImageType.UNKNOWN == "unknown"

    def test_visual_element_import(self):
        """Test VisualElement dataclass import."""
        from neurosynth.models.visual import VisualElement

        # Create a basic instance
        element = VisualElement()
        assert element.id is not None
        assert element.format == "png"
        assert element.caption == ""

    def test_figure_plate_import(self):
        """Test FigurePlate dataclass import."""
        from neurosynth.models.visual import FigurePlate, VisualElement

        plate = FigurePlate(section_title="Test Section")
        assert plate.count == 0
        assert plate.is_empty

        # Add a figure
        elem = VisualElement()
        plate.add_figure(elem)
        assert plate.count == 1
        assert not plate.is_empty

    def test_visual_index_import(self):
        """Test VisualIndex class import."""
        from neurosynth.models.visual import ImageType, VisualElement, VisualIndex

        index = VisualIndex()
        assert index.total_count == 0

        # Add an element
        elem = VisualElement(image_type=ImageType.SURGICAL_STEP)
        index.add(elem)
        assert index.total_count == 1
        assert elem.id in index.by_id


# ============================================================================
# Image Extractor Tests
# ============================================================================


class TestImageExtractorImport:
    """Test that image extractor can be imported."""

    def test_image_extractor_import(self):
        """Test ImageExtractor class import."""
        from neurosynth.parsers.image_extractor import ImageExtractor

        # Class should be importable
        assert ImageExtractor is not None

    def test_image_extractor_instantiation(self):
        """Test ImageExtractor can be instantiated."""
        from neurosynth.parsers.image_extractor import ImageExtractor

        extractor = ImageExtractor()
        assert extractor is not None
        assert extractor.min_size == 100
        assert extractor.max_size == 4096

    def test_image_extractor_has_figure_patterns(self):
        """Test ImageExtractor has figure caption patterns."""
        from neurosynth.parsers.image_extractor import ImageExtractor

        extractor = ImageExtractor()
        # FIGURE_PATTERNS is a class-level constant
        assert hasattr(extractor, "FIGURE_PATTERNS")
        assert len(extractor.FIGURE_PATTERNS) > 0


# ============================================================================
# ColPali Client Tests
# ============================================================================


class TestColPaliClientImport:
    """Test that ColPali client can be imported."""

    def test_colpali_client_import(self):
        """Test ColPaliClient class import."""
        from neurosynth.llm.colpali import ColPaliClient

        assert ColPaliClient is not None

    def test_get_colpali_client_import(self):
        """Test get_colpali_client function import."""
        from neurosynth.llm.colpali import get_colpali_client

        assert callable(get_colpali_client)

    def test_colpali_client_instantiation(self):
        """Test ColPaliClient can be instantiated (model loads lazily)."""
        from neurosynth.llm.colpali import ColPaliClient

        # Reset singleton for clean test
        ColPaliClient._instance = None
        ColPaliClient._initialized = False

        # Client should be instantiable - model loads lazily on first use
        client = ColPaliClient()
        assert client is not None
        assert client.model_name is not None


# ============================================================================
# Qdrant Store Tests
# ============================================================================


class TestQdrantStoreImport:
    """Test that Qdrant store can be imported."""

    def test_qdrant_store_import(self):
        """Test QdrantVisualStore class import."""
        from neurosynth.dedup.qdrant_store import QdrantVisualStore

        assert QdrantVisualStore is not None

    def test_get_qdrant_store_import(self):
        """Test get_qdrant_store function import."""
        from neurosynth.dedup.qdrant_store import get_qdrant_store

        assert callable(get_qdrant_store)


# ============================================================================
# Visual Associator Tests
# ============================================================================


class TestVisualAssociatorImport:
    """Test that VisualAssociator can be imported."""

    def test_visual_associator_import(self):
        """Test VisualAssociator class import."""
        from neurosynth.dedup.clustering import VisualAssociator

        assert VisualAssociator is not None

    def test_visual_associator_instantiation(self):
        """Test VisualAssociator can be instantiated."""
        from neurosynth.dedup.clustering import VisualAssociator

        associator = VisualAssociator()
        assert associator is not None
        assert associator.visual_relevance_threshold == 0.3


# ============================================================================
# LaTeX Generator Tests
# ============================================================================


class TestLaTeXGeneratorImport:
    """Test that LaTeX generator visual methods work."""

    def test_latex_generator_import(self):
        """Test LaTeXGenerator class import."""
        from neurosynth.latex.generator import LaTeXGenerator

        assert LaTeXGenerator is not None

    def test_latex_generator_instantiation(self):
        """Test LaTeXGenerator can be instantiated."""
        from neurosynth.latex.generator import LaTeXGenerator

        generator = LaTeXGenerator()
        assert generator is not None

    def test_latex_generator_has_figure_methods(self):
        """Test LaTeXGenerator has figure-related methods."""
        from neurosynth.latex.generator import LaTeXGenerator

        generator = LaTeXGenerator()
        assert hasattr(generator, "_prepare_figure")
        assert hasattr(generator, "_calculate_figure_width")


# ============================================================================
# Output Model Tests
# ============================================================================


class TestOutputModelsImport:
    """Test that output models with visual support work."""

    def test_section_has_visual_fields(self):
        """Test Section has visual-related fields."""
        from neurosynth.models.output import Section

        section = Section(title="Test")
        assert hasattr(section, "inline_figures")
        assert hasattr(section, "figure_plate")
        assert hasattr(section, "has_visuals")

    def test_chapter_has_visual_methods(self):
        """Test Chapter has visual-related methods."""
        from neurosynth.models.output import Chapter

        chapter = Chapter(title="Test", topic="Test Topic")
        assert hasattr(chapter, "total_figures")
        assert hasattr(chapter, "all_visuals")
        assert hasattr(chapter, "collect_all_visuals")


# ============================================================================
# Pipeline Integration Tests
# ============================================================================


class TestPipelineVisualIntegration:
    """Test that pipeline coordinator supports visual processing."""

    def test_pipeline_config_has_visual_options(self):
        """Test PipelineConfig has visual processing options."""
        from neurosynth.pipeline.coordinator import PipelineConfig

        config = PipelineConfig()
        assert hasattr(config, "enable_visual_extraction")
        assert hasattr(config, "enable_visual_embeddings")
        assert hasattr(config, "max_inline_figures")
        assert hasattr(config, "visual_relevance_threshold")

    def test_pipeline_state_has_visual_fields(self):
        """Test PipelineState has visual tracking fields."""
        from neurosynth.pipeline.coordinator import PipelineState

        state = PipelineState()
        assert hasattr(state, "all_visuals")
        assert hasattr(state, "visuals_embedded")

    def test_pipeline_has_visual_stages(self):
        """Test Pipeline includes visual processing stages."""
        from neurosynth.pipeline.coordinator import Pipeline

        assert "embed_visuals" in Pipeline.STAGES
        assert "associate_visuals" in Pipeline.STAGES
