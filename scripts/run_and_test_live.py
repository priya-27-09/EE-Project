"""
AI Civic Guardian — Self-contained Live Server & Test Runner
Starts FastAPI & Flask in-process/subprocess, executes test_full_website_live.py, then tears them down.
"""

import sys
import time
import subprocess
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def wait_for_url(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def main():
    py = sys.executable
    print("[1/4] Starting FastAPI backend on 127.0.0.1:8000...")
    fastapi_proc = subprocess.Popen(
        [py, "-m", "uvicorn", "fastapi_app:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    print("[2/4] Starting Flask frontend on 127.0.0.1:5000...")
    flask_proc = subprocess.Popen(
        [py, "flask_app.py"],
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    exit_code = 1
    try:
        print("[3/4] Waiting for services to become healthy...")
        api_ok = wait_for_url("http://127.0.0.1:8000/health", timeout=12)
        web_ok = wait_for_url("http://127.0.0.1:5000/", timeout=12)

        if not api_ok or not web_ok:
            print(f"[!] Services failed to respond: API ready={api_ok}, Web ready={web_ok}")
            return 1

        print("[4/4] Executing scripts/test_full_website_live.py...")
        res = subprocess.run([py, str(BASE_DIR / "scripts" / "test_full_website_live.py")], cwd=str(BASE_DIR))
        exit_code = res.returncode
    finally:
        print("[*] Tearing down test servers...")
        for p in [fastapi_proc, flask_proc]:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print(f"[*] Live test runner finished with code: {exit_code}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())

