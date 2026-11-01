import json, sys

src = sys.argv[1]                      # e.g. runs/claims_20261026_173000.json
out = "eval/da_new_labels.json"
items, seen = [], set()
for c in json.load(open(src, encoding="utf-8"))["claims"]:
    span = c["evidence_span"].strip()
    if span in seen:
        continue
    seen.add(span)
    items.append({"claim_text": c["claim_text"], "evidence_span": span,
                  "source_url": c["source_url"], "label": "", "weakness": ""})
json.dump(items, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("saved", len(items), "to", out)