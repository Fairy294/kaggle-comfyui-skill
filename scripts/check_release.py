#!/usr/bin/env python3
"""Allowlisted public-file audit. Report rule+path only, never matching secrets."""

from pathlib import Path
import ast
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOP = {
    "README.md",
    "SKILL.md",
    "LICENSE",
    "requirements.txt",
    ".gitignore",
    "assets",
    "scripts",
    "references",
    "tests",
    ".github",
    "doc",
}
DOC_IMAGE_LIMIT = 10_000_000
DOC_IMAGE_HEADERS = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
}
RULES = {
    "credential-pattern": re.compile(
        r"\b(?:KGAT_|KGRT_|ghp_|gho_|hf_)[A-Za-z0-9_]{16,}"
    ),
    "private-machine-path": re.compile(r"/ho[m]e/[^/\s]+|/Use[r]s/[^/\s]+"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "email-address": re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ipv4-literal": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}
IGNORE = {
    ".git",
    ".ai-memory",
    ".audit",
    ".venv",
    ".ruff_cache",
    "__pycache__",
    ".pytest_cache",
}


def public_files():
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, timeout=10
    )
    if result.returncode == 0 and result.stdout:
        paths = [ROOT / name.decode() for name in result.stdout.split(b"\0") if name]
        return [path for path in paths if path.exists() or path.is_symlink()]
    return [
        p
        for p in ROOT.rglob("*")
        if p.is_file() and not any(x in IGNORE for x in p.relative_to(ROOT).parts)
    ]


def main():
    failures = []
    files = public_files()
    for path in files:
        relative = path.relative_to(ROOT)
        if relative.parts[0] not in TOP or any(
            part in IGNORE for part in relative.parts
        ):
            failures.append((str(relative), "nonpublic-path"))
            continue
        doc_image = (
            relative.parts[0] == "doc" and path.suffix.lower() in DOC_IMAGE_HEADERS
        )
        size_limit = DOC_IMAGE_LIMIT if doc_image else 300_000
        if path.is_symlink() or path.stat().st_size > size_limit:
            failures.append((str(relative), "symlink-or-large-file"))
            continue
        if doc_image:
            with path.open("rb") as handle:
                header = handle.read(8)
            if not header.startswith(DOC_IMAGE_HEADERS[path.suffix.lower()]):
                failures.append((str(relative), "invalid-doc-image"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            failures.append((str(relative), "unexpected-binary"))
            continue
        scan = text.replace("127.0.0.1", "LOCALHOST").replace("0.0.0.0", "BIND-TEST")
        # URL userinfo below appears only in negative tests; never treat it as an email.
        scan = re.sub(r"https://user:(?:pass|pw)@", "https://INVALID-USERINFO/", scan)
        for name, pattern in RULES.items():
            if pattern.search(scan):
                failures.append((str(relative), name))
        if path.suffix == ".py":
            ast.parse(text, filename=str(relative))
        if path.suffix == ".json":
            json.loads(text)
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", skill):
        if not target.startswith("https://") and not (ROOT / target).is_file():
            failures.append(("SKILL.md", "missing-linked-resource"))
    for path, rule in failures:
        print(json.dumps({"file": path, "rule": rule}))
    print(
        json.dumps(
            {
                "release_audit_pass": not failures,
                "public_files_checked": len(files),
                "findings": len(failures),
            }
        )
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
