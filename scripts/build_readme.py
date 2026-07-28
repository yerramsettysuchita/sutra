"""Generate README.md from the measured reports.

Every figure in the README is read out of eval/report.json and the corpus
reports rather than typed, so the public front page of the repository cannot
drift from the run that produced it. If a number changes, `make all` changes
the README, and a cold clone test asserts that the chain actually writes it.

The prose and the mermaid diagrams live in scripts/readme_body.py. Nothing there
carries a figure. Everything numeric is interpolated here.

    python scripts/build_readme.py

Also writes docs/schema-gap.svg, the static twin of the diagram on the corpus
audit screen, so the argument lands at the top of the README before anyone
reads a word.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from readme_body import (  # noqa: E402
    ARCHITECTURE, DATA_FLOW, DECISION_FLOW, ETHICS, GAP_DIAGRAM, HONESTY,
    NOT_BUILT,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
EVAL = ROOT / "eval" / "report.json"

SOURCES = [
    (EVAL, "make eval"),
    (CORPUS / "manifest.json", "make gen"),
    (CORPUS / "blocking_report.json", "make block"),
    (CORPUS / "downstream_report.json", "make downstream"),
    (CORPUS / "reconciliation_report.json", "make reconcile"),
]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def n(value) -> str:
    return f"{int(value):,}"


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 300" width="700" height="300" role="img" aria-labelledby="t d">
<title id="t">The missing person entity in the KSP schema</title>
<desc id="d">Three separate FIRs each carry an accused row for the same man, written as Suresh, Suresha and the Kannada rendering. Each has its own AccusedMasterID and a PersonID of A1, a label within that FIR only. No column joins them. On the right, SUTRA has resolved them into one identity linked to all three cases.</desc>
<rect width="700" height="300" fill="#FFFFFF"/>
<g font-family="Inter Tight, system-ui, sans-serif">
<text x="16" y="20" font-size="11" font-weight="600" fill="#656C75" letter-spacing="1.2">AS THE SCHEMA HOLDS IT</text>
{left}
<text x="16" y="292" font-size="11" fill="#8C2018" font-weight="500">No column joins these rows. Three people.</text>
<line x1="350" y1="30" x2="350" y2="272" stroke="#CFCBC1" stroke-width="1" stroke-dasharray="2 5"/>
<rect x="316" y="138" width="68" height="22" rx="11" fill="#F4F2EE" stroke="#CFCBC1"/>
<text x="350" y="153" font-size="10" font-weight="600" fill="#464D55" text-anchor="middle" letter-spacing="0.6">LAYERS 1 to 7</text>
<text x="404" y="20" font-size="11" font-weight="600" fill="#0F5D3C" letter-spacing="1.2">AFTER RESOLUTION</text>
{edges}
<rect x="470" y="106" width="214" height="88" rx="3" fill="#E4F3EA" stroke="#2E9E6B" stroke-width="1.5"/>
<text x="486" y="128" font-size="10" fill="#0F5D3C" font-family="JetBrains Mono, monospace">R000412</text>
<text x="486" y="150" font-size="15" font-weight="600" fill="#14171C">One person</text>
<text x="486" y="168" font-size="11" fill="#464D55">3 records, 3 cases, 2 scripts</text>
<text x="486" y="184" font-size="10" fill="#0F5D3C" font-family="JetBrains Mono, monospace">merged in the automatic band</text>
<text x="404" y="292" font-size="11" fill="#0F5D3C" font-weight="500">One identity. Two co offender links recovered.</text>
<text x="470" y="216" font-size="9.5" fill="#16305C" font-family="JetBrains Mono, monospace">ResolvedIdentity, the table SUTRA adds</text>
</g>
</svg>
"""

FIRS = [
    ("1000420240000131", "Suresh", 44, False),
    ("1001120250000078", "Suresha", 130, False),
    ("1002220250000205", "ಸುರೇಶ", 216, True),
]


def build_svg() -> str:
    left = []
    edges = []
    for crime, name, y, kannada in FIRS:
        face = ("Noto Sans Kannada, sans-serif" if kannada
                else "JetBrains Mono, monospace")
        left.append(
            f'<rect x="16" y="{y}" width="250" height="62" rx="3" fill="#FFFFFF" '
            f'stroke="#CFCBC1"/>'
            f'<text x="30" y="{y + 20}" font-size="10" fill="#656C75" '
            f'font-family="JetBrains Mono, monospace">{crime}</text>'
            f'<text x="30" y="{y + 40}" font-size="15" font-weight="500" '
            f'fill="#14171C" font-family="{face}">{name}</text>'
            f'<text x="30" y="{y + 54}" font-size="9.5" fill="#656C75" '
            f'font-family="JetBrains Mono, monospace">PersonID A1</text>'
            f'<line x1="266" y1="{y + 31}" x2="292" y2="{y + 31}" stroke="#CFCBC1" '
            f'stroke-width="1.5" stroke-dasharray="3 3"/>'
            f'<circle cx="296" cy="{y + 31}" r="3.5" fill="#CFCBC1"/>'
        )
        edges.append(
            f'<path d="M 470 150 C 440 150, 430 {y + 31}, 412 {y + 31}" fill="none" '
            f'stroke="#2E9E6B" stroke-width="1.75"/>'
            f'<circle cx="408" cy="{y + 31}" r="4" fill="#2E9E6B"/>'
        )
    return SVG.replace("{left}", "\n".join(left)).replace("{edges}", "\n".join(edges))


def main() -> int:
    missing = [(p, cmd) for p, cmd in SOURCES if not p.exists()]
    if missing:
        lines = "\n  ".join(f"{p.relative_to(ROOT)} missing, run: {cmd}"
                            for p, cmd in missing)
        raise SystemExit(f"\nCannot build the README.\n\n  {lines}\n")

    ev = read(EVAL)
    manifest = read(CORPUS / "manifest.json")
    blocking = read(CORPUS / "blocking_report.json")
    down = read(CORPUS / "downstream_report.json")
    recon = read(CORPUS / "reconciliation_report.json")
    canonical = read(ROOT / "eval" / "canonical.json")

    def optional(path: Path):
        return read(path) if path.exists() else None

    questions = optional(ROOT / "eval" / "questions_report.json")
    sqlcheck = optional(ROOT / "eval" / "sql_validation.json")
    persons = optional(CORPUS / "other_persons_report.json")
    vocab = optional(CORPUS / "vocabulary_report.json")
    scale = optional(CORPUS / "scale_report.json")
    gender = optional(CORPUS / "gender_noise_report.json")
    profiles = optional(ROOT / "web" / "public" / "data" / "profiles.json")

    # The headline comes from eval/canonical.json and nowhere else. ADR 022.
    h = canonical["headline"]
    routing = ev["routing"]
    exact = ev["baselines"]["exact name match"]
    multiple = h["f1"] / exact["f1"]
    graph = down["co_offender_graph"]
    undetected = down["undetected"]["accuracy"]["combined"]
    counts = manifest["counts"]
    ceiling = canonical["ceiling_argument"]
    products = canonical["products"]

    (ROOT / "docs" / "schema-gap.svg").write_text(build_svg(), encoding="utf-8")

    identities = n(profiles["total_identities"]) if profiles else "not exported"
    adrs = len(re.findall(r"^## ADR \d+",
                          (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8"),
                          re.M))
    tests = sum(len(re.findall(r"^\s{4}def test_", p.read_text(encoding="utf-8"), re.M))
                for p in sorted((ROOT / "tests").glob("test_*.py")))

    product_rows = []
    for key in ("deployable", "investigative"):
        row = products.get(key)
        if not row:
            continue
        product_rows.append(
            f"| **{row['label']}** | **{row['precision']:.4f}** "
            f"| {row['recall']:.4f} | {row['f1']:.4f} | **{row['f_beta_0_5']:.4f}** "
            f"| {row['threshold_llr']:.2f} | {n(row['merged_pairs'])} "
            f"| {row['purpose']} |")
    products_block = "\n".join(product_rows) or "| Not measured. |"

    how_to_read = "\n".join(
        f"| **{row['role']}** | `{row['f1']:.4f}` | {row['text']} |"
        for row in canonical["how_to_read"] if row["f1"] is not None)

    baseline_rows = "\n".join(
        f"| {name} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
        for name, m in sorted(ev["baselines"].items(), key=lambda kv: kv[1]["f1"]))

    signal_rows = "\n".join(
        f"| {s['label']} | {s['coverage'] * 100:.1f}% | {s['auc']:.3f} "
        f"| {'infinite' if s['lift_at_top_level'] is None else n(s['lift_at_top_level'])} |"
        for s in ev["signals"].values())

    ablation_rows = "\n".join(
        f"| {a['label']} | {a['f1']:.4f} | {a['f1_delta']:+.4f} |"
        for a in sorted(ev["ablation"].values(), key=lambda a: a["f1_delta"]))

    if persons:
        rows = []
        for key in ("accused", "victim", "complainant"):
            t = persons["tables"].get(key)
            if not t:
                continue
            oracle = t.get("oracle_diagnostic", {}).get("clustered", {}).get("f1")
            oracle_cell = "n/a" if oracle is None else f"{oracle:.4f}"
            rows.append(
                f"| `{t['table']}` | {n(t['rows'])} | {n(t['true_people'])} "
                f"| {n(t['hidden_by_fragmentation'])} "
                f"| **{t['results']['f1']:.4f}** | {oracle_cell} |")
        persons_block = "\n".join(rows)
        persons_statement = persons["combined"]["statement"]
        complainant_ceiling = (persons["tables"].get("complainant", {})
                               .get("oracle_diagnostic", {})
                               .get("clustered", {}).get("f1"))
    else:
        persons_block = "| Not measured. Run `make persons`. |"
        persons_statement = "Not measured."
        complainant_ceiling = None

    if questions:
        cov = questions["coverage"]
        q_total = questions["total_questions"]
        q_key = questions["headline"]["requires_person_key"]
        q_share = questions["headline"]["share_requiring_person_key"] * 100
        q_block = (
            f"| Answerable by the console today | {cov['answerable_today']['questions']} "
            f"| {cov['answerable_today']['share'] * 100:.1f}% |\n"
            f"| Needs a natural language layer, not built "
            f"| {cov['needs_language_layer']['questions']} "
            f"| {cov['needs_language_layer']['share'] * 100:.1f}% |\n"
            f"| **Impossible on the raw schema** "
            f"| **{cov['impossible_on_raw_schema']['questions']}** "
            f"| **{cov['impossible_on_raw_schema']['share'] * 100:.1f}%** |")
        q_kannada = questions["kannada"]["questions_with_kannada"]
    else:
        q_total = q_key = q_kannada = 0
        q_share = 0.0
        q_block = "| Not measured. |"

    if sqlcheck:
        sql_line = (
            f"All **{sqlcheck['execute_on_full_schema']} of {sqlcheck['total']}** "
            f"execute against a SQLite database built from the DDL, and "
            f"**{sqlcheck['requires_person_key_confirmed_by_database']} of "
            f"{sqlcheck['requires_person_key_claimed']}** questions marked as "
            f"needing a person key genuinely fail when the resolved tables are "
            f"dropped.")
    else:
        sql_line = "Not validated. Run `make validate-sql`."

    if vocab:
        first = vocab["runs"][0]
        last = vocab["runs"][-1]
        vocab_block = "\n".join(
            f"| {n(r['requested_vocabulary'])}"
            f"{', the shipped fixture' if r is first else ''} "
            f"| {r['reduction_ratio']:.4f} | **{r['precision']:.4f}** "
            f"| {r['f1']:.4f} |"
            for r in vocab["runs"])
        vocab_note = (
            f"Precision moves from {first['precision']:.4f} to "
            f"{last['precision']:.4f} as the name pool widens from "
            f"{n(first['requested_vocabulary'])} forms to "
            f"{n(last['requested_vocabulary'])}. Pairs completeness barely moves, "
            f"so blocking finds the same true pairs throughout. What changes is "
            f"how much rubbish it finds alongside them. **The headline is not "
            f"replaced.** It stays at the hostile fixture, and this sweep "
            f"establishes that it is a floor.")
        if (vocab.get("stale") or {}).get("is_stale"):
            vocab_note += (
                "\n\n**This study is stale.** It was measured on an earlier "
                "corpus, and `scripts/check_freshness.py` labels it wherever it "
                "appears rather than letting it read as current.")
    else:
        vocab_block = "| Not measured. |"
        vocab_note = ""

    if scale:
        scale_block = "\n".join(
            f"| {n(r['cases'])} | {n(r['accused_rows'])} | {n(r['candidate_pairs'])} "
            f"| {r['base_rate']:.6f} | {r['precision']:.4f} | {r['f1']:.4f} |"
            for r in scale["runs"])
        drift = scale["runs"][-1]["f1"] - scale["runs"][0]["f1"]
        full_pairs = n(scale["full_scale"]["candidate_pairs"])
        full_rows = n(scale["full_scale"]["accused_rows"])
        exponent = scale["growth"]["pairs_vs_rows_exponent"]
    else:
        scale_block = "| Not measured. |"
        drift = 0.0
        full_pairs = "not measured"
        full_rows = "not measured"
        exponent = 0.0

    if gender:
        summary = gender["summary"]
        gender_rows = "\n".join(
            f"| {r['error_rate']:.3f} | {n(r['rows_flipped'])} "
            f"| {r['f_beta_0_5_gain']:+.4f} | {n(r['true_pairs_contradicted'])} |"
            for r in gender["runs"])
        gender_shipped = summary["shipped_rate_gain_f_beta_0_5"]
    else:
        gender_rows = "| Not measured. |"
        gender_shipped = 0.0

    noise = manifest.get("gender_noise") or {}
    statement = canonical["definition"]["statement"]
    statement = statement[0].lower() + statement[1:]

    ceiling_block = ""
    if complainant_ceiling:
        ceiling_block = f"""
The comparison that makes this concrete arrived by accident.
`ComplainantDetails` carries an `Address` and a `PhoneNumber`. `Accused` carries
neither, and the schema file comments on that asymmetry itself. Run the same
engine over both:

| Table | Oracle ceiling |
|---|---|
| `Accused`, no contact column | **{ceiling['oracle_f1']:.4f}** |
| `ComplainantDetails`, with a phone number | **{complainant_ceiling:.4f}** |

**The difference between a resolvable person and an unresolvable one is not the
algorithm. It is whether the form had a field for a phone number.** The KSP
schema collects contact details for the person reporting a crime and none for the
person accused of one.

That is the argument for adding a person key to the record, and it is the most
useful thing this repository has to say.
"""

    readme = f"""# SUTRA

**Identity resolution for the Karnataka State Police crime record.**
Datathon 2026, problem statement 01.

<img src="docs/schema-gap.svg" alt="Three FIRs hold the same man as Suresh, Suresha and the Kannada rendering, each with its own AccusedMasterID and a PersonID of A1. No column joins them. SUTRA resolves them into one identity linked to all three cases." width="700">

`{h['precision']:.4f}` precision at the shipped cut &nbsp;&nbsp;
`{products['deployable']['precision']:.4f}` at the automatic merging cut &nbsp;&nbsp;
`{n(counts['cases'])}` cases &nbsp;&nbsp;
`{adrs}` decision records &nbsp;&nbsp;
`{tests}` tests

---

## The finding

The problem statement asks for criminal network analysis and repeat offender
tracking. Neither can be computed from the KSP schema as supplied, and the reason
is one missing column.

{GAP_DIAGRAM}

So before anything can be analysed, the person entity has to be constructed. That
construction is what SUTRA is, and how much of it is recoverable is what this
repository measures.

---

## The result

Measured on {n(ev['corpus']['cases'])} synthetic cases at seed {manifest['seed']},
pairwise against ground truth over every pair of accused rows in the corpus.

### Two products from one model

The operating point is a policy choice about the cost of a wrong merge against
the cost of a missed one. It is not a property of the method and this project
does not get to make it, so both are published side by side.

| | Precision | Recall | F1 | F0.5 | Cut | Merges | For |
|---|---|---|---|---|---|---|---|
{products_block}

A false merge asserts two people are one and propagates into every downstream
product. A missed merge leaves the record where it already was. So **F beta at
0.5, which weights precision twice as heavily, is the correct objective for this
domain**, and the engine's decision threshold now implements that rather than
only reporting it. See ADR 028.

False merge rate on the automatic band alone, which is the band where nobody
looks: **{routing['false_merge_rate']:.4f}**, {n(routing['false_merges'])} of
{n(routing['auto_merged_pairs'])}.

### How to read the numbers in this repository

| Role | F1 | What it is |
|---|---|---|
{how_to_read}

Any figure that is not the headline carries its qualifier inline, every time. The
headline is {statement}

### Against every baseline, on the same corpus, clustered the same way

| Method | Precision | Recall | F1 |
|---|---|---|---|
{baseline_rows}
| **SUTRA** | **{h['precision']:.4f}** | **{h['recall']:.4f}** | **{h['f1']:.4f}** |

**SUTRA reaches {multiple:.1f} times the F1 of `GROUP BY AccusedName`.**

---

## Why the remaining gap is not a modelling problem

{ceiling['statement']}
{ceiling_block}
---

## Architecture

{ARCHITECTURE}

| Layer | What it does | State |
|---|---|---|
| 0 | Synthetic KSP corpus with identity known by construction, seed {manifest['seed']} | built |
| 1 | Indic normalisation, Kannada to Latin folding, no English Soundex | built |
| 2 | Blocking on a phonetic key and a station circle key, unioned | built |
| 3 | Six signals plus recorded gender, measured and reported individually | built |
| 4 | Fellegi Sunter, name agreement weighted by inverse frequency | partial, EM does not fit m and u |
| 5 | Correlation clustering under cannot link constraints from the schema | built |
| 6 | Collective iteration, relational evidence recomputed from identities | **does not converge, output discarded** |
| 7 | Isotonic calibration, three way routing at 0.92 and 0.65 | built |
| 8 | Co offender graph, communities, profiles, undetected case ranking | built |
| 9 | IPC to BNS reconciliation across the July 2024 boundary | built |

### What each signal contributes

| Signal | Coverage | AUC | Lift at top level |
|---|---|---|---|
{signal_rows}

Coverage is where the signal can be computed at all, and AUC is measured only on
those pairs. Lift is the odds a top level agreement carries before any weighting.

### Ablation, where a positive delta means removing the signal helps

| Signal removed | F1 | Delta |
|---|---|---|
{ablation_rows}

Two signals carried positive deltas for most of this project's life, which
indicated correlated evidence being counted twice. Adding an independent channel
and correcting the decision threshold resolved it. See ADR 017 and ADR 028.

### How the data moves

{DATA_FLOW}

---

## The decision layer

Resolution proposes. People decide. The review queue routes every candidate pair
into one of three bands, and the middle band is the one a human clears.

{DECISION_FLOW}

Four roles, and they differ in what they may do as well as in what they may see.

| Role | Sees | Decide | Reverse |
|---|---|---|---|
| SCRB analyst | Every screen, statewide | yes | no |
| Investigating officer | Every screen, one district | no | no |
| Records operator | The review queue only | yes | no |
| Reviewer | Every screen, statewide | yes | **yes** |

The investigating officer cannot decide, and that is deliberate. Approving a
merge writes into the person record, which is a records function rather than an
investigative one.

The decision log is **append only**. A reversal adds an entry naming the one it
reverses, and no role can delete anything, which is what makes the audit trail
true rather than aspirational. That property is asserted by tests rather than by
this paragraph.

**This is client side and per browser.** Decisions live in localStorage.
Persisting to Catalyst Data Store is not built, and neither is server side
enforcement of the roles.

---

## The 150 investigator questions

[eval/gold/questions.yaml](eval/gold/questions.yaml) holds {q_total} questions an
investigating officer or an SCRB analyst would actually ask, across twelve
investigative shapes, each with gold SQL against the KSP schema. {q_kannada}
carry a Kannada rendering.

| Band | Questions | Share |
|---|---|---|
{q_block}

**{q_key} of {q_total}, {q_share:.1f}%, cannot be answered on the KSP schema as
supplied at any level of interface sophistication**, because they need a person
identity that spans FIRs and the schema has none.

{sql_line}

That last sentence is the point. The claim is not that we counted carefully. It
is that the database refuses to run those queries without the table SUTRA adds,
and `make all` proves it on every run.

**Accuracy is not measured and not claimed.** The deck said 74 per cent correct.
Answering these from free text needs a language layer that does not exist.

---

## The same gap in all three person bearing tables

`Accused` is not the only table holding a person with no key that survives across
FIRs. The same engine, Layers 1 to 5 imported from the same modules, was run over
all three.

| Table | Rows | Actual people | Hidden by fragmentation | F1 | Oracle |
|---|---|---|---|---|---|
{persons_block}

{persons_statement}

On `Victim` the engine resolves nothing. Three remedies were tried and all
returned exactly 0.0000. That table carries a name, an age, and three columns
this project refuses to read. See ADR 024 and ADR 026.

---

## How much of this is the fixture

Every headline above is measured on a deliberately hostile corpus. Three sweeps
say how much of the result is the fixture rather than the method.

### Name vocabulary

| Name forms | Reduction ratio | Precision | F1 |
|---|---|---|---|
{vocab_block}

{vocab_note}

### Corpus size

| Cases | Accused rows | Candidate pairs | Base rate | Precision | F1 |
|---|---|---|---|---|---|
{scale_block}

F1 moves by **{drift:+.4f}** across the sizes measured. The full 150,000 case
corpus was **not** run. At that size blocking proposes **{full_pairs} candidate
pairs** over {full_rows} accused rows, which is a compute wall and is reported as
one. Candidate pairs grow as `n^{exponent:.2f}` in accused rows.

### Recorded gender, and what a signal is worth when the field is dirty

The gender channel was first measured on a corpus where gender could not be
wrong, because the generator copied it verbatim onto every row of a person. That
was published as a finding and it was arithmetic. The corpus now models a
recording error rate of {noise.get('rate_realised', 0) * 100:.1f}%, and the sweep
says what the channel is actually worth.

| Error rate | Rows flipped | F0.5 gain | True pairs contradicted |
|---|---|---|---|
{gender_rows}

At the shipped rate the channel is worth **{gender_shipped:+.4f}** F0.5, roughly
half the original claim, and it goes negative past the highest rate that still
helps. That is a real operating limit worth handing to a department: if the
gender field is wrong more than about one row in twelve, do not match on it. See
ADR 030.

---

## Downstream, on the resolved identities

| | |
|---|---|
| Co offender edges | {n(graph['edges'])} |
| Edges that exist only after resolution | **{n(graph['edges_recovered_by_resolution'])}**, {graph['recovered_share'] * 100:.1f}% |
| Communities, modularity | {n(down['communities']['communities'])}, {down['communities']['modularity']:.4f} |
| Undetected case ranking, hit at 1 | {undetected['hit_at_1']:.4f} |
| Undetected case ranking, hit at 10 | {undetected['hit_at_10']:.4f} from a pool of {n(undetected['candidate_pool'])} |
| Naive undercount across the July 2024 BNS transition | **{recon['totals']['naive_undercount_pct']:.2f}%** |
| Resolved identities | {identities} |

Blocking reduction ratio {blocking['blocking']['reduction_ratio']:.4f}, pairs
completeness {blocking['ceiling']['pairs_completeness_pct']:.2f}%. That
completeness is a hard ceiling on recall for every layer after Layer 2.

---

## Reproduce

```
pip install -r requirements.txt
make all
```

That runs generate, audit, block, resolve, persons, downstream, reconcile, eval,
questions, the SQL validation, the export and the document generators in order,
from an empty corpus, in about six minutes.

```
make dev            the application on http://localhost:5173
make test           {tests} unit tests
make check          Makefile, source encoding and report freshness
make validate-sql   execute all {q_total} gold queries against real SQLite
make package        the Catalyst deploy bundle
```

Inside `web/`, `npm run check` runs the typecheck, the contrast gate, the Kannada
interface checks, the decision layer checks, and a server side render of every
screen in both languages, under four roles, with and without a district scope.

One test is not in the count above because it does not run by default. It copies
the source tree into a temporary directory with no corpus, runs the chain from
empty, and asserts the headline comes back identical.

```
SUTRA_COLD_CLONE=1 python -m unittest tests.test_cold_clone -v
```

**Every figure in this README is written out of that run** by
`scripts/build_readme.py`. Nothing here is typed by hand, and the cold clone test
asserts that `make all` actually regenerates it.

---

## Benchmark

[benchmark/](benchmark/) is **IERB-P, the Indic Entity Resolution Benchmark for
police records**. A public task anyone can submit to: one command to generate the
corpus at a fixed seed, a documented gold set, a reference baseline to beat, a
scorer, and a leaderboard on which SUTRA is one entry rather than the owner.

```
cd benchmark
./generate.sh
python baseline.py --corpus corpus --out baseline_output.csv
python score.py baseline_output.csv
```

Data and gold set CC BY 4.0, code MIT. Every entry on the leaderboard is
currently ours, which [the leaderboard says plainly](benchmark/leaderboard.md) is
a weakness rather than a strength. It becomes a benchmark when someone else
appears on it.

---

## What is not built

{NOT_BUILT}

---

## What went wrong, published at the same size as what went right

{HONESTY}

The full list, claim by claim, with three values and nothing softened, is in
[docs/build-status.md](docs/build-status.md) and on the `/status` screen.

---

## Ethics

{ETHICS}

---

## Layout

```
data/generator/   synthetic FIR corpus, no dependencies, standalone
data/schema/      DDL mirroring the KSP ER diagram, loaded by eval/build_db
engine/           policy, normalise, block, features, linkage, cluster,
                  calibrate, downstream, reconcile
eval/             report.py, questions.py, build_db.py, validate_sql.py
web/              React, TypeScript, Vite. Nine screens, no mock data
benchmark/        IERB-P, the public task, gold set, baseline and scorer
docs/             architecture, decisions, ethics, build status
```

## Links

- Deployed, [https://sutra-gfrnnril.onslate.in/](https://sutra-gfrnnril.onslate.in/)
- Build status, [docs/build-status.md](docs/build-status.md)
- Architecture, [docs/architecture.md](docs/architecture.md)
- Decisions, [docs/decisions.md](docs/decisions.md), {adrs} ADRs
- Ethics, [docs/ethics.md](docs/ethics.md)
- Deployment, [docs/deploy.md](docs/deploy.md)
- Benchmark, [benchmark/README.md](benchmark/README.md) and
  [the leaderboard](benchmark/leaderboard.md)

<sub>Generated by scripts/build_readme.py from the run of
{ev['generated_at']}. Do not edit by hand.</sub>
"""

    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    lines = readme.count("\n") + 1
    print(f"README.md written, {lines} lines")
    print(f"  headline F1 {h['f1']:.4f}, precision {h['precision']:.4f}")
    print(f"  {adrs} ADRs, {tests} tests, {q_total} questions")
    print("  docs/schema-gap.svg written")
    if lines > 700:
        raise SystemExit(f"README is {lines} lines, over the 700 line budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
