"""Shared UI pieces: CSS loader, small HTML builders, and the static page sections."""
import html
import inspect
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from checks import faithfulness_rate

CSS_PATH = Path(__file__).with_name("styles.css")

# Full-width buttons/tables. Newer Streamlit uses width="stretch"; older uses use_container_width.
STRETCH = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.button).parameters
    else {"use_container_width": True}
)


def nav_icon(name: str) -> dict:
    """Material icon kwargs for st.button, or {} on Streamlit versions without `icon`."""
    if "icon" in inspect.signature(st.button).parameters:
        return {"icon": f":material/{name}:"}
    return {}


def esc(value) -> str:
    """Escape for HTML and flatten whitespace.

    Claim text, evidence spans and LLM explanations come from scraped pages and model
    output. They must never reach unsafe_allow_html raw. Blank lines are collapsed too:
    a blank line ends an HTML block in Markdown and breaks the card layout.
    """
    return html.escape(" ".join(str(value).split()), quote=True)


def safe_url(url) -> str:
    """Allow only http(s) links in href attributes."""
    url = str(url)
    return url if url.startswith(("http://", "https://")) else "#"


def domain_of(url) -> str:
    return urlparse(str(url)).netloc or str(url)


def initials(name: str) -> str:
    return "".join(p[0].upper() for p in str(name).split()[:2]) or "R"


def show_html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def spacer() -> None:
    show_html("<br>")


def load_css() -> None:
    show_html(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>")


# --- Small builders. Anything passed as HTML must already be escaped with esc(). ---

def badge(text, tone: str) -> str:
    return f"<span class='badge badge-{tone}'>{esc(text)}</span>"


def status_dot(text: str, tone: str) -> str:
    """tone: good | warn | bad"""
    return f'<span class="dot dot-{tone}"></span> {esc(text)}'


def alert_card(tone: str, head_left: str, head_right: str = "", body: str = "") -> None:
    """Tinted card. tone: violet | amber | rose."""
    show_html(
        f'<div class="alert-card alert-{tone}">'
        f'<div class="alert-head"><div>{head_left}</div><div>{head_right}</div></div>'
        f"{body}</div>"
    )


def stat_tile(label: str, value, tone: str) -> None:
    """tone: good | warn | bad | violet | muted"""
    show_html(
        f'<div class="stat-tile"><div class="stat-label">{esc(label)}</div>'
        f'<div class="stat-num tone-{tone}">{esc(value)}</div></div>'
    )


def kv_panel(title: str, rows) -> None:
    """Card with label/value rows. rows: list of (label, value). Values are escaped."""
    body = "".join(f'<div class="kv"><span>{esc(k)}</span><span>{esc(v)}</span></div>' for k, v in rows)
    show_html(f'<div class="panel"><div class="panel-title">{esc(title)}</div>{body}</div>')


def feature_card(title: str, blurb: str) -> None:
    show_html(
        f'<div class="feature"><div class="feature-title">{esc(title)}</div>'
        f'<div class="feature-blurb">{esc(blurb)}</div></div>'
    )


def section_label(text: str) -> None:
    show_html(f'<div class="section-label">{esc(text)}</div>')


# --- Sidebar pieces ---

def brand() -> None:
    show_html(
        '<div class="brand"><div class="brand-mark">T</div>'
        '<div><div class="brand-name">TruthEngine</div>'
        '<div class="brand-sub">Research verification</div></div></div>'
    )


def account_chip(name: str, role: str = "") -> None:
    show_html(
        f'<div class="acct"><div class="avatar">{esc(initials(name))}</div>'
        f'<div><div class="acct-name">{esc(name)}</div>'
        f'<div class="acct-role">{esc(role or "Researcher")}</div></div></div>'
    )


# --- Page sections ---

def page_header(title: str, subtitle: str, model: str, keys_ok: bool) -> None:
    keys = status_dot("Keys ready", "good") if keys_ok else status_dot("Keys missing", "warn")
    show_html(
        '<div class="page-header">'
        f'<div><div class="page-title">{esc(title)}</div><div class="page-sub">{esc(subtitle)}</div></div>'
        '<div class="page-pills">'
        f'<span class="pill pill-mono">{esc(model)}</span>'
        f'<span class="pill">{keys}</span>'
        "</div></div>"
    )


def render_hero() -> None:
    show_html(
        '<div class="hero">'
        '<div class="hero-eyebrow">Research verification</div>'
        '<div class="hero-title">Check every claim against its source</div>'
        '<p class="hero-lead">Pick an archived run or enter a topic. TruthEngine checks each quoted span '
        "against its source, then flags weak evidence, overreach and contradictions.</p>"
        "</div>"
    )


def _metric(label: str, value: str, footer: str, tone: str) -> str:
    return (
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-num tone-{tone}">{value}</div>'
        f'<div class="metric-footer">{footer}</div></div>'
    )


def render_metrics(claims) -> None:
    n = len(claims)
    if n:
        avg_conf = sum((c.confidence or 0) for c in claims) / n * 100
        faithful = faithfulness_rate(claims) * 100
        contradicted = sum(1 for c in claims if c.contradiction_flag)
        weak = sum(1 for c in claims if c.stress_verdict == "weak")
        conf_tone = "good" if avg_conf >= 70 else ("warn" if avg_conf >= 50 else "bad")
        contra_tone = "violet" if contradicted else "muted"
        weak_tone = "warn" if weak else "muted"
        faith_tone = "violet"
    else:
        avg_conf = faithful = contradicted = weak = 0
        conf_tone = contra_tone = weak_tone = faith_tone = "muted"

    show_html(
        '<div class="metrics-ribbon">'
        + _metric("Verified Claims", str(n), "Atomic claims", "muted" if not n else "violet")
        + _metric("Mean Confidence", f"{avg_conf:.1f}%", "Calibrated score", conf_tone)
        + _metric("Faithfulness", f"{faithful:.0f}%", "Exact span in source", faith_tone)
        + _metric("Contradictions", str(contradicted), "Conflicting pairs", contra_tone)
        + _metric("Epistemic Flaws", str(weak), "Hedged, causal, unbacked", weak_tone)
        + "</div>"
    )


def render_footer() -> None:
    show_html('<div class="web-footer">TruthEngine · multi-agent claim verification</div>')
