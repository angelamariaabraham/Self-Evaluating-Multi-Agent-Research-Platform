import csv, json

rows = list(csv.DictReader(open("eval/pairs.csv", encoding="utf-8-sig")))
items = []
for r in rows:
    if not r["bad_claim"].strip():
        continue
    base = {"pair_id": r["pair_id"],
            "source_url": r["source_url"],
            "evidence_span": r["evidence_span"]}
    items.append({**base, "claim": r["good_claim"], "label": "good", "error_type": ""})
    items.append({**base, "claim": r["bad_claim"], "label": "bad",
                  "error_type": r["error_type"]})

json.dump(items, open("eval/test_items.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(len(items), "items,", sum(i["label"] == "bad" for i in items), "bad")