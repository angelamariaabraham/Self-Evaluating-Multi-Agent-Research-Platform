"""Live Claim Extraction: Extracts atomic claims and verbatim evidence spans from web sources."""
import csv
import datetime
import json
import re
from pathlib import Path
from typing import Callable, List, Optional

from checks import normalize, span_in_source
from llm_util import QuotaExhausted, call
from schema import Claim, ClaimList
from sources import load_source, top_chunks

RUNS_DIR = Path("runs")
RUNS_CSV = Path("runs.csv")

JUNK_PHRASES = [
    "made available on request",
    "data availability",
    "declaration of competing interest",
    "all rights reserved",
    "conflicts of interest",
    "cookie policy",
    "privacy policy",
]


def keep_claim(c: Claim) -> bool:
    """Filter out empty, junk, or trivially short spans."""
    words = normalize(c.evidence_span).split()
    if len(words) < 8:
        return False
    low = c.evidence_span.lower()
    return not any(p in low for p in JUNK_PHRASES)


def extract_claims_from_url(url: str, topic: str, count: int = 2) -> List[Claim]:
    """Extract factual claims and exact evidence spans from a single loaded source page."""
    raw_text = load_source(url)
    if not raw_text:
        return []

    chunks = top_chunks(raw_text, topic, k=3, size=2500)
    source_text = "\n\n[...]\n\n".join(chunks)

    prompt = f"""You are a meticulous research analyst.
Source URL: {url}

SOURCE TEXT:
{source_text}

Extract {count} factual claims specifically about the topic: {topic}.
Rules:
- Ignore cookie notices, menus, ads, promotions and page metadata.
- Prefer specific, checkable statements (methods, results, numbers) over general definitions.
- evidence_span must be ONE complete sentence of at least 8 words, copied word for word from the SOURCE TEXT above.
- The claim must say no more than the span says.
- Ignore marketing language and first-person statements (words like 'Our', 'We', 'Get').
- Ignore sentences describing the document itself.
- Each claim must make sense alone: never start a claim with a pronoun (They, It, This).
- Ignore data availability statements, funding, author or copyright notices, and references.
- Never write a claim from memory.

Return a valid JSON object ONLY with no markdown code fences:
{{"claims": [{{"claim_text": "...", "evidence_span": "..."}}]}}"""

    resp = call(prompt)
    if not resp:
        return []

    clean = re.sub(r"^```(?:json)?|```$", "", resp.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", clean, flags=re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []

    extracted: List[Claim] = []
    for item in data.get("claims", []):
        c_text = str(item.get("claim_text", "")).strip()
        e_span = str(item.get("evidence_span", "")).strip()
        if c_text and e_span:
            c = Claim(
                claim_id="TEMP",
                claim_text=c_text,
                source_url=url,
                evidence_span=e_span,
            )
            if keep_claim(c):
                extracted.append(c)
    return extracted


def extract_claims_for_topic(
    topic: str,
    urls: List[str],
    max_claims_per_url: int = 2,
    status_func: Optional[Callable[[str], None]] = None,
) -> List[Claim]:
    """Iterate through sources and extract claims live."""
    all_claims: List[Claim] = []
    for idx, url in enumerate(urls, 1):
        if status_func:
            status_func(f"-> Extracting claims from source {idx}/{len(urls)}: {url[:48]}...")
        try:
            claims = extract_claims_from_url(url, topic, count=max_claims_per_url)
            all_claims.extend(claims)
        except QuotaExhausted:
            if status_func:
                status_func("API quota paused claim extraction early.")
            break
        except Exception as e:
            if status_func:
                status_func(f"Source skipped: {e}")
            continue

    for i, c in enumerate(all_claims, 1):
        c.claim_id = f"C{i:02d}"

    return all_claims


def save_new_run(topic: str, claims: List[Claim]) -> str:
    """Save extracted claims to runs/claims_<stamp>.json and append to runs.csv."""
    RUNS_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    claims_path = RUNS_DIR / f"claims_{stamp}.json"

    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump(ClaimList(claims=claims).model_dump(), f, ensure_ascii=False, indent=2)

    # Log to runs.csv
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

    new_file = not RUNS_CSV.exists()
    try:
        with open(RUNS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["time", "topic", "claims", "faithfulness", "claim_eq_span", "failed_ids", "urls"])
            w.writerow(row)
    except Exception:
        pass

    return str(claims_path)
