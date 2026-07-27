#!/usr/bin/env python3
"""Reject accidentally tracked runtime and binary artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

ALLOWED_BINARIES = {"stripe_cli.zip", "stripe_cli_bin/stripe.exe"}
FORBIDDEN_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".venv", ".dev-pids"}
FORBIDDEN_SUFFIXES = (".pyc", ".pyo", ".db-wal", ".db-shm", ".log", ".pid")


def main() -> int:
    tracked = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True).stdout.splitlines()
    violations: list[str] = []
    for name in tracked:
        path = PurePosixPath(name)
        forbidden = (
            any(part in FORBIDDEN_PARTS for part in path.parts)
            or name.endswith(FORBIDDEN_SUFFIXES)
            or (path.suffix.lower() in {".zip", ".exe"} and name not in ALLOWED_BINARIES)
        )
        if forbidden:
            violations.append(name)
    if violations:
        print("Tracked repository artifacts are not allowed:")
        print("\n".join(f"- {name}" for name in violations))
        return 1
    missing = sorted(ALLOWED_BINARIES.difference(tracked))
    if missing:
        print("Required SaaS Pegasus Stripe CLI assets are missing:")
        print("\n".join(f"- {name}" for name in missing))
        return 1
    print("Repository hygiene check passed; Stripe CLI assets are explicitly retained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
