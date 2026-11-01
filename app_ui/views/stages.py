"""Tab 2: run verification stages on loaded claims, interactive stage audit dashboard, plus sandbox."""
import pandas as pd
import streamlit as st

from checks import faithfulness_rate, span_in_source, span_near
from confidence import BASE, band, score_all, score_claim
from devils_advocate import WEAKNESSES, run_stress
from llm_util import QuotaExhausted
from schema import Claim
from support import check_support

from ..components import STRETCH, alert_card, badge, esc, show_html, spacer, stat_tile
from ..runner import run_verification
from ..state import go


def _run_stages(topic: str) -> None:
    ss = st.session_state
    ss.current_topic = topic
    if not ss.claims:
        st.warning("No claims currently loaded. Please select an archived run or enter a topic.")
        return

    with st.status("Executing Multi-Agent Verification Network...", expanded=True) as status:
        paused = run_verification(topic, ss.claims)
        if paused:
            msg = f"Verification finished with paused stages ({', '.join(paused)}) due to API quota limits."
            status.update(label=msg, state="error")
            ss.flash = ("warning", msg)
        else:
            msg = f"All 5 verification stages completed successfully for '{topic}'."
            status.update(label=msg, state="complete")
            ss.flash = ("success", msg)
    st.rerun()


def _render_pipeline_dashboard() -> None:
    ss = st.session_state
    claims = ss.claims
    cres = ss.cres
    sres = ss.sres

    if not claims:
        st.info("No claims currently loaded. Enter a topic above or pick an archived run from the sidebar.")
        return

    n = len(claims)
    faithful_count = sum(span_in_source(c.source_url, c.evidence_span) for c in claims)
    faithful_pct = (faithful_count / n * 100) if n else 0
    overstated = sum(1 for c in claims if c.span_supports_claim is False)
    contra_count = len(cres.flags) if cres else 0
    weak_count = sum(1 for c in claims if c.stress_verdict == "weak")
    holds_count = sum(1 for c in claims if c.stress_verdict == "holds")
    avg_conf = (sum((c.confidence or 0) for c in claims) / n * 100) if n else 0

    st.markdown("### Pipeline Execution Telemetry")
    st.caption(f"Active run: **{ss.current_topic}** &nbsp;·&nbsp; {n} atomic claims evaluated across 5 verification stages.")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        stat_tile("Stage 1: Faithfulness", f"{faithful_pct:.0f}%", "good" if faithful_pct >= 85 else "warn")
        st.caption(f"{faithful_count}/{n} exact source matches")
    with c2:
        entail_tone = "good" if overstated == 0 else "bad"
        stat_tile("Stage 2: Entailment", f"{n - overstated}/{n}", entail_tone)
        st.caption(f"{overstated} unsupported leaps capped")
    with c3:
        contra_tone = "good" if contra_count == 0 else "bad"
        stat_tile("Stage 3: Contradictions", str(contra_count), contra_tone)
        st.caption(f"{cres.pairs_checked if cres else 0} cross-source pairs checked")
    with c4:
        stress_tone = "good" if weak_count == 0 else "warn"
        stat_tile("Stage 4: Devil's Advocate", f"{holds_count}H / {weak_count}W", stress_tone)
        st.caption(f"{weak_count} epistemic flaws flagged")
    with c5:
        conf_tone = "good" if avg_conf >= 75 else ("warn" if avg_conf >= 50 else "bad")
        stat_tile("Stage 5: Confidence", f"{avg_conf:.0f}%", conf_tone)
        st.caption("Mean calibrated confidence")

    spacer()

    tab_audit, tab_table, tab_actions = st.tabs([
        "Stage-by-Stage Detailed Audit",
        "Pipeline Claims Summary",
        "Next Steps & Navigation",
    ])

    with tab_audit:
        with st.expander("Stage 1: Source Span Faithfulness (checks.py)", expanded=False):
            st.markdown(
                "Verifies that each claim's quoted evidence sentence exists verbatim in the raw source document."
            )
            for c in claims:
                is_exact = span_in_source(c.source_url, c.evidence_span)
                is_near = is_exact or span_near(c.source_url, c.evidence_span)
                pill = badge("Verbatim", "emerald") if is_exact else (badge("Near Match", "amber") if is_near else badge("Mismatch", "rose"))
                st.markdown(f"**[{c.claim_id}]** {pill} *\"{c.evidence_span[:120]}...\"*")

        with st.expander("Stage 2: Support Entailment (support.py)", expanded=False):
            st.markdown(
                "Ensures the claim strictly follows from the quoted sentence. Claims that extrapolate or exaggerate are capped at `0.20`."
            )
            for c in claims:
                backed = c.span_supports_claim
                if backed is True:
                    status = badge("Strictly Entailed", "emerald")
                elif backed is False:
                    status = badge("Unsupported Leap (Capped at 20%)", "rose")
                else:
                    status = badge("Untested", "neutral")
                st.markdown(f"**[{c.claim_id}]** {status} {c.claim_text}")

        with st.expander("Stage 3: Cross-Source Contradictions (contradiction.py)", expanded=False):
            st.markdown(
                f"Evaluated **{cres.pairs_checked if cres else 0}** cross-source claim pairs for conflicting numbers, dates, scope words, and facts."
            )
            if cres and cres.flags:
                for flag in cres.flags:
                    alert_card(
                        "violet",
                        head_left=badge("Contradiction Flag", "violet") + f" <strong>Claims: {esc(', '.join(flag.claim_ids))}</strong>",
                        body=f'<div class="alert-text">{esc(flag.explanation)}</div>',
                    )
            else:
                st.info("✓ Zero logical contradictions detected across candidate source pairs.")

        with st.expander("Stage 4: Devil's Advocate Stress Testing (devils_advocate.py)", expanded=False):
            st.markdown(
                "Adversarially scrutinizes evidence sentences against 5 epistemic flaws: `promotional`, `hedged`, `overgeneral`, `causal`, `no_basis`."
            )
            reasons = {i.claim_id: i.reason for i in (sres.items if sres else [])}
            weak_items = [c for c in claims if c.stress_verdict == "weak"]
            if weak_items:
                for c in weak_items:
                    crit = reasons.get(c.claim_id, "Flagged for weak evidence formulation.")
                    alert_card(
                        "amber",
                        head_left=badge(f"Weakness: {c.stress_weakness.upper()}", "amber"),
                        head_right=f'<code class="code-chip">{esc(c.claim_id)}</code>',
                        body=f'<div class="alert-title">{esc(c.claim_text)}</div><div class="alert-note-amber">Criticism: {esc(crit)}</div>',
                    )
            else:
                st.info("✓ All claims passed Devil's Advocate scrutiny with verdict HOLDS.")

        with st.expander("Stage 5: Deterministic Confidence Scoring (confidence.py)", expanded=False):
            st.markdown(
                "Scores are computed deterministically from a `0.90` base with rule deductions: `-0.30` for contradictions, `-0.25` for weak evidence, and capped at `0.20` for entailment leaps."
            )
            for c in sorted(claims, key=lambda x: -(x.confidence or 0)):
                conf_pct = round((c.confidence or 0) * 100)
                reasons_text = "; ".join(c.confidence_reasons) if c.confidence_reasons else "Clean audit (no deductions)"
                st.write(f"- **[{c.claim_id}] {conf_pct}% ({band(c.confidence or 0).upper()})**: {reasons_text}")

    with tab_table:
        data = []
        for c in claims:
            data.append({
                "Claim ID": c.claim_id,
                "Claim Statement": c.claim_text[:80] + ("..." if len(c.claim_text) > 80 else ""),
                "Faithful": "Verbatim" if span_in_source(c.source_url, c.evidence_span) else "Mismatch",
                "Entailed": "YES" if c.span_supports_claim is True else ("NO" if c.span_supports_claim is False else "Untested"),
                "Contradicted": "YES" if c.contradiction_flag else "No",
                "Stress Verdict": (c.stress_verdict or "untested").upper(),
                "Confidence": f"{(c.confidence or 0) * 100:.0f}%",
                "Band": band(c.confidence or 0).upper(),
            })
        st.dataframe(pd.DataFrame(data), **STRETCH)

    with tab_actions:
        st.markdown("#### Ready to inspect the outputs?")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("Explore in Claims Explorer →", type="primary", **STRETCH, key="goto_explorer_btn"):
                go("Claims Explorer")
        with b2:
            if st.button("View & Export Report →", **STRETCH, key="goto_report_btn"):
                go("Report")
        with b3:
            if st.button("Inspect Scraped Sources in Vault →", **STRETCH, key="goto_vault_btn"):
                go("Evidence Vault")


def _sandbox() -> None:
    st.subheader("Single-Claim Sandbox Tester")
    st.caption("Test the verification logic on any custom statement and evidence sentence on-the-fly.")

    left, right = st.columns(2)
    with left:
        claim_text = st.text_area(
            "Test Claim Statement",
            value="",
            placeholder="Type or paste any claim statement to test...",
        )
    with right:
        span_text = st.text_area(
            "Test Quoted Evidence Span",
            value="",
            placeholder="Type or paste the quoted sentence from the source...",
        )

    if not st.button("Evaluate Test Claim", key="eval_single_btn"):
        return

    if not claim_text.strip() or not span_text.strip():
        st.warning("Please enter both a claim statement and an evidence sentence to evaluate.")
        return

    dummy = Claim(claim_id="TEST01", claim_text=claim_text.strip(), source_url="https://example.com/test", evidence_span=span_text.strip())
    try:
        check_support([dummy])
        run_stress([dummy])
    except QuotaExhausted:
        st.warning("API quota paused part of the test. Showing what finished.")
    score, reasons = score_claim(dummy)

    c1, c2, c3 = st.columns(3)
    entailed = "YES" if dummy.span_supports_claim else ("NO" if dummy.span_supports_claim is False else "Unknown")
    c1.metric("Entailment Backed", entailed)
    c2.metric("Stress Verdict", (dummy.stress_verdict or "untested").upper())
    c3.metric("Calibrated Confidence", f"{score * 100:.0f}%")
    if reasons:
        st.caption(f"Score Factors: {'; '.join(reasons)}")


def render() -> None:
    ss = st.session_state
    topic = st.text_input("Topic to Run", value=ss.current_topic, help="Used to title the saved report.")

    col_run, col_recalc = st.columns(2)
    with col_run:
        run_btn = st.button("Run verification stages", type="primary", **STRETCH)
    with col_recalc:
        recalc_btn = st.button("Recalibrate All Confidence Scores", **STRETCH)

    if recalc_btn:
        score_all(ss.claims)
        ss.flash = ("success", "Recomputed confidence scores for all claims.")
        st.rerun()
    if run_btn:
        _run_stages(topic)

    spacer()
    _render_pipeline_dashboard()

    spacer()
    st.divider()
    _sandbox()
