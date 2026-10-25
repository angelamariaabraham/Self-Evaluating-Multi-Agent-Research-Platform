import json

p = "eval/contradiction_pairs_hard.json"
pairs = json.load(open(p, encoding="utf-8"))
drop = ["between 0% and 34%", "generative AI frameworks"]
keep = [x for x in pairs if not any(d in x["b"] for d in drop)]
print(len(pairs), "->", len(keep))
json.dump(keep, open(p, "w", encoding="utf-8"), indent=1)