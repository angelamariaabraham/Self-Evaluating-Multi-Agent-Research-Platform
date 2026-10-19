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
    path = _path_for(url)
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("text", "")


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
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
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