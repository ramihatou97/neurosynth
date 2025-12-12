import streamlit as st


def apply_styles():
    """
    Applies the NeuroSynth Design System global styles.
    """
    st.markdown(
        """
        <style>
        /* 1. Global Typography & Theme */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Roboto+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #E0E0E0 !important; /* Light Gray Text - Force Override */
        }

        /* 2. Background & Containers */
        .stApp {
            background-color: #0E1117 !important; /* Deep Dark Background */
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #161B22 !important; /* Slightly Lighter Sidebar */
            border-right: 1px solid #30363D;
        }

        [data-testid="stSidebar"] * {
            color: #E0E0E0 !important; /* Force light text in sidebar */
        }

        /* 3. Headers */
        h1, h2, h3 {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            color: #FFFFFF !important;
            letter-spacing: -0.02em;
        }
        h1 { font-size: 2.5rem !important; margin-bottom: 1.5rem !important; }
        h2 { font-size: 1.75rem !important; margin-top: 2rem !important; color: #58A6FF !important; /* Accent Blue */ }
        h3 { font-size: 1.25rem !important; color: #C9D1D9 !important; }

        /* 4. Cards & Containers (Glassmorphism) */
        .stCard {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .stCard:hover {
            transform: translateY(-2px);
            border-color: #58A6FF;
        }

        /* 5. Metrics & Stats */
        [data-testid="stMetricValue"] {
            font-family: 'Roboto Mono', monospace;
            color: #58A6FF;
            font-size: 2rem !important;
        }
        [data-testid="stMetricLabel"] {
            color: #8B949E;
            font-size: 0.9rem !important;
        }

        /* 6. Buttons */
        .stButton > button {
            background-color: #238636; /* GitHub Green */
            color: white;
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.2s;
        }
        .stButton > button:hover {
            background-color: #2EA043;
            box-shadow: 0 4px 12px rgba(35, 134, 54, 0.4);
        }
        /* Secondary/Outline Buttons */
        .stButton > button[kind="secondary"] {
            background-color: transparent;
            border: 1px solid #30363D;
            color: #C9D1D9;
        }

        /* 7. Alerts & Info Boxes */
        .stAlert {
            background-color: #161B22;
            border: 1px solid #30363D;
            border-radius: 8px;
        }

        /* 8. Utility Classes */
        .text-accent { color: #58A6FF; }
        .text-dim { color: #8B949E; }
        .font-mono { font-family: 'Roboto Mono', monospace; }

        /* 9. Progress Bars */
        .stProgress > div > div > div > div {
            background-color: #58A6FF;
        }

        /* 10. Force Light Text on All Streamlit Elements */
        p, span, div, label, [class*="st"] {
            color: #E0E0E0 !important;
        }

        /* Input Fields */
        input, textarea, select {
            background-color: #161B22 !important;
            color: #E0E0E0 !important;
            border: 1px solid #30363D !important;
        }

        /* Radio Buttons and Checkboxes */
        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label {
            color: #E0E0E0 !important;
        }

        /* Markdown Text */
        .stMarkdown {
            color: #E0E0E0 !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )


def card_container(key=None):
    """Returns a container styled as a card (requires manual div creation inside if not using st.container context)"""
    # Streamlit doesn't strictly adhere to CSS classes on containers easily without hacks.
    # We will use standard st.container() but assume global CSS targets it if possible,
    # or just use this for logical grouping.
    # For true cards, we often use markdown divs.
    return st.container()


def metric_card(label, value, delta=None):
    """
    Renders a custom styled metric card.
    """
    st.markdown(
        f"""
    <div class="stCard">
        <div style="font-size: 0.9rem; color: #8B949E; margin-bottom: 0.2rem;">{label}</div>
        <div style="font-size: 2rem; color: #58A6FF; font-family: 'Roboto Mono'; font-weight: 500;">{value}</div>
        {f'<div style="font-size: 0.8rem; color: {"#238636" if str(delta).startswith("+") else "#F85149"};">{delta}</div>' if delta else ''}
    </div>
    """,
        unsafe_allow_html=True,
    )
