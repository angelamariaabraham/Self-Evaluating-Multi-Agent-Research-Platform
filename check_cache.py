import json, hashlib
from pathlib import Path

for p in Path("search_cache").glob("*.json"):
    items = json.loads(p.read_text(encoding="utf-8"))
    print(p.name[:8])
    for it in items:
        name = hashlib.md5(it["url"].encode("utf-8")).hexdigest() + ".json"
        ok = (Path("source_store") / name).exists()
        print("  ", "STORED " if ok else "MISSING", it["url"])