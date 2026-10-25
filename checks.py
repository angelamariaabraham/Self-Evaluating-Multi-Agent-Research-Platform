
#checks.py
import re
from sources import load_source

def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)   # keep letters and digits only
    return s.strip()

def span_in_source(source_url: str, evidence_span: str, min_words: int = 8) -> bool:
    source = normalize(load_source(source_url))
    span = normalize(evidence_span)
    if not source or len(span.split()) < min_words:
        return False
    return span in source


def faithfulness_rate(claims) -> float:
    """claims: list of Claim objects. Fraction with a verifiable span."""
    if not claims:
        return 0.0
    ok = sum(span_in_source(c.source_url, c.evidence_span) for c in claims)
    return ok / len(claims)


def mismatch_report(source_url: str, evidence_span: str) -> str:
    src = normalize(load_source(source_url))
    sp = normalize(evidence_span)
    n = 0
    while n < len(sp) and sp[: n + 1] in src:
        n += 1

    if n == len(sp):
        if len(sp.split()) < 8:
            return "full match but span is under 8 words"
        return "full match"
    if n < 15:
        return "span does not start anywhere in the source (invented or heavily altered)"
    start = src.find(sp[:n])
    return (f"matches first {n} of {len(sp)} chars\n"
            f"  SPAN  continues: ...{sp[max(0, n - 30): n + 40]}\n"
            f"  SOURCE continues: ...{src[start + max(0, n - 30): start + n + 40]}")


def span_near(source_url: str, evidence_span: str, max_skip: int = 4, min_words: int = 8) -> bool:
    """Span words appear in order in the source, with at most max_skip extra source words."""
    src = normalize(load_source(source_url)).split()
    sp = normalize(evidence_span).split()
    if not src or len(sp) < min_words:
        return False
    for i, w0 in enumerate(src):
        if w0 != sp[0]:
            continue
        j, skipped, ok = i, 0, True
        for w in sp:
            hit = None
            for k in range(j, min(j + max_skip + 1, len(src))):
                if src[k] == w:
                    hit = k
                    break
            if hit is None:
                ok = False
                break
            skipped += hit - j
            j = hit + 1
            if skipped > max_skip:
                ok = False
                break
        if ok:
            return True
    return False


def near_rate(claims) -> float:
    if not claims:
        return 0.0
    return sum(span_near(c.source_url, c.evidence_span) for c in claims) / len(claims)