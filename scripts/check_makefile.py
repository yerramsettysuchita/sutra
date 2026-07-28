"""Verify the Makefile without running make.

The authoring environment has no make, so `make eval` on an evaluator's Linux
box is untested by definition. This narrows that gap by checking the things
that actually break a Makefile written by someone who could not execute it.

  1. every recipe line is indented with a literal tab, not spaces
  2. no recipe uses shell constructs that vary between /bin/sh implementations
  3. every module named by `python -m` actually imports
  4. every script path named in a recipe exists
  5. every target is declared .PHONY, since none of them produce a file of
     their own name

Run
    python scripts/check_makefile.py
    make check
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

# Constructs that are not portable across dash, ash and bash, or that GNU make
# passes to the shell in ways that differ by platform.
UNPORTABLE = [
    ("&&", "shell chaining, split into separate recipe lines"),
    ("||", "shell chaining, split into separate recipe lines"),
    ("[[", "bash test, use a portable form"),
    ("$(shell", "shell expansion at parse time, avoid"),
    ("source ", "bashism, use ."),
    (">/dev/null", "platform specific redirect"),
    ("2>&1", "redirect ordering differs, prefer 1>&2 for errors"),
]

TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)")
PY_MODULE_RE = re.compile(r"\$\(PYTHON\)\s+-m\s+([A-Za-z0-9_.]+)")
PY_SCRIPT_RE = re.compile(r"\$\(PYTHON\)\s+(?!-)([A-Za-z0-9_./-]+\.py)")

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def main() -> int:
    if not MAKEFILE.exists():
        fail("Makefile not found")
        return report()

    raw = MAKEFILE.read_text(encoding="utf-8")
    lines = raw.split("\n")

    targets: list[str] = []
    phony: set[str] = set()
    recipe_lines: list[tuple[int, str]] = []
    in_recipe = False

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            in_recipe = False
            continue
        if line.startswith("#"):
            continue

        if line.startswith("\t"):
            if not in_recipe:
                fail(f"line {number}: tab indented line outside any recipe")
            recipe_lines.append((number, line[1:]))
            continue

        # A line that looks like a recipe but is indented with spaces is the
        # single most common way a hand written Makefile fails, and make
        # reports it as a missing separator rather than as what it is.
        if line.startswith("    ") or line.startswith(" "):
            if in_recipe:
                fail(f"line {number}: recipe indented with spaces, must be a tab\n"
                     f"          {line!r}")
            continue

        match = TARGET_RE.match(line)
        if match:
            name = match.group(1)
            if name == ".PHONY":
                phony.update(line.split(":", 1)[1].split())
            elif name.startswith("."):
                pass
            else:
                targets.append(name)
                in_recipe = True
            continue
        in_recipe = False

    if not recipe_lines:
        fail("no recipe lines found, the tabs are probably spaces")

    # 2, portability
    #
    # An echo line is a string being printed, not a command being run, so a
    # word inside it is not a shell construct. This scanner flagged the help
    # text for containing "source encoding", which is the sort of false
    # positive that gets a checker switched off.
    for number, body in recipe_lines:
        text = body.lstrip("@-")
        if text.startswith("echo "):
            continue
        for token, why in UNPORTABLE:
            if token in text:
                fail(f"line {number}: {token!r} is not portable, {why}")

    # 3, python -m modules import
    modules = sorted({m for _, body in recipe_lines for m in PY_MODULE_RE.findall(body)})
    sys.path.insert(0, str(ROOT))
    for module in modules:
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, ModuleNotFoundError, ValueError) as exc:
            fail(f"python -m {module} will fail, {exc}")
            continue
        if spec is None:
            fail(f"python -m {module} will fail, module not found")
        else:
            notes.append(f"python -m {module}")

    # 4, script paths exist
    scripts = sorted({s for _, body in recipe_lines for s in PY_SCRIPT_RE.findall(body)})
    for script in scripts:
        if not (ROOT / script).exists():
            fail(f"recipe names {script}, which does not exist")
        else:
            notes.append(f"script {script}")

    # 5, .PHONY completeness
    missing = [t for t in targets if t not in phony]
    if missing:
        fail(f"targets missing from .PHONY: {', '.join(missing)}")

    notes.append(f"{len(targets)} targets, {len(recipe_lines)} recipe lines")
    notes.append(f"targets: {', '.join(targets)}")
    return report()


def report() -> int:
    if failures:
        print("Makefile check FAILED")
        print()
        for f in failures:
            print(f"  {f}")
        print()
        return 1
    print("Makefile check passed")
    print()
    for n in notes:
        print(f"  ok  {n}")
    print()
    print("  Not verified here, because make is absent from this environment:")
    print("  variable expansion at run time, and .DEFAULT_GOAL behaviour on")
    print("  make older than 3.81. Both are standard and neither is exotic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
