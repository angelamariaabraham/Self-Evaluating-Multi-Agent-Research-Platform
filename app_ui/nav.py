"""Page registry and sidebar (brand, navigation, active run, account)."""
from dataclasses import dataclass
from typing import Callable

import streamlit as st

from .components import STRETCH, account_chip, brand, nav_icon, section_label
from .state import HOME, apply_run, go
from .views import account, adversarial, evidence, explorer, export, history, home, stages


@dataclass(frozen=True)
class Page:
    label: str
    icon: str  # Material Symbols name
    blurb: str
    render: Callable[[], None]


PAGES = [
    Page("Home", "home", "Overview and quick start", lambda: home.render(PAGES)),
    Page("Claims Explorer", "fact_check", "Filter claims and inspect their evidence spans", explorer.render),
    Page("Pipeline", "account_tree", "Run the verification stages on the loaded claims", stages.render),
    Page("Adversarial", "balance", "Contradictions, weak evidence and entailment leaps", adversarial.render),
    Page("Report", "description", "Executive summary with Markdown and JSON export", export.render),
    Page("Evidence Vault", "folder", "Browse the raw scraped source documents", evidence.render),
    Page("History", "show_chart", "Benchmark faithfulness across past runs", history.render),
    Page("Account", "person", "Profile, model and API keys", account.render),
]
PAGES_BY_LABEL = {p.label: p for p in PAGES}


def current_page() -> Page:
    return PAGES_BY_LABEL.get(st.session_state.page, PAGES_BY_LABEL[HOME])


def _run_picker() -> None:
    ss = st.session_state
    if not ss.runs:
        st.caption("No archived runs yet.")
        return
    options = {r["path"]: r["display"] for r in ss.runs}
    paths = list(options)
    index = paths.index(ss.current_run_path) if ss.current_run_path in options else 0
    chosen = st.selectbox("Active run", paths, format_func=options.get, index=index, label_visibility="collapsed")
    if chosen != ss.current_run_path:
        ss.current_run_path = chosen
        apply_run(chosen, ss.runs)
        st.rerun()


def render_sidebar() -> None:
    ss = st.session_state
    with st.sidebar:
        brand()
        for page in PAGES:
            active = ss.page == page.label
            clicked = st.button(
                page.label,
                key=f"nav_{page.label}",
                type="primary" if active else "secondary",
                **nav_icon(page.icon),
                **STRETCH,
            )
            if clicked and not active:
                go(page.label)

        st.divider()
        section_label("Active run")
        _run_picker()

        st.divider()
        account_chip(ss.profile["name"], ss.profile["role"])
