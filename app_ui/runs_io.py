"""Read saved runs from disk. No Streamlit imports: easy to test on its own."""
import csv
import datetime
import glob
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from confidence import band, score_all
from schema import Claim, ContradictionResult, StressResult

log = logging.getLogger(__name__)

RUNS_DIR = Path("runs")
RUNS_CSV = Path("runs.csv")
SOURCE_STORE = Path("source_store")
CACHE_FILES = {
    "support": RUNS_DIR / "support_cache.json",
    "contradiction": RUNS_DIR / "contradiction_cache.json",
    "devils_advocate": RUNS_DIR / "da_cache.json",
}
STAMP_RE = re.compile(r"claims_(\d{8}_\d{6})\.json")


class RunLoadError(Exception):
    """The claims file of a run could not be read."""


def read_json(path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_rows_by_stamp() -> Dict[str, dict]:
    rows: Dict[str, dict] = {}
    if not RUNS_CSV.exists():
        return rows
    try:
        with open(RUNS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                key = row.get("time", "").replace(":", "").replace("-", "").replace("T", "_")[:15]
                rows[key] = row
    except (OSError, csv.Error) as e:
        log.warning("Could not read %s: %s", RUNS_CSV, e)
    return rows


def get_available_runs() -> List[Dict[str, Any]]:
    """All saved runs, newest first, enriched with topic/faithfulness from runs.csv."""
    csv_rows = _csv_rows_by_stamp()
    runs = []
    for path in sorted(glob.glob("runs/claims_*.json"), reverse=True):
        name = Path(path).name
        m = STAMP_RE.search(name)
        stamp = m.group(1) if m else name
        info = csv_rows.get(stamp, {})

        topic = info.get("topic")
        claims_num = info.get("claims")
        if not topic:
            try:
                claims_num = len(read_json(path).get("claims", []))
                topic = "Unknown Topic"
            except (OSError, ValueError, AttributeError) as e:
                log.warning("Unreadable run %s: %s", path, e)
                claims_num, topic = 0, "Unreadable Run"

        claims_count = int(claims_num) if str(claims_num).isdigit() else 0
        try:
            shown_time = datetime.datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%b %d, %H:%M")
        except ValueError:
            shown_time = stamp

        runs.append({
            "path": path,
            "filename": name,
            "stamp": stamp,
            "display": f"{shown_time} — {topic[:36]} ({claims_count} claims)",
            "topic": topic,
            "claims_count": claims_count,
            "faithfulness": _to_float(info.get("faithfulness")),
        })
    return runs


def _sibling(claims_path: str, prefix: str, suffix: Optional[str] = None) -> Path:
    """runs/claims_X.json -> runs/<prefix>X.json (or with a different suffix)."""
    p = Path(claims_path)
    sib = p.with_name(p.name.replace("claims_", prefix, 1))
    return sib.with_suffix(suffix) if suffix else sib


def _load_contradiction(path: str, claims: List[Claim]) -> ContradictionResult:
    result = ContradictionResult(flags=[])
    sib = _sibling(path, "contradiction_")
    if sib.exists():
        try:
            result = ContradictionResult(**read_json(sib))
            flagged = {cid for f in result.flags for cid in f.claim_ids}
            for c in claims:
                if c.contradiction_flag is None:
                    c.contradiction_flag = c.claim_id in flagged
        except (OSError, ValueError, TypeError) as e:
            log.warning("Bad contradiction file %s: %s", sib, e)
    return result


def _load_stress(path: str, claims: List[Claim]) -> StressResult:
    result = StressResult(items=[])
    sib = _sibling(path, "stress_")
    if sib.exists():
        try:
            result = StressResult(**read_json(sib))
            by_id = {item.claim_id: item for item in result.items}
            for c in claims:
                if c.claim_id in by_id and c.stress_verdict is None:
                    c.stress_verdict = by_id[c.claim_id].verdict
                    c.stress_weakness = by_id[c.claim_id].weakness
        except (OSError, ValueError, TypeError) as e:
            log.warning("Bad stress file %s: %s", sib, e)
    return result


def _merge_stages(path: str, cres: ContradictionResult, sres: StressResult):
    """Fall back to the combined stages_*.json when separate files gave nothing."""
    sib = _sibling(path, "stages_")
    if sib.exists():
        try:
            stages = read_json(sib)
            if "contradiction" in stages and not cres.flags:
                cres = ContradictionResult(**stages["contradiction"])
            if "stress" in stages and not sres.items:
                sres = StressResult(**stages["stress"])
        except (OSError, ValueError, TypeError) as e:
            log.warning("Bad stages file %s: %s", sib, e)
    return cres, sres


def _read_report(path: str) -> str:
    sib = _sibling(path, "report_", ".md")
    if sib.exists():
        try:
            return sib.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("Could not read %s: %s", sib, e)
    return ""


def _fallback_report(topic: str, claims: List[Claim], cres: ContradictionResult, sres: StressResult) -> str:
    counts = {"high": 0, "medium": 0, "low": 0}
    for c in claims:
        counts[band(c.confidence or 0)] += 1
    reasons = {i.claim_id: i.reason for i in sres.items}
    n_sources = len({c.source_url for c in claims})

    lines = [
        f"# TruthEngine Executive Report: {topic}", "",
        f"**Summary:** Verified {len(claims)} atomic claims across {n_sources} sources.", "",
        f"**Epistemic Confidence:** {counts['high']} High, {counts['medium']} Medium, {counts['low']} Low.  ",
        f"**Cross-Source Contradictions:** {len(cres.flags)} flagged across {cres.pairs_checked} evaluated pairs.", "",
        "---", "",
        "## Contradiction Analysis", "",
    ]
    if cres.flags:
        lines += [f"- **{', '.join(f.claim_ids)}**: {f.explanation}" for f in cres.flags]
    else:
        lines.append("No logical contradictions found among verified source pairs.")
    lines += ["", "## Confidence-Ranked Claims", ""]

    for c in sorted(claims, key=lambda c: -(c.confidence or 0)):
        lines += [
            f"### [{c.claim_id}] {c.claim_text}",
            f"**Confidence Score:** `{(c.confidence or 0):.2f}` ({band(c.confidence or 0).upper()})  ",
            f"- **Source URL:** {c.source_url}",
            f"- **Exact Quoted Span:** *\"{c.evidence_span}\"*",
        ]
        if c.stress_verdict:
            crit = f" ({c.stress_weakness}): {reasons.get(c.claim_id, '')}" if c.stress_verdict == "weak" else ""
            lines.append(f"- **Evidence Strength:** `{c.stress_verdict.upper()}`{crit}")
        if c.confidence_reasons:
            lines.append(f"- **Calibrated Audit:** {'; '.join(c.confidence_reasons)}")
        lines.append("")
    return "\n".join(lines)


def load_run_package(file_path: str, runs: Optional[List[Dict[str, Any]]] = None):
    """Return (claims, topic, contradiction_result, stress_result, report_markdown).

    Raises RunLoadError if the claims file itself is unreadable.
    Pass `runs` (from get_available_runs) to avoid scanning the folder again.
    """
    try:
        claims = [Claim(**c) for c in read_json(file_path).get("claims", [])]
    except (OSError, ValueError, TypeError, AttributeError) as e:
        raise RunLoadError(f"Failed to load run {file_path}: {e}") from e

    runs = runs if runs is not None else get_available_runs()
    match = next((r for r in runs if r["path"] == file_path), None)
    topic = match["topic"] if match else "Multi-Agent Research"

    cres = _load_contradiction(file_path, claims)
    sres = _load_stress(file_path, claims)
    cres, sres = _merge_stages(file_path, cres, sres)
    score_all(claims)

    report_md = _read_report(file_path) or _fallback_report(topic, claims, cres, sres)
    return claims, topic, cres, sres, report_md


def _json_len(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return len(read_json(path))
    except (OSError, ValueError, TypeError) as e:
        log.warning("Could not read cache %s: %s", path, e)
        return 0


def cache_sizes() -> Dict[str, int]:
    """Entry counts for the persistent caches plus number of scraped source files."""
    sizes = {name: _json_len(path) for name, path in CACHE_FILES.items()}
    sizes["sources"] = len(list(SOURCE_STORE.glob("*.json"))) if SOURCE_STORE.exists() else 0
    return sizes
