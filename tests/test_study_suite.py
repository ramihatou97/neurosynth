"""Tests for Study Suite brain.py functions.

Tests the P0-001 fix (get_services) and P1 fixes (template parameter passing).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetServices:
    """Tests for get_services() initialization."""

    @patch("study_suite.brain.Database")
    @patch("study_suite.brain.SearchEngine")
    @patch("study_suite.brain.TemplateManager")
    def test_get_services_returns_valid_tuple(self, mock_tm, mock_search, mock_db):
        """Test that get_services returns proper tuple with async marker."""
        # Clear cache before test
        from study_suite import brain

        brain.get_services.clear()

        db, ai_marker, search, tm = brain.get_services()

        # DB, Search, and TM should be initialized
        assert db is not None
        assert search is not None
        assert tm is not None
        # AI marker should be "async_per_request" (not None)
        assert ai_marker == "async_per_request"

    @patch("study_suite.brain.Database", side_effect=Exception("DB Error"))
    def test_get_services_handles_init_failure(self, mock_db):
        """Test that get_services handles initialization failure gracefully."""
        from study_suite import brain

        brain.get_services.clear()

        with patch("study_suite.brain.st"):  # Mock streamlit
            db, ai_marker, search, tm = brain.get_services()

        # All should be None on failure
        assert db is None
        assert ai_marker is None
        assert search is None
        assert tm is None


class TestAskExaminer:
    """Tests for ask_examiner() with template parameters."""

    @pytest.fixture
    def mock_services(self):
        """Mock all services for testing."""
        mock_db = MagicMock()
        mock_search = MagicMock()
        mock_tm = MagicMock()
        mock_tm.render_prompt.return_value = ("system prompt", "user prompt")
        return mock_db, "async_per_request", mock_search, mock_tm

    @patch("study_suite.brain.get_services")
    @patch("study_suite.brain.st")
    @patch("study_suite.brain._get_context_from_search")
    @patch("study_suite.brain.AIClient")
    def test_ask_examiner_passes_template_params(
        self, mock_ai_class, mock_context, mock_st, mock_services_fn, mock_services
    ):
        """Test that ask_examiner passes all template parameters."""
        mock_services_fn.return_value = mock_services
        mock_context.return_value = "test context"
        # Use MagicMock for session_state to allow attribute assignment
        mock_st.session_state = MagicMock()

        # Mock the async context manager
        mock_ai = AsyncMock()
        mock_ai.synthesize.return_value = "examiner response"
        mock_ai_class.return_value.__aenter__.return_value = mock_ai
        mock_ai_class.return_value.__aexit__.return_value = None

        from study_suite import brain

        result = brain.ask_examiner(
            history=[{"role": "user", "content": "test"}],
            topic="Neurosurgery",
            case_type="trauma",
            difficulty="challenging",
            focus_topics=["spine", "trauma"],
        )

        # Verify template manager was called with correct context
        _, ai_marker, _, tm = mock_services
        call_args = tm.render_prompt.call_args
        context_data = call_args[0][1]

        assert context_data["ctx"]["case_type"] == "trauma"
        assert context_data["ctx"]["difficulty"] == "challenging"
        assert context_data["ctx"]["focus_topics"] == ["spine", "trauma"]


class TestGenerateMCQs:
    """Tests for generate_mcqs() with template parameters."""

    @patch("study_suite.brain.get_services")
    @patch("study_suite.brain._get_context_from_search")
    @patch("study_suite.brain.AIClient")
    def test_generate_mcqs_passes_template_params(
        self, mock_ai_class, mock_context, mock_services_fn
    ):
        """Test that generate_mcqs passes all template parameters."""
        mock_db = MagicMock()
        mock_search = MagicMock()
        mock_tm = MagicMock()
        mock_tm.render_prompt.return_value = ("system", "user")
        mock_services_fn.return_value = (
            mock_db,
            "async_per_request",
            mock_search,
            mock_tm,
        )
        mock_context.return_value = "test context"

        # Mock the async context manager
        mock_ai = AsyncMock()
        mock_ai.synthesize.return_value = '{"questions": []}'
        mock_ai_class.return_value.__aenter__.return_value = mock_ai
        mock_ai_class.return_value.__aexit__.return_value = None

        from study_suite import brain

        result = brain.generate_mcqs(
            topic="Vascular",
            num_questions=5,
            difficulty="synthesis",
            question_style="clinical_vignette",
            subspecialty="vascular",
        )


class TestGenerateAudioBriefing:
    """Tests for generate_audio_briefing() with template parameters."""

    @patch("study_suite.brain.get_services")
    @patch("study_suite.brain.AIClient")
    def test_generate_audio_passes_template_params(
        self, mock_ai_class, mock_services_fn
    ):
        """Test that generate_audio_briefing passes all template parameters."""
        mock_db = MagicMock()
        mock_search = MagicMock()
        mock_tm = MagicMock()
        mock_tm.render_prompt.return_value = ("system", "user")
        mock_services_fn.return_value = (
            mock_db,
            "async_per_request",
            mock_search,
            mock_tm,
        )

        # Mock the async context manager
        mock_ai = AsyncMock()
        mock_ai.synthesize.return_value = "Generated script content"
        mock_ai_class.return_value.__aenter__.return_value = mock_ai
        mock_ai_class.return_value.__aexit__.return_value = None

        from study_suite import brain

        audio_bytes, script = brain.generate_audio_briefing(
            text_input="Test content to convert",
            duration="10min",
            audio_format="deep_dive",
            host_style="attending",
            target_audience="senior_resident",
        )

        # Audio bytes should be None (disabled)
        assert audio_bytes is None
        # Script should be returned
        assert script == "Generated script content"

        # Verify template manager was called with correct context
        call_args = mock_tm.render_prompt.call_args
        context_data = call_args[0][1]

        assert context_data["ctx"]["duration"] == "10min"
        assert context_data["ctx"]["format"] == "deep_dive"
        assert context_data["ctx"]["host_style"] == "attending"
        assert context_data["ctx"]["target_audience"] == "senior_resident"
