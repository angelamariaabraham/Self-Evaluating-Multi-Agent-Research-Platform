import json

SRC = "eval/da_labels.json"
OUT = "eval/da_labels_draft.json"

# key phrase inside the span -> (label, weakness, unsure)
LABELS = {
    "Hallucination Detector automatically detects": ("weak", "promotional", False),
    "Our citation checker identifies": ("weak", "promotional", False),
    "Source finder will detect": ("weak", "promotional", False),
    "GPTZero source finder is to detect": ("weak", "promotional", False),
    "Get in-depth analysis": ("weak", "promotional", False),
    "Engineers view hallucinations": ("weak", "overgeneral", False),
    "Symbolic artificial intelligence models": ("weak", "overgeneral", False),
    "Various researchers cited by Wired": ("weak", "overgeneral", True),
    "Hallucinations generally involve": ("weak", "overgeneral", True),
    "AI writing tools often generate": ("weak", "overgeneral", True),
    "Stanford research found that even specialized": ("weak", "no_basis", True),
    "A 2024 Stanford study found": ("weak", "no_basis", True),
    "Specialized legal AI tools trained on": ("weak", "no_basis", False),
    "Detecting and mitigating errors": ("holds", "none", True),
    "Generative AI models are trained": ("holds", "none", True),
    "But even RAG": ("holds", "none", True),
    "In 2023, the Cambridge dictionary": ("holds", "none", False),
    "In October 2025, several hallucinations": ("holds", "none", False),
    "AI hallucinations refer to statements": ("holds", "none", False),
    "AI hallucinations are instances": ("holds", "none", False),
    "Factual hallucinations occur": ("holds", "none", False),
    "Consistency hallucinations occur": ("holds", "none", False),
    "In 2015, computer scientist Andrej Karpathy": ("holds", "none", False),
    "In 2015, hallucinations were identified": ("holds", "none", False),
    "In computer vision, since the 2000s": ("holds", "none", False),
}

EXCLUDE = {
    "Data will be made available": "not a factual claim",
    "The present survey aims": "describes the document itself",
    "Initially, we provide a taxonomy": "describes the document itself",
    "In summary, this survey offers": "describes the document itself",
    "These behaviors raise serious problems": "span depends on earlier text",
    "In 2018, it was used": "span depends on earlier text",
    "They can be reduced but not fully": "span depends on earlier text",
}


def find(span, table):
    for key in table:
        if key in span:
            return key
    return None


rows = json.load(open(SRC, encoding="utf-8"))
seen, kept, dropped, unmatched = set(), [], [], []

for r in rows:
    span = r["evidence_span"].strip()
    if span in seen:
        continue
    seen.add(span)
    k = find(span, LABELS)
    if k:
        label, weakness, unsure = LABELS[k]
        kept.append({
            "claim_text": r["claim_text"],
            "evidence_span": span,
            "source_url": r["source_url"],
            "label": label,
            "weakness": weakness,
            "unsure": unsure,
        })
        continue
    e = find(span, EXCLUDE)
    if e:
        dropped.append((span[:70], EXCLUDE[e]))
    else:
        unmatched.append(span[:70])

json.dump(kept, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

print(f"rows {len(rows)}  unique spans {len(seen)}  kept {len(kept)}  excluded {len(dropped)}")
print("weak:", sum(x["label"] == "weak" for x in kept),
      " holds:", sum(x["label"] == "holds" for x in kept))
for w in ("promotional", "overgeneral", "hedged", "causal", "no_basis"):
    print(f"  {w}: {sum(x['weakness'] == w for x in kept)}")
print("\nUNSURE - decide these yourself:")
for x in kept:
    if x["unsure"]:
        print(" -", x["label"], x["weakness"], "|", x["evidence_span"][:80])
print("\nEXCLUDED:")
for s, why in dropped:
    print(" -", why, "|", s)
if unmatched:
    print("\nUNMATCHED (label by hand):")
    for s in unmatched:
        print(" -", s)