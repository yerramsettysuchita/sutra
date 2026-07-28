"""Corpus statistics and the recoverability audit.

Two jobs.

First, describe the corpus, so anyone can see what was generated without
reading four hundred thousand CSV rows.

Second, and this is the one that matters, answer the question Phase 0 has to
answer before any engine work starts. The generator planted identity fragments.
Are they recoverable in principle, or did we build a corpus that no system
could resolve and then congratulate ourselves for failing on it.

The audit reports a hard floor, the share of true matching pairs on which no
channel carries usable evidence. That number is a ceiling on recall for
everything built afterwards. It is printed at full precision and it is not
rounded in our favour.

Run
    python -m data.generator.audit
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from engine.console import configure as _configure_console

# Relationship and alias markers that carry no identifying content.
MARKER_TOKENS = {
    "s/o", "so", "s", "o", "d/o", "w/o", "c/o", "bin", "alias", "@",
    "ತಂದೆ", "ಬಿನ್", "ಅಲಿಯಾಸ್",
}

KANNADA_RANGE = ("ಀ", "೿")

AGE_TOLERANCE = 2


def load(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def name_tokens(s: str) -> set[str]:
    """Crude tokenisation for the surface level name check.

    Deliberately naive. This is not Layer 1 and it is not trying to be. It
    measures what a system with no Indic handling would see, which is the
    baseline the engine has to beat.
    """
    for ch in "@./,-":
        s = s.replace(ch, " ")
    return {t for t in s.lower().split() if t and t not in MARKER_TOKENS and len(t) > 1}


def has_kannada(s: str) -> bool:
    return any(KANNADA_RANGE[0] <= ch <= KANNADA_RANGE[1] for ch in s)


def script_of(s: str) -> str:
    kn = has_kannada(s)
    la = any(ch.isascii() and ch.isalpha() for ch in s)
    if kn and la:
        return "mixed"
    return "kannada" if kn else "latin"


def normalise_surface(s: str) -> str:
    return " ".join(s.lower().split())


def pct(n, d):
    return 0.0 if not d else 100.0 * n / d


def histogram(counter: Counter, total: int, label_width: int = 26, top: int | None = None):
    items = counter.most_common(top) if top else sorted(counter.items())
    lines = []
    for key, value in items:
        bar = "█" * max(1, round(30 * value / max(counter.values())))
        lines.append(f"    {str(key):<{label_width}} {value:>7,}  {pct(value, total):>5.1f}%  {bar}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def run(corpus_dir: Path):
    gt_dir = corpus_dir / "ground_truth"
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))

    cases = load(corpus_dir / "CaseMaster.csv")
    accused = load(corpus_dir / "Accused.csv")
    arrests = load(corpus_dir / "ArrestSurrender.csv")
    chargesheets = load(corpus_dir / "ChargesheetDetails.csv")
    act_sections = load(corpus_dir / "ActSectionAssociation.csv")
    sections = load(corpus_dir / "Section.csv")
    acts = load(corpus_dir / "Act.csv")
    districts = load(corpus_dir / "District.csv")
    subheads = load(corpus_dir / "CrimeSubHead.csv")

    identity = load(gt_dir / "identity_map.csv")
    persons = load(gt_dir / "persons.csv")
    undetected = load(gt_dir / "undetected_truth.csv")
    collisions = load(gt_dir / "name_collisions.csv")
    gangs = load(gt_dir / "gangs.csv")

    case_by_id = {c["CaseMasterID"]: c for c in cases}
    district_name = {d["DistrictID"]: d["DistrictName"] for d in districts}
    subhead_name = {s["CrimeSubHeadID"]: s["CrimeSubHeadName"] for s in subheads}
    act_abbr = {a["ActID"]: a["ActAbbr"] for a in acts}
    section_act = {s["SectionID"]: s["ActID"] for s in sections}

    out = []
    stats = {}

    def emit(line=""):
        out.append(line)

    # ---------------------------------------------------------------- header
    emit("=" * 78)
    emit("SUTRA  synthetic KSP FIR corpus")
    emit(f"seed {manifest['seed']}   window {manifest['corpus_start']} to {manifest['corpus_end']}"
         f"   BNS transition {manifest['bns_transition']}")
    emit("=" * 78)

    # ---------------------------------------------------------------- volume
    emit()
    emit("TABLE VOLUMES")
    emit()
    for key, value in manifest["counts"].items():
        emit(f"    {key:<26} {value:>9,}")
    stats["counts"] = manifest["counts"]

    # ------------------------------------------------------------ case shape
    per_case = Counter()
    for a in accused:
        per_case[a["CaseMasterID"]] += 1
    accused_dist = Counter(per_case.values())
    detected = len(per_case)
    emit()
    emit("ACCUSED PER DETECTED CASE")
    emit()
    emit(histogram(accused_dist, detected, label_width=6))
    emit(f"    mean {sum(k * v for k, v in accused_dist.items()) / detected:.3f}")
    stats["accused_per_case"] = dict(accused_dist)

    cstype_dist = Counter(c["cstype"] for c in chargesheets)
    no_report = len(cases) - len(chargesheets)
    emit()
    emit("FINAL REPORT CLASSIFICATION")
    emit()
    emit(histogram(cstype_dist, len(cases), label_width=6))
    emit(f"    {'pending':<6} {no_report:>7,}  {pct(no_report, len(cases)):>5.1f}%")
    stats["cstype"] = dict(cstype_dist)

    # ------------------------------------------------------- identity supply
    appearances = Counter(r["TruePersonID"] for r in identity)
    appear_dist = Counter(appearances.values())
    repeat = sum(v for k, v in appear_dist.items() if k >= 2)
    emit()
    emit("APPEARANCES PER TRUE PERSON")
    emit()
    emit(histogram(appear_dist, len(appearances), label_width=6))
    emit(f"    persons appearing at all      {len(appearances):>7,}")
    emit(f"    repeat offenders, 2 or more   {repeat:>7,}  {pct(repeat, len(appearances)):>5.1f}%")
    emit(f"    largest single identity       {max(appearances.values()):>7,} appearances")
    stats["appearances_per_person"] = dict(appear_dist)

    # --------------------------------------------------------- name renderi
    script_dist = Counter(script_of(a["AccusedName"]) for a in accused)
    variant_dist = Counter(r["Variant"] for r in identity)
    perturbed = sum(1 for r in identity if r["Perturbations"])
    noised = sum(1 for r in identity if r["Noise"])
    emit()
    emit("ACCUSED NAME, SCRIPT AS WRITTEN")
    emit()
    emit(histogram(script_dist, len(accused), label_width=10))
    emit()
    emit("ACCUSED NAME, RENDERING VARIANT")
    emit()
    emit(histogram(variant_dist, len(identity), label_width=24))
    emit()
    emit(f"    transliteration perturbation applied  {perturbed:>7,}  {pct(perturbed, len(identity)):>5.1f}%")
    emit(f"    whitespace or punctuation noise       {noised:>7,}  {pct(noised, len(identity)):>5.1f}%")
    stats["script"] = dict(script_dist)
    stats["variants"] = dict(variant_dist)

    # ------------------------------------------------------- name frequency
    canonical = Counter(r["CanonicalName"] for r in identity)
    top10 = canonical.most_common(10)
    top10_share = sum(v for _, v in top10)
    emit()
    emit("NAME FREQUENCY SKEW")
    emit("    the reason Layer 4 weights agreement by inverse name frequency")
    emit()
    for name, count in top10:
        emit(f"    {name:<30} {count:>6,}  {pct(count, len(identity)):>5.2f}%")
    emit(f"    top 10 canonical names cover {pct(top10_share, len(identity)):.1f}% of all accused rows")
    emit(f"    distinct canonical names     {len(canonical):,}")
    stats["name_frequency_top10"] = {k: v for k, v in top10}

    # ------------------------------------------------------------- geography
    district_dist = Counter(district_name[c["DistrictID"]] for c in cases)
    emit()
    emit("CASES BY DISTRICT, TOP 12")
    emit()
    emit(histogram(district_dist, len(cases), label_width=20, top=12))

    subhead_dist = Counter(subhead_name[c["CrimeSubHeadID"]] for c in cases)
    emit()
    emit("CASES BY CRIME SUB HEAD")
    emit()
    emit(histogram(subhead_dist, len(cases), label_width=26))
    stats["subheads"] = dict(subhead_dist)

    # ------------------------------------------------------ IPC to BNS split
    act_usage = Counter(act_abbr[section_act[a["SectionID"]]] for a in act_sections)
    pre = sum(1 for c in cases if c["CrimeRegisteredDate"] < manifest["bns_transition"])
    post = len(cases) - pre
    emit()
    emit("IPC TO BNS TRANSITION")
    emit()
    emit(f"    cases before {manifest['bns_transition']}   {pre:>7,}  {pct(pre, len(cases)):>5.1f}%")
    emit(f"    cases on or after           {post:>7,}  {pct(post, len(cases)):>5.1f}%")
    emit()
    emit(histogram(act_usage, len(act_sections), label_width=8))
    emit("    a trend query crossing the transition without Layer 9 reconciliation")
    emit("    will show a cliff that is an artefact of legislation, not of crime")
    stats["act_usage"] = dict(act_usage)

    # ------------------------------------------------------------- age noise
    noise_dist = Counter(r["AgeNoise"] for r in identity if r["AgeNoise"] != "")
    missing_age = sum(1 for r in identity if r["AgeRecorded"] == "")
    beyond = sum(v for k, v in noise_dist.items() if abs(int(k)) > AGE_TOLERANCE)
    emit()
    emit("RECORDED AGE AGAINST TRUE BIRTH YEAR")
    emit()
    for k in sorted(noise_dist, key=lambda x: int(x)):
        emit(f"    {int(k):>+3d} years  {noise_dist[k]:>7,}  {pct(noise_dist[k], len(identity)):>5.1f}%")
    emit(f"    age not recorded  {missing_age:>7,}  {pct(missing_age, len(identity)):>5.1f}%")
    emit(f"    beyond the plus or minus {AGE_TOLERANCE} tolerance of Layer 3c"
         f"  {beyond:,}  {pct(beyond, len(identity)):.1f}%")
    stats["age_noise"] = {k: v for k, v in noise_dist.items()}

    # ======================================================================
    # RECOVERABILITY
    # ======================================================================

    by_person = defaultdict(list)
    for r in identity:
        by_person[r["TruePersonID"]].append(r)

    co_accused = defaultdict(set)
    for r in identity:
        co_accused[r["CaseMasterID"]].add(r["TruePersonID"])

    surface = {r["AccusedMasterID"]: normalise_surface(r["RenderedName"]) for r in identity}
    tokens = {r["AccusedMasterID"]: name_tokens(r["RenderedName"]) for r in identity}

    # Variants that reduce the given name to a single letter, or replace the
    # name with a moniker, leave very little of the string behind.
    DEGRADING = {"LA_INITIAL_BOTH", "LA_INITIAL_PREFIX"}
    MONIKER_ONLY = {"LA_MONIKER", "KN_MONIKER"}

    channels = Counter()
    tiers = Counter()
    structural_hist = Counter()
    cross_script_pairs = 0
    total_pairs = 0
    unrecoverable_examples = []

    for pid, rows in by_person.items():
        if len(rows) < 2:
            continue
        for a, b in combinations(rows, 2):
            if a["CaseMasterID"] == b["CaseMasterID"]:
                continue  # cannot happen, cannot link holds by construction
            total_pairs += 1

            ta, tb = tokens[a["AccusedMasterID"]], tokens[b["AccusedMasterID"]]
            sa, sb = script_of(a["RenderedName"]), script_of(b["RenderedName"])

            exact = surface[a["AccusedMasterID"]] == surface[b["AccusedMasterID"]]
            overlap = bool(ta & tb)
            cross_script = {sa, sb} == {"latin", "kannada"} or "mixed" in (sa, sb) and sa != sb
            if cross_script:
                cross_script_pairs += 1

            degraded = (a["Variant"] in DEGRADING and b["Variant"] in DEGRADING) or \
                       (a["Variant"] in MONIKER_ONLY and b["Variant"] in MONIKER_ONLY and
                        not overlap)

            # A name channel is reachable when the canonical given name survives
            # in both renderings in some recoverable form.
            #
            # Stated as an assumption rather than a measurement, because it is
            # one. Every rendering of a person derives from the same canonical
            # given and father name, so the only way the name channel is truly
            # destroyed is if the string was reduced to initials on both sides,
            # or replaced by a moniker on both sides with nothing shared.
            # Everything else is reachable given correct cross script folding
            # and phonetic keying.
            #
            # That folding is exactly what Layer 1 has to deliver and what Layer
            # 2 pairs completeness will actually measure. This audit does not
            # prove the engine reaches these pairs. It proves the information
            # is present for it to reach. Those are different claims and the
            # second is the weaker one.
            name_reachable = exact or overlap or not degraded

            ca, cb = case_by_id[a["CaseMasterID"]], case_by_id[b["CaseMasterID"]]
            same_district = a["DistrictID"] == b["DistrictID"]
            same_station = a["UnitID"] == b["UnitID"]
            same_subhead = ca["CrimeSubHeadID"] == cb["CrimeSubHeadID"]
            shared_officer = bool(a["ArrestingOfficerID"]) and \
                a["ArrestingOfficerID"] == b["ArrestingOfficerID"]
            shared_co = bool(
                (co_accused[a["CaseMasterID"]] - {pid}) &
                (co_accused[b["CaseMasterID"]] - {pid}))

            age_ok = False
            if a["AgeRecorded"] != "" and b["AgeRecorded"] != "":
                ia = int(a["CrimeRegisteredDate"][:4]) - int(a["AgeRecorded"])
                ib = int(b["CrimeRegisteredDate"][:4]) - int(b["AgeRecorded"])
                age_ok = abs(ia - ib) <= AGE_TOLERANCE

            channels["exact name string"] += exact
            channels["raw token overlap"] += overlap
            channels["cross script pair"] += cross_script
            channels["same district"] += same_district
            channels["same police station"] += same_station
            channels["same crime sub head"] += same_subhead
            channels["shared arresting officer"] += shared_officer
            channels["shared co accused"] += shared_co
            channels["implied birth year agrees"] += age_ok

            structural = sum([same_district, same_station, same_subhead,
                              shared_officer, shared_co, age_ok])
            structural_hist[structural] += 1

            if exact:
                tiers["1. exact string, a naive matcher finds it"] += 1
            elif overlap:
                tiers["2. token overlap, lexical matching finds it"] += 1
            elif name_reachable:
                tiers["3. name reachable after normalisation, needs Layers 1 and 2"] += 1
            elif structural >= 2:
                tiers["4. name degraded, two or more structural signals survive"] += 1
            else:
                tiers["5. no channel survives, unrecoverable by construction"] += 1
                if len(unrecoverable_examples) < 8:
                    unrecoverable_examples.append(
                        (a["RenderedName"], b["RenderedName"], a["Variant"], b["Variant"],
                         structural))

    emit()
    emit("=" * 78)
    emit("RECOVERABILITY OF PLANTED IDENTITY")
    emit("=" * 78)
    emit()
    emit(f"    true matching pairs in the corpus   {total_pairs:>8,}")
    emit(f"    pairs written in different scripts  {cross_script_pairs:>8,}"
         f"  {pct(cross_script_pairs, total_pairs):>5.1f}%")
    emit()
    emit("SIGNAL SURVIVAL ACROSS TRUE MATCHING PAIRS")
    emit("    each line is the share of true pairs on which that channel agrees")
    emit()
    for label, count in channels.most_common():
        bar = "█" * max(1, round(34 * count / total_pairs))
        emit(f"    {label:<28} {count:>8,}  {pct(count, total_pairs):>5.1f}%  {bar}")

    emit()
    emit("STRUCTURAL SIGNALS PER PAIR")
    emit("    of district, station, sub head, officer, co accused, birth year")
    emit()
    emit(histogram(structural_hist, total_pairs, label_width=6))

    emit()
    emit("RECOVERABILITY TIER")
    emit()
    for label in sorted(tiers):
        count = tiers[label]
        bar = "█" * max(1, round(34 * count / total_pairs))
        emit(f"    {label:<62}")
        emit(f"        {count:>8,}  {pct(count, total_pairs):>5.2f}%  {bar}")

    floor = tiers.get("5. no channel survives, unrecoverable by construction", 0)
    naive_ceiling = tiers.get("1. exact string, a naive matcher finds it", 0)

    emit()
    emit("-" * 78)
    emit(f"    RECALL CEILING                {pct(total_pairs - floor, total_pairs):>6.2f}%"
         f"   ({total_pairs - floor:,} of {total_pairs:,} pairs)")
    emit(f"    UNRECOVERABLE BY CONSTRUCTION {pct(floor, total_pairs):>6.2f}%"
         f"   ({floor:,} pairs)")
    emit(f"    EXACT NAME MATCH REACHES      {pct(naive_ceiling, total_pairs):>6.2f}%"
         f"   ({naive_ceiling:,} pairs)")
    emit("-" * 78)
    emit()
    emit("    Read the third line against the first. The gap between them is the")
    emit("    work Layers 1 to 7 have to do, and it is the entire argument of the")
    emit("    project stated as a single number.")
    emit()
    emit("    The ceiling is high because the generator never gives one person two")
    emit("    unrelated names. That is a property of the instrument, not a result.")
    emit("    Tier 3 assumes Layer 1 folds scripts correctly and Layer 2 blocks")
    emit("    without losing the pair. Neither is measured here. Layer 2 pairs")
    emit("    completeness is the number that will turn this ceiling into a real")
    emit("    one, and it will be lower.")

    if unrecoverable_examples:
        emit()
        emit("    Sample of pairs with no surviving channel")
        emit()
        for x, y, va, vb, st in unrecoverable_examples:
            emit(f"      {x!r:<34} {va:<20}")
            emit(f"      {y!r:<34} {vb:<20}  structural signals {st}")
            emit()

    stats["recoverability"] = {
        "true_pairs": total_pairs,
        "cross_script_pairs": cross_script_pairs,
        "channels": dict(channels),
        "tiers": dict(tiers),
        "recall_ceiling_pct": round(pct(total_pairs - floor, total_pairs), 4),
        "unrecoverable_pct": round(pct(floor, total_pairs), 4),
        "exact_match_pct": round(pct(naive_ceiling, total_pairs), 4),
    }

    # ======================================================================
    # HARD NEGATIVES
    # ======================================================================

    by_surface = defaultdict(set)
    for r in identity:
        by_surface[normalise_surface(r["RenderedName"])].add(r["TruePersonID"])
    ambiguous = {k: v for k, v in by_surface.items() if len(v) > 1}
    trap_pairs = sum(len(v) * (len(v) - 1) // 2 for v in ambiguous.values())

    emit()
    emit("=" * 78)
    emit("HARD NEGATIVES, THE FALSE MERGE SURFACE")
    emit("=" * 78)
    emit()
    emit(f"    planted name collision groups            {len(collisions):>8,}")
    tight = sum(1 for c in collisions if c["TightAge"] == "Y")
    emit(f"    of which birth years also within a year  {tight:>8,}")
    emit(f"    distinct name strings shared by 2 or more people {len(ambiguous):>8,}")
    emit(f"    cross person pairs sharing an exact name string  {trap_pairs:>8,}")
    emit()
    emit("    Every one of these is a merge a name based system will make and")
    emit("    report as a success. They are the denominator of the false merge")
    emit("    rate, and that rate is the number this project lives or dies on.")

    stats["hard_negatives"] = {
        "collision_groups": len(collisions),
        "tight_age_groups": tight,
        "ambiguous_name_strings": len(ambiguous),
        "cross_person_exact_name_pairs": trap_pairs,
    }

    # ---------------------------------------------------------- relational
    emit()
    emit("RELATIONAL AND UNDETECTED STRUCTURE")
    emit()
    dr = manifest.get("dyad_recurrence", {})
    emit(f"    co offending preset           {manifest.get('co_offending_preset', 'n/a'):>7}")
    if dr:
        emit(f"    co offending dyads            {dr['dyads']:>7,}")
        emit(f"    dyads appearing together more than once {dr['recurring']:>7,}"
             f"   {dr['rate_pct']:.2f}%")
        emit("    literature anchor, Sarnecki Stockholm, about 2.5% of co offending")
        emit("    relationships persist beyond six months. Charette and Papachristos")
        emit("    find co offenders rarely offend together more than once. See ADR 012.")
        emit()
    gang_sizes = Counter(int(g["MemberCount"]) for g in gangs)
    emit(f"    co offending groups planted   {len(gangs):>7,}")
    for size in sorted(gang_sizes):
        emit(f"      size {size}                     {gang_sizes[size]:>7,}")
    multi = sum(1 for c in co_accused.values() if len(c) > 1)
    emit(f"    cases with 2 or more accused  {multi:>7,}   these are the cannot link edges")
    emit(f"    undetected cases, cstype C    {len(undetected):>7,}")
    if undetected:
        culprit_app = Counter(int(u["CulpritAppearances"]) for u in undetected)
        emit(f"    culprit appears elsewhere in the corpus, appearances "
             f"{min(culprit_app):d} to {max(culprit_app):d}")
    stats["relational"] = {
        "gangs": len(gangs),
        "cannot_link_cases": multi,
        "undetected_cases": len(undetected),
    }

    emit()
    emit("=" * 78)
    emit("VERDICT")
    emit("=" * 78)
    emit()
    ceiling = pct(total_pairs - floor, total_pairs)
    emit(f"    The planted fragments are recoverable in principle for "
         f"{ceiling:.2f}% of true pairs.")
    emit(f"    A system joining on AccusedName reaches at most "
         f"{pct(naive_ceiling, total_pairs):.2f}% of them,")
    emit(f"    while exposing {trap_pairs:,} cross person pairs that share a name string")
    emit("    and would be merged wrongly.")
    emit()
    emit("    Phase 0 is complete. The corpus is measurable and the target is set.")
    emit()

    text = "\n".join(out)
    print(text)
    (corpus_dir / "corpus_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    (corpus_dir / "corpus_stats.txt").write_text(text + "\n", encoding="utf-8")
    return stats


def main():
    _configure_console()
    parser = argparse.ArgumentParser(description="Corpus statistics and recoverability audit.")
    parser.add_argument("--corpus", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data" / "corpus")
    args = parser.parse_args()
    run(args.corpus)


if __name__ == "__main__":
    main()
