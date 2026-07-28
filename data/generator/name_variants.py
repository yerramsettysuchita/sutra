"""Name rendering variants.

One synthetic person has one identity. A station has a keyboard, a hurry, and a
local habit. What lands in `Accused.AccusedName` is the product of the two, and
this module is that product.

Every rendering records which variant produced it and which perturbations were
applied. That record goes into the ground truth file, so evaluation can answer
the question that actually matters, which is not "what is the F1" but "which
corruption is the engine losing to".

The variants here are not invented. They are the forms that appear in Indian
police records: Kannada script and Latin transliteration of the same name, the
patronymic written out, abbreviated to an initial, moved to the front, or
dropped entirely, and the locality moniker that is often the only handle the
station has on a man.
"""

import unicodedata

# ---------------------------------------------------------------------------
# Variant catalogue
# ---------------------------------------------------------------------------
# (variant_id, script, weight, requires)
#   script   latin, kannada, mixed
#   requires optional field the identity must have for the variant to apply
#
# Weights are relative and are sampled per appearance, so one person's five
# arrests can land in five different forms. That is the whole point.

VARIANTS = [
    # Latin
    ("LA_FULL",            "latin",   180, None),
    ("LA_GIVEN",           "latin",    70, None),
    ("LA_SONOF",           "latin",    55, None),
    ("LA_SONOF_DOT",       "latin",    18, None),
    ("LA_INITIAL_PREFIX",  "latin",    45, None),
    ("LA_INITIAL_SUFFIX",  "latin",    30, None),
    ("LA_INITIAL_BOTH",    "latin",     9, None),
    ("LA_REORDER",         "latin",    22, None),
    ("LA_UPPER",           "latin",    20, None),
    ("LA_MONIKER",         "latin",    26, "moniker"),
    ("LA_ALIAS",           "latin",    16, "moniker"),
    # Kannada
    ("KN_FULL",            "kannada", 120, None),
    ("KN_GIVEN",           "kannada",  45, None),
    ("KN_TANDE",           "kannada",  50, None),
    ("KN_BIN",             "kannada",  14, "use_bin"),
    ("KN_MONIKER",         "kannada",  18, "moniker"),
    ("KN_ALIAS",           "kannada",  11, "moniker"),
    # Mixed script, which happens when one field is typed and another pasted
    ("MIX_KNGIVEN_LAFATHER", "mixed",  15, None),
    ("MIX_LAGIVEN_KNFATHER", "mixed",  10, None),
]

VARIANT_IDS = [v[0] for v in VARIANTS]
SCRIPT_OF = {v[0]: v[1] for v in VARIANTS}

KN_FATHER_MARKER = "ತಂದೆ"
KN_BIN_MARKER = "ಬಿನ್"
KN_ALIAS_MARKER = "ಅಲಿಯಾಸ್"


# ---------------------------------------------------------------------------
# Latin transliteration perturbation
# ---------------------------------------------------------------------------
# Transliteration from Kannada to Latin is not standardised, so the same name
# reaches Latin by several routes. These rules reproduce the routes that
# actually occur. Each is a real alternation seen in Indian records, not random
# character noise, which matters because random noise is easy to defeat and
# systematic alternation is not.

def _trailing_a_add(t):
    return t + "a" if t and t[-1] not in "aeiou" else None


def _trailing_a_drop(t):
    return t[:-1] if len(t) > 4 and t.endswith("a") else None


def _th_to_t(t):
    return t.replace("th", "t") if "th" in t else None


def _t_to_th(t):
    # only on a final t, so Manjunat becomes Manjunath and not Tmhimmappa
    return t[:-1] + "th" if t.endswith("t") else None


def _ee_to_i(t):
    return t.replace("ee", "i") if "ee" in t else None


def _i_to_ee(t):
    idx = t.find("i", 1)
    return t[:idx] + "ee" + t[idx + 1:] if idx > 0 else None


def _oo_to_u(t):
    return t.replace("oo", "u") if "oo" in t else None


def _v_to_w(t):
    return t.replace("v", "w") if "v" in t else None


def _ksh_to_x(t):
    return t.replace("ksh", "x") if "ksh" in t else None


def _sh_to_s(t):
    return t.replace("sh", "s") if "sh" in t else None


def _degeminate(t):
    for pair in ("pp", "ll", "dd", "nn", "tt", "mm", "kk", "gg"):
        if pair in t:
            return t.replace(pair, pair[0], 1)
    return None


def _geminate(t):
    for single, double in (("p", "pp"), ("l", "ll"), ("t", "tt")):
        idx = t.find(single, 1)
        if 0 < idx < len(t) - 1 and t[idx - 1] in "aeiou" and t[idx + 1] in "aeiou":
            return t[:idx] + double + t[idx + 1:]
    return None


def _y_glide_drop(t):
    return t.replace("iya", "ia") if "iya" in t else None


def _u_to_a_final(t):
    return t[:-1] + "a" if len(t) > 4 and t.endswith("u") else None


PERTURBATIONS = [
    ("trailing_a_add",  _trailing_a_add),
    ("trailing_a_drop", _trailing_a_drop),
    ("th_to_t",         _th_to_t),
    ("t_to_th",         _t_to_th),
    ("ee_to_i",         _ee_to_i),
    ("i_to_ee",         _i_to_ee),
    ("oo_to_u",         _oo_to_u),
    ("v_to_w",          _v_to_w),
    ("ksh_to_x",        _ksh_to_x),
    ("sh_to_s",         _sh_to_s),
    ("degeminate",      _degeminate),
    ("geminate",        _geminate),
    ("y_glide_drop",    _y_glide_drop),
    ("u_to_a_final",    _u_to_a_final),
]


def perturb_latin_token(token, rng):
    """Apply one transliteration alternation to a Latin token.

    Returns (token, rule_name). Rule name is None if nothing applied, which
    happens when no rule matches the token, and that is fine.
    """
    order = list(PERTURBATIONS)
    rng.shuffle(order)
    for name, fn in order:
        # Preserve the original capitalisation of the first character.
        lowered = token.lower()
        out = fn(lowered)
        if out and out != lowered:
            return (out[0].upper() + out[1:] if token[:1].isupper() else out), name
    return token, None


# ---------------------------------------------------------------------------
# Whitespace and punctuation noise
# ---------------------------------------------------------------------------

def _noise_double_space(s, rng):
    parts = s.split(" ")
    if len(parts) < 2:
        return None
    i = rng.randrange(len(parts) - 1)
    return " ".join(parts[: i + 1]) + "  " + " ".join(parts[i + 1:])


def _noise_trailing_space(s, rng):
    return s + " "


def _noise_leading_space(s, rng):
    return " " + s


def _noise_join(s, rng):
    parts = s.split(" ")
    if len(parts) < 2:
        return None
    i = rng.randrange(len(parts) - 1)
    return " ".join(parts[:i] + [parts[i] + parts[i + 1]] + parts[i + 2:])


def _noise_strip_dots(s, rng):
    return s.replace(".", "") if "." in s else None


def _noise_zwj(s, rng):
    # Zero width joiner, which arrives from copy paste out of legacy systems.
    parts = s.split(" ")
    if len(parts) < 2:
        return None
    return parts[0] + "‍ " + " ".join(parts[1:])


NOISE_RULES = [
    ("double_space",   _noise_double_space,   0.030),
    ("trailing_space", _noise_trailing_space, 0.045),
    ("leading_space",  _noise_leading_space,  0.020),
    ("token_join",     _noise_join,           0.014),
    ("strip_dots",     _noise_strip_dots,     0.035),
    ("zero_width",     _noise_zwj,            0.008),
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _initial(latin_token):
    return latin_token[:1].upper()


def render(identity, variant, rng, perturb_probability=0.22):
    """Render one appearance of a person's name.

    `identity` is a mapping with keys given_la, given_kn, father_la, father_kn,
    moniker_la, moniker_kn, use_bin.

    Returns a dict carrying the rendered string and the full provenance of how
    it was produced. The provenance is the deliverable, not a debugging aid.
    """
    g_la = identity["given_la"]
    f_la = identity["father_la"]
    g_kn = identity["given_kn"]
    f_kn = identity["father_kn"]
    m_la = identity.get("moniker_la")
    m_kn = identity.get("moniker_kn")

    perturbations = []

    def pl(token):
        """Perturb a Latin token with probability, recording what was applied."""
        if rng.random() < perturb_probability:
            out, rule = perturb_latin_token(token, rng)
            if rule:
                perturbations.append(rule)
                return out
        return token

    if variant == "LA_FULL":
        s = f"{pl(g_la)} {pl(f_la)}"
    elif variant == "LA_GIVEN":
        s = pl(g_la)
    elif variant == "LA_SONOF":
        s = f"{pl(g_la)} S/o {pl(f_la)}"
    elif variant == "LA_SONOF_DOT":
        s = f"{pl(g_la)} s/o. {pl(f_la)}"
    elif variant == "LA_INITIAL_PREFIX":
        s = f"{_initial(g_la)}. {pl(f_la)}"
    elif variant == "LA_INITIAL_SUFFIX":
        s = f"{pl(g_la)} {_initial(f_la)}"
    elif variant == "LA_INITIAL_BOTH":
        s = f"{_initial(g_la)}.{_initial(f_la)}."
    elif variant == "LA_REORDER":
        s = f"{pl(f_la)} {pl(g_la)}"
    elif variant == "LA_UPPER":
        s = f"{pl(g_la)} {pl(f_la)}".upper()
    elif variant == "LA_MONIKER":
        s = f"{m_la} {pl(g_la)}"
    elif variant == "LA_ALIAS":
        s = f"{pl(g_la)} @ {m_la} {g_la}"
    elif variant == "KN_FULL":
        s = f"{g_kn} {f_kn}"
    elif variant == "KN_GIVEN":
        s = g_kn
    elif variant == "KN_TANDE":
        s = f"{g_kn} {KN_FATHER_MARKER} {f_kn}"
    elif variant == "KN_BIN":
        s = f"{g_kn} {KN_BIN_MARKER} {f_kn}"
    elif variant == "KN_MONIKER":
        s = f"{m_kn} {g_kn}"
    elif variant == "KN_ALIAS":
        s = f"{g_kn} {KN_ALIAS_MARKER} {m_kn} {g_kn}"
    elif variant == "MIX_KNGIVEN_LAFATHER":
        s = f"{g_kn} {pl(f_la)}"
    elif variant == "MIX_LAGIVEN_KNFATHER":
        s = f"{pl(g_la)} {f_kn}"
    else:
        raise ValueError(f"unknown variant {variant}")

    noise_applied = []
    for name, fn, prob in NOISE_RULES:
        if rng.random() < prob:
            out = fn(s, rng)
            if out is not None:
                s = out
                noise_applied.append(name)

    return {
        "rendered": s,
        "variant": variant,
        "script": SCRIPT_OF[variant],
        "perturbations": perturbations,
        "noise": noise_applied,
        "carries_father": variant not in (
            "LA_GIVEN", "KN_GIVEN", "LA_MONIKER", "KN_MONIKER",
            "LA_ALIAS", "KN_ALIAS",
        ),
        "carries_moniker": variant in ("LA_MONIKER", "KN_MONIKER", "LA_ALIAS", "KN_ALIAS"),
        "father_abbreviated": variant in ("LA_INITIAL_PREFIX", "LA_INITIAL_SUFFIX", "LA_INITIAL_BOTH"),
    }


def choose_variant(identity, rng, script_bias=None):
    """Sample a variant, honouring the identity's available fields.

    `script_bias` optionally reweights toward one script, which the generator
    uses to give each station a house habit. A station that writes in Kannada
    tends to keep writing in Kannada, and that correlation is real and matters,
    because it means script divergence tracks jurisdiction divergence.
    """
    ids, weights = [], []
    for vid, script, weight, requires in VARIANTS:
        if requires == "moniker" and not identity.get("moniker_la"):
            continue
        if requires == "use_bin" and not identity.get("use_bin"):
            continue
        w = float(weight)
        if script_bias and script == script_bias:
            w *= 3.2
        elif script_bias and script != script_bias and script != "mixed":
            w *= 0.45
        ids.append(vid)
        weights.append(w)
    return rng.choices(ids, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Helpers shared with non accused person rendering
# ---------------------------------------------------------------------------

def render_plain(identity, rng, kannada_probability=0.30):
    """Simple two token rendering for victims, complainants and officers.

    These roles are not the object of resolution, so they get script variation
    for realism but not the full variant catalogue.
    """
    if rng.random() < kannada_probability:
        return f"{identity['given_kn']} {identity['father_kn']}"
    return f"{identity['given_la']} {identity['father_la']}"


def script_of_string(s):
    """Classify a rendered string by script, for corpus statistics."""
    has_kn = any("ಀ" <= ch <= "೿" for ch in s)
    has_la = any(unicodedata.category(ch) == "Lu" or unicodedata.category(ch) == "Ll"
                 for ch in s if ch.isascii())
    if has_kn and has_la:
        return "mixed"
    if has_kn:
        return "kannada"
    return "latin"
