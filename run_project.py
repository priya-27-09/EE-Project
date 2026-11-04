#!/usr/bin/env python3
"""
AI Civic Guardian - Unified Service Runner
Launches both FastAPI (Backend API on :8000) and Flask (Frontend Web UI on :5000)
"""

import sys
import time
import signal
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    print("=" * 65)
    print("  AI Civic Guardian — Starting Platform Services")
    print("=" * 65)

    python_exe = sys.executable

    # Start FastAPI backend on port 8000
    fastapi_cmd = [
        python_exe,
        "-m",
        "uvicorn",
        "fastapi_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    print("[*] Starting FastAPI Backend API on http://127.0.0.1:8000 ...")
    fastapi_proc = subprocess.Popen(fastapi_cmd, cwd=str(BASE_DIR))

    # Give FastAPI a moment to initialize
    time.sleep(1.5)

    # Start Flask frontend on port 5000
    flask_cmd = [
        python_exe,
        "flask_app.py",
    ]
    print("[*] Starting Flask Web UI on http://127.0.0.1:5000 ...")
    flask_proc = subprocess.Popen(flask_cmd, cwd=str(BASE_DIR))

    print("-" * 65)
    print("  All Services Active:")
    print("    - Web Portal (Frontend):   http://127.0.0.1:5000")
    print("    - API Documentation (Docs): http://127.0.0.1:8000/docs")
    print("    - Health Check:            http://127.0.0.1:8000/health")
    print("-" * 65)
    print("  Demo Login Accounts:")
    print("    - Admin:   admin@civic.gov             / Admin@Civic2026!")
    print("    - Officer: officer.garbage@civic.gov   / Officer@Civic2026!")
    print("    - Citizen: (Register new or log in via portal)")
    print("=" * 65)
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 65)

    def shutdown(sig, frame):
        print("\n[*] Stopping services gracefully...")
        for proc in [fastapi_proc, flask_proc]:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("[*] All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # Wait for either process to terminate
    while True:
        if fastapi_proc.poll() is not None:
            print("[!] FastAPI process exited unexpectedly.")
            break
        if flask_proc.poll() is not None:
            print("[!] Flask process exited unexpectedly.")
            break
        time.sleep(1)

    shutdown(None, None)

if __name__ == "__main__":
    main()

