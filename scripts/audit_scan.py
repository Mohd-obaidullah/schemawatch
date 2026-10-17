from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PATTERNS = [
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]{10,}")),
    ("Slack token", re.compile(r"xox[bpas]-[0-9a-zA-Z]{10,}")),
    ("GitHub token", re.compile(r"ghp_[0-9a-zA-Z]{36}")),
    ("AWS key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Password assignment", re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{4,}['\"]")),
    ("API token assignment", re.compile(r"(?i)api_token\s*[:=]\s*['\"][^'\"]{4,}['\"]")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}")),
]

SAFE_TOKENS = [
    "test",
    "example",
    "secret-token",
    "dummy",
    "mock",
    "placeholder",
    "change-me",
    "your-",
    "your/",
    "t00/b00",
    "very_secret_key",
    "<",
    "${",
]


def is_safe(val: str) -> bool:
    val_lower = val.lower()
    return any(safe in val_lower for safe in SAFE_TOKENS)


def scan_git_history() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    try:
        log_out = subprocess.check_output(
            ["git", "log", "-p", "--all"],
            cwd=REPO_ROOT,
            text=True,
            errors="replace",
        )
    except Exception as exc:
        print(f"Error reading git log: {exc}")
        return findings

    current_commit = "unknown"
    for line in log_out.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1]
        for name, pat in PATTERNS:
            match = pat.search(line)
            if match:
                matched_val = match.group(0)
                if not is_safe(matched_val):
                    findings.append((current_commit, name, matched_val[:8] + "..."))
    return findings


def scan_working_tree() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    ignored_dirs = {
        ".git",
        ".venv",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "__pycache__",
    }

    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for fname in files:
            fpath = Path(root) / fname
            # Check sqlite / db files
            if fpath.suffix in [".db", ".sqlite", ".sqlite3"]:
                rel_path = fpath.relative_to(REPO_ROOT)
                findings.append((str(rel_path), "Database file", fname))
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for name, pat in PATTERNS:
                for line in content.splitlines():
                    match = pat.search(line)
                    if match:
                        matched_val = match.group(0)
                        if not is_safe(matched_val):
                            rel_path = fpath.relative_to(REPO_ROOT)
                            findings.append((str(rel_path), name, matched_val[:8] + "..."))
    return findings


def main() -> None:
    print("=== 1. SCANNING FULL GIT HISTORY ===")
    history_findings = scan_git_history()
    if history_findings:
        print(f"FAILED: Found {len(history_findings)} secret(s) in git history:")
        for commit, name, sample in history_findings:
            print(f"  commit {commit}: {name} ({sample})")
    else:
        print("PASSED: No secrets found in git history.")

    print("\n=== 2. SCANNING WORKING TREE ===")
    working_findings = scan_working_tree()
    if working_findings:
        print(f"WARNING: Found {len(working_findings)} item(s) in working tree:")
        for path, name, sample in working_findings:
            print(f"  {path}: {name} ({sample})")
    else:
        print("PASSED: No secrets found in working tree.")


if __name__ == "__main__":
    main()
