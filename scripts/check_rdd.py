import urllib.request
import re

url = "https://raw.githubusercontent.com/sekilab/RoadDamageDetector/master/README.md"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        print("RDD README links:")
        links = re.findall(r'https?://[^\s\)\"]+', content)
        for l in links[:20]:
            print(" ", l)
except Exception as e:
    print("Failed:", e)
