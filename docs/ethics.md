# Ethics

This document states what SUTRA refuses to build, why, and how the refusal is
enforced in code rather than in good intentions.

## 1. The line

SUTRA resolves identity. It does not assess people.

Resolving identity means deciding that two existing records describe one person.
The claim is about the record, it is auditable against evidence already in the
FIR, and it is reversible.

Assessing people means producing a score, a rank or a category that says
something about a person's future conduct or disposition. The claim is about the
person, it cannot be audited against anything, and by the time it is wrong it has
already been acted on.

SUTRA does the first. It will not do the second.

## 2. What is not built

**No individual predictive risk scoring.** No model that outputs a number
representing how likely a named person is to commit a future offence, be
involved in violence, or reoffend. No heat list, no watch list, no threat score.

**No behavioural profiling.** No inference of disposition, propensity,
affiliation or character from the record. Modus operandi similarity in Layer 3e
compares one case narrative to another case narrative. It never compares a case
to a person, and it never produces a persistent attribute of a person.

**No protected attribute features.** `CasteID`, `ReligionID` and `OccupationID`
exist in the KSP schema and are therefore present in our synthetic corpus,
because a generator that silently dropped them would misrepresent the data. They
are never read by any model, scoring function or ranking in this system.

## 3. The precedent

Two programmes are the reason these limits are written down rather than assumed.

### Chicago, the Strategic Subject List

The Chicago Police Department ran an algorithmic risk list, developed with the
Illinois Institute of Technology and generally known as the Strategic Subject
List or the heat list, from roughly 2012. It scored individuals on their
predicted likelihood of involvement in violent crime, as offender or as victim.

Three findings from its evaluation and audit matter here.

A RAND evaluation of the early deployment found no measurable effect on
victimisation, the outcome the programme existed to reduce. It did find that
people on the list were more likely to be arrested. The intervention that
actually resulted from a risk score was enforcement attention, whatever the
stated intent was.

The Chicago Office of the Inspector General reported that the list had grown to
encompass a very large population, in the hundreds of thousands, and that a
substantial share of those scored had no arrest and no shooting victimisation in
their history at all. A tool aimed at a small violent core had, in operation,
enrolled a significant fraction of a city.

The department discontinued the programme around 2019 and 2020.

The lesson is not that the model was badly fitted. It is that a person level risk
score creates an operational demand for names, that demand expands the list far
past its original scope, and the only available response to a high score turns out
to be enforcement. Scope creep is the default behaviour of this class of system,
not a failure mode of one implementation.

### Los Angeles, PredPol and LASER

The Los Angeles Police Department ran place based predictive policing with
PredPol and a parallel chronic offender programme called LASER, which maintained
scored lists of individuals.

The LAPD Inspector General audited LASER in 2019 and found inconsistent
application of the selection criteria across divisions, along with people
remaining on lists without a clear basis. LASER was discontinued that year. The
PredPol deployment ended in 2020.

Separately, the methodological critique of place based prediction, made most
clearly by Lum and Isaac in 2016, identified the feedback loop. The model is
trained on recorded crime. Recorded crime is a function of where police were
sent. The model sends police where crime was recorded. The system therefore
converges on confirming its own history rather than on discovering crime, and it
does so most strongly for offence types where recording depends heavily on
enforcement presence.

The lesson for us is direct. Our co offending graph is built from arrest and FIR
records. Arrest records reflect enforcement attention, not offending. Any product
built on that graph inherits the bias in that attention. This is survivable for
identity resolution, because we are only claiming that two records are one person
and that claim is checkable. It is not survivable for prediction about a person,
because there is nothing to check the claim against.

## 4. The undetected case matcher, and why it is on the right side of the line

Layer 8 ranks candidate suspects for cases where `ChargesheetDetails.cstype` is
`C`, undetected. This is the closest thing in SUTRA to prediction and the
distinction has to be exact.

What it does. Given an unsolved case, it retrieves people already on record for
similar method, in plausible territory, within a plausible time window, and ranks
those existing records by similarity of case to case.

What it does not do. It does not compute a property of a person. It does not
persist a score against anyone. It does not rank the population. Ask it about a
person and it has nothing to say, because the object it scores is a pair of
cases, not a human being.

The output is a retrieval result over records that an investigator could have
found by hand with unlimited time. It is a search index, not a judgement.

Four constraints hold it there.

Output is always a ranked list of case to case similarities with the contributing
evidence shown, never a bare name with a number.

Nothing is persisted to a person record. The ranking exists for the case that
requested it.

Protected attributes are excluded from the ranking exactly as they are excluded
everywhere else.

The interface states, on the panel, that this is an investigative lead requiring
independent corroboration, and states it in the copy rather than in a tooltip.

## 5. Enforcement

The exclusion is a code artefact, in `engine/policy.py`.

```python
EXCLUDED_FEATURE_COLUMNS = frozenset({
    "CasteID", "Caste", "CasteName",
    "ReligionID", "Religion", "ReligionName",
    "OccupationID", "Occupation", "OccupationName",
})
```

`assert_no_excluded_features(columns, context)` raises `ExcludedFeatureError` if
any excluded column reaches a feature matrix, a model input or a ranking. Every
feature construction path calls it. A test asserts that it raises, so removing
the guard breaks the build rather than quietly widening the model.

This is deliberately a hard failure and not a warning. A warning in a log is a
control that works until the day someone is not reading the log.

## 6. Honest reporting

The evaluation reports false merge rate and refusal rate without rounding in our
favour.

A false merge is the characteristic harm of this system. It asserts that two
people are one person, and it propagates, because every downstream product,
network, community, profile, candidate ranking, inherits it. If SUTRA merges two
different men named Manjunath, it does not produce a slightly worse graph. It
produces a fictional person with a fabricated criminal history, and everything
computed about that person afterwards is about nobody.

That number therefore goes in the deck at whatever value it takes.

## 7. Standing limitations

Stated plainly, because a limitations section that only lists things we have
already fixed is marketing.

The corpus is synthetic. Ground truth is known by construction, which is what
makes measurement possible, and it means the reported numbers are an upper bound
on real world performance. Real FIR text is messier than any generator.

Arrest data reflects enforcement attention. Section 4 applies to us too. The co
offending graph is a graph of who was arrested together, which is not the same as
who offends together.

Resolution is nightly. The graph an analyst sees can be hours stale, and the
interface says so on every panel.

Name frequency weighting is computed over the corpus. Name frequency varies by
region and community within Karnataka, and a single corpus wide frequency table
will be better calibrated for some populations than others. We have not measured
that disparity. It should be measured before anything like this touches real
data.
