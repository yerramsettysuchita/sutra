"""Fail the build on the three encoding faults that have actually bitten us.

All three came from the same source, a Windows PowerShell rewrite of a source
file, and none of them was visible in a diff.

  1. a UTF-8 byte order mark, which broke the parse of data/generator/generate.py
     and silently broke a JSON fetch in the web client
  2. a null byte, which landed inside an f-string in benchmark/score.py and ate
     the separator between two labels, so two different clusters could collide
     into one key and the scorer reported figures that were quietly wrong
  3. a literal backtick n, which PowerShell writes when a replacement string is
     single quoted, and which lands mid line where a newline was meant

The scorer incident is why this file exists. A corrupted scorer does not crash,
it returns a number, and a number is exactly the thing nobody re-checks.

Run
    python scripts/check_encoding.py
    make check
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".js", ".css", ".json", ".md",
            ".sh", ".sql"}

SKIP_PARTS = {"node_modules", "dist", ".git", "__pycache__", "work",
              "vocab_work", "corpus"}

# This file and the test that mirrors it both carry the pattern as data.
SKIP_NAMES = {"check_encoding.py", "test_artifacts.py"}

# PowerShell writes a literal backtick n when a replacement string is single
# quoted. The signature is a backtick, an n, then whitespace. Markdown inline
# code such as `name`, `num` or `npm run check` never matches, because the
# character after the n is a letter or a closing backtick.
ESCAPE = re.compile(r"`n\s")

# Suffixes where a backtick is ordinary punctuation rather than a defect.
ESCAPE_EXEMPT = {".md", ".json"}


def sources():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if set(path.parts) & SKIP_PARTS:
            continue
        yield path


def check() -> list[str]:
    problems: list[str] = []
    for path in sources():
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()

        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{rel}: byte order mark")
        if b"\x00" in raw:
            problems.append(f"{rel}: null byte")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            problems.append(f"{rel}: not valid UTF-8, {error}")
            continue

        if path.suffix in ESCAPE_EXEMPT or path.name in SKIP_NAMES:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if ESCAPE.search(line):
                problems.append(f"{rel}:{number}: literal backtick n escape")
    return problems


def main() -> int:
    problems = check()
    counted = sum(1 for _ in sources())
    if problems:
        print("Encoding check FAILED", file=sys.stderr)
        print(file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(file=sys.stderr)
        print("  Rewrite the file with the editor, not with PowerShell "
              "Set-Content.", file=sys.stderr)
        return 1
    print(f"Encoding check passed, {counted} source files")
    print("  no byte order mark, no null byte, no literal escape, all UTF-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
