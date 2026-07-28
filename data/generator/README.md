# Synthetic KSP FIR corpus generator

Standalone deliverable. Pure Python standard library, no dependencies, no
network. Seed fixed at 4471, so any two runs on any two machines produce
identical output.

```
python -m data.generator.generate --cases 5000
python -m data.generator.audit
```

Output lands in `data/corpus`, one CSV per table on the KSP schema, plus
`data/corpus/ground_truth`.

## Why this exists

Entity resolution cannot be evaluated without ground truth identity. The real
KSP corpus has none, which is exactly the problem SUTRA solves, and therefore it
also cannot be used to measure whether SUTRA solved it.

So the corpus is generated from known synthetic people, and the generator writes
the map. Every accused row can be traced to the person who produced it, and to
the specific corruption applied on the way.

This is a measuring instrument, not a stand in for real data. Numbers measured
on it are an upper bound on real world performance. Real FIR text is messier
than any generator.

## What is planted

Everything the engine is meant to find, and everything it is meant to resist.

**Identity fragments.** One person, many renderings. Kannada script and Latin
transliteration of the same name. The patronymic written out, abbreviated to an
initial, moved to the front, or dropped. `S/o`, `s/o.`, `ತಂದೆ`, `ಬಿನ್`, `@`,
`ಅಲಿಯಾಸ್`. Locality monikers such as `Kadu Ramesha`. Transliteration
alternations that actually occur, `Girish` against `Gireesh`, `Lakshmi` against
`Laxmi`, `Krishnappa` against `Krishnapa`, `Manjunath` against `Manjunatha`.
Whitespace, stray dots, and a zero width joiner arriving from a legacy paste.

**Station habit.** Each police station gets a house script preference, so a
station that writes Kannada keeps writing Kannada. Script divergence therefore
tracks jurisdiction divergence rather than being independent noise. That
correlation is what makes the problem hard in the way real data is hard.

**Birth year.** Each person has one, so implied birth year from
`year(CrimeRegisteredDate) - AgeYear` is consistent within recording noise. The
noise has a deliberate tail beyond the plus or minus two year tolerance, because
that is where the temporal signal genuinely fails and the engine must not
pretend otherwise.

**Territory.** Each person has a home station. Most offend near it. A minority
range widely, and those are the ones a station level system loses completely.

**Method.** Each person has a modus operandi family, and cases in a family share
vocabulary and structure in `BriefFacts` while varying in detail. Fifteen per
cent of narratives are written in Kannada, because real stations do.

**Relationships.** Co offending groups recur, so shared co accused is real
evidence. Arresting officers repeat within a station, so shared officer is weak
but genuine evidence.

**The legislative transition.** Cases before 1 July 2024 cite IPC. Cases after
cite the BNS successor section for the same conduct. `Section.SuccessorSectionID`
carries the mapping.

## What is planted against us

**Name collisions.** 110 groups of two or three distinct people forced onto an
identical canonical name in an identical district. Half the groups also have
birth years within a year of each other, which removes the temporal signal too
and leaves only territory, method and relational evidence to separate them.

These are the trap. A system that resolves on the name string merges them and
reports a clean result. They are the denominator of the false merge rate.

**Frequency skew.** Given names are sampled with Zipf like weights, so
`Manjunath` and `Ramesh` dominate exactly as they do in Karnataka. Agreement on
a common name is genuinely weaker evidence than agreement on a rare one, and
without that skew the inverse name frequency correction in Layer 4 could not be
demonstrated.

**Unrecoverable pairs.** Some true pairs are given no surviving channel at all.
They are not a bug. They set the honest recall ceiling, and `audit.py` reports
that ceiling rather than hiding it.

## Ground truth files

| File | Contents |
|---|---|
| `persons.csv` | Every synthetic person, canonical name in both scripts, birth year, home station, modus operandi family, active window |
| `identity_map.csv` | Every accused row mapped to its person, with the variant, script, perturbations and noise that produced the rendered string |
| `undetected_truth.csv` | The hidden perpetrator of each `cstype = C` case |
| `name_collisions.csv` | Planted hard negatives |
| `gangs.csv` | Planted co offending groups |

`identity_map.csv` carries the full provenance of each rendering, so evaluation
can answer the question that actually matters. Not "what is the F1" but "which
corruption is the engine losing to".

Ground truth is never read by the engine. Only `eval/` touches it.

## A note on the naming convention field

`persons.csv` carries a `use_bin` flag internally, which selects the `ಬಿನ್`
patronymic marker used in some communities. It is a property of how a name is
written and it appears in real records. It is never a feature. It is present
because a system that quietly ignores the ways Indian names are actually written
is a system that will fail on the records it is given, and because it shows that
name derived proxies for protected attributes exist and have to be consciously
not exploited. See `docs/ethics.md`.
