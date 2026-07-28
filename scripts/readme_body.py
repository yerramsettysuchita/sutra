"""The prose and the diagrams of README.md.

Split out of build_readme.py because that file was becoming one very long
f-string and the diagrams need to be plain text rather than interpolated. A
mermaid flowchart uses braces for node shapes, which fight with f-string
formatting, so every diagram lives here as a constant and the generator drops
it in whole.

Nothing here contains a figure. Every number in the README comes from a report
and is interpolated by build_readme.py, which is the property that keeps the
front page of this repository honest.
"""

ARCHITECTURE = """```mermaid
flowchart TD
    subgraph INPUT["The KSP record, as supplied"]
        A0["CaseMaster, Accused, Victim<br/>ComplainantDetails, ArrestSurrender<br/>no cross case person key"]
    end

    subgraph ENGINE["Nightly batch, runs locally, never in a request"]
        L1["Layer 1 &nbsp; Indic normalisation<br/>Kannada to Latin, phonetic folding"]
        L2["Layer 2 &nbsp; Blocking<br/>phonetic key plus station circle"]
        L3["Layer 3 &nbsp; Signals<br/>name, birth year, place, modus,<br/>relational, gender"]
        L4["Layer 4 &nbsp; Fellegi Sunter<br/>m and u, inverse name frequency"]
        L5["Layer 5 &nbsp; Correlation clustering<br/>under cannot link constraints"]
        L6["Layer 6 &nbsp; Collective iteration<br/>does not converge, output discarded"]
        L7["Layer 7 &nbsp; Calibration<br/>three way routing"]
        L8["Layer 8 &nbsp; Downstream<br/>graph, communities, hotspots"]
        L9["Layer 9 &nbsp; IPC to BNS<br/>reconciliation across July 2024"]
    end

    subgraph OUT["What the engine writes"]
        R1["resolved_identities.csv<br/>the table the schema lacks"]
        R2["JSON feeds for the client"]
    end

    subgraph SURFACE["Deployed, read only, static"]
        W["React client on Catalyst<br/>nine screens, two languages,<br/>four roles"]
    end

    A0 --> L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7
    L5 --> R1
    L7 --> L8 --> L9 --> R2
    R1 --> R2 --> W

    style L6 stroke-dasharray: 5 5
    style R1 stroke-width:3px
```

Layer 6 is drawn with a dashed border because it runs, does not converge, and
its output is discarded. The shipped identity table is Layer 5's. Two mechanisms
were tried to fix it and both failed, which is recorded in ADR 021 and ADR 025,
and the layer is closed.
"""

GAP_DIAGRAM = """```mermaid
flowchart LR
    subgraph FIR1["FIR 1000420240000131"]
        A1["Accused row<br/>AccusedMasterID 4471<br/>PersonID A1<br/>name Suresh"]
    end
    subgraph FIR2["FIR 1001120250000078"]
        A2["Accused row<br/>AccusedMasterID 9082<br/>PersonID A1<br/>name Suresha"]
    end
    subgraph FIR3["FIR 1002220250000205"]
        A3["Accused row<br/>AccusedMasterID 12310<br/>PersonID A1<br/>name in Kannada"]
    end

    A1 -. no column joins these .-> A2
    A2 -. no column joins these .-> A3

    A1 --> RI["ResolvedIdentity R000412<br/>one person, three cases<br/>the table SUTRA adds"]
    A2 --> RI
    A3 --> RI

    style RI stroke-width:3px
```

`AccusedMasterID` is a primary key on the row, not on the person. `PersonID`
holds A1, A2, A3, which is a sort label inside one FIR. The row carries no
father's name, no address, no phone and no biometric key. Three appearances of
one man are three unrelated rows and nothing in the schema says otherwise.
"""

DECISION_FLOW = """```mermaid
flowchart LR
    P["Candidate pair<br/>scored by Layer 4"] --> C{"Calibrated<br/>probability"}
    C -->|"above 0.92"| AUTO["Merged automatically<br/>no human sees it"]
    C -->|"0.65 to 0.92"| REV["Review queue"]
    C -->|"below 0.65"| REJ["Rejected"]

    REV --> Q{"Role in force"}
    Q -->|"Records operator<br/>SCRB analyst<br/>Reviewer"| ACT["Merge or keep separate<br/>written to the decision log"]
    Q -->|"Investigating officer"| RO["Read only<br/>clearing the queue is a<br/>records function"]

    ACT --> LOG["Append only log<br/>role, scope, timestamp,<br/>probability at the time"]
    LOG --> AUD["Audit trail"]
    AUD -->|"Reviewer only"| REVERSE["Reverse<br/>appends a reversal,<br/>never deletes"]
    REVERSE --> LOG

    style AUTO stroke-width:3px
    style LOG stroke-width:3px
```

The false merge rate is reported on the automatic band alone, because that is
the band where nobody looks. Errors in the review band are what the review band
is for.
"""

DATA_FLOW = """```mermaid
flowchart LR
    G["data/generator<br/>seed 4471<br/>no dependencies"] --> C["data/corpus<br/>CSV per table<br/>plus ground truth"]
    C --> E["engine/<br/>Layers 1 to 9"]
    C --> DB["eval/build_db<br/>SQLite from the DDL"]
    E --> RP["eval/report.json<br/>eval/canonical.json"]
    DB --> SQL["eval/validate_sql<br/>150 gold queries executed"]
    RP --> X["scripts/export_web.py"]
    C --> X
    X --> F["web/public/data<br/>static JSON"]
    F --> B["vite build"]
    B --> Z["sutra.zip<br/>build output, not committed"]
    RP --> RM["scripts/build_readme.py<br/>this file"]

    style Z stroke-width:3px
    style RM stroke-dasharray: 5 5
```

Nothing in the deployed bundle computes anything. The client fetches JSON the
engine already wrote. That is ADR 002 and it is why five of six Catalyst
services show as not used.

The zip is a build output rather than a committed file. `make package` writes it
and `docs/deploy.md` says what to do with it.
"""

ETHICS = """`CasteID`, `ReligionID` and `OccupationID` exist in the KSP schema, are
generated into the corpus for fidelity, and are never read by any model, scoring
function or ranking. That is enforced by `engine/policy.py`, which raises rather
than warns, and by a test that fails the build if the guard is removed. When the
engine was extended to `Victim`, which carries all three, the run was made to
assert that the raw header is rejected before the permitted columns are
projected. A control never seen to trip cannot be told apart from one that does
not work.

SUTRA does no individual predictive risk scoring and no behavioural profiling.
The undetected case matcher ranks records already on file against a case that has
already happened. It scores a pair of cases rather than a person, and it persists
nothing about anybody.

The precedent behind that refusal is Chicago's Strategic Subject List, which an
Inspector General audit found had enrolled a very large share of a city while a
RAND evaluation found no effect on victimisation, and the LAPD LASER programme,
discontinued in 2019 after its own Inspector General found the selection criteria
were applied inconsistently. Both are set out in [docs/ethics.md](docs/ethics.md).
"""

HONESTY = """This repository publishes its failures at the same size as its results, and the
list below is not the marketing version.

**Layer 6 does not converge.** It oscillates and stops at a cap. Damping was
swept at three factors and made it worse. Best partition selection on the
engine's own objective was measured across three corpus seeds, improved one and
hurt two, mean change 0.0000. The layer is closed and its output is discarded.

**Expectation maximisation does not fit m and u** on this corpus. It converges to
a solution that defines a match as an identical name string. m is estimated from
unsupervised leave one out seeds instead and EM fits only the mixing proportion.

**Victim resolution returns exactly zero.** Three remedies were tried, including
transferring the prior from the accused table and pooling all three tables. All
returned 0.0000. The table has a name, an age and nothing else.

**The corpus is synthetic and we generated it.** The oracle that bounds the
result is ours too. Every headline is measured on one fixture whose difficulty we
chose. No external validation exists and none is claimed.

**Three overclaims were caught and corrected in place.** A README that said it
regenerated when it did not, two studies presented as current that were stale,
and a ceiling stated to bound model families it cannot. A fourth was worse: a
gender channel measured on a corpus where gender could not be wrong, published as
a finding, then corrected by modelling the error rate and measuring again. It was
worth about half what was first claimed.

**36 of the 150 gold SQL queries were broken** when first shipped, referencing
columns that do not exist. They had never been executed. They are now, on every
run, and the build fails if one does not parse.
"""

NOT_BUILT = """**The 150 question gold set exists and its accuracy does not.** Answering the
questions from free text needs a natural language layer. No language model runs
anywhere in this system, so there is nothing to run the set through. The deck
claimed 74 per cent correct. That figure has no measurement behind it and is not
repeated.

**The query console is structured, not natural language.** You pick a question
and fill in its parameters, and it shows you the SQL it stands for.

**Kannada is interface translation only.** Navigation, panel titles, column
headers, status words and buttons. Explanatory prose stays in English, because a
machine assisted rendering of a technical argument would be worse than English
for a reader who has both. Kannada natural language querying and Kannada speech
are not built. The Kannada that changes a result is in Layer 1, where a name
written in Kannada folds to the same blocking key as its Latin spellings.

**Role scoping is a client side view filter.** It genuinely filters, and the
counts move with it, but the role comes from a dropdown and the JSON is served in
full. Catalyst Authentication and server side enforcement are both not built.

**Decisions live in one browser.** The review queue writes to localStorage. Two
officers on two machines do not see each other's work and clearing site data
clears the audit trail. Persisting to Catalyst Data Store is not built.

**Splink, RapidFuzz, Polars, leidenalg and sentence transformers are not used.**
The linkage model, the Indic phonetic folding and the string metrics are written
directly. That buys one specific thing: every weight in a merge score traces to a
fitted m and u, can be shown to an investigator as a list of contributions that
sums to the total, and can be argued with. A merge an officer cannot interrogate
is a merge they should not act on.
"""
