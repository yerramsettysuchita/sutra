"""Layer 7. Calibration and three way routing.

A Fellegi Sunter weight is a log likelihood ratio, not a probability. An
investigator asked to approve a merge needs the second, and the routing
thresholds in the brief, 0.92 and 0.65, are only meaningful against a
calibrated probability.

Isotonic regression rather than Platt scaling, per ADR 007. Platt assumes the
score to probability relationship is sigmoid, and here it is not, because the
frequency adjustment stretches the upper tail unevenly. Isotonic assumes only
monotonicity, which is the one property a log likelihood ratio genuinely has.

Routing, and the asymmetry behind it, per ADR 009.

  above 0.92   automatic merge
  0.65 to 0.92 human review, with the evidence shown in full
  below 0.65   reject

A false merge asserts that two people are one, propagates into every downstream
product, and can put a wrong name in front of an investigator. A missed merge
leaves the record where it already was. So the automatic band is narrow and the
review band is deliberately wide.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression

AUTO_MERGE = 0.92
REVIEW_FLOOR = 0.65

ROUTES = ("auto_merge", "review", "reject")


@dataclass
class Calibration:
    model: IsotonicRegression
    n_train: int
    bins: list[dict]

    def probability(self, scores: np.ndarray) -> np.ndarray:
        return np.clip(self.model.predict(scores), 0.0, 1.0)


def fit(scores: np.ndarray, labels: np.ndarray) -> Calibration:
    """Fit score to probability on a labelled set.

    This is the one place in the engine that requires labels, and it is
    honest about that. In deployment it is fitted on the review queue's own
    decisions, which accumulate as investigators work, so the calibration
    improves with use rather than being frozen at build time.
    """
    model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    model.fit(scores, labels.astype(float))

    # Reliability table, so the calibration can be inspected rather than
    # trusted. Each row is a score decile with its predicted and observed rate.
    predicted = np.clip(model.predict(scores), 0.0, 1.0)
    edges = np.quantile(scores, np.linspace(0, 1, 11))
    bins = []
    for i in range(10):
        lo, hi = edges[i], edges[i + 1]
        sel = (scores >= lo) & (scores <= hi if i == 9 else scores < hi)
        if not sel.any():
            continue
        bins.append({
            "score_from": float(lo),
            "score_to": float(hi),
            "pairs": int(sel.sum()),
            "predicted": float(predicted[sel].mean()),
            "observed": float(labels[sel].mean()),
        })
    return Calibration(model=model, n_train=len(scores), bins=bins)


def route(probabilities: np.ndarray) -> np.ndarray:
    """Assign each pair to auto merge, review or reject."""
    out = np.full(len(probabilities), 2, dtype=np.int8)   # reject
    out[probabilities >= REVIEW_FLOOR] = 1                # review
    out[probabilities >= AUTO_MERGE] = 0                  # auto merge
    return out


def routing_report(probabilities: np.ndarray, labels: np.ndarray | None = None) -> dict:
    """Counts per route, and the false merge rate on auto merges only.

    The false merge rate is reported on the automatic band alone, because that
    is the band where no human sees the decision. Errors in the review band are
    what the review band is for.
    """
    routes = route(probabilities)
    out: dict = {"thresholds": {"auto_merge": AUTO_MERGE, "review_floor": REVIEW_FLOOR}}
    for index, name in enumerate(ROUTES):
        sel = routes == index
        entry = {"pairs": int(sel.sum())}
        if labels is not None and sel.any():
            entry["true_pairs"] = int(labels[sel].sum())
            entry["false_pairs"] = int((~labels[sel].astype(bool)).sum())
            entry["precision"] = float(labels[sel].mean())
        out[name] = entry

    if labels is not None:
        auto = routes == 0
        false_merges = int((~labels[auto].astype(bool)).sum()) if auto.any() else 0
        out["false_merge_rate"] = (
            float(false_merges / auto.sum()) if auto.any() else 0.0
        )
        out["false_merges"] = false_merges
        out["auto_merged_pairs"] = int(auto.sum())
    return out
