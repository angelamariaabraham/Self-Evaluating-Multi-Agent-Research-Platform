from sources import fetch_full_text

url = "https://neurips.cc/virtual/2024/poster/95584"
for i in range(5):
    print(i, len(fetch_full_text(url)))