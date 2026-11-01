import os, re, json, time, hashlib, logging
import litellm
from dotenv import load_dotenv
from schema import ContradictionFlag, ContradictionResult
from llm_util import call

load_dotenv()
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

MODEL = "gemini/gemini-3.5-flash-lite"
CALL_GAP = 4.5               
CACHE_PATH = "runs/contradiction_cache.json"
MAX_PAIRS = 90
MIN_OVERLAP = 1
PROMPT = """Compare two claims. They CONTRADICT if they cannot both be true at the same time.
Check carefully for conflicts in: numbers, dates, names, quantities, and scope words (all, some, none, always, never, only).
Two claims about different topics are COMPATIBLE. A claim that is only more or less detailed than the other is COMPATIBLE.
Answer with exactly one word: CONTRADICT or COMPATIBLE.

CLAIM A: {a}
CLAIM B: {b}"""

os.makedirs("runs", exist_ok=True)
try:
    _cache = json.load(open(CACHE_PATH, encoding="utf-8"))
except Exception:
    _cache = {}


def judge(a: str, b: str):
    """True = contradict, False = compatible, None = failed."""
    prompt = PROMPT.format(a=a, b=b)
    key = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    if key in _cache:
        return _cache[key]
    text = call(prompt)
    if not text:
        return None
    verdict = text.upper().startswith("CONTRADICT")
    _cache[key] = verdict
    json.dump(_cache, open(CACHE_PATH, "w", encoding="utf-8"))
    return verdict







def _toks(s: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 3}


def candidate_pairs(claims):
    """Cross-source pairs that share topic words, most similar first."""
    cands = []
    for i, x in enumerate(claims):
        for y in claims[i + 1:]:
            if x.source_url == y.source_url:
                continue
            ov = len(_toks(x.claim_text) & _toks(y.claim_text))
            if ov >= MIN_OVERLAP:
                cands.append((ov, x, y))
    cands.sort(key=lambda t: -t[0])
    return [(x, y) for _, x, y in cands[:MAX_PAIRS]]


def run_contradiction(claims) -> ContradictionResult:
    pairs = candidate_pairs(claims)
    print(f"contradiction: checking {len(pairs)} candidate pairs")
    flags, failed = [], 0
    for x, y in pairs:
        v = judge(x.claim_text, y.claim_text)
        if v is None:
            failed += 1
        elif v:
            flags.append(ContradictionFlag(
                claim_ids=[x.claim_id, y.claim_id],
                explanation=f"A: {x.claim_text} | B: {y.claim_text}"))
    flagged = {cid for f in flags for cid in f.claim_ids}
    for c in claims:
        c.contradiction_flag = c.claim_id in flagged
    return ContradictionResult(flags=flags, pairs_checked=len(pairs), pairs_failed=failed)