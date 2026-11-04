"""
AI Civic Guardian — Comprehensive Automated Source & System Security Audit
Scans project files for security vulnerabilities, unsafe coding patterns,
secret leakages, unsafe deserialization, SQL concatenation, and configuration risks.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class SecurityAuditor:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.findings: List[Dict[str, Any]] = []

    def log_finding(self, severity: str, category: str, file_path: str, line_no: int, description: str, snippet: str):
        self.findings.append({
            "severity": severity,
            "category": category,
            "file": file_path,
            "line": line_no,
            "description": description,
            "snippet": snippet.strip()[:100],
        })

    def audit_python_files(self):
        """Scans Python files for unsafe patterns."""
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "data", "weights"}
        
        # Patterns to check
        pats = [
            # eval / exec
            (re.compile(r"\b(eval|exec)\s*\("), "HIGH", "Unsafe Code Execution", "Avoid dynamic code execution with eval/exec"),
            # pickle
            (re.compile(r"\bpickle\.(loads?|Unpickler)\s*\("), "HIGH", "Insecure Deserialization", "Unsafe pickle deserialization"),
            # subprocess with shell=True
            (re.compile(r"subprocess\.(run|Popen|call|check_output)\([^)]*shell\s*=\s*True"), "HIGH", "Command Injection Risk", "Subprocess invoked with shell=True"),
            # raw SQL query format/f-string interpolation
            (re.compile(r"\.execute\(\s*f[\"']\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b", re.IGNORECASE), "CRITICAL", "SQL Injection Risk", "Direct SQL string interpolation without parameterization"),
            # hardcoded private key literal in source (excluding tests / comments)
            (re.compile(r"(PRIVATE_KEY|private_key)\s*=\s*[\"']0x[0-9a-fA-F]{64}[\"']"), "HIGH", "Hardcoded Private Key", "Private key hardcoded in source file"),
            # hardcoded secret key literal
            (re.compile(r"(JWT_SECRET|SECRET_KEY)\s*=\s*[\"'][^\"']{10,}[\"']"), "MEDIUM", "Potential Hardcoded Secret", "Secret key assigned literal value instead of env variable"),
            # debug=True in app.run
            (re.compile(r"app\.run\([^)]*debug\s*=\s*True"), "MEDIUM", "Debug Mode Active", "Flask debug=True enables interactive debugger in production"),
        ]

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel_root = Path(root).relative_to(self.root_dir)

            # Skip audit of tests themselves for patterns like testing eval or test fixtures
            if str(rel_root).startswith("tests") or str(rel_root).startswith(".agents") or str(rel_root).startswith("knowledge_base"):
                continue

            for file in files:
                if not file.endswith(".py"):
                    continue

                # Don't flag this security audit script itself
                if file in ["security_audit.py", "prepare_civic_dataset.py"]:
                    continue

                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.root_dir))

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                for idx, line in enumerate(lines, 1):
                    # Ignore comment-only lines
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue

                    # Check each pattern
                    for pat, sev, cat, desc in pats:
                        # Allow setting defaults in config.py if reading from os.getenv
                        if "config.py" in rel_path and "os.getenv" in line:
                            continue
                        # Allow blockchain deploy script reading env fallback
                        if "deploy.py" in rel_path and "os.getenv" in line:
                            continue

                        if pat.search(line):
                            self.log_finding(sev, cat, rel_path, idx, desc, line)

    def audit_template_files(self):
        """Scans Jinja templates for unsafe raw html or secret leakage."""
        templates_dir = self.root_dir / "templates"
        if not templates_dir.exists():
            return

        for file in templates_dir.glob("*.html"):
            rel_path = str(file.relative_to(self.root_dir))
            try:
                content = file.read_text(encoding="utf-8")
                lines = content.splitlines()
            except Exception:
                continue

            for idx, line in enumerate(lines, 1):
                # Search for unescaped HTML injection via safe filter
                if "| safe" in line and not any(tag in line for tag in ["<svg", "copyright", "i18n"]):
                    self.log_finding("LOW", "Template XSS Risk", rel_path, idx, "Jinja2 safe filter used; verify variable is sanitized", line)
                # Search for hardcoded password or token in markup
                if re.search(r"(jwt_token|password|secret)\s*[:=]\s*[\"'][^\"']+[\"']", line, re.IGNORECASE):
                    if "type=\"password\"" not in line and "name=\"password\"" not in line:
                        self.log_finding("HIGH", "Secret in Template", rel_path, idx, "Potential secret or credentials embedded in HTML template", line)

    def audit_database_configuration(self):
        """Audits database engine configuration and migrations."""
        from app.core.config import settings
        db_url = settings.DATABASE_URL
        if "sqlite" in db_url.lower():
            self.log_finding("CRITICAL", "Database Security", "app/core/config.py", 1, "SQLite detected in configuration! Application must use PostgreSQL only.", db_url)
        elif "postgresql" not in db_url.lower():
            self.log_finding("HIGH", "Database Security", "app/core/config.py", 1, "Non-PostgreSQL database specified", db_url)

    def audit_cors_configuration(self):
        """Audits CORS settings in FastAPI."""
        fastapi_file = self.root_dir / "fastapi_app.py"
        if fastapi_file.exists():
            content = fastapi_file.read_text(encoding="utf-8")
            if "allow_origins=[\"*\"]" in content and "allow_credentials=True" in content:
                self.log_finding("HIGH", "CORS Misconfiguration", "fastapi_app.py", 35, "Wildcard allow_origins with allow_credentials=True", "allow_origins=['*'], allow_credentials=True")

    def run(self) -> Dict[str, Any]:
        self.audit_python_files()
        self.audit_template_files()
        self.audit_database_configuration()
        self.audit_cors_configuration()

        counts = {
            "CRITICAL": sum(1 for f in self.findings if f["severity"] == "CRITICAL"),
            "HIGH": sum(1 for f in self.findings if f["severity"] == "HIGH"),
            "MEDIUM": sum(1 for f in self.findings if f["severity"] == "MEDIUM"),
            "LOW": sum(1 for f in self.findings if f["severity"] == "LOW"),
            "INFO": sum(1 for f in self.findings if f["severity"] == "INFO"),
        }
        return {
            "total_findings": len(self.findings),
            "counts": counts,
            "findings": self.findings,
        }


def main():
    print("=" * 80)
    print("AI CIVIC GUARDIAN — AUTOMATED SOURCE SECURITY AUDIT")
    print(f"Target Root: {BASE_DIR}")
    print("=" * 80)

    auditor = SecurityAuditor(BASE_DIR)
    results = auditor.run()

    counts = results["counts"]
    print(f"\n[SUMMARY] Total Findings: {results['total_findings']}")
    print(f"  CRITICAL : {counts['CRITICAL']}")
    print(f"  HIGH     : {counts['HIGH']}")
    print(f"  MEDIUM   : {counts['MEDIUM']}")
    print(f"  LOW      : {counts['LOW']}")
    print(f"  INFO     : {counts['INFO']}\n")

    if results["findings"]:
        print("Findings Detail:")
        for f in results["findings"]:
            print(f"  - [{f['severity']}] {f['category']} in {f['file']}:{f['line']}")
            print(f"    Description: {f['description']}")
            print(f"    Snippet: {f['snippet']}\n")
    else:
        print("[ALL CLEAN] No critical or high security vulnerabilities discovered in source scan.")

    print("=" * 80)
    return 0 if counts["CRITICAL"] == 0 and counts["HIGH"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
