"""Mirror the build status table from the screen into docs/build-status.md.

There is one source of truth, `CLAIMS` in web/src/screens/Status.tsx, and this
script parses it so the page and the README can never disagree. A status table
that drifts from the code is worse than no status table.

    python scripts/build_status_md.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web" / "src" / "screens" / "Status.tsx"
TARGET = ROOT / "docs" / "build-status.md"
EVAL = ROOT / "eval" / "report.json"
DATA = ROOT / "web" / "public" / "data"
CORPUS = ROOT / "web" / "public" / "corpus"
PROFILES = DATA / "profiles.json"


def read(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def indian(value) -> str:
    """Indian digit grouping, matching toLocaleString('en-IN') on the screen."""
    if value is None:
        return "not measured"
    digits = f"{int(round(value)):d}"
    sign, digits = ("-", digits[1:]) if digits.startswith("-") else ("", digits)
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return sign + ",".join(parts + [tail])


def tokens() -> dict[str, str]:
    """The same substitutions the Status screen makes, from the same files.

    `tokensFrom` in web/src/screens/Status.tsx is the other half of this. Both
    read the exported JSON, so a figure in the status table exists in exactly
    one place, the file the engine wrote.
    """
    canonical = read(ROOT / "eval" / "canonical.json") or {}
    ev = read(DATA / "eval.json") or read(EVAL) or {}
    blocking = read(CORPUS / "blocking_report.json") or {}
    profiles = read(PROFILES) or {}
    cases = read(DATA / "cases.json") or {}
    vocab = read(DATA / "vocabulary.json") or {}
    recon = read(DATA / "reconciliation.json") or {}
    scale = read(DATA / "scale.json") or {}
    hot = read(DATA / "hotspots.json") or {}
    questions = read(ROOT / "eval" / "questions_report.json") or {}
    persons = read(ROOT / "data" / "corpus" / "other_persons_report.json") or {}
    gender = read(ROOT / "data" / "corpus" / "gender_noise_report.json") or {}
    manifest = read(ROOT / "data" / "corpus" / "manifest.json") or {}

    def dig(payload, *keys):
        for key in keys:
            if not isinstance(payload, dict):
                return None
            payload = payload.get(key)
        return payload

    def f4(value):
        return "not measured" if value is None else f"{value:.4f}"

    def pc(value):
        return "not measured" if value is None else f"{value:.2f}%"

    head = canonical.get("headline") or {}
    exact = dig(ev, "baselines", "exact name match", "f1")
    runs = vocab.get("runs") or [{}]
    delta = dig(ev, "linkage", "frequency_adjustment_f1_delta")

    return {
        "precision": f4(head.get("precision")),
        "recall": f4(head.get("recall")),
        "f1": f4(head.get("f1")),
        "fmr": f4(head.get("false_merge_rate")),
        "exactF1": f4(exact),
        "multiple": (f"{head['f1'] / exact:.1f}x"
                     if head.get("f1") and exact else "not measured"),
        "reductionRatio": f4(dig(blocking, "blocking", "reduction_ratio")),
        "completeness": pc(dig(blocking, "ceiling", "pairs_completeness_pct")),
        "freqDelta": ("not measured" if delta is None
                      else f"{'+' if delta >= 0 else ''}{delta:.4f}"),
        "edges": indian(dig(profiles, "graph", "edges")),
        "recoveredEdges": indian(dig(profiles, "graph", "edges_recovered_by_resolution")),
        "modularity": f4(dig(profiles, "communities", "modularity")),
        "hit1": f4(dig(cases, "accuracy", "combined", "hit_at_1")),
        "hit10": f4(dig(cases, "accuracy", "combined", "hit_at_10")),
        "mrr": f4(dig(cases, "accuracy", "combined", "mean_reciprocal_rank")),
        "vocabPrecisionLow": f4(runs[0].get("precision")),
        "vocabPrecisionHigh": f4(runs[-1].get("precision")),
        "vocabRrLow": f4(runs[0].get("reduction_ratio")),
        "vocabRrHigh": f4(runs[-1].get("reduction_ratio")),
        "naiveUndercount": pc(dig(recon, "totals", "naive_undercount_pct")),
        "correspondences": indian(recon.get("correspondences")),
        "fullScalePairs": indian(dig(scale, "full_scale", "candidate_pairs")),
        "hotspotInflation": pc(dig(hot, "totals", "inflation_pct")),
        "anomalyMultiple": (str(hot["anomaly_multiple"])
                            if "anomaly_multiple" in hot else "not measured"),

        "questionsKannada": indian(dig(questions, "kannada", "questions_with_kannada")),
        "questionsPersonKey": indian(dig(questions, "headline", "requires_person_key")),
        "questionsPersonKeyShare": (
            f"{dig(questions, 'headline', 'share_requiring_person_key') * 100:.1f}%"
            if dig(questions, "headline", "share_requiring_person_key") is not None
            else "not measured"),
        "questionsToday": indian(
            dig(questions, "coverage", "answerable_today", "questions")),
        "questionsLayer": indian(
            dig(questions, "coverage", "needs_language_layer", "questions")),
        "questionsImpossible": indian(
            dig(questions, "coverage", "impossible_on_raw_schema", "questions")),

        "personRows": indian(dig(persons, "combined", "person_bearing_rows")),
        "personPeople": indian(dig(persons, "combined", "actual_people")),
        "personRelationships": indian(
            dig(persons, "combined", "invisible_relationships")),
        "victimOracle": f4(dig(persons, "tables", "victim",
                               "oracle_diagnostic", "clustered", "f1")),
        "complainantF1": f4(dig(persons, "tables", "complainant", "results", "f1")),
        "complainantPrecision": f4(
            dig(persons, "tables", "complainant", "results", "precision")),
        "complainantCeiling": f4(dig(persons, "tables", "complainant",
                                     "oracle_diagnostic", "clustered", "f1")),
        "deployablePrecision": f4(
            dig(canonical, "products", "deployable", "precision")),
        "deployableRecall": f4(dig(canonical, "products", "deployable", "recall")),
        "ceilingF1": f4(dig(canonical, "ceiling_argument", "oracle_f1")),
        "genderGain": (
            f"{dig(gender, 'summary', 'shipped_rate_gain_f_beta_0_5'):+.4f}"
            if dig(gender, "summary", "shipped_rate_gain_f_beta_0_5") is not None
            else "not measured"),
        "genderRate": (
            f"{dig(manifest, 'gender_noise', 'rate_realised') * 100:.1f}%"
            if dig(manifest, "gender_noise", "rate_realised") is not None
            else "not measured"),
        "ceilingShare": (
            f"{dig(canonical, 'ceiling_argument', 'share_of_ceiling') * 100:.0f}%"
            if dig(canonical, "ceiling_argument", "share_of_ceiling") is not None
            else "not measured"),
        "complainantOracle": f4(dig(persons, "tables", "complainant",
                                    "oracle_diagnostic", "clustered", "f1")),
    }


def fill(detail: str, substitutions: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}",
                  lambda m: substitutions.get(m.group(1), m.group(0)), detail)


def deck_section() -> list[str]:
    """The deck against the repo, with measured values read rather than typed."""
    if not EVAL.exists():
        return []
    ev = json.loads(EVAL.read_text(encoding="utf-8"))
    identities = "not exported"
    if PROFILES.exists():
        identities = f"{json.loads(PROFILES.read_text(encoding='utf-8'))['total_identities']:,}"

    rows = [
        ("Precision", "0.94", f"{ev['headline']['precision']:.4f}"),
        ("Recall", "0.87", f"{ev['headline']['recall']:.4f}"),
        ("F1", "0.90", f"{ev['headline']['f1']:.4f}"),
        ("False merge rate", "0.012", f"{ev['routing']['false_merge_rate']:.4f}"),
        ("Corpus size", "4,86,220 records",
         f"{ev['corpus']['accused_rows']:,} accused rows on the development corpus"),
        ("Resolved identities", "3,11,904", identities),
        ("Investigator questions", "150, 74% correct", ev["questions"]["status"]),
    ]
    lines = [
        "## What the submitted deck claims, and what this repository measures",
        "",
        "| Figure | Deck claims | This repository measures |",
        "|---|---|---|",
    ]
    lines += [f"| {a} | `{b}` | `{c}` |" for a, b, c in rows]
    lines += [
        "",
        "The deck figures were written at submission time, before Layers 3 to 8",
        "existed, and were illustrative. Every figure in this repository is produced",
        "by `make eval` and none is typed by hand. Where the two differ, this",
        "repository is correct.",
        "",
    ]
    return lines

def claim_bodies(block: str):
    """Each top level { ... } object in the CLAIMS array.

    Brace matching rather than a regex, because a detail string carries
    substitution tokens like {precision} and a non greedy `\\{[^{}]*?\\}`
    matches the token instead of the object that contains it. That silently
    dropped every claim carrying a figure, which is to say every claim anyone
    would check, and the markdown mirror looked complete while missing them.

    Braces inside a quoted string are skipped, so a token can never be mistaken
    for the start of an object.
    """
    depth = 0
    start = 0
    quote = ""
    i = 0
    while i < len(block):
        ch = block[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                yield block[start:i]
        i += 1


FIELD = r"{name}:\s*\n?\s*'((?:[^'\\]|\\.)*)'"


def field(body: str, name: str) -> str | None:
    match = re.search(FIELD.format(name=name), body, re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1).replace("\\'", "'")).strip()


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found")

    text = SOURCE.read_text(encoding="utf-8")
    block = text.split("export const CLAIMS: Claim[] = [", 1)[1].split("\n]\n", 1)[0]
    substitutions = tokens()

    claims = []
    for body in claim_bodies(block):
        area = field(body, "area")
        claim = field(body, "claim")
        state = field(body, "state")
        detail = field(body, "detail") or ""
        if area and claim and state:
            claims.append((area, claim, state, fill(detail, substitutions)))

    if not claims:
        raise SystemExit("no claims parsed, the Status.tsx shape has changed")

    counts: dict[str, int] = {}
    for _, _, state, _ in claims:
        counts[state] = counts.get(state, 0) + 1

    lines = [
        "<!-- Generated by scripts/build_status_md.py from",
        "     web/src/screens/Status.tsx. Do not edit by hand. -->",
        "",
        "# Build status",
        "",
        "Every claim on the submission deck against its true state in this",
        "repository. Three values only. Nothing here is softened.",
        "",
        f"**{counts.get('BUILT', 0)} built, {counts.get('PARTIAL', 0)} partial, "
        f"{counts.get('NOT BUILT', 0)} not built.**",
        "",
        *deck_section(),
        "## Claim by claim",
        "",
        "| Area | Claim | State | What is actually there |",
        "|---|---|---|---|",
    ]
    for area, claim, state, detail in claims:
        lines.append(f"| {area} | {claim} | **{state}** | {detail} |")

    lines += [
        "",
        "## On the libraries we did not use",
        "",
        "The linkage model, the Indic phonetic folding and the string metrics are",
        "implemented directly rather than imported from Splink, jellyfish or",
        "RapidFuzz. That was deliberate and it buys one specific thing. Every",
        "weight in a merge score traces to a fitted m and u, can be shown to an",
        "investigator as a list of contributions that sums to the total, and can",
        "be argued with. A library that returns a score cannot do that, and a merge",
        "an officer cannot interrogate is a merge they should not act on. The same",
        "reasoning rules out an embedding model for modus operandi similarity,",
        "where TF-IDF over word and character n grams is inspectable and a sentence",
        "transformer is not.",
        "",
        "## On the deployed surface being static",
        "",
        "Resolution is a nightly batch job by design, recorded as ADR 002.",
        "Expectation maximisation over every comparison vector, iteration to a",
        "fixed point and corpus wide frequency tables are global computations that",
        "cannot run inside a request. So the engine runs locally, exports JSON, and",
        "Catalyst serves it. That is why most Catalyst services show as not built.",
        "There is no function, no database and no runtime dependency, because the",
        "architecture does not need one. The honest cost is staleness, and the",
        "provenance bar carries the resolution timestamp on every screen so a",
        "reader always knows how old the answer is.",
        "",
    ]

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(claims)} claims written to {TARGET.relative_to(ROOT)}")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
