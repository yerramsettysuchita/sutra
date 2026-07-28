"""Fail the build when a published report is older than the corpus it describes.

    python scripts/check_freshness.py
    make check

WHY THIS EXISTS

An audit found `scale_report.json` and `vocabulary_report.json` timestamped
16:52 and 16:55 UTC against a corpus regenerated at 20:41. Both were rendered on
/evaluation and printed in the README with no staleness marker, describing a
corpus that no longer existed.

That is exactly the failure `eval/canonical.json` was built to prevent, and it
slipped through for one reason: neither study was in `make all`, so nothing ever
re-ran them and nothing ever noticed. The canonical system guards the figures it
was pointed at. This guards the ones nobody pointed it at.

THE RULE

Every report that describes the corpus must be at least as new as the corpus
manifest. A report older than the corpus is describing something else.

Studies that are deliberately expensive to re-run, the vocabulary sweep and the
scale study, are allowed to be stale, but they must then be *labelled* stale in
the exports rather than presented as current. This script writes that label into
their JSON so the screens can render it, and fails only when a report that is
supposed to track every run has fallen behind.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
MANIFEST = CORPUS / "manifest.json"

# Reports that must never be older than the corpus. These are produced by
# `make all`, so a stale one means the chain did not complete.
BLOCKING = [
    (CORPUS / "blocking_report.json", "make block"),
    (CORPUS / "resolution_report.json", "make resolve"),
    (CORPUS / "other_persons_report.json", "make persons"),
    (CORPUS / "downstream_report.json", "make downstream"),
    (CORPUS / "reconciliation_report.json", "make reconcile"),
    (ROOT / "eval" / "report.json", "make eval"),
    (ROOT / "eval" / "canonical.json", "make eval"),
]

# Reports that are allowed to lag, because re-running them costs many minutes.
# They are labelled rather than rejected.
ADVISORY = [
    (CORPUS / "vocabulary_report.json", "python scripts/vocabulary_study.py"),
    (CORPUS / "scale_report.json", "python scripts/scale_study.py"),
    (CORPUS / "layer6_selection_report.json",
     "python scripts/layer6_selection_study.py"),
    (CORPUS / "sparse_table_report.json",
     "python scripts/sparse_table_study.py"),
]


def stamp(path: Path) -> datetime | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    raw = payload.get("generated_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def main() -> int:
    corpus_at = stamp(MANIFEST)
    if corpus_at is None:
        print("no corpus manifest, nothing to check against. Run: make gen")
        return 0

    print("Report freshness, against a corpus generated at")
    print(f"  {corpus_at.isoformat()}")
    print()

    failures: list[str] = []
    for path, command in BLOCKING:
        at = stamp(path)
        name = path.relative_to(ROOT).as_posix()
        if at is None:
            failures.append(f"{name} is missing or carries no timestamp, run: {command}")
            print(f"  FAIL {name:<44} missing")
            continue
        if at < corpus_at:
            failures.append(
                f"{name} is older than the corpus by "
                f"{corpus_at - at}, run: {command}")
            print(f"  FAIL {name:<44} {at.isoformat()}  STALE")
        else:
            print(f"  ok   {name:<44} {at.isoformat()}")

    print()
    stale_advisory = []
    for path, command in ADVISORY:
        at = stamp(path)
        name = path.relative_to(ROOT).as_posix()
        if at is None:
            print(f"  note {name:<44} not produced")
            continue
        if at < corpus_at:
            stale_advisory.append(name)
            print(f"  note {name:<44} {at.isoformat()}  stale, will be labelled")
            # Write the label into the file so the screens can render it. A
            # figure a reader cannot tell is stale is worse than an absent one.
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["stale"] = {
                "is_stale": True,
                "report_generated_at": payload.get("generated_at"),
                "corpus_generated_at": corpus_at.isoformat(),
                "refresh_with": command,
                "note": ("This study was run against an earlier corpus. Its "
                         "figures are not from the run that produced the "
                         "headline and are labelled wherever they appear."),
            }
            path.write_text(json.dumps(payload, indent=2, default=float),
                            encoding="utf-8")
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.pop("stale", None) is not None:
                path.write_text(json.dumps(payload, indent=2, default=float),
                                encoding="utf-8")
            print(f"  ok   {name:<44} {at.isoformat()}")

    print()
    if failures:
        print("Freshness check FAILED")
        print()
        for f in failures:
            print(f"  {f}")
        return 1

    print("Freshness check passed.")
    if stale_advisory:
        print(f"  {len(stale_advisory)} advisory report(s) labelled stale: "
              f"{', '.join(stale_advisory)}")
        print("  They are not blocking. They are marked so no screen can show")
        print("  them as current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
