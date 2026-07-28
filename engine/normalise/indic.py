"""Layer 1. Indic normalisation.

Folds a Kannada or Latin `AccusedName` into a common comparable form, so that
`ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ`, `Ramesh S/o Krishnappa`, `R. Krishnappa` and
`Kadu Rameshu` can be reasoned about as strings describing one person.

English Soundex is not used here and is not used anywhere in this engine. See
docs/decisions.md ADR 003. Soundex deletes vowels outright, and Kannada vowel
length and quality carry meaning, so a scheme that throws them away collapses
names that are genuinely different. This module keeps vowel structure in a
reduced three class form and instead normalises the distinctions that Latin
transliteration is physically incapable of representing.

That last point is the one worth being precise about, because it is a
deliberate loss rather than an oversight.

Kannada distinguishes retroflex from dental, ಟ from ತ and ಡ from ದ and ಣ from ನ
and ಳ from ಲ. Latin transliteration in police records writes both as t, d, n
and l. So the distinction exists on one side of a cross script comparison and
cannot exist on the other. Preserving it would guarantee that every cross script
pair mismatches. We therefore fold retroflex onto dental at transliteration
time, and we lose real phonemic information to gain cross script comparability.
That trade is forced by the data, not chosen.

The same argument applies to aspiration. ಥ against ತ is a real contrast that
transliteration renders as th against t inconsistently, so both fold to t.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

__all__ = [
    "transliterate",
    "fold_token",
    "normalise",
    "NormalisedName",
    "is_kannada",
    "MARKER_TOKENS",
]

# ---------------------------------------------------------------------------
# Kannada block, U+0C80 to U+0CFF
# ---------------------------------------------------------------------------

VIRAMA = "್"
ANUSVARA = "ಂ"
VISARGA = "ಃ"
AVAGRAHA = "ಽ"
NUKTA = "಼"
ZERO_WIDTH = {"​", "‌", "‍", "﻿"}

# Consonant to Latin base, with no inherent vowel. The inherent 'a' is added by
# the transliterator when no vowel sign and no virama follows.
#
# Retroflex maps onto the dental letter deliberately. See the module docstring.
CONSONANTS = {
    "ಕ": "k",   "ಖ": "kh",  "ಗ": "g",   "ಘ": "gh",  "ಙ": "ng",
    "ಚ": "c",   "ಛ": "ch",  "ಜ": "j",   "ಝ": "jh",  "ಞ": "ny",
    "ಟ": "t",   "ಠ": "th",  "ಡ": "d",   "ಢ": "dh",  "ಣ": "n",
    "ತ": "t",   "ಥ": "th",  "ದ": "d",   "ಧ": "dh",  "ನ": "n",
    "ಪ": "p",   "ಫ": "ph",  "ಬ": "b",   "ಭ": "bh",  "ಮ": "m",
    "ಯ": "y",   "ರ": "r",   "ಱ": "r",   "ಲ": "l",   "ಳ": "l",
    "ವ": "v",   "ಶ": "sh",  "ಷ": "sh",  "ಸ": "s",   "ಹ": "h",
    "ೞ": "zh",
}

# Independent vowels.
VOWELS = {
    "ಅ": "a",   "ಆ": "aa",  "ಇ": "i",   "ಈ": "ii",
    "ಉ": "u",   "ಊ": "uu",  "ಋ": "ri",  "ೠ": "ri",
    "ಌ": "lu",  "ೡ": "lu",
    "ಎ": "e",   "ಏ": "ee",  "ಐ": "ai",
    "ಒ": "o",   "ಓ": "oo",  "ಔ": "au",
}

# Dependent vowel signs. The vocalic r sign is rendered 'ri' rather than 'ru',
# because that is how it reaches Latin in practice, Krishna and not Krushna.
MATRAS = {
    "ಾ": "aa",  "ಿ": "i",   "ೀ": "ii",  "ು": "u",
    "ೂ": "uu",  "ೃ": "ri",  "ೄ": "ri",  "ೆ": "e",
    "ೇ": "ee",  "ೈ": "ai",  "ೊ": "o",   "ೋ": "oo",
    "ೌ": "au",
}

KANNADA_START, KANNADA_END = "ಀ", "೿"


def is_kannada(text: str) -> bool:
    return any(KANNADA_START <= ch <= KANNADA_END for ch in text)


def transliterate(text: str) -> str:
    """Kannada to Latin. Latin input passes through unchanged.

    Standard abugida walk. A consonant carries an inherent 'a' unless it is
    followed by a virama, which suppresses it, or by a dependent vowel sign,
    which replaces it.
    """
    text = unicodedata.normalize("NFC", text)
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ZERO_WIDTH or ch == NUKTA or ch == AVAGRAHA:
            i += 1
            continue
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
        elif ch in MATRAS or ch == VIRAMA:
            pass  # orphaned sign, nothing to attach to
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Relationship, alias and honorific tokens
# ---------------------------------------------------------------------------
# Compared after transliteration and lowercasing, before folding, so the
# Kannada and Latin forms of the same marker are both caught. ತಂದೆ becomes
# tande, ಬಿನ್ becomes bin, ಅಲಿಯಾಸ್ becomes aliyaas.

MARKER_TOKENS = frozenset({
    "so", "do", "wo", "co",
    "son", "daughter", "wife", "care",
    "bin", "binte", "alias", "aliyas", "aliyaas",
    "tande", "tandi", "tande", "tayi",
    "sri", "shri", "srii", "shrii", "smt", "smti", "srimati", "shrimati",
    "kum", "kumari", "mr", "mrs", "ms",
})

_RELATION_RE = re.compile(r"\b([sdwc])\s*[/\\]\s*o\.?", re.IGNORECASE)
_SPLIT_RE = re.compile(r"[^a-z]+")


# ---------------------------------------------------------------------------
# Folding
# ---------------------------------------------------------------------------
# Order matters throughout. Longer digraphs are consumed before the single
# characters they contain.

_DIGRAPHS = [
    ("ksh", "ks"),
    ("x", "ks"),
    ("chh", "c"),
    ("ch", "c"),
    ("sh", "s"),
    ("kh", "k"),
    ("gh", "g"),
    ("jh", "j"),
    ("th", "t"),
    ("dh", "d"),
    ("bh", "b"),
    ("ph", "f"),
    ("f", "p"),
    ("ow", "au"),
    ("aw", "au"),
    ("w", "v"),
    ("z", "j"),
    ("q", "k"),
]

_VOWEL_RUN = re.compile(r"[aeiou]+")
_DOUBLED = re.compile(r"(.)\1+")

# A word final y after a consonant is a vowel, not a consonant. Puttaswamy
# against ಪುಟ್ಟಸ್ವಾಮಿ, Krishnamurthy against ಕೃಷ್ಣಮೂರ್ತಿ. Latin spelling writes
# it y, Kannada writes the matra ಿ, and the transliterator produces i.
#
# After a vowel it is a real consonant and must stay. Vijay is ವಿಜಯ, so the y
# carries the ಯ and rewriting it to i would fold Vijay onto Viji.
_FINAL_Y = re.compile(r"(?<=[^aeiou])y$")

# A y directly after a vowel is a glide that transliteration writes or drops at
# will. Muniyappa against Muniappa, and ವಿಜಯ reaching Latin as Vijaya or Vijay.
# Dropping it removes the choice.
#
# This does fold Vijay onto Viji, which is an over merge we accept. The
# alternative is that ವಿಜಯ and Vijay never match, and a cross script miss on a
# real name costs more than a collision with a name that is not in the record.
_GLIDE_Y = re.compile(r"(?<=[aeiou])y")

# A nasal before a consonant assimilates to the place of that consonant, so
# ಅಂಬಿಕಾ is ambika and not anbika, while ಕೆಂಪು is kempu. Latin transliteration
# picks m or n inconsistently for the same anusvara. Folding both to one nasal
# symbol removes the choice rather than trying to predict it.
_NASAL_BEFORE_CONSONANT = re.compile(r"[mn](?=[bcdgjklmnprstv])")


def _vowel_class(match: re.Match) -> str:
    """Collapse a vowel run to one of three classes.

    Transliteration is not standardised, so vowel length and the e against i
    and o against u contrasts survive inconsistently. Gireesh and Girish are
    the same man. Three classes keep enough vowel structure to separate
    genuinely different names while absorbing that inconsistency, which is the
    thing Soundex gets wrong by deleting vowels entirely.
    """
    run = match.group(0)
    if "u" in run or "o" in run:
        return "u"
    if "i" in run or "e" in run:
        return "i"
    return "a"


def fold_token(token: str) -> str:
    """Fold one already transliterated, lowercased token to its phonetic form."""
    t = re.sub(r"[^a-z]", "", token.lower())
    if not t:
        return ""
    if len(t) > 1:
        t = _FINAL_Y.sub("i", t)
        t = _GLIDE_Y.sub("", t)
    for src, dst in _DIGRAPHS:
        if src in t:
            t = t.replace(src, dst)
    t = _NASAL_BEFORE_CONSONANT.sub("n", t)
    t = _VOWEL_RUN.sub(_vowel_class, t)
    t = _DOUBLED.sub(r"\1", t)
    # Kannada transliteration adds a final inherent vowel that Latin
    # transliteration usually drops. Ramesha against Ramesh, Basappa against
    # Basapp. Stripping trailing vowels removes the difference.
    t = t.rstrip("aiu")
    return t


@dataclass(frozen=True)
class NormalisedName:
    original: str
    transliterated: str
    tokens: tuple[str, ...]      # folded, length two or more
    initials: tuple[str, ...]    # single letters, folded to their first char
    markers: tuple[str, ...]     # relationship and honorific tokens removed
    script: str                  # kannada, latin or mixed

    @property
    def canonical(self) -> str:
        """Token order removed. Handles the reordered patronymic form."""
        return " ".join(sorted(self.tokens))

    @property
    def is_empty(self) -> bool:
        return not self.tokens

    @property
    def letters(self) -> frozenset[str]:
        """First letters available from tokens or from explicit initials.

        This is what the territorial blocking key uses, because it is the only
        thing left when a name has been reduced to R.K.
        """
        return frozenset([t[0] for t in self.tokens if t] + list(self.initials))


def _script_of(original: str) -> str:
    kn = is_kannada(original)
    la = any(ch.isascii() and ch.isalpha() for ch in original)
    if kn and la:
        return "mixed"
    return "kannada" if kn else "latin"


def normalise(name: str) -> NormalisedName:
    """Full Layer 1 pipeline for one AccusedName."""
    script = _script_of(name)
    text = unicodedata.normalize("NFC", name)
    for zw in ZERO_WIDTH:
        text = text.replace(zw, "")

    text = transliterate(text)
    text = text.lower()
    # s/o, d/o, w/o and c/o before punctuation is stripped, so the o does not
    # survive as a spurious initial.
    text = _RELATION_RE.sub(" ", text)

    parts = [p for p in _SPLIT_RE.split(text) if p]

    markers, kept = [], []
    for part in parts:
        if part in MARKER_TOKENS:
            markers.append(part)
        else:
            kept.append(part)

    tokens, initials = [], []
    for part in kept:
        if len(part) == 1:
            initials.append(part)
            continue
        folded = fold_token(part)
        if len(folded) >= 2:
            tokens.append(folded)
        elif folded:
            initials.append(folded)

    return NormalisedName(
        original=name,
        transliterated=text.strip(),
        tokens=tuple(tokens),
        initials=tuple(sorted(set(initials))),
        markers=tuple(markers),
        script=script,
    )
