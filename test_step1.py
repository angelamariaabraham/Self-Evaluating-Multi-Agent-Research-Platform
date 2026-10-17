from sources import fetch_full_text, save_source, load_source, chunk_text

url = "https://neurips.cc/virtual/2024/poster/95584"

text = fetch_full_text(url)
print("length:", len(text))
print(text[:300])

save_source(url, text)
assert load_source(url) == text
print("save/load OK")

chunks = chunk_text(text)
print("chunks:", len(chunks))
if len(chunks) > 1:
    assert chunks[0][-300:] == chunks[1][:300]
    print("overlap OK")