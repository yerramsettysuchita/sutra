"""Package web/dist into a Catalyst deployable zip.

The one thing this gets right that a manual zip usually gets wrong.

Catalyst Web Client Hosting expects `index.html` at the archive root. Zipping
the folder rather than its contents produces an archive with a `dist/` prefix
on every entry, the upload succeeds, and the deployed URL returns 404. It is
the most common way to lose twenty minutes on this platform, so the archive is
built from the contents and then read back to prove no entry carries a
directory prefix.

Verification is not duplicated here. It shells out to web/scripts/verify-dist.mjs
so there is one definition of what a shippable bundle is.

    python scripts/package_catalyst.py

Writes catalyst/sutra.zip. Does not upload. Deployment is a console action, see
docs/deploy.md.

The catalyst/ directory is a build output and is not committed. This creates it
when it runs and .gitignore keeps it out of history, because a 900 KB binary
that changes on every build is not something a repository should carry.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
OUT = ROOT / "catalyst" / "sutra.zip"
VERIFY = ROOT / "web" / "scripts" / "verify-dist.mjs"

REQUIRED_AT_ROOT = ["index.html"]
REQUIRED_REPORTS = [
    "corpus/manifest.json",
    "corpus/corpus_stats.json",
    "corpus/blocking_report.json",
]


def fail(message: str) -> None:
    print(f"\nPACKAGING FAILED\n\n  {message}\n", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not DIST.exists():
        fail("web/dist not found. Build it first:\n"
             "    npm --prefix web run build\n"
             "  or\n"
             "    make build")

    node = shutil.which("node")
    if node is None:
        fail("node not found on PATH, needed to verify the bundle")

    print("verifying the bundle")
    result = subprocess.run(
        [node, str(VERIFY)], cwd=ROOT / "web",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        print(result.stdout)
        fail("web/scripts/verify-dist.mjs rejected the bundle, see above. "
             "Nothing was packaged.")
    print("  bundle accepted")

    files = sorted(p for p in DIST.rglob("*") if p.is_file())
    if not files:
        fail("web/dist is empty")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    print(f"\nwriting {OUT.relative_to(ROOT)}")
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for path in files:
            # arcname relative to dist, so index.html lands at the archive root
            # and never under a dist/ prefix.
            archive.write(path, arcname=path.relative_to(DIST).as_posix())

    # Read the archive back rather than trusting that the write did what we
    # intended. This is the check that the deployment actually depends on.
    with zipfile.ZipFile(OUT) as archive:
        names = archive.namelist()
        problems = []
        for required in REQUIRED_AT_ROOT:
            if required not in names:
                problems.append(f"{required} is not at the archive root")
        for required in REQUIRED_REPORTS:
            if required not in names:
                problems.append(f"{required} is missing from the archive")
        for name in names:
            head = name.split("/", 1)[0]
            if head in {"dist", "web"}:
                problems.append(
                    f"entry {name!r} carries a {head}/ prefix, so the archive "
                    f"wraps the folder instead of its contents")
                break
        fonts = [n for n in names if n.endswith(".woff2")]
        if len(fonts) < 8:
            problems.append(f"only {len(fonts)} woff2 files in the archive, expected 8")
        if problems:
            fail("\n  ".join(problems))

        total = sum(i.file_size for i in archive.infolist())
        compressed = OUT.stat().st_size

        print(f"\n  {len(names)} entries at the archive root")
        print(f"  {total / 1024:.0f} KB uncompressed, {compressed / 1024:.0f} KB zipped")
        print()
        for name in sorted(names):
            info = archive.getinfo(name)
            print(f"    {name:<44} {info.file_size / 1024:>8.1f} KB")

    print(f"\nREADY  {OUT}")
    print("\nUpload through the Catalyst console. Do not create a new app.")
    print("App sutra, deployment default. See docs/deploy.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
