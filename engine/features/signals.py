"""Layer 3. Six signal feature extraction.

Each signal produces a continuous score and an ordinal agreement level. The
score is what the Layer 3 report measures separation on. The level is what
Layer 4 consumes, because Fellegi Sunter is defined over a discrete comparison
vector.

The six, and what each is for.

  a lexical      Jaro Winkler and token set ratio on the Layer 1 folded name
  b phonetic     agreement of the Indic phonetic tokens from Layer 1
  c temporal     birth year implied by CrimeRegisteredDate minus AgeYear
  d spatial      Haversine over case coordinates, plus Unit.ParentUnit distance
  e modus        similarity of the BriefFacts narrative
  f relational   shared co accused and shared arresting officer

Every signal reports coverage separately from agreement. A signal that cannot
be computed for a pair is not the same as a signal that disagrees, and
collapsing the two is how a model quietly learns that missing data means
different person. Level -1 means not computable and Layer 4 treats it as its
own level rather than as disagreement.

CasteID, ReligionID and OccupationID are never read here. The guard in
engine/policy.py is called on the feature name list at construction time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from engine.policy import assert_no_excluded_features

# Level -1 is "not computable". Every signal uses it.
NOT_COMPUTABLE = -1

# The six signals the brief names, measured and reported individually.
SIGNALS = ("lexical", "phonetic", "temporal", "spatial", "modus", "relational")

# The features Layer 4 actually models. Note that lexical and phonetic are
# replaced by one composite, `name`.
#
# This resolves the conditional independence violation recorded in ADR 006,
# and it was forced by a measurement rather than chosen on principle. Fitted
# separately, lexical agreement scored 3.276 and phonetic agreement 4.011, so
# a pair with an identical name collected 7.287 before any other evidence was
# consulted, against a decision threshold of 4.032. The two are 0.686
# correlated because they are two readings of the same string, so Fellegi
# Sunter counted one piece of evidence twice.
#
# The result was a model whose merge set was exactly the set of pairs with
# identical names, 57,872 of them, which is `GROUP BY AccusedName` with extra
# steps. Precision 0.0896. See ADR 017.
MODEL_SIGNALS = ("name", "temporal", "spatial", "modus", "relational",
                 "gender")

# Number of agreement levels per signal, excluding NOT_COMPUTABLE.
LEVELS = {
    "lexical": 4,
    "phonetic": 3,
    "name": 6,
    "temporal": 3,
    "spatial": 4,
    "modus": 4,
    "relational": 3,
    # Recorded gender. Present on Accused, Victim and ComplainantDetails.
    "gender": 3,
    # Contact channels. Only ComplainantDetails carries these columns, so they
    # are never part of MODEL_SIGNALS and never reach the accused pipeline.
    # They are opted into per table by engine/resolve_other.py. See ADR 026.
    "phone": 2,
    "address": 3,
}

# Direction of the raw score. Temporal holds a year gap and spatial holds
# kilometres, so for both a smaller number means more similar. Separation
# measures have to be told, otherwise they report an inverted AUC and the
# signal looks anti correlated with matching when it is simply measured the
# other way up.
ORIENTATION = {
    "lexical": 1,
    "phonetic": 1,
    "name": 1,
    "temporal": -1,
    "spatial": -1,
    "modus": 1,
    "relational": 1,
    "gender": 1,
    "phone": 1,
    "address": 1,
}


def name_level(lexical_score: float, phon_level: int, keys_equal: bool) -> int:
    """The composite name channel, one reading of one piece of evidence.

    The levels are cut where the data actually separates, measured on the
    candidate set rather than chosen by eye. Purity is the share of pairs at
    that level that are genuine matches, against a 0.0032 base rate.

      5  both folded tokens agree           57,872 pairs   purity 0.0892
      4  no usable tokens, initials only     8,072 pairs   purity 0.0248
      3  one token agrees, keys equal       62,737 pairs   purity 0.0077
      2  one token agrees, keys differ    2,331,647 pairs   purity 0.0017
      1  no token agrees, strings close     ~90,000 pairs   purity 0.0011
      0  no agreement of any kind         ~640,000 pairs   purity 0.0005

    Two things this ordering captures that an obvious one does not.

    Agreeing on a full name is twelve times stronger than agreeing on a given
    name alone, so a single token match with equal keys is level 3 and not
    level 5. A first attempt lumped both into one level and threw that
    distinction away.

    Level 4 looks out of order and is not. A pair recorded as initials on both
    sides has no phonetic tokens at all and is reachable only through the
    territorial blocking key, so surviving into the candidate set already
    implies the same station circle. The level is measuring that, and Fellegi
    Sunter fits a weight per level without assuming the levels are monotone.
    """
    if phon_level == 2:
        return 5
    if phon_level == NOT_COMPUTABLE:
        return 4
    if phon_level == 1:
        return 3 if keys_equal else 2
    if lexical_score >= 0.70:
        return 1
    return 0

def gender_level(left: str, right: str) -> int:
    """Recorded gender agreement. A disagreement is near proof of a non match.

    This channel is the cheapest evidence in the schema and it was ignored for
    the entire project. `Accused.GenderID` sits next to the name on every row.

    Measured on the development corpus: of 3,840 true people, **zero** have two
    rows that disagree on gender. Station writers get the name wrong constantly,
    across scripts and spellings and initials, and they do not get this wrong.
    So a disagreement is as close to a deterministic non match as this schema
    offers, and Fellegi Sunter will fit it a large negative weight without being
    told to.

    Three levels rather than two, because an unrecorded gender is not a
    disagreement and must not be scored as one. Absence of a measurement is
    never evidence, which is the same rule Layer 4 applies to NOT_COMPUTABLE.

      2  both recorded and equal
      1  reserved, currently unused, kept so the level codes are stable if a
         future schema distinguishes a recorded unknown from a blank
      0  both recorded and different

    Why this is not a protected attribute. Sex is recorded on the FIR as a
    descriptive fact about a person the police have already identified in that
    case, and it is used here only to ask whether two rows can be the same
    individual. It is not used to score risk, to rank, or to predict anything
    about anybody. Caste, religion and occupation remain excluded and are
    enforced by engine/policy.py, which this module asserts against on import.
    """
    if not left or not right:
        return NOT_COMPUTABLE
    return 2 if left == right else 0


SIGNAL_LABELS = {
    "lexical": "a  lexical, Jaro Winkler and token set",
    "phonetic": "b  Indic phonetic code agreement",
    "temporal": "c  implied birth year within two years",
    "spatial": "d  Haversine and unit hierarchy",
    "modus": "e  modus operandi over BriefFacts",
    "relational": "f  shared co accused and arresting officer",
    "gender": "g  recorded gender agreement",
    "phone": "g  phone number equality, complainant rows only",
    "address": "h  address agreement, complainant rows only",
}

assert_no_excluded_features(SIGNALS, context="engine.features.signals")

EARTH_RADIUS_KM = 6371.0088


@dataclass
class FeatureSet:
    """Scores and levels for every candidate pair."""

    pair_a: np.ndarray
    pair_b: np.ndarray
    scores: dict[str, np.ndarray] = field(default_factory=dict)
    levels: dict[str, np.ndarray] = field(default_factory=dict)
    # The folded name value the pair agreed on, used by Layer 4 frequency
    # adjustment. Empty string when the pair did not agree on a name.
    agreed_name: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.pair_a)


# ---------------------------------------------------------------------------
# a, lexical
# ---------------------------------------------------------------------------

def _jaro(a: str, b: str) -> float:
    la, lb = len(a), len(b)
    # Two empty names are not a match. The length check comes before the
    # equality check deliberately, because an absent name is absence of
    # evidence and must never score as agreement. See ADR 020.
    if la == 0 or lb == 0:
        return 0.0
    if a == b:
        return 1.0
    window = max(la, lb) // 2 - 1
    if window < 0:
        window = 0
    a_flags = [False] * la
    b_flags = [False] * lb
    matches = 0
    for i in range(la):
        lo = max(0, i - window)
        hi = min(i + window + 1, lb)
        for j in range(lo, hi):
            if not b_flags[j] and a[i] == b[j]:
                a_flags[i] = b_flags[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    transpositions = 0
    k = 0
    for i in range(la):
        if not a_flags[i]:
            continue
        while not b_flags[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2
    return (matches / la + matches / lb + (matches - transpositions) / matches) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """Jaro Winkler.

    Written out rather than imported so the engine has one fewer dependency in
    its hot path and so the prefix behaviour is visible. Jaro Winkler rewards a
    shared prefix, which suits names, where the given name leads and the
    corruption usually lands later in the string.
    """
    jaro = _jaro(a, b)
    if jaro < 0.7:
        return jaro
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return jaro + prefix * prefix_weight * (1.0 - jaro)


def token_set_ratio(tokens_a: frozenset[str], tokens_b: frozenset[str]) -> float:
    """Jaccard over folded name tokens.

    Order free by construction, which is what handles the reordered patronymic
    without a separate rule.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def lexical_level(score: float) -> int:
    if score >= 0.94:
        return 3
    if score >= 0.86:
        return 2
    if score >= 0.74:
        return 1
    return 0


# ---------------------------------------------------------------------------
# b, phonetic
# ---------------------------------------------------------------------------

def phonetic_level(tokens_a: frozenset[str], tokens_b: frozenset[str]) -> int:
    """Agreement of the Layer 1 phonetic tokens.

    Two tokens agreeing is the given name and the patronymic both matching,
    which is far stronger than one. One is the common case where a record
    dropped the patronymic or abbreviated it to an initial.
    """
    if not tokens_a or not tokens_b:
        return NOT_COMPUTABLE
    shared = len(tokens_a & tokens_b)
    if shared >= 2:
        return 2
    if shared == 1:
        return 1
    return 0


# ---------------------------------------------------------------------------
# c, temporal
# ---------------------------------------------------------------------------

def implied_birth_year(registered: str, age: str) -> float:
    """year(CrimeRegisteredDate) minus AgeYear.

    NaN when the station did not record an age, which is 4% of rows. That is
    absence, not disagreement.
    """
    if not age:
        return math.nan
    try:
        return float(registered[:4]) - float(age)
    except (ValueError, TypeError):
        return math.nan


def temporal_level(delta: float) -> int:
    if math.isnan(delta):
        return NOT_COMPUTABLE
    gap = abs(delta)
    if gap <= 1:
        return 2
    if gap <= 2:
        return 1
    return 0


# ---------------------------------------------------------------------------
# d, spatial
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    """Vectorised great circle distance."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def unit_paths(units: dict[str, dict]) -> dict[str, list[str]]:
    """Root path for every unit, so hierarchy distance is a list comparison."""
    paths: dict[str, list[str]] = {}

    def walk(unit_id: str) -> list[str]:
        if unit_id in paths:
            return paths[unit_id]
        unit = units.get(unit_id)
        parent = unit.get("ParentUnitID") if unit else ""
        path = ([] if not parent else walk(parent)) + [unit_id]
        paths[unit_id] = path
        return path

    for unit_id in units:
        walk(unit_id)
    return paths


def hierarchy_distance(path_a: list[str], path_b: list[str]) -> int:
    """Edges between two units through their lowest common ancestor.

    Administrative distance is not physical distance. Two stations either side
    of a district boundary can be five kilometres apart and four edges apart,
    and an investigator's reach follows the edges rather than the kilometres.
    """
    shared = 0
    for x, y in zip(path_a, path_b):
        if x != y:
            break
        shared += 1
    return (len(path_a) - shared) + (len(path_b) - shared)


def spatial_level(km: float, hops: int) -> int:
    if hops == 0:
        return 3                      # same police station
    if hops <= 2 or km <= 15.0:
        return 2                      # same sub division, or genuinely close
    if hops <= 4 or km <= 60.0:
        return 1                      # same district, or same neighbourhood
    return 0


# ---------------------------------------------------------------------------
# e, modus operandi
# ---------------------------------------------------------------------------

def modus_level(cosine: float) -> int:
    if cosine >= 0.55:
        return 3
    if cosine >= 0.35:
        return 2
    if cosine >= 0.18:
        return 1
    return 0


# ---------------------------------------------------------------------------
# f, relational
# ---------------------------------------------------------------------------

def relational_level(shared_co_accused: bool, shared_officer: bool,
                     computable: bool) -> int:
    if not computable:
        return NOT_COMPUTABLE
    if shared_co_accused:
        return 2
    if shared_officer:
        return 1
    return 0
