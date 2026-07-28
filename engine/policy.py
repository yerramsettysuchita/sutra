"""Feature policy enforcement.

docs/ethics.md commits to never using protected attributes as model features.
This module is that commitment expressed as code that fails loudly, because a
commitment written only in a document is a commitment until someone is in a
hurry.

The columns exist in the KSP schema and therefore in our corpus. Removing them
from the data would make the control untestable, since there would be nothing
for the guard to catch. Keeping them and proving they are never read is the
stronger claim. See docs/decisions.md ADR 010.
"""

from __future__ import annotations

from typing import Iterable

__all__ = [
    "EXCLUDED_FEATURE_COLUMNS",
    "ExcludedFeatureError",
    "assert_no_excluded_features",
    "is_excluded",
]


class ExcludedFeatureError(RuntimeError):
    """Raised when a protected attribute reaches a model input.

    Deliberately an exception and not a warning. A warning in a log is a
    control that works right up until the day nobody is reading the log.
    """


# Names are matched case insensitively and with underscores and spaces removed,
# so caste_id, CasteID, "Caste ID" and CASTEID are all caught. Renaming a column
# to slip it past the guard has to be deliberate, which is the point.
EXCLUDED_FEATURE_COLUMNS = frozenset({
    "CasteID", "Caste", "CasteName", "CasteCategory", "SubCaste",
    "ReligionID", "Religion", "ReligionName", "Community",
    "OccupationID", "Occupation", "OccupationName",
})

_NORMALISED = {c.lower().replace("_", "").replace(" ", "")
               for c in EXCLUDED_FEATURE_COLUMNS}


def _normalise(column: str) -> str:
    return column.lower().replace("_", "").replace(" ", "")


def is_excluded(column: str) -> bool:
    return _normalise(column) in _NORMALISED


def assert_no_excluded_features(columns: Iterable[str], context: str) -> None:
    """Raise if any protected attribute is present.

    Call this at every point where a column set becomes a feature matrix, a
    model input, a similarity computation or a ranking. `context` names the
    call site so the traceback says where the leak was, not merely that there
    was one.
    """
    offending = sorted({c for c in columns if is_excluded(c)})
    if offending:
        raise ExcludedFeatureError(
            f"{context}: protected attributes are not permitted as features. "
            f"Offending columns: {', '.join(offending)}. "
            f"See docs/ethics.md section 2. If this column is genuinely needed "
            f"for display rather than for modelling, read it outside the "
            f"feature path."
        )
