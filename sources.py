#sources.py
import os
import json
import re
import hashlib
from pathlib import Path
import time

from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

SOURCE_DIR = Path("source_store")
SOURCE_DIR.mkdir(exist_ok=True)

_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])


def _path_for(url: str) -> Path:
    name = hashlib.md5(url.encode("utf-8")).hexdigest()
    return SOURCE_DIR / f"{name}.json"


def _extract_markdown(result) -> str:
    """Result may be a dict or an object, depending on firecrawl version."""
    if result is None:
        return ""
    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            return data.get("markdown", "") or ""
        return result.get("markdown", "") or ""
    data = getattr(result, "data", None)
    if data is not None:
        return getattr(data, "markdown", "") or ""
    return getattr(result, "markdown", "") or ""

MIN_CHARS = 3000

def fetch_full_text(url: str, tries: int = 3) -> str:
    """Scrape page, return cleaned markdown. Retry if result looks thin."""
    best = ""
    for attempt in range(tries):
        try:
            result = _client.scrape(
                url,
                formats=["markdown"],
                only_main_content=True,
                max_age=0,
            )
            text = clean_markdown(_extract_markdown(result))
            if len(text) > len(best):
                best = text
            if len(best) >= MIN_CHARS:
                return best
        except Exception as e:
            print(f"Scrape failed for {url} (try {attempt + 1}): {e}")
        time.sleep(2)
    return best


def save_source(url: str, text: str) -> None:
    with open(_path_for(url), "w", encoding="utf-8") as f:
        json.dump({"url": url, "text": text}, f, ensure_ascii=False)

def load_source(url: str) -> str:
    name = hashlib.md5(url.encode("utf-8")).hexdigest() + ".json"
    for base in (SOURCE_DIR, FIXTURE_DIR / "pages"):
        path = base / name
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("text", "")
    return ""



def chunk_text(text: str, max_chars: int = 6000, overlap: int = 300) -> list[str]:
    if max_chars <= overlap:
        raise ValueError("max_chars must be bigger than overlap")
    chunks = []
    start = 0
    step = max_chars - overlap
    while start < len(text):
        chunks.append(text[start:start + max_chars])
        start += step
    return chunks


TAIL_MARKERS = [
    "[Bytez.com]",
    "protected by **reCAPTCHA**",
    "uses cookies for essential functions",
]


def clean_markdown(text: str) -> str:
    # [label](url) -> label
    #text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[((?:\\.|[^\]\\])*)\]\([^)]*\)", r"\1", text)
    # cut footer boilerplate: keep text before earliest marker
    cut = len(text)
    for m in TAIL_MARKERS:
        i = text.find(m)
        if i != -1:
            cut = min(cut, i)
    text = text[:cut]
    # collapse blank-line runs
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def top_chunks(text: str, query: str, k: int = 3, size: int = 2500) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3]
    chunks = chunk_text(text, max_chars=size, overlap=200)
    scored = []
    for i, ch in enumerate(chunks):
        low = ch.lower()
        scored.append((sum(low.count(w) for w in words), i, ch))
    scored.sort(key=lambda t: (-t[0], t[1]))
    best = sorted(scored[:k], key=lambda t: t[1])   # back to page order
    return [ch for _, _, ch in best]

SEARCH_DIR = Path("search_cache")
SEARCH_DIR.mkdir(exist_ok=True)
FIXTURE_DIR = Path("fixtures")
MODE = os.getenv("SOURCE_MODE", "cache")  # live | cache | offline


def _extract_items(results) -> list[dict]:
    if isinstance(results, dict):
        items = results.get("data", []) or results.get("web", [])
    else:
        items = getattr(results, "data", None) or getattr(results, "web", None) or []
    out = []
    for item in items:
        if isinstance(item, dict):
            url, title = item.get("url", ""), item.get("title", "")
        else:
            url, title = getattr(item, "url", ""), getattr(item, "title", "")
        if url:
            out.append({"url": url, "title": title})
    return out


def _search_key(query: str, limit: int) -> str:
    raw = json.dumps({"q": query.strip().lower(), "limit": limit}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cached_search(query: str, limit: int = 5) -> list[dict]:
    key = _search_key(query, limit)
    if MODE != "live":
        for base in (SEARCH_DIR, FIXTURE_DIR / "search"):
            p = base / f"{key}.json"
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
    if MODE == "offline":
        raise RuntimeError(f"offline: no cache or fixture for query {query!r}")
    items = _extract_items(_client.search(query, limit=limit))
    if items:  # never cache empty results
        (SEARCH_DIR / f"{key}.json").write_text(
            json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


def get_source_text(url: str) -> str:
    text = load_source(url)
    if text:
        return text
    if MODE == "offline":
        return ""
    text = fetch_full_text(url)
    if len(text) >= MIN_CHARS:
        save_source(url, text)
        return text
    return ""