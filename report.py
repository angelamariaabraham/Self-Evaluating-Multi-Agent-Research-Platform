import datetime
from confidence import band


def build_report(topic, claims, cres, sres, path):
    reasons = {i.claim_id: i.reason for i in sres.items}
    ordered = sorted(claims, key=lambda c: -(c.confidence or 0))
    counts = {"high": 0, "medium": 0, "low": 0}
    for c in claims:
        counts[band(c.confidence or 0)] += 1

    L = [f"# Research report: {topic}", "",
         f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M}. "
         f"{len(claims)} claims from {len(set(c.source_url for c in claims))} sources.", "",
         f"Confidence: {counts['high']} high, {counts['medium']} medium, {counts['low']} low. "
         f"Contradictions flagged: {len(cres.flags)} "
         f"({cres.pairs_checked} pairs checked, {cres.pairs_failed} failed).", ""]

    L += ["## Contradictions", ""]
    if cres.flags:
        for f in cres.flags:
            L.append(f"- {', '.join(f.claim_ids)}: {f.explanation}")
    else:
        L.append("None found among the pairs checked.")
    L.append("")

    L += ["## Claims, highest confidence first", ""]
    for c in ordered:
        L += [f"### {c.claim_id}  {c.confidence:.2f} ({band(c.confidence or 0)})", "",
              c.claim_text, "",
              f"- Source: {c.source_url}",
              f"- Evidence: \"{c.evidence_span}\""]
        if c.stress_verdict:
            L.append(f"- Evidence strength: {c.stress_verdict}"
                     + (f" ({c.stress_weakness}): {reasons.get(c.claim_id, '')}"
                        if c.stress_verdict == "weak" else ""))
        if c.confidence_reasons:
            L.append("- Score reduced because: " + "; ".join(c.confidence_reasons))
        L.append("")

    L += ["## How scores are computed", "",
          "Start at 0.90. Subtract 0.05 for loose evidence match, 0.30 if contradicted, "
          "0.25 if evidence is weak, 0.10 per check that did not run. "
          "Cap at 0.20 if the evidence does not back the claim. Score 0 if the evidence "
          "is not found in the source. Weights are set by hand and not calibrated.", "",
          "## Limits", "",
          "- Scores judge how well the evidence supports a claim. They do not prove the claim is true.",
          "- Contradiction was tested on synthetic pairs only. Evidence-strength check was tuned on one topic.",
          "- Only the sentences the analyst chose are checked. Missing facts are not detected."]
    open(path, "w", encoding="utf-8").write("\n".join(L))
    print("report saved:", path)