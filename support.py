import os, json, time, hashlib, logging
import litellm
from dotenv import load_dotenv
from checks import normalize

load_dotenv()
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

MODEL = "gemini/gemini-3.5-flash-lite"
CALL_GAP = 4.5
CACHE_PATH = "runs/support_cache.json"

PROMPT = """You check whether a CLAIM is fully supported by an EVIDENCE sentence.
Use ONLY the evidence. If the claim adds, changes or contradicts anything, it is not supported.
Answer deterministically with exactly one word: SUPPORTED or UNSUPPORTED.

EVIDENCE: {span}
CLAIM: {claim}"""

os.makedirs("runs", exist_ok=True)
try:
    _cache = json.load(open(CACHE_PATH, encoding="utf-8"))
except Exception:
    _cache = {}


def _unsupported(span: str, claim: str):
    """True = unsupported, False = supported, None = failed."""
    prompt = PROMPT.format(span=span, claim=claim)
    key = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    if key in _cache:
        return _cache[key]
    for attempt in range(4):
        try:
            r = litellm.completion(
                model=MODEL, api_key=os.environ["GEMINI_API_KEY"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0, timeout=60, num_retries=0)
            text = (r.choices[0].message.content or "").strip().upper()
            if text:
                verdict = text.startswith("UNSUPPORTED")
                _cache[key] = verdict
                json.dump(_cache, open(CACHE_PATH, "w", encoding="utf-8"))
                time.sleep(CALL_GAP)
                return verdict
        except Exception as e:
            print("  support llm error:", type(e).__name__)
            time.sleep(20 * (attempt + 1))
    return None


def check_support(claims):
    """Fills claim.span_supports_claim. Skips the LLM when claim equals span."""
    calls = 0
    for c in claims:
        if normalize(c.claim_text) == normalize(c.evidence_span):
            c.span_supports_claim = True
            continue
        v = _unsupported(c.evidence_span, c.claim_text)
        calls += 1
        c.span_supports_claim = None if v is None else (not v)
    n_bad = sum(1 for c in claims if c.span_supports_claim is False)
    n_fail = sum(1 for c in claims if c.span_supports_claim is None)
    print(f"support check: {n_bad} unsupported, {n_fail} failed, {calls} llm checks")