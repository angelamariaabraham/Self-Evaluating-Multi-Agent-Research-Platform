import json, collections
from devils_advocate import judge

items = json.load(open("eval/da_labels_final.json", encoding="utf-8"))
agree = 0
conf = collections.Counter()
by_w = collections.defaultdict(lambda: [0, 0])
wrong, skipped = [], 0
wtype_ok = wtype_n = 0

for it in items:
    out = judge(it["evidence_span"])
    if out is None:
        skipped += 1
        continue
    gold, pred = it["label"], out["verdict"]
    conf[(gold, pred)] += 1
    if gold == "weak":
        by_w[it["weakness"]][1] += 1
    if gold == pred:
        agree += 1
        if gold == "weak":
            by_w[it["weakness"]][0] += 1
            wtype_n += 1
            wtype_ok += out["weakness"] == it["weakness"]
    else:
        wrong.append((it, out))

n = len(items) - skipped
print(f"\nagreement {agree}/{n}   skipped {skipped}")
print(f"gold weak -> pred weak {conf[('weak','weak')]}, pred holds {conf[('weak','holds')]}")
print(f"gold holds -> pred holds {conf[('holds','holds')]}, pred weak {conf[('holds','weak')]}")
print(f"weakness type correct on caught weak items: {wtype_ok}/{wtype_n}")
for w, (c, t) in sorted(by_w.items()):
    print(f"   {w:12s} caught {c}/{t}")
for it, out in wrong:
    print(f"\nDISAGREE gold={it['label']}/{it['weakness']}  model={out['verdict']}/{out['weakness']}")
    print("  SPAN  :", it["evidence_span"])
    print("  REASON:", out["reason"])