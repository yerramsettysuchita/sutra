"""Layer 3 extraction over the candidate set.

Three million candidate pairs on the development corpus, so the work is
organised around not recomputing anything.

Names come from a small pool, so the distinct folded name strings number in
the thousands rather than the millions. Lexical scores are memoised on the
pair of name keys. Unit hierarchy distance is precomputed for every station
pair. Modus operandi vectors are built once per case and compared in chunks.
Everything else is vectorised over numpy arrays.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from engine.block.candidates import Records
from engine.features import signals as S
from engine.features.signals import FeatureSet

MODUS_CHUNK = 250_000


def _name_key(norm) -> str:
    """Canonical folded name, the memo key for lexical scoring."""
    return norm.canonical


def extract(records: Records, pair_a: np.ndarray, pair_b: np.ndarray,
            progress=None) -> FeatureSet:
    n_pairs = len(pair_a)
    features = FeatureSet(pair_a=pair_a, pair_b=pair_b)

    def step(label: str) -> None:
        if progress:
            progress(label)

    # ---- per row precomputation ----------------------------------------
    name_keys = [_name_key(norm) for norm in records.norms]
    token_sets = [frozenset(norm.tokens) for norm in records.norms]

    key_a = [name_keys[i] for i in pair_a]
    key_b = [name_keys[i] for i in pair_b]

    # ---- a, lexical -----------------------------------------------------
    step("a lexical")
    memo: dict[tuple[str, str], tuple[float, float]] = {}
    lex_score = np.empty(n_pairs, dtype=np.float32)
    lex_level = np.empty(n_pairs, dtype=np.int8)
    agreed_name: list[str] = []

    for k in range(n_pairs):
        ka, kb = key_a[k], key_b[k]
        cache_key = (ka, kb) if ka <= kb else (kb, ka)
        cached = memo.get(cache_key)
        if cached is None:
            jw = S.jaro_winkler(ka, kb)
            ts = S.token_set_ratio(token_sets[pair_a[k]], token_sets[pair_b[k]])
            cached = (jw, ts)
            memo[cache_key] = cached
        jw, ts = cached
        # Both measures, combined. Jaro Winkler carries character level
        # corruption, token set carries reordering and dropped tokens, and a
        # pair needs only one of the two routes to survive.
        combined = max(jw, ts) * 0.65 + min(jw, ts) * 0.35
        lex_score[k] = combined
        level = S.lexical_level(combined)
        lex_level[k] = level
        agreed_name.append(ka if (level == 3 and ka == kb) else "")

    features.scores["lexical"] = lex_score
    features.levels["lexical"] = lex_level
    features.agreed_name = agreed_name

    # ---- b, phonetic ----------------------------------------------------
    step("b phonetic")
    phon_level = np.empty(n_pairs, dtype=np.int8)
    phon_score = np.zeros(n_pairs, dtype=np.float32)
    for k in range(n_pairs):
        ta, tb = token_sets[pair_a[k]], token_sets[pair_b[k]]
        phon_level[k] = S.phonetic_level(ta, tb)
        phon_score[k] = len(ta & tb) if ta and tb else 0.0
    features.scores["phonetic"] = phon_score
    features.levels["phonetic"] = phon_level

    # ---- composite name channel ----------------------------------------
    # Lexical and phonetic are two readings of one string. Layer 4 models this
    # composite instead of both, so the name evidence is counted once. See
    # ADR 017 and the note on MODEL_SIGNALS.
    name_lvl = np.empty(n_pairs, dtype=np.int8)
    for k in range(n_pairs):
        name_lvl[k] = S.name_level(
            float(lex_score[k]), int(phon_level[k]), bool(agreed_name[k]))
    features.levels["name"] = name_lvl
    features.scores["name"] = name_lvl.astype(np.float32)

    # ---- c, temporal ----------------------------------------------------
    step("c temporal")
    implied = np.array([
        S.implied_birth_year(
            records.cases[records.case_id[i]]["CrimeRegisteredDate"],
            row["AgeYear"],
        )
        for i, row in enumerate(records.accused)
    ], dtype=np.float64)

    delta = np.abs(implied[pair_a] - implied[pair_b])
    temp_level = np.where(
        np.isnan(delta), S.NOT_COMPUTABLE,
        np.where(delta <= 1, 2, np.where(delta <= 2, 1, 0)),
    ).astype(np.int8)
    features.scores["temporal"] = np.nan_to_num(delta, nan=-1.0).astype(np.float32)
    features.levels["temporal"] = temp_level

    # ---- d, spatial -----------------------------------------------------
    step("d spatial")
    lat = np.array([float(records.cases[c]["Latitude"] or "nan")
                    for c in records.case_id])
    lon = np.array([float(records.cases[c]["Longitude"] or "nan")
                    for c in records.case_id])
    km = S.haversine_km(lat[pair_a], lon[pair_a], lat[pair_b], lon[pair_b])

    paths = S.unit_paths(records.units)
    unit_codes = {u: i for i, u in enumerate(dict.fromkeys(records.unit))}
    unit_of = np.array([unit_codes[u] for u in records.unit], dtype=np.int32)
    unit_list = list(unit_codes)
    n_units = len(unit_list)
    hop_table = np.zeros((n_units, n_units), dtype=np.int8)
    for i in range(n_units):
        for j in range(i + 1, n_units):
            d = S.hierarchy_distance(paths[unit_list[i]], paths[unit_list[j]])
            hop_table[i, j] = hop_table[j, i] = d
    hops = hop_table[unit_of[pair_a], unit_of[pair_b]]

    spat_level = np.where(
        hops == 0, 3,
        np.where((hops <= 2) | (km <= 15.0), 2,
                 np.where((hops <= 4) | (km <= 60.0), 1, 0)),
    ).astype(np.int8)
    features.scores["spatial"] = km.astype(np.float32)
    features.levels["spatial"] = spat_level

    # ---- e, modus operandi ----------------------------------------------
    step("e modus operandi")
    case_order = list(dict.fromkeys(records.case_id))
    case_index = {c: i for i, c in enumerate(case_order)}
    briefs = [records.cases[c]["BriefFacts"] or "" for c in case_order]

    # Word level TF-IDF with sublinear term frequency. Character n grams are
    # added because 15% of narratives are written in Kannada and a word level
    # model alone would treat the two scripts as disjoint vocabularies.
    # min_df must never exceed the document count. On the development corpus
    # there are thousands of briefs and the constants below are the right ones.
    # On a small corpus, which happens in tests and would happen to anyone
    # running the engine over a single station, a min_df above the document
    # count makes scikit-learn raise "max_df corresponds to < documents than
    # min_df" and takes the whole extraction down. Found by the Layer 3 tests.
    n_briefs = max(len(briefs), 1)
    word_vec = TfidfVectorizer(
        analyzer="word", ngram_range=(1, 2), sublinear_tf=True,
        min_df=min(2, n_briefs), max_features=40_000,
    )
    char_vec = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 4), sublinear_tf=True,
        min_df=min(3, n_briefs), max_features=40_000,
    )
    from scipy.sparse import hstack
    from sklearn.preprocessing import normalize

    matrix = normalize(hstack([word_vec.fit_transform(briefs),
                               char_vec.fit_transform(briefs)]).tocsr())

    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    ca, cb = case_of[pair_a], case_of[pair_b]
    cosine = np.empty(n_pairs, dtype=np.float32)
    for start in range(0, n_pairs, MODUS_CHUNK):
        end = min(start + MODUS_CHUNK, n_pairs)
        left = matrix[ca[start:end]]
        right = matrix[cb[start:end]]
        cosine[start:end] = np.asarray(left.multiply(right).sum(axis=1)).ravel()

    features.scores["modus"] = cosine
    features.levels["modus"] = np.where(
        cosine >= 0.55, 3, np.where(cosine >= 0.35, 2, np.where(cosine >= 0.18, 1, 0)),
    ).astype(np.int8)

    # ---- f, relational --------------------------------------------------
    step("f relational")
    # Co accused are identified by their folded name key on this first pass.
    # The engine has no identities yet, which is the circularity Layer 6
    # exists to resolve. This is the seed, not the final answer.
    co_by_case: dict[str, set[str]] = {}
    for i, cid in enumerate(records.case_id):
        co_by_case.setdefault(cid, set()).add(name_keys[i])

    officer = records.arrest_officer
    rel_level = np.empty(n_pairs, dtype=np.int8)
    rel_score = np.zeros(n_pairs, dtype=np.float32)
    for k in range(n_pairs):
        i, j = pair_a[k], pair_b[k]
        others_a = co_by_case[records.case_id[i]] - {name_keys[i]}
        others_b = co_by_case[records.case_id[j]] - {name_keys[j]}
        has_officers = bool(officer[i]) and bool(officer[j])
        computable = bool(others_a and others_b) or has_officers
        shared_co = bool(others_a & others_b)
        shared_off = has_officers and officer[i] == officer[j]
        rel_level[k] = S.relational_level(shared_co, shared_off, computable)
        rel_score[k] = (2.0 if shared_co else 0.0) + (1.0 if shared_off else 0.0)

    features.scores["relational"] = rel_score
    features.levels["relational"] = rel_level

    # ---- g, recorded gender ---------------------------------------------
    # The cheapest evidence in the schema and it sat unread for the whole
    # project. A disagreement is near proof of a non match: zero of 3,840 true
    # people have two rows that disagree. Blank on either side is not a
    # disagreement and is scored NOT_COMPUTABLE.
    step("g gender")
    gender = records.gender or [""] * len(records)
    g_level = np.array(
        [S.gender_level(gender[i], gender[j]) for i, j in zip(pair_a, pair_b)],
        dtype=np.int8)
    features.levels["gender"] = g_level
    features.scores["gender"] = g_level.astype(np.float32)

    return features


def name_frequency(records: Records) -> dict[str, float]:
    """Corpus frequency of every folded name key.

    Layer 4 uses this to weight name agreement by inverse frequency. Agreeing
    on a name held by 235 rows is much weaker evidence than agreeing on one
    held by two, and a model that treats them alike is information
    theoretically wrong.
    """
    counts: dict[str, int] = {}
    for norm in records.norms:
        key = norm.canonical
        counts[key] = counts.get(key, 0) + 1
    total = float(len(records.norms))
    return {key: count / total for key, count in counts.items()}
