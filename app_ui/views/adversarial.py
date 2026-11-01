"""Tab 3: Devil's Advocate flaws, contradictions, and entailment leaps."""
from collections import Counter

import streamlit as st

from confidence import CAP_UNSUPPORTED
from devils_advocate import WEAKNESSES

from ..components import alert_card, badge, esc, spacer, stat_tile


def _weakness_counts(claims) -> Counter:
    return Counter(
        c.stress_weakness or ("none" if c.stress_verdict == "holds" else "untested")
        for c in claims
    )


def _contradictions() -> None:
    flags = st.session_state.cres.flags
    if not flags:
        st.info("No logical contradictions flagged among candidate pairs for this run.")
        return
    st.markdown(f"Found **{len(flags)}** cross-source contradiction flags:")
    for flag in flags:
        alert_card(
            "violet",
            head_left=badge("Contradiction", "violet") + f" <strong>Involved Claims: {esc(', '.join(flag.claim_ids))}</strong>",
            body=f'<div class="alert-text">{esc(flag.explanation)}</div>',
        )


def _weak_claims(claims) -> None:
    weak = [c for c in claims if c.stress_verdict == "weak"]
    if not weak:
        st.info("No claims flagged as weak by the Devil's Advocate stage in this run.")
        return
    reasons = {i.claim_id: i.reason for i in st.session_state.sres.items}
    for c in weak:
        flaw = (c.stress_weakness or "unspecified").upper()
        criticism = reasons.get(c.claim_id) or "Flagged for epistemic weakness in source formulation."
        alert_card(
            "amber",
            head_left=badge(f"Flaw: {flaw}", "amber"),
            head_right=f'<code class="code-chip">{esc(c.claim_id)}</code>',
            body=(
                f'<div class="alert-title">{esc(c.claim_text)}</div>'
                f'<div class="alert-note-amber">Criticism: {esc(criticism)}</div>'
            ),
        )


def _entailment_leaps(claims) -> None:
    unsupported = [c for c in claims if c.span_supports_claim is False]
    if not unsupported:
        st.info("All claims are backed by their underlying evidence spans without unearned leaps.")
        return
    for c in unsupported:
        alert_card(
            "rose",
            head_left=badge("Unsupported Entailment", "rose"),
            head_right=f'<code class="code-chip">{esc(c.claim_id)}</code>',
            body=(
                f'<div class="alert-title">Claim: {esc(c.claim_text)}</div>'
                f'<div class="alert-meta">Source Span: <em>"{esc(c.evidence_span)}"</em></div>'
                '<div class="alert-note-rose">Verdict: Claim asserts more than or contradicts its underlying '
                f"evidence sentence. Confidence capped at {CAP_UNSUPPORTED:.2f}.</div>"
            ),
        )


def render() -> None:
    claims = st.session_state.claims
    st.markdown(
        "The **Devil's Advocate Agent** evaluates evidence sentences for 5 distinct epistemic flaws "
        "without outside knowledge: `hedged`, `promotional`, `overgeneral`, `causal`, and `no_basis`. "
        "Claims with zero flaws are marked **HOLDS**."
    )

    counts = _weakness_counts(claims)
    for col, weakness in zip(st.columns(len(WEAKNESSES)), WEAKNESSES):
        with col:
            stat_tile(weakness, counts[weakness], "good" if weakness == "none" else "warn")

    spacer()
    tab_contra, tab_weak, tab_leaps = st.tabs([
        "Cross-Source Contradiction Pairs",
        "Devil's Advocate Criticisms",
        "Entailment Leaps",
    ])
    with tab_contra:
        _contradictions()
    with tab_weak:
        _weak_claims(claims)
    with tab_leaps:
        _entailment_leaps(claims)
