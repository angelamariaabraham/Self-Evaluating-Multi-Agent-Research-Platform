from schema import Claim
from contradiction import run_contradiction

def mk(i, url, text):
    return Claim(claim_id=f"T{i}", claim_text=text, source_url=url, evidence_span=text)

claims = [
    mk(1, "https://a.example", "Stanford research found that specialized legal AI tools hallucinate between 17% and 34% of the time."),
    mk(2, "https://b.example", "Stanford research found that specialized legal AI tools hallucinate less than 1% of the time."),
    mk(3, "https://c.example", "GPTZero's Hallucination Detector detects hallucinated sources in essays."),
]
res = run_contradiction(claims)
print(res.flags)
print([c.contradiction_flag for c in claims])