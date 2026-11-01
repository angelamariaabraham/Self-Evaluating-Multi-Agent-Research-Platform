from checks import span_in_source, span_near

BASE = 0.90
PENALTY = {
    "near_only": 0.05,       # span matches the source only loosely
    "contradicted": 0.30,    # flagged by contradiction stage
    "weak": 0.25,            # devil's advocate marked evidence weak
    "check_missing": 0.10,   # a check failed to run
}
CAP_UNSUPPORTED = 0.20       # span does not back the claim


def score_claim(c):
    """Return (score, reasons). Rules only, no LLM."""
    strict = span_in_source(c.source_url, c.evidence_span)
    near = strict or span_near(c.source_url, c.evidence_span)
    if not near:
        return 0.0, ["evidence span not found in source"]

    s, why = BASE, []
    if not strict:
        s -= PENALTY["near_only"]
        why.append("span matches source only loosely")
    if c.span_supports_claim is False:
        s = min(s, CAP_UNSUPPORTED)
        why.append("claim says more than its evidence span")
    elif c.span_supports_claim is None:
        s -= PENALTY["check_missing"]
        why.append("support check did not run")
    if c.contradiction_flag:
        s -= PENALTY["contradicted"]
        why.append("contradicted by another source")
    elif c.contradiction_flag is None:
        s -= PENALTY["check_missing"]
        why.append("contradiction check did not run")
    if c.stress_verdict == "weak":
        s -= PENALTY["weak"]
        why.append(f"weak evidence ({c.stress_weakness})")
    elif c.stress_verdict is None:
        s -= PENALTY["check_missing"]
        why.append("evidence-strength check did not run")
    return max(0.0, round(s, 2)), why


def band(x: float) -> str:
    return "high" if x >= 0.75 else ("medium" if x >= 0.5 else "low")


def score_all(claims):
    for c in claims:
        c.confidence, c.confidence_reasons = score_claim(c)