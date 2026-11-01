"""Tab 1: filterable claim list with a per-claim audit."""
import streamlit as st

from checks import mismatch_report, span_in_source, span_near
from confidence import BASE, band

from ..components import badge, domain_of, esc, safe_url, show_html

VERDICT_FILTERS = {
    "All Verdicts": lambda c: True,
    "Holds (Strong)": lambda c: c.stress_verdict == "holds",
    "Weak Evidence": lambda c: c.stress_verdict == "weak",
    "Unsupported Entailment": lambda c: c.span_supports_claim is False,
}
CONTRA_FILTERS = {
    "All Claims": lambda c: True,
    "Contradicted Only": lambda c: bool(c.contradiction_flag),
    "Non-Contradicted Only": lambda c: not c.contradiction_flag,
}
BAND_FILTERS = {
    "All Confidence": lambda c: True,
    "High (≥75%)": lambda c: (c.confidence or 0) >= 0.75,
    "Medium (50–74%)": lambda c: 0.50 <= (c.confidence or 0) < 0.75,
    "Low (<50%)": lambda c: (c.confidence or 0) < 0.50,
}
BAND_TONE = {"high": "emerald", "medium": "amber", "low": "rose"}
GAUGE_CLASS = {"high": "gauge-fill-high", "medium": "gauge-fill-med", "low": "gauge-fill-low"}


def _has_keyword(c, keyword: str) -> bool:
    if not keyword:
        return True
    kw = keyword.lower()
    return kw in c.claim_text.lower() or kw in c.evidence_span.lower() or kw in c.source_url.lower()


def _faith_pill(is_faithful: bool, is_near: bool) -> str:
    if is_faithful:
        return badge("Verbatim Span", "emerald")
    return badge("Near Match", "amber") if is_near else badge("Span Mismatch", "rose")


def _stress_pill(c) -> str:
    if c.stress_verdict == "holds":
        return badge("Holds", "emerald")
    if c.stress_verdict == "weak":
        return badge(f"Weak ({c.stress_weakness or 'flaw'})", "amber")
    return badge("Pending Stress", "neutral")


def _support_pill(c) -> str:
    if c.span_supports_claim is False:
        return badge("Entailment Capped", "rose")
    if c.span_supports_claim is True:
        return badge("Supported", "emerald")
    return ""


def _claim_card(c, is_faithful: bool, is_near: bool) -> None:
    conf = c.confidence or 0
    conf_pct = round(conf * 100)
    c_band = band(conf)
    pills = "".join([
        badge(f"Confidence {conf_pct}% ({c_band.upper()})", BAND_TONE[c_band]),
        _stress_pill(c),
        badge("Contradicted", "violet") if c.contradiction_flag else "",
        _support_pill(c),
        _faith_pill(is_faithful, is_near),
    ])
    show_html(
        '<div class="claim-box"><div class="claim-top-row">'
        f'<div class="claim-pills"><code class="code-chip">{esc(c.claim_id)}</code>{pills}</div>'
        f'<div><a class="claim-link" href="{esc(safe_url(c.source_url))}" target="_blank" rel="noopener noreferrer">'
        f"{esc(domain_of(c.source_url))} ↗</a></div></div>"
        f'<div class="claim-headline">{esc(c.claim_text)}</div>'
        f'<div class="gauge-track"><div class="{GAUGE_CLASS[c_band]}" style="width: {conf_pct}%;"></div></div>'
        "</div>"
    )


def _audit(c, is_faithful: bool) -> None:
    ss = st.session_state
    left, right = st.columns(2)
    with left:
        st.markdown("**Quoted Sentence from Source Webpage:**")
        st.markdown(f"> *\"{c.evidence_span}\"*")
        if is_faithful:
            st.success("Verbatim 100% character match in raw webpage source.")
        else:
            st.caption("Character Divergence vs. Scraped Webpage Text:")
            st.code(mismatch_report(c.source_url, c.evidence_span), language="text")

    with right:
        st.markdown("**Calibrated Score Formulation:**")
        st.write(f"- Base Confidence: `{BASE:.2f}`")
        if c.confidence_reasons:
            for reason in c.confidence_reasons:
                st.write(f"- Deduction: `{reason}`")
        else:
            st.write("- No deductions applied (Rigorous verification)")
        st.write(f"- Final Calibrated Score: **`{(c.confidence or 0):.2f}`**")

        if c.stress_verdict == "weak":
            st.markdown(f"**Devil's Advocate Ruling ({c.stress_weakness}):**")
            reason = next((i.reason for i in ss.sres.items if i.claim_id == c.claim_id), "")
            if reason:
                st.info(f"Rationale: {reason}")

        if c.contradiction_flag:
            st.markdown("**Contradiction Evidence:**")
            for flag in (f for f in ss.cres.flags if c.claim_id in f.claim_ids):
                others = [cid for cid in flag.claim_ids if cid != c.claim_id]
                st.warning(f"Conflicts with {', '.join(others)}: {flag.explanation}")


def render() -> None:
    claims = st.session_state.claims
    st.caption(f"Active run: **{st.session_state.current_topic}** ({len(claims)} claims loaded)")
    if not claims:
        st.info("No claims currently loaded. Enter a topic on the Home page and click 'Verify topic' to run live extraction, or select an archived run from the sidebar.")
        return

    col_verdict, col_contra, col_band, col_text = st.columns([2, 2, 2, 3])
    with col_verdict:
        verdict = st.selectbox("Verdict", list(VERDICT_FILTERS), label_visibility="collapsed")
    with col_contra:
        contra = st.selectbox("Contradiction", list(CONTRA_FILTERS), label_visibility="collapsed")
    with col_band:
        band_choice = st.selectbox("Confidence Band", list(BAND_FILTERS), label_visibility="collapsed")
    with col_text:
        keyword = st.text_input(
            "Filter claims...",
            placeholder="Filter claims by text, evidence, or domain...",
            label_visibility="collapsed",
        )

    shown = [
        c for c in claims
        if VERDICT_FILTERS[verdict](c)
        and CONTRA_FILTERS[contra](c)
        and BAND_FILTERS[band_choice](c)
        and _has_keyword(c, keyword)
    ]
    st.caption(f"Showing **{len(shown)}** of **{len(claims)}** claims")
    if not shown:
        st.info("No claims match the specified filter criteria.")
        return

    for c in shown:
        is_faithful = span_in_source(c.source_url, c.evidence_span)
        is_near = is_faithful or span_near(c.source_url, c.evidence_span)
        _claim_card(c, is_faithful, is_near)
        with st.expander(f"Inspect Epistemic Audit & Evidence Span for {c.claim_id}"):
            _audit(c, is_faithful)
