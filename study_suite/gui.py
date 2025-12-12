import json

import streamlit as st

from . import brain  # Import the logic sibling


def render_study_suite():
    st.markdown("## 🧠 FRCSC Resident Core")

    # Load Context ONCE
    # if "exam_context" not in st.session_state:
    #     with st.spinner("Ingesting 2024 Exam Data..."):
    #         st.session_state.exam_context = brain.load_exam_context()
    #         if len(st.session_state.exam_context) < 100:
    #             st.warning("No data found in /study_suite/data. Please add your .md files.")

    # Create Tabs
    tabs = st.tabs(
        ["💀 Oral Examiner", "📝 2024 MCQ Bank", "🎧 Audio Rounds", "🗂️ Anki Factory"]
    )

    # --- TAB 1: ORAL EXAMINER ---
    with tabs[0]:
        st.caption(
            "Simulates 'Hot Seat' cases based on your 'Spring/Fall 2024 Memories' files."
        )

        # Template parameter controls (P1-002 fix)
        with st.expander("⚙️ Exam Settings", expanded=False):
            col1, col2, col3 = st.columns(3)
            case_type = col1.selectbox(
                "Case Type",
                options=[
                    "random",
                    "trauma",
                    "tumor",
                    "vascular",
                    "spine",
                    "pediatric",
                    "functional",
                ],
                key="oral_case_type",
            )
            difficulty = col2.selectbox(
                "Difficulty",
                options=["standard", "challenging", "malignant"],
                key="oral_difficulty",
            )
            focus_topic = col3.text_input(
                "Focus Topic", value="", key="oral_focus_topic"
            )

        if "oral_history" not in st.session_state:
            st.session_state.oral_history = []

        # Start button - separate from chat input to avoid reset issues
        if st.button("Start New Case"):
            # Include settings in the initial prompt
            case_desc = (
                f"case type: {case_type}" if case_type != "random" else "random case"
            )
            diff_desc = f"difficulty: {difficulty}"
            topic_desc = f" focusing on {focus_topic}" if focus_topic else ""

            st.session_state.oral_history = [
                {
                    "role": "user",
                    "content": f"Start a {case_desc}, {diff_desc}{topic_desc} from the files.",
                }
            ]
            with st.spinner("Examiner is preparing case..."):
                initial_reply = brain.ask_examiner(
                    st.session_state.oral_history,
                    case_type=None if case_type == "random" else case_type,
                    difficulty=difficulty,
                    focus_topics=[focus_topic] if focus_topic else None,
                )
            st.session_state.oral_history.append(
                {"role": "assistant", "content": initial_reply}
            )
            st.rerun()

        # Chat Loop
        for msg in st.session_state.oral_history:
            if msg["role"] == "assistant":
                st.chat_message("assistant", avatar="👨‍⚕️").write(msg["content"])
            elif msg["role"] == "user" and "Start a random" not in msg["content"]:
                st.chat_message("user", avatar="🩺").write(msg["content"])

        if user_reply := st.chat_input("Your management..."):
            st.session_state.oral_history.append(
                {"role": "user", "content": user_reply}
            )
            # Display user message immediately
            st.chat_message("user", avatar="🩺").write(user_reply)

            with st.spinner("Examiner is judging..."):
                reply = brain.ask_examiner(st.session_state.oral_history)
                st.session_state.oral_history.append(
                    {"role": "assistant", "content": reply}
                )
            st.rerun()

    # --- TAB 2: MCQ BANK ---
    with tabs[1]:
        st.caption(
            "Generates questions derived directly from 'FRCSC_Complete_Question_Bank.md'."
        )

        # Template parameter controls (P1-003 fix)
        with st.expander("⚙️ MCQ Settings", expanded=False):
            mcq_col1, mcq_col2, mcq_col3 = st.columns(3)
            num_questions = mcq_col1.slider(
                "Number of Questions", min_value=1, max_value=10, value=3, key="mcq_num"
            )
            mcq_difficulty = mcq_col2.selectbox(
                "Question Level",
                options=["recall", "application", "synthesis"],
                index=1,  # default to application
                key="mcq_difficulty",
            )
            question_style = mcq_col3.selectbox(
                "Question Style",
                options=["clinical_vignette", "direct", "image_based"],
                key="mcq_style",
            )
            subspecialty = st.selectbox(
                "Subspecialty Filter (optional)",
                options=[
                    "none",
                    "tumor",
                    "vascular",
                    "spine",
                    "trauma",
                    "pediatric",
                    "functional",
                ],
                key="mcq_subspecialty",
            )

        col1, col2 = st.columns([3, 1])
        topic = col1.text_input(
            "Focus Topic (e.g., 'Posterior Fossa Tumors', 'Spine Trauma')",
            value="Vascular",
        )

        if col2.button("Generate MCQs"):
            with st.spinner(f"Mining exam data for {topic}..."):
                raw_json = brain.generate_mcqs(
                    topic,
                    num_questions=num_questions,
                    difficulty=mcq_difficulty,
                    question_style=question_style,
                    subspecialty=None if subspecialty == "none" else subspecialty,
                )
                if raw_json:
                    try:
                        # Extract JSON from potential markdown wrappers
                        clean_json = (
                            raw_json.replace("```json", "").replace("```", "").strip()
                        )
                        st.session_state.mcqs = json.loads(clean_json)
                    except:
                        st.error("Parser Error. Try again.")
                        st.expander("Raw Output").write(raw_json)

        if "mcqs" in st.session_state:
            for i, q in enumerate(st.session_state.mcqs):
                st.markdown(
                    f"**{i+1}. {q.get('question', 'Error: No question found')}**"
                )
                options = q.get("options", [])
                if options:
                    ans = st.radio(f"Select Answer {i}", options, key=f"q_{i}")
                    with st.expander("Check Answer"):
                        correct_ans = q.get("answer", "")
                        if ans == correct_ans:
                            st.success("Correct!")
                        else:
                            st.error(f"Incorrect. Answer: {correct_ans}")
                        st.info(
                            f"Source: {q.get('explanation', 'No explanation provided.')}"
                        )

    # --- TAB 3: AUDIO ROUNDS ---
    with tabs[2]:
        st.caption("Convert your notes or guidelines into a 'Morning Commute' podcast.")

        # Template parameter controls (P1-004 fix)
        with st.expander("⚙️ Audio Settings", expanded=False):
            audio_col1, audio_col2 = st.columns(2)
            duration = audio_col1.selectbox(
                "Target Duration",
                options=["2min", "5min", "10min"],
                key="audio_duration",
            )
            audio_format = audio_col1.selectbox(
                "Format",
                options=["morning_rounds", "deep_dive", "case_review", "rapid_fire"],
                key="audio_format",
            )
            host_style = audio_col2.selectbox(
                "Host Style",
                options=["senior_resident", "attending", "dual_host"],
                key="audio_host_style",
            )
            target_audience = audio_col2.selectbox(
                "Target Audience",
                options=["junior_resident", "intern", "senior_resident"],
                key="audio_target_audience",
            )

        text_to_read = st.text_area(
            "Paste text (e.g., Abstracts, Guidelines):", height=200
        )

        if st.button("Generate Podcast"):
            with st.spinner("Generating script..."):
                audio_bytes, script = brain.generate_audio_briefing(
                    text_to_read,
                    duration=duration,
                    audio_format=audio_format,
                    host_style=host_style,
                    target_audience=target_audience,
                )
                if script:
                    st.markdown("### 📝 Generated Script")
                    st.markdown(script)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

    # --- TAB 4: ANKI FACTORY ---
    with tabs[3]:
        st.caption("Quickly convert tables/lists into Anki importable CSVs.")
        # (This logic is simpler, can be added directly or via brain.py similarly to others)
        st.info("Paste any content here to format it for Anki import.")
        anki_text = st.text_area("Content to Convert", height=150)
        if st.button("Convert to CSV"):
            st.success("Feature coming soon - check brain.py to implement!")
