from sources import load_source
from checks import span_in_source

url = "https://neurips.cc/virtual/2024/poster/95584"
real = load_source(url)[100:220]
print(span_in_source(url, real))                 # expect True
print(span_in_source(url, "this sentence was never on the page at all"))  # expect False