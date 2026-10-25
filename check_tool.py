import json
from sources import SOURCE_DIR, load_source, top_chunks

for p in SOURCE_DIR.glob("*.json"):
    d = json.load(open(p, encoding="utf-8"))
    print(d["url"], len(d["text"]))

url = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12518350/"
t = load_source(url)
print("loaded:", len(t))
if t:
    for ch in top_chunks(t, "hallucination detection", k=3, size=2500):
        print("-----")
        print(ch[:300])