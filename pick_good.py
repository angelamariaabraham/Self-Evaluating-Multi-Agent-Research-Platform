import json, glob
from pathlib import Path

Path("eval").mkdir(exist_ok=True)
seen, good = set(), []

def run():
    for path in sorted(glob.glob("runs/claims_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        for c in data["claims"]:
            key = c["claim_text"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            print("\n#", len(good), c["source_url"])
            print("CLAIM:", c["claim_text"])
            print("SPAN: ", c["evidence_span"])
            ans = input("span alone fully backs claim? [y/n/q] ").strip().lower()
            if ans == "q":
                return
            if ans == "y":
                good.append({
                    "source_url": c["source_url"],
                    "evidence_span": c["evidence_span"],
                    "claim_text": c["claim_text"],
                })

run()
with open("eval/good_claims.json", "w", encoding="utf-8") as f:
    json.dump(good, f, ensure_ascii=False, indent=2)
print("kept", len(good))
