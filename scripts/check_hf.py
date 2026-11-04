import urllib.request
import urllib.parse
import json

queries = ['illegal dumping', 'water leak', 'sewage', 'street light', 'street lights', 'drainage', 'drain blockage', 'damaged road', 'garbage']
for q in queries:
    url = f"https://huggingface.co/api/datasets?search={urllib.parse.quote(q)}&limit=10"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode())
            print(f"HF search '{q}': {len(results)} found")
            for r in results[:4]:
                print(f"   {r.get('id')} | downloads: {r.get('downloads')} | tags: {r.get('tags', [])[:4]}")
    except Exception as e:
        print(f"HF error for {q}:", e)
