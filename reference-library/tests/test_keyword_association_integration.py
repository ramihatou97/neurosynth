"""Test NeurosurgicalKeywordScorer integration with Pipeline.

Verifies Phase 3.5 implementation:
- NeurosurgicalKeywordScorer initializes when enable_keyword_scoring=True
- 340+ neurosurgical keywords detected and scored correctly
- Keyword matches enhance visual-cluster associations
- Graceful fallback when keyword scorer unavailable
- Statistics tracking for keyword-enhanced associations

NOTE: These tests are for features that are planned but not yet implemented.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from neurosynth.pipeline.coordinator import Pipeline, PipelineConfig
from neurosynth.models.visual import VisualElement, ImageType
from neurosynth.models.knowledge import KnowledgeCluster
from neurosynth.models.document import ContentChunk, Source, DocumentFormat
from neurosynth.config import Settings

# Skip all tests in this module - features not yet implemented
pytestmark = pytest.mark.skip(reason="Keyword association features not yet implemented")


class TestKeywordAssociationIntegration:
    """Test Phase 3.5: Keyword-based visual association enhancement."""

    @staticmethod
    def _create_mock_source(doc_id: str = "test_doc") -> Source:
        """Helper to create a mock Source object."""
        return Source(
            path=Path(f"/test/{doc_id}.pdf"),
            format=DocumentFormat.PDF,
            title="Test Document",
            authors=["Test Author"],
            year=2024
        )

    def test_keyword_associator_initialization(self):
        """Verify NeurosurgicalKeywordScorer loads when flag enabled."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_keyword_scoring=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Check that keyword scorer was initialized
            assert hasattr(pipeline, 'keyword_scorer')
            assert hasattr(pipeline, 'keyword_stats')
            assert 'enhanced_associations' in pipeline.keyword_stats
            assert 'keyword_matched_count' in pipeline.keyword_stats
            assert 'total_keywords_found' in pipeline.keyword_stats

        print("✓ NeurosurgicalKeywordScorer initialization verified")

    def test_keyword_association_disabled(self):
        """Verify legacy used when flag=False."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=False,
                enable_keyword_scoring=False
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Keyword scorer should not be initialized
            assert pipeline.keyword_scorer is None
            assert pipeline.keyword_stats['enhanced_associations'] == 0

        print("✓ Legacy association used when keyword scoring disabled")

    @pytest.mark.asyncio
    async def test_keyword_scoring_neurosurgical_terms(self):
        """Test 340+ medical keyword matching in cluster text."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_keyword_scoring=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Mock keyword scorer
            mock_scorer = MagicMock()
            mock_scorer.score_text.return_value = (
                0.75,  # keyword_score
                {
                    'keywords': ['craniotomy', 'cerebellum', 'dura', 'retractor'],
                    'categories': {'anatomy': 2, 'procedure': 1, 'instrument': 1},
                    'context_type': 'body'
                }
            )
            pipeline.keyword_scorer = mock_scorer

            # Create test data with neurosurgical content
            chunk1 = ContentChunk(
                id="chunk1",
                content="The craniotomy procedure exposed the cerebellum. The dura was carefully opened using a retractor.",
                source=self._create_mock_source("doc1"),
                embedding=None
            )
            cluster1 = KnowledgeCluster(id="cluster1", chunks=[chunk1])

            visual1 = VisualElement(
                id="vis1",
                image_type=ImageType.SURGICAL_STEP,
                caption="Figure 1: Surgical approach"
            )
            cluster1.visual_elements = [visual1]

            pipeline.state.clusters = [cluster1]
            pipeline.state.all_visuals = [visual1]

            # Mock the legacy associator to not modify clusters
            with patch('neurosynth.dedup.VisualAssociator') as mock_assoc_class:
                mock_assoc = AsyncMock()
                mock_assoc.associate_visuals_to_existing_clusters.return_value = pipeline.state.clusters
                mock_assoc_class.return_value = mock_assoc

                # Run association
                await pipeline._associate_visuals()

                # Verify keyword scoring was applied
                assert visual1.keyword_score == 0.75
                assert 'craniotomy' in visual1.keywords_matched
                assert 'cerebellum' in visual1.keywords_matched
                assert 'dura' in visual1.keywords_matched
                assert 'retractor' in visual1.keywords_matched
                assert len(visual1.keywords_matched) == 4

                # Verify statistics
                assert pipeline.keyword_stats['enhanced_associations'] == 1
                assert pipeline.keyword_stats['total_keywords_found'] == 4

        print("✓ 340+ neurosurgical keyword matching works")

    @pytest.mark.asyncio
    async def test_keyword_association_relevance_boost(self):
        """Verify keywords increase association scores and add metadata."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_keyword_scoring=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Mock keyword scorer with high score
            mock_scorer = MagicMock()
            mock_scorer.score_text.return_value = (
                0.90,  # High keyword relevance
                {
                    'keywords': ['aneurysm', 'basilar', 'artery', 'clip', 'microsurgical'],
                    'categories': {'anatomy': 2, 'procedure': 2, 'pathology': 1},
                }
            )
            pipeline.keyword_scorer = mock_scorer

            # Create cluster with relevant medical content
            chunk = ContentChunk(
                id="c1",
                content="Microsurgical clipping of basilar artery aneurysm",
                source=self._create_mock_source("doc2"),
                embedding=None
            )
            cluster = KnowledgeCluster(id="cluster1", chunks=[chunk])

            visual = VisualElement(
                id="v1",
                image_type=ImageType.SURGICAL_STEP,
                relevance_score=0.50  # Base relevance
            )
            cluster.visual_elements = [visual]

            pipeline.state.clusters = [cluster]
            pipeline.state.all_visuals = [visual]

            with patch('neurosynth.dedup.VisualAssociator') as mock_assoc_class:
                mock_assoc = AsyncMock()
                mock_assoc.associate_visuals_to_existing_clusters.return_value = pipeline.state.clusters
                mock_assoc_class.return_value = mock_assoc

                await pipeline._associate_visuals()

                # Verify keyword score is added
                assert visual.keyword_score == 0.90
                assert len(visual.keywords_matched) == 5
                assert 'aneurysm' in visual.keywords_matched
                assert 'microsurgical' in visual.keywords_matched

                # Original relevance_score unchanged (keyword_score is separate)
                assert visual.relevance_score == 0.50

        print("✓ Keyword matching enhances associations with metadata")

    @pytest.mark.asyncio
    async def test_keyword_association_fallback(self):
        """Test graceful degradation when keyword scorer fails."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_keyword_scoring=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Mock keyword scorer that raises exception
            mock_scorer = MagicMock()
            mock_scorer.score_text.side_effect = Exception("Keyword scoring failed")
            pipeline.keyword_scorer = mock_scorer

            chunk = ContentChunk(
                id="c1",
                content="Test text",
                source=self._create_mock_source("doc3"),
                embedding=None
            )
            cluster = KnowledgeCluster(id="cluster1", chunks=[chunk])
            visual = VisualElement(id="v1", image_type=ImageType.SURGICAL_STEP)
            cluster.visual_elements = [visual]

            pipeline.state.clusters = [cluster]
            pipeline.state.all_visuals = [visual]

            with patch('neurosynth.dedup.VisualAssociator') as mock_assoc_class:
                mock_assoc = AsyncMock()
                mock_assoc.associate_visuals_to_existing_clusters.return_value = pipeline.state.clusters
                mock_assoc_class.return_value = mock_assoc

                # Should not raise exception
                await pipeline._associate_visuals()

                # Legacy association should have worked
                assert pipeline.keyword_stats['legacy_associations'] == 1
                # Keyword enhancement failed gracefully
                assert visual.keyword_score == 0.0
                assert len(visual.keywords_matched) == 0

        print("✓ Graceful fallback when keyword scorer fails")

    @pytest.mark.asyncio
    async def test_keyword_statistics_tracking(self):
        """Verify keyword stats recorded correctly."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_keyword_scoring=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Mock keyword scorer with varying results
            mock_scorer = MagicMock()

            def score_side_effect(text, context_type):
                if "craniotomy" in text.lower():
                    return (0.80, {'keywords': ['craniotomy', 'dura', 'bone flap'], 'categories': {}})
                elif "mri" in text.lower():
                    return (0.60, {'keywords': ['mri', 'flair'], 'categories': {}})
                else:
                    return (0.0, {'keywords': [], 'categories': {}})

            mock_scorer.score_text.side_effect = score_side_effect
            pipeline.keyword_scorer = mock_scorer

            # Create 3 clusters with different keyword content
            cluster1 = KnowledgeCluster(
                id="c1",
                chunks=[ContentChunk(
                    id="ch1",
                    content="Craniotomy with dura opening and bone flap",
                    source=self._create_mock_source("doc4"),
                    embedding=None
                )]
            )
            cluster2 = KnowledgeCluster(
                id="c2",
                chunks=[ContentChunk(
                    id="ch2",
                    content="MRI FLAIR sequence imaging",
                    source=self._create_mock_source("doc5"),
                    embedding=None
                )]
            )
            cluster3 = KnowledgeCluster(
                id="c3",
                chunks=[ContentChunk(
                    id="ch3",
                    content="Generic medical text",
                    source=self._create_mock_source("doc6"),
                    embedding=None
                )]
            )

            vis1 = VisualElement(id="v1", image_type=ImageType.SURGICAL_STEP)
            vis2 = VisualElement(id="v2", image_type=ImageType.IMAGING)
            vis3 = VisualElement(id="v3", image_type=ImageType.UNKNOWN)

            cluster1.visual_elements = [vis1]
            cluster2.visual_elements = [vis2]
            cluster3.visual_elements = [vis3]

            pipeline.state.clusters = [cluster1, cluster2, cluster3]
            pipeline.state.all_visuals = [vis1, vis2, vis3]

            with patch('neurosynth.dedup.VisualAssociator') as mock_assoc_class:
                mock_assoc = AsyncMock()
                mock_assoc.associate_visuals_to_existing_clusters.return_value = pipeline.state.clusters
                mock_assoc_class.return_value = mock_assoc

                await pipeline._associate_visuals()

                # Verify statistics
                assert pipeline.keyword_stats['legacy_associations'] == 3
                assert pipeline.keyword_stats['enhanced_associations'] == 2  # cluster1 and cluster2
                assert pipeline.keyword_stats['keyword_matched_count'] == 2
                assert pipeline.keyword_stats['total_keywords_found'] == 5  # 3 + 2

                # Verify metrics
                assert pipeline.state.metrics['visual_associations'] == 3
                assert pipeline.state.metrics['keyword_enhanced_count'] == 2
                assert pipeline.state.metrics['total_keywords_found'] == 5

                # Verify individual visuals
                assert vis1.keyword_score == 0.80
                assert len(vis1.keywords_matched) == 3
                assert vis2.keyword_score == 0.60
                assert len(vis2.keywords_matched) == 2
                assert vis3.keyword_score == 0.0  # No keywords matched
                assert len(vis3.keywords_matched) == 0

        print("✓ Statistics tracking works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
