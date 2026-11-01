"""TruthEngine front-end. Run with:  streamlit run app_streamlit.py

Layout of the UI code:
    .streamlit/config.toml   pastel light theme (must sit in the folder you run from)
    app_ui/styles.css        all custom CSS
    app_ui/components.py     HTML helpers, page header, hero, metrics, footer
    app_ui/nav.py            page registry + sidebar (navigation, active run, account)
    app_ui/state.py          session state, profile, settings
    app_ui/runs_io.py        read saved runs from disk (no Streamlit)
    app_ui/runner.py         the 5 verification stages
    app_ui/views/*.py        one module per page
"""
import sys

if sys.platform == "win32":  # Windows terminal UTF-8
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app_ui import litellm_patch  # noqa: E402

litellm_patch.apply()  # must run BEFORE project modules import litellm

from app_ui.components import load_css, page_header, render_footer  # noqa: E402
from app_ui.nav import current_page, render_sidebar  # noqa: E402
from app_ui.runs_io import get_available_runs  # noqa: E402
from app_ui.state import apply_settings, init_session, keys_ready  # noqa: E402

st.set_page_config(
    page_title="TruthEngine",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_css()


def show_flash() -> None:
    """One-shot message left by an action that ended with st.rerun()."""
    flash = st.session_state.pop("flash", None)
    if flash:
        level, message = flash
        getattr(st, level)(message)


init_session(get_available_runs())
apply_settings()
render_sidebar()

page = current_page()
page_header(page.label, page.blurb, st.session_state.settings["model"], keys_ready())
show_flash()
page.render()
render_footer()
