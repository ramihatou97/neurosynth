import asyncio
import json

import streamlit as st
import structlog

from src.ai import AIClient
from src.index import Database, SearchEngine
from src.templates import TemplateManager

# Structured logging for observability
logger = structlog.get_logger(__name__)


# Initialize core services (singleton-ish pattern via streamlit cache)
@st.cache_resource
def get_services():
    """
    Get shared services for Study Suite.

    Note: AIClient is instantiated per-request using async context manager,
    so we return a marker value instead of None to indicate service availability.
    """
    try:
        db = Database()
        search = SearchEngine(db)
        tm = TemplateManager()
        logger.info("study_suite_services_initialized")
        # Return "async" marker for AI - actual client is created per-request
        # via `async with AIClient() as ai_local:`
        return db, "async_per_request", search, tm
    except Exception as e:
        logger.error("study_suite_services_init_failed", error=str(e))
        st.error(f"Failed to initialize core services: {e}")
        return None, None, None, None


def _get_context_from_search(topic: str, search_engine) -> str:
    """Retrieve relevant context using vector search.

    AIClient is instantiated per-request via async context manager.
    """

    async def _run_search():
        async with AIClient() as ai_local:
            embedding = await ai_local.get_embedding(f"medical content for {topic}")
            results = search_engine.search_chunks(embedding, top_k=15)
            parts = []
            for match in results:
                parts.append(
                    f"[SOURCE: {match.chunk.source_title}]\n{match.chunk.content}"
                )
            return "\n\n".join(parts)

    try:
        return asyncio.run(_run_search())
    except Exception as e:
        return f"Error retrieving context: {e}"


def ask_examiner(
    history: list[dict],
    topic: str = "Neurosurgery General",
    case_type: str | None = None,
    difficulty: str = "standard",
    focus_topics: list[str] | None = None,
) -> str:
    """
    Conduct Oral Board Exam simulation using the central infrastructure.

    Args:
        history: Conversation history
        topic: Main topic for the exam
        case_type: Optional case type (trauma/tumor/vascular/spine/pediatric/functional)
        difficulty: Difficulty level (standard/challenging/malignant)
        focus_topics: Optional list of specific topics to focus on
    """
    db, _ai_marker, search, tm = get_services()
    if db is None or search is None or tm is None:
        return "System Error: Core services unavailable."

    # 1. Retrieve Context
    # We cache the exam context in session state to avoid re-searching every turn
    if "exam_context_cache" not in st.session_state:
        st.session_state.exam_context_cache = _get_context_from_search(topic, search)

    exam_context = st.session_state.exam_context_cache

    # 2. Render Prompt with all template parameters (P1-002 fix)
    context_data = {
        "ctx": {
            "history": history,
            "exam_context": exam_context,
            "case_type": case_type,
            "difficulty": difficulty,
            "focus_topics": focus_topics,
        }
    }

    try:
        sys_prompt, usr_prompt = tm.render_prompt(
            "study/oral_examiner.md.j2", context_data
        )

        # 3. Generate Response
        async def _run_exam():
            async with AIClient() as ai_local:
                return await ai_local.synthesize(usr_prompt, system_prompt=sys_prompt)

        return asyncio.run(_run_exam())
    except Exception as e:
        return f"Examiner Error: {e}"


def generate_mcqs(
    topic: str,
    num_questions: int = 3,
    difficulty: str = "application",
    question_style: str = "clinical_vignette",
    subspecialty: str | None = None,
) -> str:
    """
    Generate MCQs using the central infrastructure.

    Args:
        topic: Focus topic for questions
        num_questions: Number of questions to generate (1-10)
        difficulty: Question level (recall/application/synthesis)
        question_style: Question format (clinical_vignette/direct/image_based)
        subspecialty: Optional subspecialty filter
    """
    db, _ai_marker, search, tm = get_services()
    if db is None or search is None or tm is None:
        return json.dumps({"error": "Core services unavailable"})

    # 1. Retrieve Context
    exam_context = _get_context_from_search(topic, search)

    # 2. Render Prompt with all template parameters (P1-003 fix)
    context_data = {
        "ctx": {
            "topic": topic,
            "exam_context": exam_context,
            "num_questions": num_questions,
            "difficulty": difficulty,
            "question_style": question_style,
            "subspecialty": subspecialty,
        }
    }

    try:
        sys_prompt, usr_prompt = tm.render_prompt(
            "study/mcq_generator.md.j2", context_data
        )

        # 3. Generate Response
        async def _run_mcq():
            async with AIClient() as ai_local:
                return await ai_local.synthesize(usr_prompt, system_prompt=sys_prompt)

        return asyncio.run(_run_mcq())
    except Exception as e:
        return json.dumps({"error": str(e)})


def generate_audio_briefing(
    text_input: str,
    duration: str = "2min",
    audio_format: str = "morning_rounds",
    host_style: str = "senior_resident",
    target_audience: str = "junior_resident",
) -> tuple[None, str]:
    """
    Generate audio script and synthesize speech.

    Args:
        text_input: Source content to convert to audio script
        duration: Target duration (2min/5min/10min)
        audio_format: Script format (morning_rounds/deep_dive/case_review/rapid_fire)
        host_style: Voice style (attending/senior_resident/dual_host)
        target_audience: Target audience level (intern/junior_resident/senior_resident)

    Returns:
        Tuple of (audio_bytes, script_text) - audio_bytes is None (disabled)
    """
    db, _ai_marker, search, tm = get_services()
    if tm is None:
        return None, "Error: Template manager unavailable"

    # 1. Generate Script with all template parameters (P1-004 fix)
    context_data = {
        "ctx": {
            "content": text_input,
            "duration": duration,
            "format": audio_format,
            "host_style": host_style,
            "target_audience": target_audience,
        }
    }
    sys_prompt, usr_prompt = tm.render_prompt("study/audio_script.md.j2", context_data)

    async def _run_audio():
        async with AIClient() as ai_local:
            return await ai_local.synthesize(usr_prompt, system_prompt=sys_prompt)

    script = asyncio.run(_run_audio())

    # 2. Convert to Audio
    # Audio generation disabled to comply with Claude-only directive
    return None, script
