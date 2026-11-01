"""Account page: profile, model and API settings, workspace stats."""
import streamlit as st

from ..components import STRETCH, account_chip, kv_panel, show_html, status_dot
from ..runs_io import cache_sizes
from ..state import CUSTOM_MODEL, MODEL_CHOICES, save_profile


def _profile() -> None:
    ss = st.session_state
    st.markdown("#### Profile")
    account_chip(ss.profile["name"], ss.profile["role"])
    name = st.text_input("Display name", value=ss.profile["name"])
    role = st.text_input("Role", value=ss.profile["role"], placeholder="e.g. Research assistant")
    if st.button("Save profile", **STRETCH):
        profile = {"name": name.strip() or "Researcher", "role": role.strip()}
        if save_profile(profile):
            ss.profile = profile
            ss.flash = ("success", "Profile saved to account.json.")
            st.rerun()
    st.caption("Stored locally in `account.json`. There is no sign-in; this only labels your workspace.")


def _workspace() -> None:
    ss = st.session_state
    sizes = cache_sizes()
    kv_panel("Workspace", [
        ("Archived runs", len(ss.runs)),
        ("Claims loaded", len(ss.claims)),
        ("Loaded topic", ss.current_topic),
        ("Scraped documents", sizes["sources"]),
        ("Cached entailment checks", sizes["support"]),
        ("Contradiction pairs evaluated", sizes["contradiction"]),
        ("Devil's Advocate rulings", sizes["devils_advocate"]),
    ])


def _model_and_keys() -> None:
    s = st.session_state.settings
    st.markdown("#### Model and API keys")
    left, right = st.columns(2)

    with left:
        choices = MODEL_CHOICES + [CUSTOM_MODEL]
        index = choices.index(s["model"]) if s["model"] in MODEL_CHOICES else len(choices) - 1
        choice = st.selectbox(
            "Active LLM", choices, index=index,
            help="Each Gemini model has its own free-tier request quota pool.",
        )
        if choice == CUSTOM_MODEL:
            default = s["model"] if s["model"] not in MODEL_CHOICES else "gemini/gemini-1.5-flash"
            s["model"] = st.text_input("Model identifier", value=default).strip() or default
        else:
            s["model"] = choice
        s["source_limit"] = st.slider("Source ingestion limit", 3, 8, s["source_limit"])

    with right:
        s["gemini"] = st.text_input("Gemini API key", value=s["gemini"], type="password")
        s["firecrawl"] = st.text_input("Firecrawl API key", value=s["firecrawl"], type="password")
        for label, value in (("Gemini", s["gemini"]), ("Firecrawl", s["firecrawl"])):
            text = f"{label} key set" if value else f"{label} key missing"
            show_html(f'<div class="run-meta">{status_dot(text, "good" if value else "warn")}</div>')
    st.caption("Keys live in this browser session only. Put them in `.env` to load them automatically.")


def render() -> None:
    left, right = st.columns(2)
    with left:
        _profile()
    with right:
        st.markdown("#### Workspace")
        _workspace()
    st.divider()
    _model_and_keys()
