import os, re, sys, json, csv, time, hashlib, datetime, collections, logging
import litellm
from dotenv import load_dotenv
from checks import span_in_source

load_dotenv()
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)   # hides the warning spam

FRESH = "--fresh" in sys.argv        # ignore saved LLM answers, make a new run
MODEL = "gemini/gemini-3.5-flash-lite"
CALL_GAP = 4.5                       # seconds between real calls (free tier: 15/min)
CACHE_PATH = "eval/llm_cache.json"

items = json.load(open("eval/test_items.json", encoding="utf-8"))


def toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


# ---------- methods: return True (flag as bad), False (pass), None (failed) ----------

def m_spanmatch(it):
    return not span_in_source(it["source_url"], it["evidence_span"])


def m_numbers(it):
    nc = set(re.findall(r"\d+(?:\.\d+)?", it["claim"]))
    ns = set(re.findall(r"\d+(?:\.\d+)?", it["evidence_span"]))
    return bool(nc - ns)


def m_words(it, k=3):
    novel = {w for w in toks(it["claim"]) - toks(it["evidence_span"]) if len(w) > 3}
    return len(novel) >= k


def m_rules(it):
    return m_numbers(it) or m_words(it)


PROMPT = """You check whether a CLAIM is fully supported by an EVIDENCE sentence.
Use ONLY the evidence. If the claim adds, changes or contradicts anything, it is not supported.
Answer deterministically with exactly one word: SUPPORTED or UNSUPPORTED.

EVIDENCE: {span}
CLAIM: {claim}"""

try:
    cache = {} if FRESH else json.load(open(CACHE_PATH, encoding="utf-8"))
except Exception:
    cache = {}

llm_calls = 0
llm_errors = 0


def m_llm(it):
    global llm_calls, llm_errors
    prompt = PROMPT.format(span=it["evidence_span"], claim=it["claim"])
    key = hashlib.md5(prompt.encode("utf-8")).hexdigest()
    if key in cache:
        return cache[key]

    verdict = None
    for attempt in range(4):
        try:
            r = litellm.completion(
                model=MODEL,
                api_key=os.environ["GEMINI_API_KEY"],
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
                num_retries=0,
            )
            text = (r.choices[0].message.content or "").strip().upper()
            if text:
                verdict = text.startswith("UNSUPPORTED")
                break
        except litellm.RateLimitError:
            print("  rate limit, waiting 60s...")
            time.sleep(60)
        except Exception as e:
            print("  llm error:", type(e).__name__, str(e)[:100])
            time.sleep(10 * (attempt + 1))

    if verdict is None:
        llm_errors += 1
        return None

    cache[key] = verdict
    json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"))
    llm_calls += 1
    print(f"  llm calls this run: {llm_calls}", end="\r")
    time.sleep(CALL_GAP)
    return verdict


# ---------- scoring ----------

def score(name, method):
    tp = fp = fn = tn = skipped = 0
    by_type = collections.defaultdict(lambda: [0, 0])
    wrong, log = [], []

    for it in items:
        pred_bad = method(it)
        if pred_bad is None:
            skipped += 1
            continue
        log.append({"pair_id": it["pair_id"], "label": it["label"],
                    "error_type": it["error_type"], "pred_bad": pred_bad})
        if it["label"] == "bad":
            by_type[it["error_type"]][1] += 1
            if pred_bad:
                tp += 1
                by_type[it["error_type"]][0] += 1
            else:
                fn += 1
                wrong.append(("MISSED", it))
        else:
            if pred_bad:
                fp += 1
                wrong.append(("FALSE ALARM", it))
            else:
                tn += 1

    recall = tp / max(tp + fn, 1)
    fa = fp / max(fp + tn, 1)
    print(f"\n== {name}  (skipped {skipped})")
    print(f"recall {tp}/{tp+fn} = {recall:.2f}   false alarms {fp}/{fp+tn} = {fa:.2f}")
    for t, (c, n) in sorted(by_type.items()):
        print(f"   {t:7s} {c}/{n}")

    fname = "eval/results_" + name.replace(" ", "_") + ".json"
    json.dump(log, open(fname, "w", encoding="utf-8"), indent=1)

    if name == "single LLM check":
        for kind, it in wrong:
            print(f"   {kind} pair {it['pair_id']} [{it['error_type']}]: {it['claim'][:110]}")

    return [datetime.datetime.now().isoformat(timespec="seconds"), name,
            tp, tp + fn, round(recall, 3), fp, fp + tn, round(fa, 3), skipped]


rows = []
for name, m in [("span-match only", m_spanmatch),
                ("numbers rule", m_numbers),
                ("novel-words rule", m_words),
                ("numbers OR novel-words", m_rules),
                ("single LLM check", m_llm)]:
    rows.append(score(name, m))

print(f"\nLLM calls this run: {llm_calls}   LLM errors (skipped items): {llm_errors}")
if llm_errors:
    print("Some items failed. Run again: finished answers are saved, only failed ones retry.")

# append a summary to eval/score_log.csv
path = "eval/score_log.csv"
new = not os.path.exists(path)
try:
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "method", "caught", "bad_total", "recall",
                        "false_alarms", "good_total", "false_alarm_rate", "skipped"])
        w.writerows(rows)
except PermissionError:
    print("score_log.csv is open in Excel. Close it. Rows not saved.")