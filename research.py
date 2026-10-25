#research.py
import os
import sys
import asyncio
import csv
import json
import datetime
from pathlib import Path
from checks import faithfulness_rate, span_in_source, normalize, mismatch_report, near_rate
# Ensure Windows terminal supports emoji / utf-8 characters without charmap errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import litellm
import crewai
import langchain
from schema import ClaimList
from crewai import LLM, Agent, Task, Crew, Process
from crewai.tools import tool
from firecrawl import FirecrawlApp
from google.genai import errors as genai_errors
from dotenv import load_dotenv
load_dotenv()
#from sources import fetch_full_text, save_source, load_source, top_chunks, MIN_CHARS
from sources import cached_search, get_source_text, load_source, top_chunks, MIN_CHARS
from contradiction import run_contradiction
from support import check_support


# --- 1. Monkeypatch LiteLLM cache breakpoint ---
if not getattr(litellm, "_cache_breakpoint_patched", False):
    _original_completion = litellm.completion

    def _patched_completion(*args, **kwargs):
        messages = kwargs.get("messages")
        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    msg.pop("cache_breakpoint", None)
        return _original_completion(*args, **kwargs)

    litellm.completion = _patched_completion
    litellm._cache_breakpoint_patched = True



# --- 3. Models (Using flash-lite for reliable free-tier quota) ---

strong_llm = LLM(
    model="gemini/gemini-3.5-flash-lite",
    api_key=os.environ["GEMINI_API_KEY"],
    max_retries=5,
    temperature=0,
)

# --- 4. Firecrawl Tool (Supports both Dict and Object return types) ---
firecrawl_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
HEAD_CHARS = 2000




TOPIC = "hallucination detection"
def get_sources(topic):
    items = cached_search(topic, limit=5)
    return [it["url"] for it in items if len(get_source_text(it["url"])) >= MIN_CHARS]

@tool("Read Stored Source")
def read_source(url: str) -> str:
    """Return the most topic-relevant passages of a stored source URL."""
    try:
        text = load_source(url)
        if not text:
            return "Source not found."
        return "\n\n[...]\n\n".join(top_chunks(text, TOPIC, k=3, size=2500))
    except Exception as e:
        return f"TOOL ERROR: {type(e).__name__}: {e}"




@tool("Firecrawl Web Search")
def firecrawl_search(query: str) -> str:
    """Search the web for a topic. Returns the URL and title of each source."""
    try:
        output = []
        for item in cached_search(TOPIC, limit=5):
            if len(get_source_text(item["url"])) < MIN_CHARS:
                continue
            output.append(f"URL: {item['url']}\nTitle: {item['title']}\n")
        return "\n---\n".join(output) if output else "No results found."
    except Exception as e:
        return f"Error executing search: {str(e)}"

    
# --- 5. Agents ---
research_agent = Agent(
    role="Web Research Specialist",
    goal="Gather raw, relevant source content on the given topic from the web via Firecrawl, without interpreting or drawing conclusions from it.",
    backstory=(
        "You are a meticulous researcher who casts a wide net across credible sources. "
        "You collect information faithfully and note where it came from, but you never "
        "summarize, interpret, or judge the claims — that is someone else's job."
    ),
    tools=[firecrawl_search],
    llm=strong_llm,
    max_iter=5,
    verbose=True,
)

analysis_agent = Agent(
    role="Research Analyst",
    goal="Synthesize raw source content into clear, structured claims, each tagged with its originating source.",
    backstory=(
        "You are a sharp analyst who turns messy raw text into organized, atomic claims. "
        "You extract what was said and by whom, but you don't verify whether claims agree "
        "with each other across sources — that's the Contradiction Detection Agent's job."
    ),
    llm=strong_llm,
    max_iter=10,
    verbose=True,
    tools=[],
)

contradiction_agent = Agent(
    role="Contradiction Detection Specialist",
    goal="Cross-verify structured claims against each other and flag any that disagree or conflict across sources.",
    backstory=(
        "You are a skeptical fact-checker who compares every claim against every other claim "
        "on the same topic. You flag disagreements precisely, but you don't judge which claim "
        "is 'right' or stress-test the reasoning behind them — that's the Devil's Advocate's job."
    ),
    llm=strong_llm,
    max_iter=5,
    verbose=True,
)

devils_advocate_agent = Agent(
    role="Devil's Advocate",
    goal="Adversarially challenge the surviving claims and conclusions to expose weak reasoning or unsupported leaps.",
    backstory=(
        "You are a rigorous critic whose only goal is to find holes. Given a claim or conclusion, "
        "you actively argue against it and note where the reasoning doesn't hold up. "
        "You don't score confidence or generate the final report — that's the next stage."
    ),
    llm=strong_llm,
    max_iter=5,
    verbose=True,
)

report_agent = Agent(
    role="Report Generation Specialist",
    goal="Compile verified claims, contradiction flags, and stress-test results into a confidence-scored summary report, citing every source.",
    backstory=(
        "You are a precise technical writer who turns structured findings into a polished, "
        "readable report. You clearly show confidence scores and cite sources for every claim, "
        "but you don't generate new claims or re-judge anything upstream."
    ),
    llm=strong_llm,
    max_iter=5,
    verbose=True,
)

# --- 6. Tasks ---
research_task = Task(
    description=(
    "Research the topic: '{topic}'. Use the Firecrawl Web Search tool to find "
    "5 credible, distinct sources. Once you have 5, STOP searching. "
    "Return only each source's URL and title."
    ),
    expected_output="A list of exactly 5 entries, each with a URL and title.",
    agent=research_agent,
)
analysis_task = Task(
    description=(
        "Source URL: {url}\n\n"
        "SOURCE TEXT:\n{source_text}\n\n"
        "Extract exactly 3 factual claims about the topic: {topic}. "
        "Ignore cookie notices, menus, ads, promotions and page metadata. "
        "Prefer specific, checkable statements (methods, results, numbers) over general definitions. "
        "For each claim give: claim_id, claim_text, source_url, evidence_span. "
        "evidence_span must be ONE complete sentence of at least 8 words, copied word for word from the SOURCE TEXT above. "
        "The claim must say no more than the span says. "
        "Ignore marketing language and first-person statements (words like 'Our', 'We', 'Get'). "
        "Ignore sentences that describe the document itself, such as what this survey, paper or article does or contains. "
        "Each claim must make sense alone: never start a claim with a pronoun (They, It, This). "
        "If the best sentence starts with a pronoun, pick a different sentence. "
        "Ignore data availability statements, funding, acknowledgements, author or copyright notices, and references. "
        "Never write a claim from memory. Do not fill any other field."
    ),
    expected_output="A ClaimList with claim_id, claim_text, source_url, evidence_span for exactly 3 claims.",
    agent=analysis_agent,
    output_pydantic=ClaimList,
)

contradiction_task = Task(
    description=(
        "Compare the structured claims against each other. Identify any pairs or groups "
        "of claims that disagree, conflict, or contradict one another across sources. "
        "For each conflict found, note which claim_ids are involved and why they disagree."
    ),
    expected_output=(
        "A list of contradiction flags, each with: claim_ids involved, and a short "
        "explanation of the conflict. Claims with no conflicts should be marked clean."
    ),
    agent=contradiction_agent,
    context=[analysis_task],
)

devils_advocate_task = Task(
    description=(
        "For each claim in the structured claims, actively argue against it. "
        "Use the contradiction flags as extra evidence. Identify weak reasoning, "
        "missing evidence, or unsupported leaps. Give each claim a stress_test_verdict "
        "of exactly one of: holds, weak, unsupported. Add a one-sentence justification. "
        "Keep each claim's claim_id and source_url."
    ),
    expected_output="A list of claims annotated with: stress_test_verdict and a short justification for each.",
    agent=devils_advocate_agent,
    context=[analysis_task,contradiction_task],
)

report_task = Task(
    description=(
        "Compile all claims, their contradiction flags, and their stress-test verdicts "
        "into a final report. Assign each claim a confidence score based on whether it "
        "was contradicted and how it held up under stress-testing. Cite the source URL for every claim."
    ),
    expected_output="A confidence-scored report, with every claim cited to its source and annotated with a confidence score.",
    agent=report_agent,
    context=[analysis_task, contradiction_task,devils_advocate_task],
)

# --- 7. Crew ---
research_crew = Crew(
    agents=[analysis_agent],
    tasks=[analysis_task],
    process=Process.sequential,
    verbose=True,
)
# --- 8. Validation and Async Execution Helper ---
def is_bad_output(result) -> bool:
    """Helper to detect empty, malformed, or refused outputs."""
    if not result:
        return True
    raw_str = getattr(result, "raw", str(result)).strip()
    if not raw_str or len(raw_str) < 50:
        return True
    refusals = ["i cannot fulfill", "i am unable to", "policy violation", "as an ai language model"]
    return any(refusal in raw_str.lower() for refusal in refusals)

async def run_crew_with_retry(crew, inputs, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        try:
            result = await crew.kickoff_async(inputs=inputs)
            if is_bad_output(result) and attempt < max_attempts:
                print(f"Empty/refused output (attempt {attempt}/{max_attempts}) — retrying...")
                continue
            return result
        except (litellm.RateLimitError, litellm.InternalServerError, litellm.APIError, genai_errors.APIError) as e:
            if attempt < max_attempts:
                wait = 30 * attempt
                print(f"{type(e).__name__}: {e} (attempt {attempt}/{max_attempts}) — waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            raise
        except litellm.BadRequestError as e:
            msg = str(e)
            known_bugs = ["Tool choice is none", "Failed to parse tool call arguments"]
            if any(b in msg for b in known_bugs) and attempt < max_attempts:
                print(f"Known bug (attempt {attempt}/{max_attempts}) — retrying...")
                continue
            raise
        except Exception as e:
            msg = str(e)
            transient = ["None or empty", "Invalid response from LLM"]
            if any(t in msg for t in transient) and attempt < max_attempts:
                wait = 20 * attempt
                print(f"Empty LLM response (attempt {attempt}/{max_attempts}) — waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            raise
    raise RuntimeError("Crew failed after max attempts.")

# --- 9. Entrypoint ---
def log_run(topic, claims):
    ok = [span_in_source(c.source_url, c.evidence_span) for c in claims]
    copies = sum(normalize(c.claim_text) == normalize(c.evidence_span) for c in claims)
    failed = [c.claim_id for c, good in zip(claims, ok) if not good]
    row = [
        datetime.datetime.now().isoformat(timespec="seconds"),
        topic,
        len(claims),
        round(sum(ok) / len(claims), 3) if claims else 0,
        copies,
        ";".join(failed),
        ";".join(sorted(set(c.source_url for c in claims))),
    ]

    new = not Path("runs.csv").exists()
    try:
        with open("runs.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "topic", "claims", "faithfulness",
                            "claim_eq_span", "failed_ids", "urls"])
            w.writerow(row)
    except PermissionError:
        backup = "runs_pending.csv"
        with open(backup, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
        print(f"runs.csv is open in Excel. Row saved to {backup}. Close Excel, then merge.")

JUNK_PHRASES = ["made available on request", "data availability",
                "declaration of competing interest", "all rights reserved",
                "conflicts of interest"]

def keep_claim(c) -> bool:
    if len(normalize(c.evidence_span).split()) < 8:
        return False
    low = c.evidence_span.lower()
    return not any(p in low for p in JUNK_PHRASES)

async def main():
    print(f"Starting research for topic: '{TOPIC}'...")
    urls = get_sources(TOPIC)
    print("sources:", len(urls))

    claims = []
    for url in urls:
        text = "\n\n[...]\n\n".join(top_chunks(load_source(url), TOPIC, k=3, size=2500))
        result = await run_crew_with_retry(
            research_crew, {"topic": TOPIC, "url": url, "source_text": text})
        out = result.tasks_output[0].pydantic
        if not out:
            print("no parsed output for", url)
            continue
        for c in out.claims:
            c.source_url = url                  # code decides the source, not the LLM
            c.contradiction_flag = None         # clear fields the LLM invented
            c.stress_verdict = None
            c.confidence = None
            claims.append(c)
        print(f"  {len(out.claims)} claims from {url}")

    before = len(claims)
    claims = [c for c in claims if keep_claim(c)]
    print(f"dropped {before - len(claims)} junk or too-short claims")

    for i, c in enumerate(claims, 1):
        c.claim_id = f"C{i:02d}"

    check_support(claims)
    for c in claims:
        if c.span_supports_claim is False:
            print("UNSUPPORTED:", c.claim_id, c.claim_text[:120])
    print("\nclaims:", len(claims))
    print("faithfulness:", faithfulness_rate(claims))
    print("near-match rate:", near_rate(claims))
    log_run(TOPIC, claims)

    Path("runs").mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"runs/claims_{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(ClaimList(claims=claims).model_dump(), f, ensure_ascii=False, indent=2)

    cres = run_contradiction(claims)
    print(f"contradiction flags: {len(cres.flags)} "
          f"(pairs checked {cres.pairs_checked}, failed {cres.pairs_failed})")
    for fl in cres.flags:
        print("  FLAG", fl.claim_ids, fl.explanation[:200])
    with open(f"runs/contradiction_{stamp}.json", "w", encoding="utf-8") as fh:
        json.dump(cres.model_dump(), fh, ensure_ascii=False, indent=2)

    for c in claims:
        ok = span_in_source(c.source_url, c.evidence_span)
        if not ok:
            print("\n", c.claim_id, "OK" if ok else "FAILED", c.source_url)
            print("CLAIM:", c.claim_text)
            print("SPAN: ", c.evidence_span)
            print("DIAG:", mismatch_report(c.source_url, c.evidence_span))


if __name__ == "__main__":
    asyncio.run(main())


