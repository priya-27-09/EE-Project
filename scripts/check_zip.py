import urllib.request

for ds_id in ["9t3y6hhddk", "5ty2wb6gvg", "264p83c276"]:
    url = f"https://data.mendeley.com/public-api/zip/{ds_id}/download/1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Mendeley {ds_id} zip status: {resp.status}, length: {resp.headers.get('content-length')}, type: {resp.headers.get('content-type')}")
    except Exception as e:
        print(f"Mendeley {ds_id} zip error: {e}")
