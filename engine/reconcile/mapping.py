"""Layer 9. IPC to BNS correspondence.

The Bharatiya Nyaya Sanhita 2023 replaced the Indian Penal Code 1860 with
effect from 1 July 2024. `Act.Active` and `Section.Active` mark that boundary
in the KSP schema, and `Section.SuccessorSectionID` carries the link.

Every row below covers a section the corpus actually contains. Nothing is
listed speculatively, because a mapping table that reaches beyond the data is
a table nobody has checked.

On authority. These are the correspondences published alongside the Sanhita
and reproduced in the police handbooks issued for the transition. They are
recorded here as data rather than compiled into the query planner, so
correcting an entry is a data change and not a code change. Where a
correspondence is not one to one in law, that is noted on the row. This table
is an engineering aid, not a legal instrument.

THE HAZARD THIS EXISTS TO PREVENT.

A section number is not a stable identifier for an offence across the
boundary. IPC 324 is voluntarily causing hurt by dangerous weapon. BNS 324 is
mischief causing damage, which is the successor of IPC 427. An analyst
filtering on the string "324" across a window spanning July 2024 gets a pile
of two unrelated offences and no warning that anything is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

TRANSITION = date(2024, 7, 1)


@dataclass(frozen=True)
class Correspondence:
    ipc: str
    bns: str
    offence: str
    head: str
    note: str = ""


# ipc, bns, offence, crime head, note
CORRESPONDENCES: tuple[Correspondence, ...] = (
    # Offences against the body.
    Correspondence("302", "103", "Murder", "Body"),
    Correspondence("304", "105", "Culpable homicide not amounting to murder", "Body"),
    Correspondence("307", "109", "Attempt to murder", "Body"),
    Correspondence("323", "115", "Voluntarily causing hurt", "Body"),
    Correspondence(
        "324", "118", "Hurt by dangerous weapon", "Body",
        note="BNS 324 is a different offence, mischief. See the module docstring.",
    ),
    Correspondence("341", "126", "Wrongful restraint", "Body"),
    # Offences against women.
    Correspondence("354", "74", "Assault on a woman with intent to outrage modesty",
                   "Women"),
    # Offences against property.
    Correspondence("379", "303", "Theft", "Property"),
    Correspondence("380", "305", "Theft in a dwelling house", "Property"),
    Correspondence("392", "309", "Robbery", "Property"),
    Correspondence("395", "310", "Dacoity", "Property"),
    Correspondence("411", "317", "Dishonestly receiving stolen property", "Property"),
    Correspondence(
        "427", "324", "Mischief causing damage", "Property",
        note="Successor number collides with IPC 324, a body offence.",
    ),
    Correspondence("457", "331", "Lurking house trespass by night", "Property"),
    # Economic.
    Correspondence("420", "318", "Cheating and dishonestly inducing delivery",
                   "Economic"),
    # Public order.
    Correspondence("506", "351", "Criminal intimidation", "Public order"),
    Correspondence("143", "189", "Unlawful assembly", "Public order"),
    Correspondence("147", "191", "Rioting", "Public order"),
)

IPC_TO_BNS: dict[str, str] = {c.ipc: c.bns for c in CORRESPONDENCES}
BNS_TO_IPC: dict[str, str] = {c.bns: c.ipc for c in CORRESPONDENCES}
BY_IPC: dict[str, Correspondence] = {c.ipc: c for c in CORRESPONDENCES}

HEADS: tuple[str, ...] = tuple(dict.fromkeys(c.head for c in CORRESPONDENCES))


def ambiguous_codes() -> dict[str, list[str]]:
    """Section numbers that mean different things in the two codes.

    Any number appearing as both an IPC section and a BNS section is a trap for
    a query written against the raw string.
    """
    ipc_codes = {c.ipc for c in CORRESPONDENCES}
    bns_codes = {c.bns for c in CORRESPONDENCES}
    out: dict[str, list[str]] = {}
    for code in sorted(ipc_codes & bns_codes):
        meanings = []
        for c in CORRESPONDENCES:
            if c.ipc == code:
                meanings.append(f"IPC {code}, {c.offence}")
            if c.bns == code:
                meanings.append(f"BNS {code}, {c.offence}")
        out[code] = meanings
    return out


def equivalents(code: str) -> set[str]:
    """Every section number denoting the same offence, either side of the boundary."""
    out = {code}
    if code in IPC_TO_BNS:
        out.add(IPC_TO_BNS[code])
    if code in BNS_TO_IPC:
        out.add(BNS_TO_IPC[code])
    return out
