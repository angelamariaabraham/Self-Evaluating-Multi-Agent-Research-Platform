import os
import sys
import asyncio
from datetime import datetime

# Windows terminal UTF-8 support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import streamlit as st
import litellm

# --- LiteLLM Patch ---
if not getattr(litellm, "_cache_breakpoint_patched", False):
    _original_completion = litellm.completion

    def _patched_completion(*args, **kwargs):
        messages = kwargs.get("messages")
        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    msg.pop("cache_breakpoint", None)
        return _original_completion(*args, **kwargs)

    litellm.completion = _patched_completion
    litellm._cache_breakpoint_patched = True

# --- API Keys ---
DEFAULT_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6JIkmiISrep91Jvzsd-5aRyukgc_93ajGeCdXIGvClF_A")
DEFAULT_FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-679d654c32e449119404fada655f687c")

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Veritas — Research Verification",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Minimalist, Restrained CSS ---
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  code, pre {
    font-family: 'JetBrains Mono', monospace !important;
  }

  /* Minimal, matte dark canvas */
  .stApp {
    background-color: #0d0f12;
    color: #e5e7eb;
  }

  /* Clean minimal header */
  .minimal-header {
    padding: 10px 0 24px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }

  .minimal-title {
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #f9fafb;
    margin: 0;
  }

  .minimal-subtitle {
    font-size: 0.85rem;
    color: #9ca3af;
    margin-top: 2px;
  }

  /* Subdued Tag Pills */
  .tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .tag-holds {
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
  }
  .tag-weak {
    background: rgba(245, 158, 11, 0.12);
    color: #fbbf24;
  }
  .tag-unsupported {
    background: rgba(239, 68, 68, 0.12);
    color: #f87171;
  }
  .tag-conflict {
    background: rgba(139, 92, 246, 0.12);
    color: #c084fc;
  }

  /* Card styling: crisp, subtle outline */
  div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #13161c !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 8px !important;
    transition: border-color 0.15s ease;
  }
  div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: rgba(255, 255, 255, 0.15) !important;
  }

  /* Button: understated minimal */
  div.stButton > button {
    background: #1f242d !important;
    color: #f3f4f6 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 6px !important;
    padding: 6px 16px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
  }
  div.stButton > button:hover {
    background: #282f3c !important;
    border-color: rgba(255, 255, 255, 0.25) !important;
    color: #ffffff !important;
  }

  /* Quick chips */
  .chip-btn div.stButton > button {
    background: transparent !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    color: #9ca3af !important;
    font-size: 0.78rem !important;
    padding: 3px 10px !important;
  }
  .chip-btn div.stButton > button:hover {
    color: #f3f4f6 !important;
    border-color: rgba(255, 255, 255, 0.2) !important;
  }

  /* Tabs styling */
  button[data-baseweb="tab"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
  }
</style>
""", unsafe_allow_html=True)

# --- Baseline Data ---
DEFAULT_CLAIMS = [
    {
        "id": "claim_1",
        "claim": "Fully remote work is associated with ~10% lower productivity than in-person work.",
        "contradiction": "Contradicted by claim_4, claim_11, and claim_12.",
        "verdict": "Weak",
        "score": 20,
        "source": "https://www.pewresearch.org/social-trends/2022/02/16/covid-19-pandemic-continues-to-reshape-work-in-america/",
        "justification": "Confuses correlation with causation. Lower output in remote setups often reflects legacy management and sudden forced transitions rather than intrinsic limits of remote work."
    },
    {
        "id": "claim_2",
        "claim": "Hybrid working appears to have no impact on productivity.",
        "contradiction": "Contradicted by absolute claim_6.",
        "verdict": "Unsupported",
        "score": 10,
        "source": "https://www.mckinsey.com/mgi/our-research/empty-spaces-and-hybrid-places-chapter-1",
        "justification": "Zero-impact claim assumes coordination friction perfectly cancels focus gains across all roles without granular proof."
    },
    {
        "id": "claim_3",
        "claim": "Hybrid working improves recruitment and employee retention.",
        "contradiction": "None.",
        "verdict": "Holds",
        "score": 85,
        "source": "https://news.stanford.edu/stories/2024/06/hybrid-work-is-a-win-win-win-for-companies-workers",
        "justification": "Robustly supported by revealed labor market choices, employee survey consensus, and wider hiring reach."
    },
    {
        "id": "claim_4",
        "claim": "BLS data links remote work to positive Total Factor Productivity growth.",
        "contradiction": "Contradicted by claim_1.",
        "verdict": "Weak",
        "score": 20,
        "source": "https://siepr.stanford.edu/publications/policy-brief/how-working-home-works-out",
        "justification": "Macro TFP reflects broader automation, cloud tech, and economic shifts. Attributing it directly to remote work is a post hoc fallacy."
    },
    {
        "id": "claim_5",
        "claim": "Remote and hybrid arrangements do not drag down economic output.",
        "contradiction": "None.",
        "verdict": "Unsupported",
        "score": 10,
        "source": "https://www.hbs.edu/faculty/Pages/item.aspx?num=66633",
        "justification": "Broad macroeconomic assertion that lacks sector-level granularity."
    },
    {
        "id": "claim_6",
        "claim": "Hybrid work has zero negative impact on performance.",
        "contradiction": "Contradicted by claim_2.",
        "verdict": "Unsupported",
        "score": 10,
        "source": "https://www.gallup.com/workplace/694361/hybrid-work-retreat-barely.aspx",
        "justification": "Absolute term 'zero' ignores documented communication silos and junior onboarding friction."
    },
    {
        "id": "claim_7",
        "claim": "Working from home 2 days a week maintains parity in productivity.",
        "contradiction": "None.",
        "verdict": "Weak",
        "score": 30,
        "source": "https://www.nber.org/system/files/working_papers/w30292/w30292.pdf",
        "justification": "Arbitrary 2-day threshold based largely on subjective self-reporting rather than audited output."
    },
    {
        "id": "claim_8",
        "claim": "Hybrid employees working 2 days at home have equal promotion rates.",
        "contradiction": "None.",
        "verdict": "Weak",
        "score": 30,
        "source": "https://www.nber.org/system/files/working_papers/w30292/w30292.pdf",
        "justification": "Conflicts with documented corporate proximity bias: out-of-sight often degrades promotion velocity."
    },
    {
        "id": "claim_9",
        "claim": "Two days remote per week significantly lowers quit rates.",
        "contradiction": "None.",
        "verdict": "Holds",
        "score": 85,
        "source": "https://news.stanford.edu/stories/2024/06/hybrid-work-is-a-win-win-win-for-companies-workers",
        "justification": "Consistently verified by HR attrition records showing schedule flexibility directly cuts turnover."
    },
    {
        "id": "claim_10",
        "claim": "Remote workers log fewer overall working hours.",
        "contradiction": "Conflicts with always-on studies.",
        "verdict": "Weak",
        "score": 20,
        "source": "https://www.gallup.com/workplace/693539/remote-staff-hours-fall-productivity-steady.aspx",
        "justification": "Contradicts evidence of blurred work-life boundaries. Digital activity monitoring is notoriously noisy."
    },
    {
        "id": "claim_11",
        "claim": "Output remains steady across remote cohorts.",
        "contradiction": "Contradicted by claim_1.",
        "verdict": "Weak",
        "score": 20,
        "source": "https://www.worktime.com/blog/statistics/remote-work-productivity-statistics-trends-data",
        "justification": "Cohort averages hide wide dispersion between high performers and struggling teams."
    },
    {
        "id": "claim_12",
        "claim": "Remote workers demonstrate >7% higher productivity than in-office peers.",
        "contradiction": "Contradicted by claim_1.",
        "verdict": "Weak",
        "score": 20,
        "source": "https://www.hbs.edu/faculty/Pages/item.aspx?num=66633",
        "justification": "Heavily skewed toward self-directed software tasks; neglects long-term mentorship and team cohesion erosion."
    }
]

# --- State ---
if "claims" not in st.session_state:
    st.session_state.claims = DEFAULT_CLAIMS
if "current_topic" not in st.session_state:
    st.session_state.current_topic = "Impact of remote work on productivity"
if "latest_markdown" not in st.session_state:
    st.session_state.latest_markdown = """# Stress-Test and Confidence-Scored Report: Remote and Hybrid Work Claims

### Core Findings
1. **Confirmed Retention Benefit (85%)**: Hybrid flexibility significantly reduces employee turnover.
2. **Contested Productivity Metrics (10–30%)**: Numerical claims (-10% vs +7%) suffer from high variance, selection bias, and contradictory research methodology.

*Synthesized across Stanford, NBER, Pew Research, Harvard Business School, and Gallup.*
"""

# --- Sidebar (Subtle & Compact) ---
with st.sidebar:
    st.caption("CONFIGURATION")
    selected_model = st.selectbox(
        "Model",
        options=["gemini/gemini-3.5-flash-lite", "gemini/gemini-3.5-flash"],
        index=0,
        label_visibility="collapsed"
    )
    source_limit = st.slider("Source Limit", min_value=3, max_value=8, value=5)
    
    st.divider()
    st.caption("CREDENTIALS")
    gemini_key = st.text_input("Gemini Key", value=DEFAULT_GEMINI_KEY, type="password")
    firecrawl_key = st.text_input("Firecrawl Key", value=DEFAULT_FIRECRAWL_KEY, type="password")
    
    os.environ["GEMINI_API_KEY"] = gemini_key
    os.environ["FIRECRAWL_API_KEY"] = firecrawl_key

# --- Minimal Header ---
st.markdown("""
<div class="minimal-header">
  <div>
    <h1 class="minimal-title">VERITAS ◇ RESEARCH</h1>
    <div class="minimal-subtitle">Multi-agent fact verification and adversarial stress-testing</div>
  </div>
  <div style="font-size: 0.8rem; color: #6b7280; font-family: monospace;">
    ● Gemini 3.5 &nbsp;·&nbsp; Firecrawl &nbsp;·&nbsp; CrewAI
  </div>
</div>
""", unsafe_allow_html=True)

# --- Search / Run Row ---
col_input, col_run = st.columns([5, 1])

with col_input:
    user_topic = st.text_input(
        "Topic",
        value=st.session_state.current_topic,
        placeholder="Enter research topic...",
        label_visibility="collapsed"
    )

with col_run:
    run_btn = st.button("Run Verification", use_container_width=True)

# Topic presets
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("Remote Work Productivity", key="t1", use_container_width=True):
        st.session_state.current_topic = "Impact of remote work on productivity"
        st.rerun()
with c2:
    if st.button("Solid-State Batteries 2027", key="t2", use_container_width=True):
        st.session_state.current_topic = "Commercial viability of solid-state batteries by 2027"
        st.rerun()
with c3:
    if st.button("Quantum vs RSA-2048", key="t3", use_container_width=True):
        st.session_state.current_topic = "Quantum computing threat to RSA-2048 cryptography"
        st.rerun()
with c4:
    if st.button("AI Coding & Code Quality", key="t4", use_container_width=True):
        st.session_state.current_topic = "Impact of AI coding assistants on software reliability"
        st.rerun()

# --- Execution Logic (If clicked) ---
if run_btn:
    st.session_state.current_topic = user_topic
    
    with st.status(f"Verifying: {user_topic}", expanded=True) as status_box:
        st.write("Harvesting credible web sources via Firecrawl...")
        try:
            from crewai import LLM, Agent, Task, Crew, Process
            from crewai.tools import tool
            from firecrawl import FirecrawlApp

            model = LLM(model=selected_model, api_key=os.environ["GEMINI_API_KEY"], max_retries=5)
            firecrawl_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])

            @tool("Firecrawl Web Search")
            def firecrawl_search(query: str) -> str:
                """Search web for credible sources."""
                results = firecrawl_client.search(query, limit=source_limit)
                items = results.get("data", []) if isinstance(results, dict) else (getattr(results, "data", None) or [])
                out = []
                for it in items:
                    u = it.get("url", "") if isinstance(it, dict) else getattr(it, "url", "")
                    t = it.get("title", "") if isinstance(it, dict) else getattr(it, "title", "")
                    d = (it.get("description", "") or "")[:300] if isinstance(it, dict) else (getattr(it, "description", "") or "")[:300]
                    out.append(f"URL: {u}\nTitle: {t}\nContent: {d}\n")
                return "\n---\n".join(out) if out else "No results found."

            r_agent = Agent(role="Web Researcher", goal="Collect raw sources.", backstory="Objective collector.", tools=[firecrawl_search], llm=model, verbose=False)
            a_agent = Agent(role="Analyst", goal="Extract atomic claims.", backstory="Extracts factual claims.", llm=model, verbose=False)
            c_agent = Agent(role="Fact-Checker", goal="Find contradictions.", backstory="Finds disagreements.", llm=model, verbose=False)
            d_agent = Agent(role="Devil's Advocate", goal="Stress-test reasoning.", backstory="Exposes flawed logic.", llm=model, verbose=False)
            rep_agent = Agent(role="Report Writer", goal="Score confidence and report.", backstory="Formats findings.", llm=model, verbose=False)

            t1 = Task(description=f"Gather 5 distinct sources on '{user_topic}'.", expected_output="5 sources.", agent=r_agent)
            t2 = Task(description="Extract atomic claims with URLs.", expected_output="List of claims.", agent=a_agent, context=[t1])
            t3 = Task(description="Identify contradictions across claims.", expected_output="Contradiction flags.", agent=c_agent, context=[t2])
            t4 = Task(description="Stress test each claim: Holds, Weak, Unsupported.", expected_output="Verdicts.", agent=d_agent, context=[t3])
            t5 = Task(description="Output structured report with confidence scores 0-100.", expected_output="Final report.", agent=rep_agent, context=[t4])

            crew = Crew(agents=[r_agent, a_agent, c_agent, d_agent, rep_agent], tasks=[t1, t2, t3, t4, t5], process=Process.sequential, verbose=False)
            st.write("Executing 5-agent verification pipeline...")
            result = crew.kickoff(inputs={"topic": user_topic})
            st.session_state.latest_markdown = getattr(result, "raw", str(result))
            status_box.update(label="Complete", state="complete", expanded=False)
        except Exception as e:
            status_box.update(label=f"Notice: {e}", state="error")

st.markdown("<br>", unsafe_allow_html=True)

# --- Minimal Metrics Row ---
total_claims = len(st.session_state.claims)
contradicted_count = sum(1 for c in st.session_state.claims if c["contradiction"] != "None.")
holds_count = sum(1 for c in st.session_state.claims if c["verdict"] == "Holds")
weak_count = sum(1 for c in st.session_state.claims if c["verdict"] in ["Weak", "Unsupported"])
contradiction_rate = round((contradicted_count / total_claims) * 100) if total_claims else 0

m1, m2, m3, m4 = st.columns(4)
with m1:
    with st.container(border=True):
        st.metric(label="Claims", value=total_claims)
with m2:
    with st.container(border=True):
        st.metric(label="Contested", value=f"{contradiction_rate}%")
with m3:
    with st.container(border=True):
        st.metric(label="Supported", value=holds_count)
with m4:
    with st.container(border=True):
        st.metric(label="Weak / Refuted", value=weak_count)

st.markdown("<br>", unsafe_allow_html=True)

# --- Clean Tabs ---
tab_claims, tab_report, tab_sources = st.tabs(["Claims Explorer", "Executive Summary", "Sources"])

# --- Tab 1: Minimal Claims Explorer ---
with tab_claims:
    col_f, col_s = st.columns([3, 2])
    with col_f:
        filter_option = st.radio(
            "Filter",
            options=["All", "Supported (Holds)", "Contested", "Weak / Unsupported"],
            horizontal=True,
            label_visibility="collapsed"
        )
    with col_s:
        search_query = st.text_input("Filter", placeholder="Filter claims...", label_visibility="collapsed")

    filtered = st.session_state.claims
    if filter_option == "Supported (Holds)":
        filtered = [c for c in filtered if c["verdict"] == "Holds"]
    elif filter_option == "Contested":
        filtered = [c for c in filtered if c["contradiction"] != "None."]
    elif filter_option == "Weak / Unsupported":
        filtered = [c for c in filtered if c["verdict"] in ["Weak", "Unsupported"]]

    if search_query:
        filtered = [c for c in filtered if search_query.lower() in c["claim"].lower() or search_query.lower() in c["justification"].lower()]

    st.caption(f"{len(filtered)} of {total_claims} claims")

    for c in filtered:
        with st.container(border=True):
            r1, r2 = st.columns([4, 1])
            with r1:
                # Minimal badges
                v_color = ":green-background[Holds]" if c["verdict"] == "Holds" else (":orange-background[Weak]" if c["verdict"] == "Weak" else ":red-background[Unsupported]")
                c_tag = " · :violet-background[Contested]" if c["contradiction"] != "None." else ""
                st.markdown(f"`{c['id']}` · {v_color}{c_tag}")
            with r2:
                st.markdown(f"<div style='text-align: right; color: #9ca3af; font-size: 0.85rem;'>Confidence <strong>{c['score']}%</strong></div>", unsafe_allow_html=True)

            st.markdown(f"**{c['claim']}**")

            with st.expander("Stress-test evaluation & citations", expanded=False):
                st.markdown(f"**Criticism:** {c['justification']}")
                if c["contradiction"] != "None.":
                    st.markdown(f"**Conflict:** {c['contradiction']}")
                st.markdown(f"**Source:** [{c['source']}]({c['source']})")

# --- Tab 2: Minimal Executive Summary ---
with tab_report:
    st.download_button(
        label="Download Markdown",
        data=st.session_state.latest_markdown,
        file_name=f"report_{datetime.now().strftime('%Y%m%d')}.md",
        mime="text/markdown"
    )
    st.markdown(st.session_state.latest_markdown)

# --- Tab 3: Sources ---
with tab_sources:
    sources = [
        {"title": "Study Finds Hybrid Work Benefits Companies and Employees", "inst": "Stanford SIEPR", "url": "https://news.stanford.edu/stories/2024/06/hybrid-work-is-a-win-win-win-for-companies-workers"},
        {"title": "How Hybrid Working From Home Works Out", "inst": "National Bureau of Economic Research (NBER)", "url": "https://www.nber.org/system/files/working_papers/w30292/w30292.pdf"},
        {"title": "Empty Spaces and Hybrid Places", "inst": "McKinsey Global Institute", "url": "https://www.mckinsey.com/mgi/our-research/empty-spaces-and-hybrid-places-chapter-1"},
        {"title": "COVID-19 Pandemic Continues To Reshape Work in America", "inst": "Pew Research Center", "url": "https://www.pewresearch.org/social-trends/2022/02/16/covid-19-pandemic-continues-to-reshape-work-in-america/"},
        {"title": "Remote Staff Hours Fall, but Productivity Steady", "inst": "Gallup", "url": "https://www.gallup.com/workplace/693539/remote-staff-hours-fall-productivity-steady.aspx"},
        {"title": "The Rise of Remote Work: Evidence on Productivity and Preferences", "inst": "Harvard Business School", "url": "https://www.hbs.edu/faculty/Pages/item.aspx?num=66633"}
    ]
    for s in sources:
        with st.container(border=True):
            st.markdown(f"**[{s['title']}]({s['url']})**")
            st.caption(f"{s['inst']} · [{s['url']}]({s['url']})")

st.markdown("<br>", unsafe_allow_html=True)
st.caption("Veritas · Minimal Fact Verification Engine")
