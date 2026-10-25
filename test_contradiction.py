import os, sys, json, glob, random, time, re
import litellm
from dotenv import load_dotenv
load_dotenv()
import logging
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

MODEL = "gemini/gemini-3.5-flash-lite"
PAIRS = "eval/contradiction_pairs.json"
HARD = "eval/contradiction_pairs_hard.json"
os.makedirs("eval", exist_ok=True)


def ask(prompt):
    for attempt in range(4):
        try:
            r = litellm.completion(
                model=MODEL, api_key=os.environ["GEMINI_API_KEY"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0, timeout=60, num_retries=0)
            text = (r.choices[0].message.content or "").strip()
            if text:
                time.sleep(4.5)
                return text
        except Exception as e:
            print("llm error:", type(e).__name__)
            time.sleep(20 * (attempt + 1))
    return None


def build():
    latest = sorted(glob.glob("runs/claims_*.json"))[-1]
    claims = json.load(open(latest, encoding="utf-8"))["claims"]
    random.seed(1)
    pairs = []

    # 10 planted contradictions: opposite of a real claim
    for c in random.sample(claims, min(10, len(claims))):
        neg = ask("Rewrite this claim so it states the opposite. "
                  "One sentence, same topic, no commentary.\n"
                  f"CLAIM: {c['claim_text']}")
        if neg:
            pairs.append({"a": c["claim_text"], "b": neg, "label": "contradict"})

    # 10 clean pairs: most similar claims from different sources
    def toks(s):
        return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 3}

    cands = []
    for i, x in enumerate(claims):
        for y in claims[i + 1:]:
            if x["source_url"] == y["source_url"]:
                continue
            ov = len(toks(x["claim_text"]) & toks(y["claim_text"]))
            cands.append((ov, x["claim_text"], y["claim_text"]))
    cands.sort(reverse=True)
    for ov, a, b in cands[:10]:
        pairs.append({"a": a, "b": b, "label": "compatible"})

    json.dump(pairs, open(PAIRS, "w", encoding="utf-8"), indent=1)
    print("saved", len(pairs), "pairs to", PAIRS, "- read them by eye before evaluating")

def build_hard():
    latest = sorted(glob.glob("runs/claims_*.json"))[-1]
    claims = json.load(open(latest, encoding="utf-8"))["claims"]
    random.seed(2)
    pairs = []
    for c in random.sample(claims, min(10, len(claims))):
        sub = ask("Rewrite this claim changing exactly ONE specific detail "
                  "(a number, date, name, or a scope word such as 'all' or 'some') "
                  "so the new claim conflicts with the original. Keep everything "
                  "else the same. One sentence, no commentary.\n"
                  f"CLAIM: {c['claim_text']}")
        if sub:
            pairs.append({"a": c["claim_text"], "b": sub, "label": "contradict"})
    for c in random.sample(claims, min(10, len(claims))):
        par = ask("Paraphrase this claim in different words. Add no new facts "
                  "and remove none. One sentence, no commentary.\n"
                  f"CLAIM: {c['claim_text']}")
        if par:
            pairs.append({"a": c["claim_text"], "b": par, "label": "compatible"})
    json.dump(pairs, open(HARD, "w", encoding="utf-8"), indent=1)
    print("saved", len(pairs), "pairs to", HARD, "- read them by eye before evaluating")

PROMPT = """Compare two claims. They CONTRADICT if they cannot both be true at the same time.
Check carefully for conflicts in: numbers, dates, names, quantities, and scope words (all, some, none, always, never, only).
Two claims about different topics are COMPATIBLE. A claim that is only more or less detailed than the other is COMPATIBLE.
Answer with exactly one word: CONTRADICT or COMPATIBLE.

CLAIM A: {a}
CLAIM B: {b}"""

def evaluate(path=PAIRS):
    pairs = json.load(open(path, encoding="utf-8"))
    #pairs = json.load(open(PAIRS, encoding="utf-8"))
    tp = fp = fn = tn = 0
    for p in pairs:
        ans = ask(PROMPT.format(a=p["a"], b=p["b"]))
        if ans is None:
            continue
        pred = ans.upper().startswith("CONTRADICT")
        if p["label"] == "contradict":
            if pred: tp += 1
            else:
                fn += 1
                #print("MISSED:", p["a"][:80], "|", p["b"][:80])
                print("MISSED:\n  A:", p["a"], "\n  B:", p["b"])
        else:
            if pred:
                fp += 1
                print("FALSE ALARM:", p["a"][:80], "|", p["b"][:80])
            else: tn += 1
    print(f"recall {tp}/{tp+fn}   false alarms {fp}/{fp+tn}   precision {tp}/{max(tp+fp,1)}")

if __name__ == "__main__":
    if "hard-build" in sys.argv:
        build_hard()
    elif "hard" in sys.argv:
        evaluate(HARD)
    elif "build" in sys.argv:
        build()
    else:
        evaluate()


