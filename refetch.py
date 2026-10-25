import hashlib, sys
from pathlib import Path
import sources

url = sys.argv[1]
name = hashlib.md5(url.encode("utf-8")).hexdigest() + ".json"
for base in (Path("source_store"), Path("fixtures/pages")):
    p = base / name
    if p.exists():
        p.unlink()
        print("deleted", p)
text = sources.fetch_full_text(url)
print("fetched chars:", len(text))
if len(text) >= sources.MIN_CHARS:
    sources.save_source(url, text)
    print("saved. check for leftover:", "wired magazine" in text.lower())