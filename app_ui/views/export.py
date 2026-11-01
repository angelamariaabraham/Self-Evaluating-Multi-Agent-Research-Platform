"""Tab 4: executive report and downloads."""
import datetime
import json

import streamlit as st

from ..components import STRETCH, spacer


def render() -> None:
    ss = st.session_state
    claims = ss.claims

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    claims_json = json.dumps([c.model_dump() for c in claims], indent=2, ensure_ascii=False)

    col_md, col_json = st.columns(2)
    with col_md:
        st.download_button(
            "Download Markdown Report (.md)", data=ss.report_md,
            file_name=f"truthengine_report_{stamp}.md", mime="text/markdown", **STRETCH,
        )
    with col_json:
        st.download_button(
            "Export Verified Claims (.json)", data=claims_json,
            file_name=f"truthengine_claims_{stamp}.json", mime="application/json", **STRETCH,
        )

    spacer()
    st.markdown(ss.report_md)
