"""Tab 5: browse the raw scraped source documents."""
from pathlib import Path

import streamlit as st

from ..runs_io import SOURCE_STORE, read_json


@st.cache_data(show_spinner=False)
def _read_source(path: str, mtime: float) -> dict:
    """mtime is part of the cache key, so edited files reload."""
    return read_json(path)


def render() -> None:
    ss = st.session_state
    active_urls = {c.source_url for c in ss.claims if c.source_url}

    all_options = {}
    active_options = {}

    for f in sorted(SOURCE_STORE.glob("*.json")):
        try:
            data = _read_source(str(f), f.stat().st_mtime)
        except (OSError, ValueError):
            continue
        url = data.get("url", f.name)
        text_len = len(data.get("text", ""))
        label = f"{url} ({text_len:,} chars)"
        all_options[str(f)] = label
        if url in active_urls:
            active_options[str(f)] = label

    if not all_options:
        st.info("No stored sources found in `source_store/`.")
        return

    # Radio filter: default to active run if active sources exist
    has_active = bool(active_options)
    view_mode = st.radio(
        "Source scope",
        options=[
            f"Active Topic Sources ({len(active_options)} for '{ss.current_topic}')",
            f"All Cached Sources in Vault ({len(all_options)} total)",
        ] if has_active else [f"All Cached Sources in Vault ({len(all_options)} total)"],
        horizontal=True,
        label_visibility="collapsed",
    )

    use_active = has_active and view_mode.startswith("Active Topic")
    display_options = active_options if use_active else all_options

    if not display_options:
        st.info(f"No cached sources found specifically for '{ss.current_topic}'. Switch to 'All Cached Sources' to browse the archive.")
        return

    chosen = st.selectbox(
        "Select Source Page to Inspect",
        list(display_options),
        format_func=display_options.get,
    )
    if not chosen:
        return

    data = _read_source(chosen, Path(chosen).stat().st_mtime)
    url, text = data.get("url", ""), data.get("text", "")
    st.markdown(f"**URL:** [{url}]({url})")
    st.caption(f"Document Size: {len(text):,} characters &nbsp;·&nbsp; Word Count: ~{len(text.split()):,} words")

    source_claims = [c for c in ss.claims if c.source_url == url]
    if source_claims:
        st.markdown(f"**Claims derived from this source ({len(source_claims)}):**")
        for c in source_claims:
            st.markdown(f"- **`{c.claim_id}`**: {c.claim_text}")
