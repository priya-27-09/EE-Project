import urllib.request
import re

url = "https://data.mendeley.com/datasets/bundle.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        js = resp.read().decode("utf-8", errors="ignore")
        for pattern in ["download-all", "download_url", "files/", "direct_download"]:
            matches = [m.start() for m in re.finditer(pattern, js, re.IGNORECASE)]
            print(f"Pattern '{pattern}' occurrences: {len(matches)}")
            for idx in matches[:2]:
                print("  context:", js[max(0, idx-50):min(len(js), idx+100)])
except Exception as e:
    print("Error:", e)
