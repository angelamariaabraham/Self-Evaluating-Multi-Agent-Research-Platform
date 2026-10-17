from sources import load_source
t = load_source("https://neurips.cc/virtual/2024/poster/95584")
print(t[5000:5600])
print("-----")
print(t[-600:])
