"""Layer 2. Blocking keys.

Scoring all pairs of accused rows is quadratic and pointless. Blocking narrows
the field cheaply, and the price is that any true pair the blocker fails to
propose can never be recovered by anything downstream. Pairs completeness is
therefore a hard ceiling on recall for Layers 3 to 7, which is why it is
reported rather than assumed.

Three key families, unioned rather than intersected. See docs/decisions.md
ADR 004.

  PH   the full folded name token, from Layer 1
  P4   the first four characters of that token
  TR   station circle paired with an available first letter

Each record contributes one PH and one P4 key per name token, and one TR key
per distinct first letter. Multi key blocking is what makes token reordering
and dropped patronymics survive, because the record is reachable through any
one of its tokens rather than through a single composite key.

TR exists for one specific failure. A name recorded as R.K. has no tokens at
all, so it has no phonetic key and is invisible to PH and P4. It still has
letters and it still has a station. Pairing the circle with the initial letter
keeps such a record reachable without collapsing to a block of every accused in
the district.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.normalise.indic import NormalisedName

__all__ = ["keys_for", "FAMILIES", "BlockedRecord"]

FAMILIES = ("PH", "P4", "TR")


@dataclass(frozen=True)
class BlockedRecord:
    row_id: int
    name: NormalisedName
    circle_id: int
    district_id: int
    case_id: int


def keys_for(name: NormalisedName, circle_id: int) -> dict[str, frozenset[str]]:
    """Blocking keys for one accused row, grouped by family."""
    phonetic = {f"PH:{t}" for t in name.tokens}
    short = {f"P4:{t[:4]}" for t in name.tokens if len(t) >= 2}
    territorial = {f"TR:{circle_id}:{c}" for c in name.letters}
    return {"PH": frozenset(phonetic),
            "P4": frozenset(short),
            "TR": frozenset(territorial)}
