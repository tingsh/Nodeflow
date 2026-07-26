#!/usr/bin/env python3
"""Validate local links in active Markdown documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")


def active_markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "AGENTS.md"]
    files.extend(path for path in (ROOT / "docs").rglob("*.md") if "archive" not in path.parts)
    return sorted(set(files))


def validate_link(source: Path, raw_target: str) -> str | None:
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(SKIP_PREFIXES):
        return None
    if target.startswith("file://"):
        return "uses a machine-local file:// link"
    path_text = unquote(target.split("#", 1)[0])
    if not path_text or any(marker in path_text for marker in ("{", "}")):
        return None
    resolved = (source.parent / path_text).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return "points outside the repository"
    if not resolved.exists():
        return f"target does not exist: {path_text}"
    return None


def main() -> int:
    errors: list[str] = []
    for source in active_markdown_files():
        text = source.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            error = validate_link(source, match.group(1))
            if error:
                errors.append(f"{source.relative_to(ROOT)}: {error}")
    if errors:
        print("Active documentation link check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Validated local links in {len(active_markdown_files())} active Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
