# IERB-P, the Indic Entity Resolution Benchmark for police records

A public task for resolving person identity in police records written in mixed
Kannada and Latin script, where the schema provides no cross case person key.

Version 1.0. Licence CC BY 4.0 for the data and the gold set, MIT for the code.

## Why this task exists

Entity resolution benchmarks are dominated by Latin script, Western name
structure and clean commercial records. Restaurants, citations, products,
census households.

Indian police records are none of those things. One person appears as
`ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ` at one station, `Ramesh S/o Krishnappa` at the next,
`R. Krishnappa` in a hurried entry, and `Kadu Ramesha` where the writer used
the locality moniker the man is actually known by. The record carries no
father's name field, no address, no phone and no biometric key. Given names are
heavily skewed, so a name match carries far less information than it does in a
Western corpus.

A method that scores well on the standard benchmarks does not necessarily
transfer. This task is built to find out.

## The task

Given a corpus of FIRs on the Karnataka State Police schema, partition the
`Accused` rows into people.

Input is every table in `corpus/`. The only identifying string on an `Accused`
row is `AccusedName`, free text, written in either script. `AccusedMasterID` is
scoped to one FIR and `PersonID` is a sort label within one FIR, so neither
identifies a person.

Output is one row per `AccusedMasterID` with a cluster identifier of your
choosing.

## What is provided

```
generate.sh        one command, produces corpus/ at a fixed seed
corpus/            the FIR tables, generated, not committed
gold/identities.csv    AccusedMasterID to true person, the gold partition
gold/pairs.csv         a labelled pair sample, for methods that train on pairs
gold/README.md         the format of both, in full
baseline.py        a reference implementation to run and beat
leaderboard.md     the methods measured so far
```

The corpus is synthetic. Identity is known by construction because a generator
emitted every row from a known person. No real FIR is used and none could be,
since the real record has no ground truth identity, which is the whole problem.

The generator is pure Python standard library, seed 4471, and produces byte
identical output on any machine.

## Constraints

Two rules, and both are about what the task is for.

**No protected attribute may be used as a feature.** `CasteID`, `ReligionID`
and `OccupationID` are present in the corpus because they are present in the
real schema. A submission that reads them as model input is not scored. This is
not a technicality. See `../docs/ethics.md`.

**Ground truth may not be read at inference.** `gold/` is for scoring and for
supervised training if your method needs it, but a method that reads it while
resolving is measuring itself.

## Scoring

Pairwise precision, recall and F1 over **every pair of accused rows in the
corpus**, not over a candidate shortlist. A pair is positive when both rows
carry the same gold person.

```
python score.py my_output.csv
```

Reported alongside:

- **F beta at 0.5**, which weights precision twice as heavily as recall. This is
  the primary ranking metric. A false merge asserts two people are one and
  propagates into everything computed downstream. A missed merge leaves the
  record where it already was. The two errors are not symmetric and the metric
  should not pretend they are.
- **Reduction ratio and pairs completeness**, if your method blocks. Pairs
  completeness is a hard ceiling on recall, so a method reporting high recall
  and low completeness has an error somewhere.
- **Wall clock**, on the stated hardware.

## Submitting a method

Open a pull request adding one row to `leaderboard.md` and a directory under
`methods/` containing your code and a README with the exact command that
reproduces your numbers. Include the hardware and the wall clock.

Numbers that cannot be reproduced from the repository are removed.

## Difficulty, and where it comes from

The corpus is built to be hard in the specific ways this domain is hard.

- **41% of true matching pairs are written in different scripts.** A method with
  no Indic handling cannot see them.
- **Given names follow a Zipf distribution.** The ten most common canonical
  names cover 14% of all rows.
- **Deliberate collisions.** Groups of two or three genuinely different people
  are forced onto an identical name in an identical district, half of them also
  with birth years within a year. There are 17,710 cross person pairs sharing an
  identical name string. A method that resolves on the name merges them and
  reports success.
- **A hard constraint is available for free.** Two `Accused` rows sharing one
  `CaseMasterID` are A1 and A2 of the same FIR and are provably different
  people. Methods are expected to use it.
- **A recall ceiling exists and is measured.** 98.12% of true pairs survive a
  reference blocking scheme. Recall above that implies you are not blocking, or
  you have a bug.

## The name vocabulary parameter

`generate.sh` accepts a name pool size. The default of 86 given and patronymic
forms is a deliberately hostile fixture, far narrower than any real
jurisdiction, and it depresses precision heavily by flooding every phonetic
block.

Methods should report at the default. Reporting additionally at 1000 or 3000
forms is encouraged, because the sensitivity is large and worth seeing. On the
reference implementation, precision moves from 0.5770 at 86 forms to 0.8427 at
3000.

## Licence and citation

Data and gold set, Creative Commons Attribution 4.0. Code, MIT.

The corpus is synthetic and contains no real person. It models the Karnataka
State Police FIR schema and is not affiliated with or endorsed by the Karnataka
State Police.
