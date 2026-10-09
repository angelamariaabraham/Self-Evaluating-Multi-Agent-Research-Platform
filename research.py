import os
import sys
import asyncio

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
from crewai import LLM, Agent, Task, Crew, Process
from crewai.tools import tool
from firecrawl import FirecrawlApp
from google.genai import errors as genai_errors

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

# --- 2. API Keys ---
# Set your keys here or via system environment variables
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6JIkmiISrep91Jvzsd-5aRyukgc_93ajGeCdXIGvClF_A")
os.environ["FIRECRAWL_API_KEY"] = os.getenv("FIRECRAWL_API_KEY", "fc-679d654c32e449119404fada655f687c")

# --- 3. Models (Using flash-lite for reliable free-tier quota) ---
lite_llm = LLM(
    model="gemini/gemini-3.5-flash-lite",
    api_key=os.environ["GEMINI_API_KEY"],
    max_retries=5,
)
strong_llm = LLM(
    model="gemini/gemini-3.5-flash-lite",
    api_key=os.environ["GEMINI_API_KEY"],
    max_retries=5,
)

# --- 4. Firecrawl Tool (Supports both Dict and Object return types) ---
firecrawl_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])

@tool("Firecrawl Web Search")
def firecrawl_search(query: str) -> str:
    """Search the web for a topic and return raw text content from multiple credible sources with their URLs. Input should be a search query string."""
    try:
        results = firecrawl_client.search(query, limit=5)
        
        # Safely extract from both dictionary and object formats
        if isinstance(results, dict):
            items = results.get("data", []) or results.get("web", [])
        else:
            items = getattr(results, "data", None) or getattr(results, "web", None) or []

        output = []
        for item in items:
            if isinstance(item, dict):
                url = item.get("url", "unknown URL")
                title = item.get("title", "")
                description = (item.get("description", "") or item.get("markdown", "") or "")[:350]
            else:
                url = getattr(item, "url", "unknown URL")
                title = getattr(item, "title", "")
                description = (getattr(item, "description", "") or getattr(item, "markdown", "") or "")[:350]
            output.append(f"URL: {url}\nTitle: {title}\nContent: {description}\n")

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
    max_iter=10,
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
    max_iter=10,
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
    max_iter=10,
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
    max_iter=10,
    verbose=True,
)

# --- 6. Tasks ---
research_task = Task(
    description=(
        "Research the topic: '{topic}'. Use the Firecrawl Web Search tool to gather content from "
        "5 credible, distinct sources - no more. Once you have 5 distinct sources, STOP searching "
        "and compile your final answer immediately. Do not search for the same source twice. "
        "For each source, capture the raw text and the source URL. Do not summarize or interpret — just collect."
    ),
    expected_output="A list of exactly 5 source entries, each containing raw text and its source URL.",
    agent=research_agent,
)

analysis_task = Task(
    description=(
        "Given the raw source entries collected above, extract the key factual claims from each. "
        "Break the text into atomic, individually-verifiable claims. Tag each claim with "
        "the source URL it came from and assign each a unique claim ID."
    ),
    expected_output="A list of structured claims, each with: claim_id, claim_text, source_url.",
    agent=analysis_agent,
    context=[research_task],
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
        "Compile all claims, their contradiction flags, and their stress-test verdicts "
        "into a final report. Assign each claim a confidence score based on whether it "
        "was contradicted and how it held up under stress-testing. Cite the source URL for every claim, "
        "using the source_url field from the original structured claims — do not omit it or write "
        "'not provided' if it exists anywhere in the upstream context."
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
    agents=[research_agent, analysis_agent, contradiction_agent, devils_advocate_agent, report_agent],
    tasks=[research_task, analysis_task, contradiction_task, devils_advocate_task, report_task],
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
    raise RuntimeError("Crew failed after max attempts.")

# --- 9. Entrypoint ---
async def main():
    topic = "hallucination detection"
    print(f"Starting research crew for topic: '{topic}'...")
    result = await run_crew_with_retry(research_crew, {"topic": topic})
    print("\n================ FINAL REPORT ================\n")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
