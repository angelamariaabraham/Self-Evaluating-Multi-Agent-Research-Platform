import json, glob
from checks import span_in_source

known_good = {g["claim_text"].strip().lower()
              for g in json.load(open("eval/good_claims.json", encoding="utf-8"))}
out, seen = [], set()

def run():
    for path in sorted(glob.glob("runs/claims_*.json")):
        for c in json.load(open(path, encoding="utf-8"))["claims"]:
            key = c["claim_text"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            item = {"source_url": c["source_url"],
                    "evidence_span": c["evidence_span"],
                    "claim": c["claim_text"],
                    "error_type": "real",
                    "span_ok": span_in_source(c["source_url"], c["evidence_span"])}
            if key in known_good:
                item["label"] = "good"
            else:
                print("\nCLAIM:", c["claim_text"])
                print("SPAN: ", c["evidence_span"])
                ans = input("span alone fully backs claim? [y/n/s/q] ").strip().lower()
                if ans == "q":
                    return
                if ans == "s":
                    continue
                item["label"] = "good" if ans == "y" else "bad"
            out.append(item)

run()
json.dump(out, open("eval/real_items.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(len(out), "items,", sum(i["label"] == "bad" for i in out), "bad")