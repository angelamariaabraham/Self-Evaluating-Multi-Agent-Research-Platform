🔬 A five-agent research pipeline that gathers sources, extracts claims, checks them against the original source text, and produces a confidence-scored report. Built to study one narrow question: can a pipeline verify its own claims against the evidence it collected?

⏳**Status** :Currently implementing a self retry loop (work in progress).

▶️**Demo**:https://drive.google.com/file/d/15VxmL4oyJAj3knBj73t5RBiSa1FaB_0c/view?usp=sharing

🧠**How it works**

User query
   -> Research Agent        (gathers raw sources via Firecrawl)
   -> Analysis Agent        (structures findings into claims, each with a verbatim evidence span)
   -> Contradiction Agent   (cross-checks claims across sources)
   -> Devil's Advocate      (stress-tests conclusions for weak reasoning)
   -> Quality Gate          (low confidence -> retry loop; pass -> report)
   -> Report Agent          (confidence-scored markdown file)
   
✨ Features

🤖 Autonomous end-to-end research: enter a topic and get a structured report with no manual steps in between

⚔️ Cross-source contradiction detection: flags where sources disagree instead of averaging them away

📊 Per-claim confidence scoring: every claim in the report carries a confidence score

😈 Devil's advocate stress-testing: a dedicated agent argues against the draft conclusions

🔁 Quality-gated retry loop: output below the quality threshold is sent back for another pass

🧾 Evidence-span faithfulness check: each claim must be backed by a span of retrieved source text

📄 Exportable markdown file report.
