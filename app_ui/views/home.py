"""Home: hero, topic console, metrics, feature cards, recent runs."""
import streamlit as st

from sources import MIN_CHARS, cached_search, get_source_text

from ..components import STRETCH, esc, feature_card, render_hero, render_metrics, section_label, show_html, spacer
from ..runner import run_verification
from ..state import apply_run, go

from ..extractor import extract_claims_for_topic, save_new_run
from ..runs_io import get_available_runs

# (button label, topic, keyword to auto-load a matching archived run, or None)
TOPIC_CHIPS = [
    ("Hallucination Detection", "Hallucination detection in large language models", "hallucination"),
    ("Intermittent Fasting", "Intermittent fasting metabolic and health effects", "fasting"),
    ("Solid-State Batteries", "Commercial viability of solid-state batteries by 2027", None),
    ("AI Code Reliability", "Impact of AI coding assistants on software reliability", None),
    ("Remote Work Output", "Impact of remote work on productivity", None),
]


def _verify_topic(topic: str) -> None:
    ss = st.session_state
    runs = ss.runs
    ss.current_topic = topic

    with st.status(f"Verifying '{topic}'", expanded=True) as box:
        st.write("**Phase 1:** retrieving web sources via Firecrawl...")
        found = cached_search(topic, limit=ss.settings["source_limit"])
        valid = [s["url"] for s in found if len(get_source_text(s["url"])) >= MIN_CHARS]
        if not valid:
            box.update(label=f"Could not retrieve substantive sources for '{topic}'.", state="error")
            return
        st.write(f"✓ Retrieved {len(valid)} substantive web documents.")

        match = next((r for r in runs if topic.lower() in r["topic"].lower()), None)
        if match:
            st.write(f"**Phase 2:** loading archived claims for '{match['topic']}'...")
            if apply_run(match["path"], runs, keep_topic=True):
                st.write(f"✓ Loaded {len(ss.claims)} archived claims with evidence spans.")
        else:
            st.write(f"**Phase 2:** extracting atomic claims live across {len(valid)} sources...")
            extracted = extract_claims_for_topic(
                topic,
                valid,
                max_claims_per_url=2,
                status_func=lambda msg: st.write(msg),
            )
            if not extracted:
                box.update(label=f"Could not extract claims for '{topic}'. Check API quota or sources.", state="error")
                return
            claims_path = save_new_run(topic, extracted)
            ss.claims = extracted
            ss.runs = get_available_runs()
            ss.current_run_path = claims_path
            st.write(f"✓ Extracted {len(extracted)} atomic claims with exact quotation spans.")

        st.write("**Phase 3:** verifying claims across all 5 verification stages...")
        paused = run_verification(topic, ss.claims)
        if paused:
            box.update(label=f"Finished '{topic}' with paused stages ({', '.join(paused)}): API quota.", state="error")
        else:
            box.update(label=f"Successfully verified '{topic}': {len(ss.claims)} claims evaluated.", state="complete")
            st.success(f"Verification complete for '{topic}'! Head over to Claims Explorer to inspect all audited claims.")


def _topic_chips() -> None:
    ss = st.session_state
    for i, (col, (label, topic, keyword)) in enumerate(zip(st.columns(len(TOPIC_CHIPS)), TOPIC_CHIPS)):
        if col.button(label, key=f"chip_{i}", **STRETCH):
            ss.current_topic = topic
            if keyword:
                match = next((r for r in ss.runs if keyword in r["topic"].lower()), None)
                if match:
                    apply_run(match["path"], ss.runs, keep_topic=True)
            st.rerun()


def _topic_console() -> None:
    col_input, col_run = st.columns([5, 1.3])
    with col_input:
        topic = st.text_input(
            "Enter Topic",
            value=st.session_state.current_topic,
            placeholder="e.g. Impact of synthetic data on LLM hallucination rates",
            label_visibility="collapsed",
        )
    with col_run:
        verify = st.button("Verify topic", type="primary", **STRETCH)
    _topic_chips()
    if verify:
        _verify_topic(topic)


def _feature_grid(pages) -> None:
    cards = [p for p in pages if p.label not in ("Home", "Account")]
    for start in range(0, len(cards), 3):
        for col, page in zip(st.columns(3), cards[start:start + 3]):
            with col:
                feature_card(page.label, page.blurb)
                if st.button("Open", key=f"open_{page.label}", **STRETCH):
                    go(page.label)


def _recent_runs() -> None:
    ss = st.session_state
    runs = ss.runs[:5]
    if not runs:
        st.caption("No archived runs yet. Runs saved to `runs/` will show up here.")
        return
    for r in runs:
        info, action = st.columns([5, 1])
        faith = f" · faithfulness {r['faithfulness']:.2f}" if r["faithfulness"] is not None else ""
        active = " · active" if r["path"] == ss.current_run_path else ""
        with info:
            show_html(
                f'<div class="run-row"><div class="run-title">{esc(r["topic"][:70])}</div>'
                f'<div class="run-meta">{esc(r["stamp"])} · {r["claims_count"]} claims{esc(faith)}{active}</div></div>'
            )
        with action:
            if st.button("Load", key=f"load_{r['path']}", **STRETCH) and r["path"] != ss.current_run_path:
                ss.current_run_path = r["path"]
                apply_run(r["path"], ss.runs)
                st.rerun()


def render(pages) -> None:
    render_hero()
    _topic_console()
    spacer()
    render_metrics(st.session_state.claims)

    section_label("Features")
    _feature_grid(pages)

    spacer()
    section_label("Recent runs")
    _recent_runs()
