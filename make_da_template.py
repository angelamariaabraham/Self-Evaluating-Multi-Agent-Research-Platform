import json, glob, os

os.makedirs("eval", exist_ok=True)
OUT = "eval/da_labels.json"
items, seen = [], set()

for path in sorted(glob.glob("runs/claims_*.json"), reverse=True)[:6]:
    for c in json.load(open(path, encoding="utf-8"))["claims"]:
        key = c["claim_text"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "claim_text": c["claim_text"],
            "evidence_span": c["evidence_span"],
            "source_url": c["source_url"],
            "label": "",
            "weakness": "",
        })

json.dump(items, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("saved", len(items), "unique claims to", OUT)