"""Test ProceduralSequenceDetector integration with Pipeline.

Verifies Phase 3.6 implementation:
- ProceduralSequenceDetector initializes when enable_procedural_detection=True
- Detects 5 types of sequences: numbered steps, subfigures, lettered panels, staged procedures, implicit
- Sequence metadata applied to VisualElement objects
- Graceful fallback when detector unavailable
- Statistics tracking for sequences detected
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from neurosynth.pipeline.coordinator import Pipeline, PipelineConfig
from neurosynth.models.visual import VisualElement, ImageType
from neurosynth.config import Settings


class TestProceduralSequenceIntegration:
    """Test Phase 3.6: Procedural sequence detection integration."""

    @staticmethod
    def _create_mock_visual(vis_id: str, caption: str, page: int) -> VisualElement:
        """Helper to create a mock VisualElement for testing."""
        return VisualElement(
            id=vis_id,
            caption=caption,
            page_number=page,
            bbox=(100, 100, 400, 400),
            context_text=f"Context for {caption}",
            image_type=ImageType.SURGICAL_STEP
        )

    def test_sequence_detector_initialization(self):
        """Verify ProceduralSequenceDetector initializes when enable_procedural_detection=True."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Verify detector initialized
            assert hasattr(pipeline, 'procedural_detector')
            assert hasattr(pipeline, 'sequence_stats')
            assert 'sequences_detected' in pipeline.sequence_stats
            assert 'total_sequence_elements' in pipeline.sequence_stats
            assert 'procedural_confidence_avg' in pipeline.sequence_stats
            assert 'sequence_type_counts' in pipeline.sequence_stats

        print("✓ ProceduralSequenceDetector initialization verified")

    def test_sequence_detector_disabled(self):
        """Verify detector not initialized when flag=False."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=False,
                enable_procedural_detection=False
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            assert pipeline.procedural_detector is None

        print("✓ Legacy behavior when procedural detection disabled")

    @pytest.mark.asyncio
    async def test_numbered_step_sequence_detection(self):
        """Test detection of 'Step 1 → Step 2 → Step 3' sequences."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Create 3 visuals with step captions
            vis1 = self._create_mock_visual("v1", "Step 1: Initial incision", 10)
            vis2 = self._create_mock_visual("v2", "Step 2: Exposure of dura", 11)
            vis3 = self._create_mock_visual("v3", "Step 3: Tumor resection", 12)

            pipeline.state.all_visuals = [vis1, vis2, vis3]

            # Mock detector to return numbered_steps sequence
            from neurosynth.enhancements.procedural_detector import (
                ProceduralSequence, SequenceElement, SequenceType
            )

            mock_detector = MagicMock()
            mock_detector.detect_sequences.return_value = [
                ProceduralSequence(
                    sequence_id="seq_001",
                    title="Surgical Procedure",
                    sequence_type=SequenceType.NUMBERED_STEPS,
                    elements=[
                        SequenceElement(
                            image_id="v1",
                            page_number=10,
                            position=(100, 100, 400, 400),
                            sequence_number=1,
                            subfigure_id=None,
                            step_label="Step 1",
                            caption="Step 1: Initial incision",
                            description="",
                            sequence_type=SequenceType.NUMBERED_STEPS,
                            confidence=0.95
                        ),
                        SequenceElement(
                            image_id="v2",
                            page_number=11,
                            position=(100, 100, 400, 400),
                            sequence_number=2,
                            subfigure_id=None,
                            step_label="Step 2",
                            caption="Step 2: Exposure of dura",
                            description="",
                            sequence_type=SequenceType.NUMBERED_STEPS,
                            confidence=0.95
                        ),
                        SequenceElement(
                            image_id="v3",
                            page_number=12,
                            position=(100, 100, 400, 400),
                            sequence_number=3,
                            subfigure_id=None,
                            step_label="Step 3",
                            caption="Step 3: Tumor resection",
                            description="",
                            sequence_type=SequenceType.NUMBERED_STEPS,
                            confidence=0.95
                        ),
                    ],
                    procedure_keywords=["incision", "dura", "resection"],
                    chapter=None,
                    start_page=10,
                    end_page=12,
                    completeness=1.0,
                    confidence=0.95
                )
            ]
            pipeline.procedural_detector = mock_detector

            # Run detection
            await pipeline._detect_procedural_sequences()

            # Verify sequence metadata applied to visuals
            assert vis1.sequence_id == "seq_001"
            assert vis1.sequence_position == 1
            assert vis1.sequence_type == "numbered_steps"
            assert vis1.step_label == "Step 1"
            assert vis1.is_procedural == True
            assert vis1.procedural_confidence == 0.95

            assert vis2.sequence_id == "seq_001"
            assert vis2.sequence_position == 2
            assert vis2.sequence_type == "numbered_steps"
            assert vis2.step_label == "Step 2"

            assert vis3.sequence_id == "seq_001"
            assert vis3.sequence_position == 3
            assert vis3.sequence_type == "numbered_steps"
            assert vis3.step_label == "Step 3"

            # Verify statistics
            assert pipeline.sequence_stats['sequences_detected'] == 1
            assert pipeline.sequence_stats['total_sequence_elements'] == 3
            assert abs(pipeline.sequence_stats['procedural_confidence_avg'] - 0.95) < 0.001
            assert pipeline.sequence_stats['sequence_type_counts']['numbered_steps'] == 1

        print("✓ Numbered step sequence detection works (Step 1→2→3)")

    @pytest.mark.asyncio
    async def test_subfigure_sequence_detection(self):
        """Test detection of 'Fig 3a → 3b → 3c' subfigure sequences."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Create 3 visuals with subfigure captions
            vis1 = self._create_mock_visual("v1", "Figure 3a: Axial view", 15)
            vis2 = self._create_mock_visual("v2", "Figure 3b: Coronal view", 15)
            vis3 = self._create_mock_visual("v3", "Figure 3c: Sagittal view", 15)

            pipeline.state.all_visuals = [vis1, vis2, vis3]

            # Mock detector to return subfigures sequence
            from neurosynth.enhancements.procedural_detector import (
                ProceduralSequence, SequenceElement, SequenceType
            )

            mock_detector = MagicMock()
            mock_detector.detect_sequences.return_value = [
                ProceduralSequence(
                    sequence_id="seq_002",
                    title="Figure 3 Series",
                    sequence_type=SequenceType.SUBFIGURES,
                    elements=[
                        SequenceElement(
                            image_id="v1",
                            page_number=15,
                            position=(100, 100, 400, 400),
                            sequence_number=1,
                            subfigure_id="a",
                            step_label="(a)",
                            caption="Figure 3a: Axial view",
                            description="",
                            sequence_type=SequenceType.SUBFIGURES,
                            confidence=0.90
                        ),
                        SequenceElement(
                            image_id="v2",
                            page_number=15,
                            position=(100, 100, 400, 400),
                            sequence_number=2,
                            subfigure_id="b",
                            step_label="(b)",
                            caption="Figure 3b: Coronal view",
                            description="",
                            sequence_type=SequenceType.SUBFIGURES,
                            confidence=0.90
                        ),
                        SequenceElement(
                            image_id="v3",
                            page_number=15,
                            position=(100, 100, 400, 400),
                            sequence_number=3,
                            subfigure_id="c",
                            step_label="(c)",
                            caption="Figure 3c: Sagittal view",
                            description="",
                            sequence_type=SequenceType.SUBFIGURES,
                            confidence=0.90
                        ),
                    ],
                    procedure_keywords=[],
                    chapter=None,
                    start_page=15,
                    end_page=15,
                    completeness=1.0,
                    confidence=0.90
                )
            ]
            pipeline.procedural_detector = mock_detector

            # Run detection
            await pipeline._detect_procedural_sequences()

            # Verify sequence metadata
            assert vis1.sequence_type == "subfigures"
            assert vis1.step_label == "(a)"
            assert vis1.is_procedural == True

            assert vis2.step_label == "(b)"
            assert vis3.step_label == "(c)"

            # Verify statistics
            assert pipeline.sequence_stats['sequences_detected'] == 1
            assert pipeline.sequence_stats['sequence_type_counts']['subfigures'] == 1

        print("✓ Subfigure sequence detection works (Fig 3a→3b→3c)")

    @pytest.mark.asyncio
    async def test_multiple_sequences_detection(self):
        """Test detection of multiple independent sequences."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Sequence 1: Steps 1-3 on pages 10-12 (numbered_steps)
            vis1 = self._create_mock_visual("v1", "Step 1: Prep", 10)
            vis2 = self._create_mock_visual("v2", "Step 2: Execute", 11)
            vis3 = self._create_mock_visual("v3", "Step 3: Close", 12)

            # Sequence 2: Fig 5a-c on page 20 (subfigures)
            vis4 = self._create_mock_visual("v4", "Figure 5a: View 1", 20)
            vis5 = self._create_mock_visual("v5", "Figure 5b: View 2", 20)
            vis6 = self._create_mock_visual("v6", "Figure 5c: View 3", 20)

            # Non-sequence visual
            vis7 = self._create_mock_visual("v7", "Random image", 30)

            pipeline.state.all_visuals = [vis1, vis2, vis3, vis4, vis5, vis6, vis7]

            # Mock detector to return 2 sequences
            from neurosynth.enhancements.procedural_detector import (
                ProceduralSequence, SequenceElement, SequenceType
            )

            mock_detector = MagicMock()
            mock_detector.detect_sequences.return_value = [
                # Sequence 1: Numbered steps
                ProceduralSequence(
                    sequence_id="seq_001",
                    title="Surgical Steps",
                    sequence_type=SequenceType.NUMBERED_STEPS,
                    elements=[
                        SequenceElement(
                            image_id="v1", page_number=10, position=(0,0,0,0),
                            sequence_number=1, subfigure_id=None, step_label="Step 1",
                            caption="Step 1: Prep", description="",
                            sequence_type=SequenceType.NUMBERED_STEPS, confidence=0.95
                        ),
                        SequenceElement(
                            image_id="v2", page_number=11, position=(0,0,0,0),
                            sequence_number=2, subfigure_id=None, step_label="Step 2",
                            caption="Step 2: Execute", description="",
                            sequence_type=SequenceType.NUMBERED_STEPS, confidence=0.95
                        ),
                        SequenceElement(
                            image_id="v3", page_number=12, position=(0,0,0,0),
                            sequence_number=3, subfigure_id=None, step_label="Step 3",
                            caption="Step 3: Close", description="",
                            sequence_type=SequenceType.NUMBERED_STEPS, confidence=0.95
                        ),
                    ],
                    procedure_keywords=["prep", "execute", "close"],
                    chapter=None, start_page=10, end_page=12,
                    completeness=1.0, confidence=0.95
                ),
                # Sequence 2: Subfigures
                ProceduralSequence(
                    sequence_id="seq_002",
                    title="Figure 5",
                    sequence_type=SequenceType.SUBFIGURES,
                    elements=[
                        SequenceElement(
                            image_id="v4", page_number=20, position=(0,0,0,0),
                            sequence_number=1, subfigure_id="a", step_label="(a)",
                            caption="Figure 5a: View 1", description="",
                            sequence_type=SequenceType.SUBFIGURES, confidence=0.90
                        ),
                        SequenceElement(
                            image_id="v5", page_number=20, position=(0,0,0,0),
                            sequence_number=2, subfigure_id="b", step_label="(b)",
                            caption="Figure 5b: View 2", description="",
                            sequence_type=SequenceType.SUBFIGURES, confidence=0.90
                        ),
                        SequenceElement(
                            image_id="v6", page_number=20, position=(0,0,0,0),
                            sequence_number=3, subfigure_id="c", step_label="(c)",
                            caption="Figure 5c: View 3", description="",
                            sequence_type=SequenceType.SUBFIGURES, confidence=0.90
                        ),
                    ],
                    procedure_keywords=[],
                    chapter=None, start_page=20, end_page=20,
                    completeness=1.0, confidence=0.90
                )
            ]
            pipeline.procedural_detector = mock_detector

            # Run detection
            await pipeline._detect_procedural_sequences()

            # Verify both sequences detected
            assert pipeline.sequence_stats['sequences_detected'] == 2
            assert len(pipeline.state.procedural_sequences) == 2
            assert pipeline.sequence_stats['total_sequence_elements'] == 6

            # Verify sequence 1 visuals
            assert vis1.sequence_id == "seq_001"
            assert vis2.sequence_id == "seq_001"
            assert vis3.sequence_id == "seq_001"

            # Verify sequence 2 visuals
            assert vis4.sequence_id == "seq_002"
            assert vis5.sequence_id == "seq_002"
            assert vis6.sequence_id == "seq_002"

            # Verify non-sequence visual not marked
            assert vis7.is_procedural == False
            assert vis7.sequence_id is None

            # Verify type counts
            assert pipeline.sequence_stats['sequence_type_counts']['numbered_steps'] == 1
            assert pipeline.sequence_stats['sequence_type_counts']['subfigures'] == 1

        print("✓ Multiple independent sequences detected correctly")

    @pytest.mark.asyncio
    async def test_sequence_api_format_conversion(self):
        """Test VisualElement → dict conversion for detector API."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Create test visual with all fields
            vis = VisualElement(
                id="v1",
                caption="Figure 3: Test image",
                page_number=15,
                bbox=(100, 200, 300, 400),
                context_text="Surrounding context text",
                image_type=ImageType.SURGICAL_STEP
            )
            pipeline.state.all_visuals = [vis]

            # Mock detector to capture input
            captured_input = []
            def capture_input(images):
                captured_input.extend(images)
                return []

            mock_detector = MagicMock()
            mock_detector.detect_sequences.side_effect = capture_input
            pipeline.procedural_detector = mock_detector

            # Run detection
            await pipeline._detect_procedural_sequences()

            # Verify conversion format
            assert len(captured_input) == 1
            img_dict = captured_input[0]

            assert 'id' in img_dict
            assert img_dict['id'] == "v1"

            assert 'page' in img_dict
            assert img_dict['page'] == 15

            assert 'bbox' in img_dict
            assert isinstance(img_dict['bbox'], tuple)
            assert len(img_dict['bbox']) == 4
            assert img_dict['bbox'] == (100, 200, 300, 400)

            assert 'caption' in img_dict
            assert img_dict['caption'] == "Figure 3: Test image"

            assert 'figure_id' in img_dict
            assert img_dict['figure_id'] == "3"  # Extracted from caption

            assert 'context' in img_dict
            assert img_dict['context'] == "Surrounding context text"

            assert 'chapter' in img_dict

        print("✓ API format conversion works correctly")

    @pytest.mark.asyncio
    async def test_sequence_statistics_tracking(self):
        """Verify all statistics tracked correctly."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Create test visuals
            pipeline.state.all_visuals = [
                self._create_mock_visual("v1", "Step 1", 10),
                self._create_mock_visual("v2", "Step 2", 11),
                self._create_mock_visual("v3", "Fig 5a", 20),
                self._create_mock_visual("v4", "Fig 5b", 20),
            ]

            # Mock detector with 2 sequences, varying confidence
            from neurosynth.enhancements.procedural_detector import (
                ProceduralSequence, SequenceElement, SequenceType
            )

            mock_detector = MagicMock()
            mock_detector.detect_sequences.return_value = [
                ProceduralSequence(
                    sequence_id="seq_001",
                    title="Steps",
                    sequence_type=SequenceType.NUMBERED_STEPS,
                    elements=[
                        SequenceElement(
                            image_id="v1", page_number=10, position=(0,0,0,0),
                            sequence_number=1, subfigure_id=None, step_label="Step 1",
                            caption="", description="",
                            sequence_type=SequenceType.NUMBERED_STEPS, confidence=0.95
                        ),
                        SequenceElement(
                            image_id="v2", page_number=11, position=(0,0,0,0),
                            sequence_number=2, subfigure_id=None, step_label="Step 2",
                            caption="", description="",
                            sequence_type=SequenceType.NUMBERED_STEPS, confidence=0.90
                        ),
                    ],
                    procedure_keywords=[], chapter=None,
                    start_page=10, end_page=11,
                    completeness=1.0, confidence=0.925
                ),
                ProceduralSequence(
                    sequence_id="seq_002",
                    title="Figure 5",
                    sequence_type=SequenceType.SUBFIGURES,
                    elements=[
                        SequenceElement(
                            image_id="v3", page_number=20, position=(0,0,0,0),
                            sequence_number=1, subfigure_id="a", step_label="(a)",
                            caption="", description="",
                            sequence_type=SequenceType.SUBFIGURES, confidence=0.85
                        ),
                        SequenceElement(
                            image_id="v4", page_number=20, position=(0,0,0,0),
                            sequence_number=2, subfigure_id="b", step_label="(b)",
                            caption="", description="",
                            sequence_type=SequenceType.SUBFIGURES, confidence=0.80
                        ),
                    ],
                    procedure_keywords=[], chapter=None,
                    start_page=20, end_page=20,
                    completeness=1.0, confidence=0.825
                )
            ]
            pipeline.procedural_detector = mock_detector

            # Run detection
            await pipeline._detect_procedural_sequences()

            # Verify statistics
            assert pipeline.sequence_stats['sequences_detected'] == 2
            assert pipeline.sequence_stats['total_sequence_elements'] == 4

            # Average confidence: (0.95 + 0.90 + 0.85 + 0.80) / 4 = 0.875
            assert abs(pipeline.sequence_stats['procedural_confidence_avg'] - 0.875) < 0.001

            assert 'numbered_steps' in pipeline.sequence_stats['sequence_type_counts']
            assert pipeline.sequence_stats['sequence_type_counts']['numbered_steps'] == 1

            assert 'subfigures' in pipeline.sequence_stats['sequence_type_counts']
            assert pipeline.sequence_stats['sequence_type_counts']['subfigures'] == 1

            # Verify metrics updated
            assert pipeline.state.metrics['sequences_detected'] == 2
            assert pipeline.state.metrics['procedural_elements'] == 4
            assert abs(pipeline.state.metrics['procedural_confidence_avg'] - 0.875) < 0.001

        print("✓ Statistics tracking works correctly")

    @pytest.mark.asyncio
    async def test_sequence_detection_fallback(self):
        """Test graceful degradation when detector fails."""
        with patch('neurosynth.pipeline.coordinator.get_settings') as mock_settings:
            settings = Settings(
                enable_enhancements=True,
                enable_procedural_detection=True
            )
            mock_settings.return_value = settings

            pipeline = Pipeline(topic="Test", config=PipelineConfig())

            # Create test visuals
            vis1 = self._create_mock_visual("v1", "Step 1", 10)
            vis2 = self._create_mock_visual("v2", "Step 2", 11)
            pipeline.state.all_visuals = [vis1, vis2]

            # Mock detector that raises exception
            mock_detector = MagicMock()
            mock_detector.detect_sequences.side_effect = Exception("Detection failed")
            pipeline.procedural_detector = mock_detector

            # Should not raise exception
            await pipeline._detect_procedural_sequences()

            # Metrics should show 0 sequences
            assert pipeline.state.metrics['sequences_detected'] == 0

            # Visuals should remain unmodified
            assert vis1.is_procedural == False
            assert vis1.sequence_id is None
            assert vis2.is_procedural == False
            assert vis2.sequence_id is None

        print("✓ Graceful fallback when detector fails")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
