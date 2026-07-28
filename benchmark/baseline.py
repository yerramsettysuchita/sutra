"""IERB-P reference baseline. Run it, then beat it.

    python baseline.py --corpus corpus --out baseline_output.csv

Deliberately simple and deliberately not very good. Pure standard library, no
dependencies, about a hundred lines of actual logic. It exists so a newcomer
has something running in two minutes and a number to improve on.

What it does.

  1. Strip relationship markers, S/o, ತಂದೆ, bin, alias, and punctuation
  2. Transliterate Kannada to Latin with a small syllable table
  3. Fold the result crudely, collapse doubled letters and long vowels
  4. Group rows whose folded key matches exactly
  5. Split any group that would place two rows from one FIR together, because
     the schema proves those are different people

Step 5 is the only thing here that is not naive, and it is free. Two Accused
rows sharing a CaseMasterID are A1 and A2 of the same FIR.

What it does not do, and where the headroom is.

  no phonetic blocking beyond exact key equality
  no fuzzy string comparison at all
  nothing with age, location, narrative or co accused
  no probabilistic model, no calibration, no notion of name rarity

A method that adds any one of those should beat this comfortably.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

# Kannada consonants without the inherent vowel.
CONSONANTS = {
    "ಕ": "k", "ಖ": "kh", "ಗ": "g", "ಘ": "gh", "ಙ": "ng",
    "ಚ": "c", "ಛ": "ch", "ಜ": "j", "ಝ": "jh", "ಞ": "ny",
    "ಟ": "t", "ಠ": "th", "ಡ": "d", "ಢ": "dh", "ಣ": "n",
    "ತ": "t", "ಥ": "th", "ದ": "d", "ಧ": "dh", "ನ": "n",
    "ಪ": "p", "ಫ": "ph", "ಬ": "b", "ಭ": "bh", "ಮ": "m",
    "ಯ": "y", "ರ": "r", "ಱ": "r", "ಲ": "l", "ಳ": "l",
    "ವ": "v", "ಶ": "sh", "ಷ": "sh", "ಸ": "s", "ಹ": "h", "ೞ": "zh",
}
VOWELS = {
    "ಅ": "a", "ಆ": "aa", "ಇ": "i", "ಈ": "ii", "ಉ": "u", "ಊ": "uu",
    "ಋ": "ri", "ಎ": "e", "ಏ": "ee", "ಐ": "ai", "ಒ": "o", "ಓ": "oo", "ಔ": "au",
}
MATRAS = {
    "ಾ": "aa", "ಿ": "i", "ೀ": "ii", "ು": "u", "ೂ": "uu", "ೃ": "ri",
    "ೆ": "e", "ೇ": "ee", "ೈ": "ai", "ೊ": "o", "ೋ": "oo", "ೌ": "au",
}
VIRAMA, ANUSVARA, VISARGA = "್", "ಂ", "ಃ"

MARKERS = {
    "so", "do", "wo", "co", "bin", "alias", "aliyas", "aliyaas",
    "tande", "tandi", "sri", "shri", "smt", "kum",
}

DIGRAPHS = [
    ("ksh", "ks"), ("x", "ks"), ("chh", "c"), ("ch", "c"), ("sh", "s"),
    ("kh", "k"), ("gh", "g"), ("jh", "j"), ("th", "t"), ("dh", "d"),
    ("bh", "b"), ("ph", "f"), ("f", "p"), ("ow", "au"), ("aw", "au"),
    ("w", "v"), ("z", "j"), ("q", "k"),
]


def transliterate(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in CONSONANTS:
            out.append(CONSONANTS[ch])
            nxt = text[i + 1] if i + 1 < n else ""
            if nxt == VIRAMA:
                i += 2
            elif nxt in MATRAS:
                out.append(MATRAS[nxt])
                i += 2
            else:
                out.append("a")
                i += 1
            continue
        if ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch == ANUSVARA:
            out.append("n")
        elif ch == VISARGA:
            out.append("h")
        elif ch not in MATRAS and ch != VIRAMA:
            out.append(ch)
        i += 1
    return "".join(out)


def fold_token(token: str) -> str:
    t = re.sub(r"[^a-z]", "", token.lower())
    if not t:
        return ""
    for src, dst in DIGRAPHS:
        t = t.replace(src, dst)
    t = re.sub(r"[aeiou]+", lambda m: "u" if set("uo") & set(m.group(0))
               else ("i" if set("ie") & set(m.group(0)) else "a"), t)
    t = re.sub(r"(.)\1+", r"\1", t)
    return t.rstrip("aiu")


def key_for(name: str) -> str:
    text = transliterate(name).lower()
    text = re.sub(r"\b([sdwc])\s*[/\\]\s*o\.?", " ", text)
    parts = [p for p in re.split(r"[^a-z]+", text) if p and p not in MARKERS]
    folded = sorted({fold_token(p) for p in parts if len(fold_token(p)) >= 2})
    return " ".join(folded)


def main() -> int:
    parser = argparse.ArgumentParser(description="IERB-P reference baseline.")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with (args.corpus / "Accused.csv").open(encoding="utf-8", newline="") as fh:
        accused = list(csv.DictReader(fh))

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in accused:
        key = key_for(row["AccusedName"]) or f"__singleton_{row['AccusedMasterID']}"
        groups[key].append(row)

    assignment: dict[str, str] = {}
    cluster_id = 0
    for members in groups.values():
        # Cannot link. Two rows on one FIR are provably different people, so a
        # group holding several rows from one case is split until no case
        # appears twice in any part.
        parts: list[list[dict]] = []
        for row in members:
            placed = False
            for part in parts:
                if all(other["CaseMasterID"] != row["CaseMasterID"] for other in part):
                    part.append(row)
                    placed = True
                    break
            if not placed:
                parts.append([row])
        for part in parts:
            cluster_id += 1
            for row in part:
                assignment[row["AccusedMasterID"]] = f"B{cluster_id:06d}"

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["AccusedMasterID", "PredictedPersonID"])
        for row in accused:
            writer.writerow([row["AccusedMasterID"], assignment[row["AccusedMasterID"]]])

    print(f"baseline wrote {args.out}")
    print(f"  {len(accused):,} rows into {cluster_id:,} clusters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
