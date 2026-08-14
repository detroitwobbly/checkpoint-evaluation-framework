from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".ps1"}
SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    ".test_tmp",
    ".verify_dist",
    ".verify_run",
    ".verify_venv",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
FORBIDDEN_SUFFIXES = {".ckpt", ".safetensors", ".pt", ".pth"}
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
WINDOWS_USER_PATH = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\", re.IGNORECASE)
POSIX_USER_PATH = re.compile(r"/(?:home|Users)/[^/\s]+/")
BEARER_VALUE = re.compile(r"Bearer\s+[A-Za-z0-9._~-]{16,}", re.IGNORECASE)
SECRET_ASSIGNMENT = re.compile(
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"](?!your-|example|replace|$)([^'\"]{8,})['\"]",
    re.IGNORECASE,
)


def audit(root: Path) -> dict[str, list[str]]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    files = list(_files(root))

    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden model/weight artifact: {relative}")
        if path.suffix.lower() == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid JSON: {relative}: {exc}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append(f"unreadable text file: {relative}: {exc}")
            continue
        if WINDOWS_USER_PATH.search(text) or POSIX_USER_PATH.search(text):
            errors.append(f"personal absolute path: {relative}")
        if BEARER_VALUE.search(text) or SECRET_ASSIGNMENT.search(text):
            errors.append(f"credential-like value: {relative}")
        if path.suffix.lower() == ".md":
            errors.extend(_broken_links(root, path, text))

    placeholders = []
    for relative in ("README.md", "pyproject.toml"):
        path = root / relative
        if path.exists() and "OWNER" in path.read_text(encoding="utf-8-sig"):
            placeholders.append(relative)
    if placeholders:
        warnings.append(f"publication identity placeholder remains: {', '.join(placeholders)}")

    return {"errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def _files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS or part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        yield path


def _broken_links(root: Path, markdown: Path, text: str) -> list[str]:
    errors: list[str] = []
    for match in MARKDOWN_LINK.finditer(text):
        target = match.group(1).strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = (markdown.parent / target).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"link escapes repository: {markdown.relative_to(root).as_posix()} -> {target}")
            continue
        if not candidate.exists():
            errors.append(f"broken local link: {markdown.relative_to(root).as_posix()} -> {target}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a curated CEF tree for release-blocking sanitation issues.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = audit(args.root)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
