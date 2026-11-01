"""Session-state helpers: one place that knows which keys exist."""
import json
import os
from pathlib import Path

import streamlit as st

from schema import ContradictionResult, StressResult

from .runs_io import RunLoadError, load_run_package, read_json

DEFAULT_TOPIC = "Hallucination detection in large language models"
DEFAULT_MODEL = "gemini/gemini-3.5-flash-lite"
MODEL_CHOICES = [
    DEFAULT_MODEL,
    "gemini/gemini-2.0-flash",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-pro",
]
CUSTOM_MODEL = "Custom Model"
HOME = "Home"
PROFILE_PATH = Path("account.json")


# --- Results -----------------------------------------------------------------

def reset_results(topic: str = DEFAULT_TOPIC) -> None:
    ss = st.session_state
    ss.claims = []
    ss.current_topic = topic
    ss.cres = ContradictionResult(flags=[])
    ss.sres = StressResult(items=[])
    ss.report_md = ""


def apply_run(path: str, runs=None, keep_topic: bool = False) -> bool:
    """Load a saved run into session state. Returns False (and shows an error) on failure."""
    try:
        claims, topic, cres, sres, report_md = load_run_package(path, runs)
    except RunLoadError as e:
        st.error(str(e))
        return False
    ss = st.session_state
    ss.claims, ss.cres, ss.sres, ss.report_md = claims, cres, sres, report_md
    if not keep_topic:
        ss.current_topic = topic
    return True


# --- Profile (stored locally in account.json; there is no login) ---------------

def load_profile() -> dict:
    profile = {"name": os.getenv("TRUTHENGINE_USER_NAME", "Researcher"), "role": ""}
    try:
        saved = read_json(PROFILE_PATH)
        profile.update({k: str(v) for k, v in saved.items() if k in profile})
    except (OSError, ValueError, AttributeError):
        pass
    return profile


def save_profile(profile: dict) -> bool:
    try:
        PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except OSError as e:
        st.error(f"Could not save profile: {e}")
        return False


# --- Settings (model + keys live in session state, pushed to env every run) -----

def apply_settings() -> None:
    s = st.session_state.settings
    os.environ["VERITAS_MODEL"] = s["model"]
    os.environ["TRUTHENGINE_MODEL"] = s["model"]
    if s["gemini"]:
        os.environ["GEMINI_API_KEY"] = s["gemini"]
    if s["firecrawl"]:
        os.environ["FIRECRAWL_API_KEY"] = s["firecrawl"]


def keys_ready() -> bool:
    s = st.session_state.settings
    return bool(s["gemini"] and s["firecrawl"])


# --- Navigation ------------------------------------------------------------------

def go(page_label: str) -> None:
    st.session_state.page = page_label
    st.rerun()


def init_session(runs) -> None:
    ss = st.session_state
    ss.runs = runs  # refreshed every run
    ss.setdefault("page", HOME)
    ss.setdefault("profile", load_profile())
    ss.setdefault("settings", {
        "model": os.getenv("VERITAS_MODEL", DEFAULT_MODEL),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "firecrawl": os.getenv("FIRECRAWL_API_KEY", ""),
        "source_limit": 5,
    })
    default_path = runs[0]["path"] if runs else ""
    ss.setdefault("current_run_path", default_path)
    if "claims" not in ss:
        reset_results()
        if default_path:
            apply_run(default_path, runs)
