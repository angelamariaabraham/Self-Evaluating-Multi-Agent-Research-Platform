import os, re, json, time, hashlib, logging
import litellm
from dotenv import load_dotenv
from schema import StressItem, StressResult
from llm_util import call, QuotaExhausted


load_dotenv()
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

MODEL = "gemini/gemini-3.5-flash-lite"
CALL_GAP = 4.5
CACHE_PATH = "runs/da_cache.json"
WEAKNESSES = ["hedged", "promotional", "overgeneral", "causal", "no_basis", "none"]

PROMPT = """You review one EVIDENCE sentence taken from a web page. Judge only how strong the sentence is as evidence.
Use ONLY the wording of the sentence. Do not use outside knowledge. Do not judge whether the fact is true.

Mark it WEAK if it has any of these problems:
- hedged: uses may, might, could, suggests or similar uncertainty words.
- promotional: a seller or author describes its own product, service or work, or uses marketing wording.
- overgeneral: sweeping wording such as generally, often, all, always, never, or a claim about what a whole group (engineers, researchers, experts) thinks or does. A statement is not overgeneral just because it says something is a challenge or is important.
- causal: states a cause or an effect without naming any method, data or study.
- no_basis: gives a number or result without a citable source. An institution name, a company name or a year alone is NOT a citable source. A citable source needs a paper title, authors, journal, venue or named dataset.
Mark WEAK only for a problem from the list above. If you cannot name one of the five, mark HOLDS.
Otherwise mark it HOLDS: a specific, checkable statement, or a plain definition, with nothing above.

Reply with JSON only, no other text, no code fences:
{{"verdict": "holds" or "weak", "weakness": "hedged" or "promotional" or "overgeneral" or "causal" or "no_basis" or "none", "reason": "one short sentence quoting the words that decided it"}}

EVIDENCE: {span}"""

os.makedirs("runs", exist_ok=True)
try:
    _cache = json.load(open(CACHE_PATH, encoding="utf-8"))
except Exception:
    _cache = {}


def _parse(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    v = str(d.get("verdict", "")).lower()
    w = str(d.get("weakness", "")).lower()
    if v not in ("holds", "weak"):
        return None
    if w not in WEAKNESSES:
        w = "none" if v == "holds" else "no_basis"
    if v == "holds":
        w = "none"
    return {"verdict": v, "weakness": w, "reason": str(d.get("reason", ""))[:300]}


def judge(span: str):
    """Returns dict with verdict, weakness, reason. None if failed."""
    prompt = PROMPT.format(span=span)
    key = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    if key in _cache:
        return _cache[key]
    for attempt in range(3):
        try:
            text = call(prompt)
            out = _parse(text) if text else None
            if out:
                _cache[key] = out
                json.dump(_cache, open(CACHE_PATH, "w", encoding="utf-8"))
                return out
        except QuotaExhausted:
            raise
        except Exception as e:
            print("  da llm error:", type(e).__name__)
            time.sleep(10 * (attempt + 1))
    return None


def run_stress(claims) -> StressResult:
    items, failed = [], 0
    for c in claims:
        out = judge(c.evidence_span)
        if out is None:
            failed += 1
            continue
        c.stress_verdict = out["verdict"]
        c.stress_weakness = out["weakness"]
        items.append(StressItem(claim_id=c.claim_id, verdict=out["verdict"],
                                weakness=out["weakness"], reason=out["reason"]))
    print(f"devil's advocate: {sum(i.verdict == 'weak' for i in items)} weak, "
          f"{sum(i.verdict == 'holds' for i in items)} holds, {failed} failed")
    return StressResult(items=items, failed=failed)