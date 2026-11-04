import urllib.request
import re
import json

def check_mendeley(ds_id):
    url = f"https://data.mendeley.com/datasets/{ds_id}/1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # find JSON-LD
            # Find all occurrences of .zip, .tar, .xml, .csv
            matches = re.findall(r'([^"\'\s]+\.(?:zip|rar|tar\.gz|tar|7z|xml|json))', html)
            print("Archive/file matches in HTML:", set(matches))
            # Also search for files: or download:
            dl_matches = re.findall(r'"([^"]*download[^"]*)"', html)
            print("Download matches:", set(dl_matches))
    except Exception as e:
        print(f"Error {ds_id}: {e}")

if __name__ == "__main__":
    check_mendeley("9t3y6hhddk")
    check_mendeley("264p83c276")
    check_mendeley("5ty2wb6gvg")
