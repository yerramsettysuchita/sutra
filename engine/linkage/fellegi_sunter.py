"""Layer 4. Frequency adjusted Fellegi Sunter linkage.

For each signal we estimate two probabilities.

  m_k(l)  probability signal k shows agreement level l given the pair matches
  u_k(l)  probability it shows level l given the pair does not

Under conditional independence the log likelihood ratio of a comparison vector
is the sum of per signal log(m/u) terms, which is what makes the evidence
additive and therefore explainable to an investigator. Layer 7 shows a merge as
a list of contributions that sum to the score. A gradient boosted classifier
would score similarly and could not do that. See ADR 006.

m and u are fitted by expectation maximisation over the unlabelled candidate
set, so the model calibrates to this corpus rather than to constants someone
chose, and so the same code runs in a deployment that has no gold set.

The frequency adjustment is the part most implementations skip.

Under plain Fellegi Sunter, agreeing on Manjunath Basappa scores exactly as
agreeing on a name held by one person. That is wrong. For a non matching pair,
the probability of agreeing on a specific value v is p_v squared, and the
probability of agreeing on anything is the sum of p_v squared over all values.
So the generic agreement weight uses that sum, while the value specific weight
uses p_v itself:

    generic   log( m_agree / sum_v p_v^2 )
    adjusted  log( m_agree / p_v )

The adjustment is therefore additive, log(u_generic / p_v). It is positive for
a rare name and negative for a common one, which is the behaviour we want and
is derived rather than tuned.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from engine.features.signals import LEVELS, MODEL_SIGNALS as SIGNALS, NOT_COMPUTABLE

# Levels are shifted by one so NOT_COMPUTABLE at -1 becomes index 0 and is
# modelled as its own outcome. Missingness is not disagreement.
LEVEL_OFFSET = 1

MIN_PROB = 1e-9


# A level seen fewer times than this in the whole candidate set carries no
# evidence, whatever the smoothed arithmetic says about it.
MIN_LEVEL_SUPPORT = 30


@dataclass
class FittedModel:
    p_match: float
    m: dict[str, np.ndarray]
    u: dict[str, np.ndarray]
    support: dict[str, np.ndarray] = field(default_factory=dict)
    seed_sizes: dict[str, int] = field(default_factory=dict)
    trace: list[dict] = field(default_factory=list)
    iterations: int = 0
    converged: bool = False
    method: str = "direct"
    # The signal set this model was fitted over. Defaults to the module wide
    # MODEL_SIGNALS, and is overridden when a table carries columns the
    # accused table does not, such as a complainant's phone number. Carrying
    # it on the model means weights() and score() can never disagree about
    # which channels exist.
    signals: tuple[str, ...] = SIGNALS

    def weights(self) -> dict[str, np.ndarray]:
        """log(m/u) per signal per level.

        Levels with no support are forced to zero.

        Without this an unobserved level produces a large positive weight out
        of nothing. Smoothing gives m and u the same pseudo count but different
        normalisers, so an empty cell lands at log(m/u) around +5.4, which was
        enough on its own to carry a pair over the decision threshold. Two
        signals had a never occurring level, so thousands of pairs were merged
        on the strength of evidence that did not exist.

        Zero is the correct weight for a level nothing was ever observed at.
        It says the comparison told us nothing, which is the truth.
        """
        out = {}
        for s in self.signals:
            w = np.log(np.maximum(self.m[s], MIN_PROB) / np.maximum(self.u[s], MIN_PROB))
            if s in self.support:
                w = np.where(self.support[s] < MIN_LEVEL_SUPPORT, 0.0, w)
            # Absence of a measurement is never evidence. The not computable
            # level always carries zero weight, whatever the fit says.
            #
            # Left free, it does real damage. Relational is not computable on
            # 1,125,109 candidate pairs, and because those pairs happen to be
            # slightly enriched for matches the fit gave the level a weight of
            # +0.26 and quietly shifted a third of the corpus upward. A model
            # must not learn that a missing field means same person.
            w[0] = 0.0
            out[s] = w
        return out


def _level_matrix(levels: dict[str, np.ndarray],
                  signals: tuple[str, ...] = SIGNALS) -> np.ndarray:
    """Candidate pairs as an integer matrix, one column per signal."""
    return np.column_stack([
        levels[s].astype(np.int16) + LEVEL_OFFSET for s in signals
    ])


def leave_one_out_seed(levels: dict[str, np.ndarray], target: str,
                       minimum: int = 200,
                       signals: tuple[str, ...] = SIGNALS) -> np.ndarray:
    """A high purity match seed that never looks at the signal it will estimate.

    To estimate m for signal k we need a set of pairs that are mostly true
    matches and were selected without consulting k. Otherwise the estimate is
    conditioned on its own answer. So the seed for each signal is built from
    strong agreement on the other signals only.

    Conditions are dropped from the weakest upward if the seed comes out too
    small to estimate from, so a signal is never fitted on a handful of pairs.
    """
    conditions = [
        ("modus", levels["modus"] >= 2),
        ("name", levels["name"] >= 4),
        ("temporal", levels["temporal"] == 2),
        ("spatial", levels["spatial"] == 3),
    ]
    usable = [(n, c) for n, c in conditions if n != target]

    mask = np.ones(len(levels[target]), dtype=bool)
    for _, condition in usable:
        mask &= condition
    while mask.sum() < minimum and len(usable) > 1:
        usable.pop(0)                       # drop the weakest condition
        mask = np.ones(len(levels[target]), dtype=bool)
        for _, condition in usable:
            mask &= condition
    return mask


def estimate_m_from_seeds(levels: dict[str, np.ndarray],
                          smoothing: float = 1.0,
                          signals: tuple[str, ...] = SIGNALS) -> tuple[dict, dict]:
    """Estimate m per signal from its own leave one out seed.

    Returns the estimates and the seed size used for each, so the report can
    show what each parameter was fitted on.

    This replaces expectation maximisation for the m parameters, and the reason
    is recorded in ADR 019. EM converges to the same wrong fixed point from
    every initialisation tried, including a seed of purity 0.846, so the
    failure is misspecification of the independence assumption rather than a
    local optimum. No amount of restarting fixes a likelihood surface whose
    global optimum is the wrong partition.

    The seeds carry roughly fifteen per cent contamination, which shrinks each
    m toward u and makes every weight slightly conservative. Understating the
    evidence is the safe direction for a system whose characteristic harm is a
    false merge.
    """
    m: dict[str, np.ndarray] = {}
    sizes: dict[str, int] = {}
    for signal in signals:
        seed = leave_one_out_seed(levels, signal, signals=signals)
        size = LEVELS[signal] + LEVEL_OFFSET
        idx = levels[signal][seed].astype(np.int16) + LEVEL_OFFSET
        counts = np.bincount(idx, minlength=size).astype(float) + smoothing
        m[signal] = counts / counts.sum()
        sizes[signal] = int(seed.sum())
    return m, sizes


def seed_masks(levels: dict[str, np.ndarray]) -> np.ndarray:
    """A high purity match seed found without any labels.

    Expectation maximisation on this corpus does not converge on the right
    mixture from an uninformative start. It settles on a class roughly twelve
    times larger than the true match set, because "similar" is a much bigger
    and tighter cluster than "same person" once 120,000 deliberate name
    collisions are in the candidate set. Informative initialisation is the
    standard remedy and it needs a seed that can be found without labels.

    The seed used is agreement of the same police station, an implied birth
    year within one year, and a modus operandi cosine above 0.35. None of those
    three is the name channel, so the seed is unbiased for estimating what a
    true match looks like on names, which is the parameter that matters most.

    Measured purity of this seed on the development corpus is 0.846 across
    1,013 pairs, against a base rate of 0.0032. That is 262 times the base rate
    and it was obtained without reading a single label.
    """
    return (
        (levels["spatial"] == 3)
        & (levels["temporal"] == 2)
        & (levels["modus"] >= 2)
    )


def fit_em(levels: dict[str, np.ndarray], max_iter: int = 300,
           tol: float = 1e-10, seed_p: float = 0.003,
           fix_u: bool = True, smoothing: float = 1.0,
           seed_mask: np.ndarray | None = None,
           estimate_only: bool = True,
           signals: tuple[str, ...] = SIGNALS,
           m_prior: dict[str, np.ndarray] | None = None) -> FittedModel:
    """Fit m, u and the match proportion by expectation maximisation.

    Pairs are collapsed to distinct comparison patterns first. Three million
    pairs reduce to a few thousand patterns, so each iteration is arithmetic
    over the pattern table rather than over the corpus, and the fit is exact
    rather than sampled.

    Two departures from the textbook, both forced by what this corpus is.

    `fix_u` estimates u once from the marginal distribution of the candidate
    set and holds it there. This is standard practice in modern record linkage
    and it is sound here because matches are roughly three in a thousand
    candidate pairs, so the candidate marginals are the non match marginals to
    three decimal places. It also removes the failure that free u produces
    here, which is worth naming.

    With both m and u free, EM converges on a solution that defines a match as
    an identical name string. It fits p at 0.038 against a true 0.003, drives
    m for lexical agreement to 1.0 and u to 4e-7, and produces weights above
    fourteen. That is not a bug in the implementation. It is the corpus telling
    the truth. The candidate set contains roughly 120,000 pairs of distinct
    people who share an identical folded name, because those collisions were
    planted deliberately, and "same name" is a far larger and tighter cluster
    than "same person". Unsupervised EM has no way to prefer the smaller one.

    Fixing u removes that degree of freedom. The frequency adjustment then
    handles the collisions at scoring time, which is where the information
    about name rarity actually lives. See ADR 016.

    `smoothing` adds a pseudo count before normalising, so no level can reach
    exactly zero probability and produce an infinite weight from a single
    unobserved cell.
    """
    matrix = _level_matrix(levels, signals)
    patterns, _, counts = np.unique(
        matrix, axis=0, return_inverse=True, return_counts=True)
    counts = counts.astype(np.float64)
    n_patterns = len(patterns)
    total = counts.sum()

    sizes = {s: LEVELS[s] + LEVEL_OFFSET for s in signals}

    def normalise(raw: np.ndarray) -> np.ndarray:
        smoothed = raw + smoothing
        return smoothed / smoothed.sum()

    # u is the marginal distribution over the candidate set. Under fix_u it
    # stays here. Under free u it is only the starting point.
    u: dict[str, np.ndarray] = {}
    support: dict[str, np.ndarray] = {}
    for k, signal in enumerate(signals):
        size = sizes[signal]
        observed = np.bincount(patterns[:, k], weights=counts, minlength=size)
        support[signal] = observed.copy()
        u[signal] = normalise(observed)

    m: dict[str, np.ndarray] = {}
    seed_sizes: dict[str, int] = {}
    if m_prior is not None:
        # m comes from somewhere else, usually a table with enough independent
        # channels to estimate it. u is still estimated locally from this
        # table's own candidate marginals, because u describes the blocking
        # scheme's output rather than the population. EM then fits only the
        # mixing proportion. See ADR 026.
        m = {s: np.asarray(m_prior[s], dtype=float) for s in signals}
        seed_sizes = {}
    elif estimate_only:
        # Direct estimation. m from leave one out seeds, u from the candidate
        # marginals, and only the mixing proportion left for EM to find. See
        # ADR 019.
        m, seed_sizes = estimate_m_from_seeds(levels, smoothing=smoothing,
                                              signals=signals)
    elif seed_mask is not None and seed_mask.any():
        # Initialise m from an unsupervised high purity seed. See seed_masks.
        seed_matrix = _level_matrix({s: levels[s][seed_mask] for s in signals},
                                    signals)
        for k, signal in enumerate(signals):
            size = sizes[signal]
            m[signal] = normalise(
                np.bincount(seed_matrix[:, k], minlength=size).astype(float))
    else:
        # Fallback. m peaked on agreement, which keeps EM out of the mirror
        # solution where the match class is the one that disagrees.
        for signal in signals:
            size = sizes[signal]
            shape = np.array([0.4] + [(level + 1.0) ** 3 for level in range(size - 1)])
            m[signal] = shape / shape.sum()

    p = seed_p
    trace: list[dict] = []
    previous_ll = -np.inf
    converged = False
    iterations = 0

    for iteration in range(1, max_iter + 1):
        iterations = iteration

        # E step
        log_m = np.zeros(n_patterns)
        log_u = np.zeros(n_patterns)
        for k, signal in enumerate(signals):
            idx = patterns[:, k]
            log_m += np.log(np.maximum(m[signal][idx], MIN_PROB))
            log_u += np.log(np.maximum(u[signal][idx], MIN_PROB))

        a = math.log(max(p, MIN_PROB)) + log_m
        b = math.log(max(1.0 - p, MIN_PROB)) + log_u
        top = np.maximum(a, b)
        denom = top + np.log(np.exp(a - top) + np.exp(b - top))
        g = np.exp(a - denom)

        log_likelihood = float((counts * denom).sum())

        # M step
        weight_m = counts * g
        p = float(weight_m.sum() / total)

        for k, signal in enumerate(signals):
            size = sizes[signal]
            idx = patterns[:, k]
            if m_prior is None and not estimate_only:
                m[signal] = normalise(
                    np.bincount(idx, weights=weight_m, minlength=size))
            if not fix_u and m_prior is None and not estimate_only:
                u[signal] = normalise(
                    np.bincount(idx, weights=counts * (1.0 - g), minlength=size))

        trace.append({
            "iteration": iteration,
            "log_likelihood": log_likelihood,
            "p_match": p,
            "delta": (log_likelihood - previous_ll) if iteration > 1 else None,
        })

        if iteration > 1 and abs(log_likelihood - previous_ll) < tol * abs(previous_ll):
            converged = True
            previous_ll = log_likelihood
            break
        previous_ll = log_likelihood

    return FittedModel(
        p_match=p, m=m, u=u, support=support, seed_sizes=seed_sizes,
        trace=trace, iterations=iterations, converged=converged,
        signals=tuple(signals),
        method=("transferred m, EM for the mixing proportion only"
                if m_prior is not None else
                "direct estimation, EM for the mixing proportion only"
                if estimate_only else "full expectation maximisation"),
    )


def score(model: FittedModel, levels: dict[str, np.ndarray]) -> np.ndarray:
    """Log likelihood ratio per pair, unadjusted."""
    weights = model.weights()
    total = np.zeros(len(next(iter(levels.values()))), dtype=np.float64)
    for signal in model.signals:
        idx = levels[signal].astype(np.int16) + LEVEL_OFFSET
        total += weights[signal][idx]
    return total


def per_signal_contributions(model: FittedModel,
                             levels: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Each signal's contribution, so a merge can be explained term by term."""
    weights = model.weights()
    return {
        signal: weights[signal][levels[signal].astype(np.int16) + LEVEL_OFFSET]
        for signal in model.signals
    }


def frequency_adjustment(agreed_name: list[str],
                         name_frequency: dict[str, float],
                         u_generic: float) -> np.ndarray:
    """Additive correction to the name agreement weight.

    Returns log(u_generic / p_v) for pairs that agreed on a name value, zero
    elsewhere. Positive for a rare name, negative for a common one.
    """
    out = np.zeros(len(agreed_name), dtype=np.float64)
    floor = MIN_PROB
    for i, value in enumerate(agreed_name):
        if not value:
            continue
        p_v = max(name_frequency.get(value, floor), floor)
        out[i] = math.log(max(u_generic, floor) / p_v)
    return out


def generic_agreement_u(name_frequency: dict[str, float]) -> float:
    """Sum of p_v squared, the probability a random non match pair agrees.

    This is the quantity plain Fellegi Sunter uses in place of the specific
    p_v, and computing it here keeps the adjustment consistent with the theory
    rather than with a fitted constant.
    """
    return float(sum(p * p for p in name_frequency.values()))


# How much worse a false merge is than a missed merge, as a ratio of costs.
#
# This project has argued from the beginning that the two errors are not equal.
# A false merge asserts two people are one, writes that into the record, and
# propagates into every downstream product. A missed merge leaves the record
# exactly where it already was. The evaluation reports F beta at 0.5 for that
# reason, and F beta at 0.5 is precisely the statement that recall is worth
# beta squared, a quarter, of precision.
#
# So the cost ratio implied by our own stated objective is 1 / 0.5**2 = 4. The
# argument was being made in the report and not in the engine: the decision
# threshold sat at posterior 0.5, which is the threshold for a model that
# believes the two errors cost the same.
#
# Setting it here makes the engine do what the project says. It reads no
# labels. It is a policy constant derived from a stated position about harm,
# and a department that disagrees changes this one number. See ADR 028.
FALSE_MERGE_COST_RATIO = 4.0


def posterior_threshold(model: FittedModel,
                        cost_ratio: float = FALSE_MERGE_COST_RATIO) -> float:
    """Log likelihood ratio at the decision boundary, given the cost of an error.

    Derived from the fitted prior rather than chosen, so it needs no labels.

    Under equal costs the boundary is at posterior 0.5. Under a cost ratio `c`
    it moves to posterior c / (1 + c), which is where the expected cost of
    merging equals the expected cost of not merging. At c = 4 that is 0.8, so
    the engine now requires four to one odds before it merges rather than even
    odds.

    Layer 7 replaces this with calibrated routing for the three way decision.
    """
    p = min(max(model.p_match, MIN_PROB), 1.0 - MIN_PROB)
    prior_odds = math.log((1.0 - p) / p)
    # Cost ratio 1 collapses to the classical posterior 0.5 boundary.
    return prior_odds + math.log(max(cost_ratio, MIN_PROB))
