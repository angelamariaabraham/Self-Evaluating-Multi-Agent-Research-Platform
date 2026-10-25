import shutil
from sources import _search_key, SEARCH_DIR

TOPIC = "hallucination detection"
src = next(SEARCH_DIR.glob("e1fdea58*.json"))
dst = SEARCH_DIR / f"{_search_key(TOPIC, 5)}.json"
shutil.copy(src, dst)
print("seeded", dst.name)