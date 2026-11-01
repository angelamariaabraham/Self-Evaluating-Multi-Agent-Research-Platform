🔬 A five-agent research pipeline that gathers sources, extracts claims, checks them against the original source text, and produces a confidence-scored report. Built to study one narrow question: can a pipeline verify its own claims against the evidence it collected?
**Status** :Currently implementing a self retry loop (work in progress).
**How it works**
User query
   -> Research Agent        (gathers raw sources via Firecrawl)
   -> Analysis Agent        (structures findings into claims, each with a verbatim evidence span)
   -> Contradiction Agent   (cross-checks claims across sources)
   -> Devil's Advocate      (stress-tests conclusions for weak reasoning)
   -> Quality Gate          (low confidence -> retry loop; pass -> report)
   -> Report Agent          (confidence-scored PDF via ReportLab)
