import re
from sources import load_source

def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)   # keep letters and digits only
    return s.strip()

def span_in_source(source_url: str, evidence_span: str) -> bool:
    source = normalize(load_source(source_url))
    span = normalize(evidence_span)
    if not source or len(span) < 20:    # too short = meaningless match
        return False
    return span in source


def faithfulness_rate(claims) -> float:
    """claims: list of Claim objects. Fraction with a verifiable span."""
    if not claims:
        return 0.0
    ok = sum(span_in_source(c.source_url, c.evidence_span) for c in claims)
    return ok / len(claims)