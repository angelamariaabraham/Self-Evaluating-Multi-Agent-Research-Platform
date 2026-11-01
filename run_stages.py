import sys, glob, json
from schema import ClaimList, ContradictionResult, StressResult
from llm_util import QuotaExhausted
from support import check_support
from contradiction import run_contradiction
from devils_advocate import run_stress
from confidence import score_all
from report import build_report

path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("runs/claims_*.json"))[-1]
topic = sys.argv[2] if len(sys.argv) > 2 else "unknown topic"
claims = ClaimList(**json.load(open(path, encoding="utf-8"))).claims
print("loaded", len(claims), "claims from", path)

incomplete = []

try:
    check_support(claims)
except QuotaExhausted as e:
    print("support check stopped:", e)
    incomplete.append("support")

try:
    cres = run_contradiction(claims)
except QuotaExhausted as e:
    print("contradiction stopped:", e)
    cres = ContradictionResult(flags=[])
    incomplete.append("contradiction")
print("contradiction flags:", len(cres.flags),
      "pairs", cres.pairs_checked, "failed", cres.pairs_failed)
for f in cres.flags:
    print("  FLAG", f.claim_ids, f.explanation[:200])

try:
    sres = run_stress(claims)
except QuotaExhausted as e:
    print("devil's advocate stopped:", e)
    sres = StressResult(items=[])
    incomplete.append("devils_advocate")

score_all(claims)

stages = path.replace("claims_", "stages_")
json.dump({"incomplete": incomplete, "contradiction": cres.model_dump(),
           "stress": sres.model_dump(), "claims": [c.model_dump() for c in claims]},
          open(stages, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("saved", stages)
if incomplete:
    print("INCOMPLETE stages:", incomplete, "- rerun after the quota resets. Finished calls are cached.")

build_report(topic, claims, cres, sres,
             path.replace("claims_", "report_").replace(".json", ".md"))