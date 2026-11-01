"""The verification stages, shared by the main Verify button and the Stages tab."""
import datetime
import json
from typing import List

import streamlit as st

from checks import span_in_source
from confidence import score_all
from contradiction import run_contradiction
from devils_advocate import run_stress
from llm_util import QuotaExhausted
from report import build_report
from support import check_support

from .runs_io import RUNS_DIR


def run_verification(topic: str, claims) -> List[str]:
    """Run all 5 stages on `claims`, writing progress with st.write.

    Updates st.session_state (cres, sres, report_md) and saves stages/report files.
    Returns names of stages paused by API quota (empty list = all finished).
    """
    ss = st.session_state
    paused: List[str] = []

    st.write("**Stage 1/5: Checking span faithfulness in raw markdown...**")
    ok_count = sum(span_in_source(c.source_url, c.evidence_span) for c in claims)
    st.write(f"✓ {ok_count}/{len(claims)} claims match source markdown verbatim.")

    st.write("**Stage 2/5: Evaluating support entailment (does the evidence back the claim?)...**")
    try:
        check_support(claims)
        overstated = sum(1 for c in claims if c.span_supports_claim is False)
        st.write(f"✓ Support check completed. {overstated} claims overstated their evidence.")
    except QuotaExhausted as e:
        st.warning(f"Quota paused in support check: {e}")
        paused.append("support")

    st.write("**Stage 3/5: Cross-checking candidate source pairs for contradictions...**")
    try:
        ss.cres = run_contradiction(claims)
        st.write(f"✓ Contradiction detection completed: {len(ss.cres.flags)} conflicts detected.")
    except QuotaExhausted as e:
        st.warning(f"Quota paused in contradiction check: {e}")
        paused.append("contradiction")

    st.write("**Stage 4/5: Devil's Advocate adversarial stress testing...**")
    try:
        ss.sres = run_stress(claims)
        weak = sum(i.verdict == "weak" for i in ss.sres.items)
        holds = sum(i.verdict == "holds" for i in ss.sres.items)
        st.write(f"✓ Stress testing completed: {weak} weak, {holds} holds.")
    except QuotaExhausted as e:
        st.warning(f"Quota paused in Devil's Advocate stage: {e}")
        paused.append("devils_advocate")

    st.write("**Stage 5/5: Deterministic confidence scoring and report synthesis...**")
    score_all(claims)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    RUNS_DIR.mkdir(exist_ok=True)
    with open(RUNS_DIR / f"stages_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump({
            "incomplete": paused,
            "contradiction": ss.cres.model_dump(),
            "stress": ss.sres.model_dump(),
            "claims": [c.model_dump() for c in claims],
        }, f, ensure_ascii=False, indent=2)

    report_path = RUNS_DIR / f"report_{stamp}.md"
    build_report(topic, claims, ss.cres, ss.sres, str(report_path))
    if report_path.exists():
        ss.report_md = report_path.read_text(encoding="utf-8")
    return paused
