import json, csv

good = json.load(open("eval/good_claims.json", encoding="utf-8"))
with open("eval/pairs.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "source_url", "evidence_span",
                "good_claim", "bad_claim", "error_type"])
    for i, g in enumerate(good, 1):
        w.writerow([i, g["source_url"], g["evidence_span"],
                    g["claim_text"], "", ""])
print("wrote", len(good), "rows")