# Decisions

Architecture decision records. Newest at the bottom. Each records what was
chosen, what was rejected, and what it costs us.

---

## ADR 001, treat missing person identity as the problem statement

**Status** accepted, Phase 0

**Context.** The brief asks for conversational access to the KSP crime database,
including criminal network analysis and repeat offender tracking. The schema has
no cross case person key. `Accused.AccusedMasterID` is case scoped and
`PersonID` is a within FIR label.

**Decision.** Build the identity layer as the product. Natural language access is
the surface over a corrected network, not the deliverable in itself.

**Rejected.** Building a competent text to SQL system over the raw schema. It
would demonstrate well and answer network questions wrongly, because
`GROUP BY AccusedName` both over splits and over merges. The failure would be
invisible in a demo and consequential in use.

**Cost.** More engineering before anything is visible on screen, and a harder
story to tell in the first thirty seconds of a pitch.

---

## ADR 002, batch resolution and a read only online path

**Status** accepted, Phase 0

**Context.** Expectation maximisation over all comparison vectors, iteration to a
fixed point, and sentence embeddings are corpus level computations. Catalyst
functions are request scoped.

**Decision.** Resolution runs locally as a batch job and exports JSON. Catalyst
serves the JSON. Scheduled re resolution uses Catalyst Job Scheduling.

**Rejected.** Online incremental resolution. Correct incremental entity
resolution requires maintaining the frequency tables, the fitted m and u, and the
collective iteration state under concurrent writes. That is a much larger system
and it would be a worse one at this scale.

**Cost.** Staleness between batch runs. Stated in the interface rather than
hidden, with the resolution timestamp on the audit strip of every panel.

---

## ADR 003, no English Soundex anywhere in the engine

**Status** accepted, Phase 0

**Context.** Soundex is the default reflex for phonetic name matching and it is
wrong for Kannada. It was built for American census surnames. It discards vowels,
which are phonemic in Kannada, and it does not distinguish retroflex from dental
or aspirated from unaspirated, which are the distinctions that separate names.

**Decision.** Layer 1 uses an Indic phonetic scheme operating on a cross script
folded representation. Soundex appears only as a baseline in the evaluation.

**Cost.** More work, and a component with no off the shelf reference
implementation we can point at.

---

## ADR 004, union blocking rather than intersection

**Status** accepted, Phase 0

**Context.** Two blocking key families, Indic phonetic and territorial. Combining
by intersection is cheaper. Combining by union is safer.

**Decision.** Union. An offender who travels breaks the territorial key. An
offender written in another script breaks the phonetic key. Intersection loses
both.

**Cost.** A larger candidate set and a worse reduction ratio. Both are reported.
Pairs completeness is the number that matters, because it is a hard ceiling on
recall for every layer after it.

---

## ADR 005, connected components plus local search for constrained clustering

**Status** accepted, Phase 0

**Context.** Correlation clustering with cannot link constraints is NP hard. The
cannot link edges come free from the schema, since two Accused rows on one
`CaseMasterID` are provably different people.

**Decision.** Connected components over the auto merge threshold, then local
search that repairs each constraint violation by splitting the offending cluster
on its weakest internal edge, iterated until no violation remains or a cap is
hit.

**Rejected.** Integer programming, which does not scale to corpus size here.
Spectral relaxation, which does not naturally accept hard cannot link edges.
Ignoring the constraint, which discards the single most reliable structural fact
in the data.

**Cost.** No optimality guarantee. The relaxation can split a cluster at a place
a global optimiser would not. Clusters that cannot be repaired within the cap are
escalated as conflicts to the review queue rather than resolved silently, and the
interface shows that case explicitly.

---

## ADR 006, frequency adjusted Fellegi Sunter over a learned pairwise classifier

**Status** accepted, Phase 0

**Context.** A gradient boosted classifier on pair features would probably score
well on the synthetic gold set.

**Decision.** Classical Fellegi Sunter with m and u fitted by expectation
maximisation, and the name agreement weight scaled by inverse name frequency.

**Reasoning.** The output is a log likelihood ratio decomposable into per feature
contributions, which is what the review queue has to display for a human to make
a decision. A classifier gives a score and a feature attribution that is an
approximation of its own behaviour. For a system where every merge has to be
explainable to an investigator, an additive evidence model is not a compromise,
it is the requirement. Expectation maximisation also fits without labels, which
matters because real deployment has no gold set.

**Known violation.** Fellegi Sunter assumes conditional independence between
features. Lexical and phonetic agreement are correlated by construction, and
spatial and relational evidence are correlated through station catchment. This
inflates weight magnitudes for pairs that agree on correlated channels.

**Mitigation.** Layer 7 isotonic calibration absorbs systematic miscalibration
without modelling the dependence structure. The residual effect is that raw
weights are not directly interpretable as bits of evidence. Calibrated
probabilities are what the routing and the interface use.

---

## ADR 007, isotonic regression over Platt scaling for calibration

**Status** accepted, Phase 0

**Decision.** Isotonic.

**Reasoning.** Platt scaling assumes the score to probability relationship is
sigmoid. Here it is not, because the frequency adjustment stretches the upper
tail unevenly. Isotonic assumes only monotonicity, which is the one property
Fellegi Sunter weights genuinely have.

**Cost.** Isotonic needs more calibration data and can overfit in sparse score
regions. Fitted with cross validation and the calibration curve is published in
the evaluation report.

---

## ADR 008, Leiden over Louvain for community detection

**Status** accepted, Phase 0

**Decision.** Leiden.

**Reasoning.** Louvain can return communities that are internally disconnected,
which for a criminal network means presenting a group that has no actual link
between its halves. Leiden guarantees connected communities. For this
application that guarantee is the whole reason to run community detection at
all.

---

## ADR 009, asymmetric routing thresholds

**Status** accepted, Phase 0

**Decision.** Automatic merge above 0.92, review between 0.65 and 0.92, reject
below 0.65.

**Reasoning.** The errors are not symmetric. A false merge asserts that two
people are one, propagates into every downstream product, and can put a wrong
name in front of an investigator. A missed merge leaves the record where it
already was, which is the status quo the department is in today. So the automatic
band is narrow and conservative and the review band is deliberately wide.

**Cost.** Review queue volume. That is the intended trade and the queue depth is
reported.

---

## ADR 010, generate the protected attribute columns rather than omit them

**Status** accepted, Phase 0

**Context.** `CasteID`, `ReligionID` and `OccupationID` are in the KSP schema. We
will never use them as features.

**Decision.** The generator emits them. The engine refuses them at a guard in
`engine/policy.py` that raises rather than warns.

**Reasoning.** A generator that omitted them would misrepresent the schema and
would make the exclusion untestable, since there would be nothing for the guard
to catch. Emitting them and blocking them in code is a demonstrable control. A
column that is absent proves nothing. A column that is present and provably
never read proves the control works.

---

## ADR 011, pure standard library for the corpus generator

**Status** accepted, Phase 0

**Decision.** No third party imports in `data/generator/`.

**Reasoning.** The generator is named in the brief as a standalone headline
deliverable. Anyone should be able to clone the directory and run it with a
stock Python. Nothing it does, seeded sampling, string manipulation, Haversine
jitter, CSV writing, needs more than the standard library.

**Cost.** A hand written Zipf sampler and Haversine rather than numpy. Both are a
few lines and both are tested.

---

## ADR 012, co offending density is a parameter and not a constant

**Status** accepted, Phase 1. Supersedes an unrecorded tuning made in Phase 0.

**Context.** The Phase 0 audit showed shared co accused surviving on only 2.4% of
true matching pairs. Layer 3f relational evidence was close to vacuous and Layer
6 collective iteration had almost no edges to iterate on. We raised the co
offending density until the signal had mass, reaching 10.9%.

That was the wrong instinct. Tuning a generator until a feature looks useful
produces a feature that looks useful. The resulting ablation delta would have
measured our own constant.

**What the literature says.** Repeat co offending with the same accomplice is the
exception rather than the rule.

Charette and Papachristos, tracking co arrest dyads across eight years of Chicago
arrest records, find that co offenders rarely commit more than one offence
together, and that the longevity of co offending relationships is short, though a
small minority persists.

Sarnecki's Stockholm work on young delinquents puts roughly 2.5% of co offending
relationships persisting beyond six months.

Warr goes furthest, arguing that delinquent groups are so short lived that
speaking of groups at all is barely meaningful.

McGloin and colleagues, examining the stability of co offending among youthful
offenders, reach the same direction, that offenders more often take new
accomplices than reuse old ones.

**The measurable quantity.** None of those sources reports the statistic we had
been tuning, which was the share of true matching pairs sharing a co accused.
They report dyad recurrence, the share of co offending pairs who appear together
more than once. So that is the quantity the generator now reports and calibrates
against, in `dyad_recurrence()`.

**Measured, at 5,000 cases, seed 4471.**

| Preset | Dyad recurrence | Shared co accused on true pairs | Gangs |
|---|---|---|---|
| sparse | 1.02% | 1.05% | 100 |
| moderate | 3.54% | 4.68% | 197 |
| dense | 7.83% | 10.90% | 283 |

**Decision.** Default to `moderate`. Its 3.54% dyad recurrence sits just above
Sarnecki's 2.5% persistence figure, which is the right side to err on, because
any recurrence is a weaker condition than persistence beyond six months and
should therefore read slightly higher.

The Phase 0 tuning corresponds to `dense`, which runs at roughly three times the
literature rate. It is retained only as the upper bound of the sweep.

**And the sweep.** The Layer 3f ablation is reported across all three presets,
never as a single number. What we publish is how the relational signal's
contribution to F1 moves as co offending density moves, so a reader can see how
much of the contribution is the world and how much is our parameter. A single
ablation delta here would be a claim about our own configuration.

**Cost.** Layer 3f is genuinely weak at the calibrated setting, 4.68% of true
pairs. That is a fact about co offending and not a defect to be engineered away.
Layer 6 iteration operates on a small number of edges, so convergence will be
fast and the F1 movement across iterations will be modest. We report that rather
than inflating the input until the curve looks impressive.

---

## ADR 013, blocking ships the four character prefix key and the territorial key

**Status** accepted, Phase 1

**Context.** Layer 2 was built with three candidate key families. PH, the full
folded name token. P4, its first four characters. TR, station circle paired with
an available first letter.

**Measured, 7,621 accused rows, 29,036,010 possible pairs.**

| Families | Candidate pairs | Reduction ratio | Pairs completeness |
|---|---|---|---|
| PH | 2,418,046 | 0.9167 | 93.19% |
| P4 | 3,009,628 | 0.8963 | 94.69% |
| TR | 259,289 | 0.9911 | 60.35% |
| PH+TR | 2,599,790 | 0.9105 | 96.94% |
| PH+P4 | 3,009,628 | 0.8963 | 94.69% |
| P4+TR | 3,172,809 | 0.8907 | **97.58%** |
| PH+P4+TR | 3,172,809 | 0.8907 | 97.58% |

**Two findings.**

PH is a strict subset of P4. Truncating a token to four characters can only merge
blocks, never split them, so any pair sharing a PH key necessarily shares a P4
key. `PH+P4` equals `P4` exactly. The full token key contributes nothing once the
prefix key is present, and is kept only as a diagnostic. This is asserted as an
invariant in `tests/test_block.py`.

The real choice is `PH+TR` against `P4+TR`. The prefix key buys 0.64 percentage
points of completeness, about 67 more true pairs, for 573,019 extra candidate
pairs. That is roughly 8,700 pairs scored per true pair gained.

**Decision.** Ship `P4+TR`.

**Reasoning.** The asymmetry from ADR 004 again. Pairs completeness is a hard
ceiling on recall for Layers 3 to 7, and a pair blocking never proposes can never
be recovered by anything downstream, at any cost. Scoring cost lands on a batch
job that runs overnight and can be bought with hardware. An irrecoverable pair
cannot be bought back.

**Cost.** A reduction ratio of 0.8907 is poor by the standards of the record
linkage literature, where above 0.99 is normal.

**Why it is poor here, and why we are not fixing it.** The corpus draws names
from 58 given forms and 28 patronymic forms, giving roughly 200 distinct folded
tokens across 7,621 rows. Real Karnataka has orders of magnitude more distinct
names, so phonetic blocks in the field would be far smaller and the reduction
ratio far better. The measured 0.8907 is pessimistic by construction.

Pairs completeness is not distorted by the same effect, which is why it is the
figure carried forward and the reduction ratio is reported with this caveat
attached. Widening the name pool would improve the reduction ratio and would also
make the false merge problem artificially easy, so we leave it narrow.

---

## ADR 014, folding retroflex onto dental, and the losses that come with it

**Status** accepted, Phase 1

**Context.** Kannada distinguishes retroflex from dental, ಟ from ತ, ಡ from ದ, ಣ
from ನ, ಳ from ಲ. Latin transliteration in police records writes both as t, d, n
and l.

**Decision.** Fold retroflex onto dental at transliteration time. Fold aspiration
likewise, ಥ onto ತ. Reduce vowels to three classes rather than deleting them.

**Reasoning.** The distinction exists on one side of a cross script comparison
and cannot exist on the other. Preserving it guarantees that every cross script
pair mismatches, which is the opposite of what Layer 1 is for. The loss is forced
by the data, not chosen.

Vowels are a different matter, and this is where the scheme parts company with
Soundex. Soundex deletes vowels entirely. Kannada vowel length and quality carry
meaning, so deletion collapses genuinely different names. Three classes keep
enough structure to separate names while absorbing the inconsistency of
unstandardised transliteration.

**Measured.** 116 of 118 name pairs in the reference pool fold together across
scripts, 98.3%. Across the corpus, 93.8% of cross script true pairs share a
folded token after Layer 1, and 97.3% survive into the candidate set, the gap
being pairs reachable only through the territorial key.

**Known failures, recorded rather than hidden.**

English loanword monikers do not fold. ಆಟೋ is correct Kannada for auto and ಲಾರಿ
for lorry, but the English vowel and the Kannada vowel are genuinely different
sounds and no phonetic scheme brings them together. Two of the 118 pool entries.

The glide rule folds Vijay onto Viji. Accepted deliberately. ವಿಜಯ reaches Latin
as both Vijaya and Vijay, and a cross script miss on a name that is in the record
costs more than a collision with one that is not.

Names reduced to initials on both sides survive Layer 1 with no token at all,
1.17% of accused rows. They are reachable only through TR, which is the reason TR
exists.

---

## ADR 015, connected components plus weakest edge repair for Layer 5

**Status** accepted, Phase 2. Implements the relaxation promised in ADR 005.

**Context.** Correlation clustering under cannot link constraints is NP hard.
The constraints come free from the schema, since two Accused rows sharing a
CaseMasterID are provably different people. On the 5,000 case corpus there are
**4,706 such pairs across 1,891 cases**.

A note on that figure. The brief cites 1,883 cannot link edges. That is the count
of multi accused *cases*. The count of constrained *pairs* is 4,706, because a
case with five accused contributes ten pairs and not one. Both are reported.

**Decision, first attempt, and why it failed.** Connected components over the
merge threshold, then repair violations by removing the weakest edge on a path
between the offending pair.

It does not work, and the failure is instructive. At the operating threshold the
graph has 10,620 edges over 7,611 rows, an average degree of 2.8. That is
comfortably above the percolation threshold, so a giant component forms and
transitive closure turns a model with pairwise precision 0.48 into **1,706,180
false pairs**. The repair loop then removed 2,587 edges and still left 4,468
violations, because it was trying to carve a sound partition out of one enormous
blob. Connected components merges two groups on the strength of a single
bridging edge, and at this density there is always a bridge.

**Decision, adopted.** Greedy constrained agglomeration, strongest edge first.
Two clusters merge only when both hold.

- No cannot link edge spans them. This is checked at merge time and the merge is
  refused, rather than made and repaired afterwards. Cheaper, and faithful to the
  fact that the constraint is certain.
- At least half the cross pairs between the two clusters are themselves above
  threshold. One bridge between two groups of five is 1 of 25 cross pairs and is
  refused.

The density rule is average linkage in spirit and it is what stops a chain of
weak links becoming one identity.

**Measured, on the 5,000 case corpus.**

| | Connected components | Constrained agglomeration |
|---|---|---|
| False positive pairs | 1,706,180 | **3,538** |
| Violations remaining | 4,468 | **0** |
| Clusters | 145 | 4,255 |
| Pairwise F1 | 0.0085 | **0.5117** |

**Cost.** No optimality guarantee, and the density rule is a threshold we chose
rather than derived. It biases toward splitting, which costs recall and protects
precision, and that is the correct direction for a system whose characteristic
harm is a false merge.

---

## ADR 019, m is estimated from leave one out seeds, not by expectation maximisation

**Status** accepted, Phase 2. Supersedes the EM approach in ADR 006 and closes
ADR 018.

**Context.** ADR 018 recorded that unsupervised EM reached pairwise F1 0.1269
against an oracle ceiling of 0.5870. Three remedies were tried.

Fixing u at the candidate marginals, ADR 016. Helped, insufficient.

Informative initialisation from a seed of purity 0.846. **Made no difference at
all.** The fitted match proportion was 0.03814 from both the seeded and the
uninformative start, to five decimal places.

That last result is the diagnostic that mattered. EM converging to the same fixed
point from every start means the likelihood surface has one dominant optimum and
it is not the partition we want. This is misspecification of the conditional
independence assumption, not a local optimum, and no amount of restarting fixes
it.

**Decision.** Estimate m directly. For each signal, build a seed from strong
agreement on the *other* signals only, and estimate that signal's m from it. u
stays at the candidate marginals. EM is retained for the mixing proportion alone,
which is one dimensional and well behaved.

**Why leave one out.** A seed selected using signal k cannot be used to estimate
m for signal k without conditioning on its own answer. Excluding the target
signal from its own seed removes that circularity.

**Measured seed purity, none of which required a label.**

| Signal | Seed pairs | Purity |
|---|---|---|
| name | 1,013 | 0.846 |
| temporal | 991 | 0.901 |
| spatial | 678 | 0.860 |
| modus | 2,045 | 0.863 |
| relational | 456 | 0.985 |

Against a base rate of 0.0032, these are 260 to 300 times enriched.

**Result.** Pairwise F1 at the derived threshold moves from 0.0352 to **0.4903**.
The fitted match proportion moves from 0.03814 to **0.00514** against a true
0.00323. End to end after Layer 5, F1 **0.5117**.

**Cost.** The seeds carry roughly fifteen per cent contamination, which shrinks
every m toward u and makes all weights slightly conservative. Understating the
evidence is the safe direction here. It also means the headline claim is no
longer "fitted by expectation maximisation", and the deck must not say that.

---

## ADR 020, a missing measurement never carries evidence

**Status** accepted, Phase 2

**Context.** Every signal has a "not computable" level for pairs where it cannot
be evaluated, 4% of rows have no recorded age and relational is uncomputable on
1,125,109 candidate pairs.

Fitted freely, that level acquired a weight of +0.26 for relational, because the
pairs where relational cannot be computed happen to be slightly enriched for
matches. A third of the corpus was being shifted upward on the strength of a
field being empty.

**Decision.** The not computable level is forced to weight zero for every signal,
whatever the fit says.

**Reasoning.** A model must never learn that a missing field means same person.
The absence of a measurement is not evidence, and any weight on it is the model
fitting the pattern of what stations forget to type rather than the pattern of
who people are. A level observed fewer than thirty times in the whole candidate
set is likewise forced to zero, after an unobserved level produced a spurious
+5.40 weight from the asymmetry between the smoothed m and u normalisers, which
was on its own enough to carry a pair over the decision threshold.

---

## ADR 021, Layer 6 does not converge, and damping does not fix it

**Status** accepted as a limitation, Phase 3. Layer 6 stays PARTIAL.

**Context.** Layer 6 recomputes relational evidence from the current partition,
rescores, and reclusters. It never reaches a fixed point. It oscillates within
0.003 F1 with between 166 and 386 rows reassigned per pass, and stops at the
iteration cap of eight.

The obvious remedy is damping. Rather than replacing the relational evidence
each pass, blend the new continuous score with the previous one and re derive
the levels from the blend, so the partition moves toward the new evidence
instead of jumping onto it. The method is unchanged, only its trajectory.

**Measured, three factors, 5,000 case corpus.** The factor is the weight on the
new evidence, so 1.00 is the undamped loop.

| Damping | Converged | Rows reassigned per iteration | F1 range |
|---|---|---|---|
| 1.00 | no | 166 to 386 | 0.5111 to 0.5140 |
| 0.50 | no | 333 to 415 | 0.5125 to 0.5156 |
| 0.30 | no | 298 to 396 | 0.5115 to 0.5173 |

**Damping makes the movement worse, not better.** The undamped loop has the
smallest oscillation of the three. That result is the diagnosis.

**Decision.** Keep the undamped loop, keep reporting Layer 6 as non convergent,
and state why rather than tuning until a number looks acceptable.

**Why it oscillates, and why damping cannot help.** Damping smooths a
continuous input. The output of this loop is not continuous. Layer 5 produces a
hard partition through a merge threshold, a link density rule and a cannot link
constraint, all of which are step functions. A relational score sitting near a
decision boundary flips a merge on or off outright, and that flip changes the
co accused set for other pairs discretely, which flips further merges. Smoothing
the evidence does not smooth a threshold crossing, and by slowing the approach
it leaves more pairs sitting near the boundary for longer, which is consistent
with the damped runs moving more rows rather than fewer.

So the oscillation is a property of the coupling between a continuous evidence
channel and a discrete partitioning step, not a bug in the iteration and not a
step size problem.

**What would actually address it**, none of which is done. Hysteresis, where a
merge once made requires materially weaker evidence to be undone than it
required to be made. A soft partition carried between iterations instead of a
hard one. Or accepting the oscillation and reporting the modal partition across
the final iterations rather than the last one.

**Cost of leaving it.** The reported figures come from a single iteration of a
loop that is still moving, so F1 carries roughly plus or minus 0.003 of
iteration noise. That band is stated wherever the convergence curve is shown,
and the screen is labelled non convergent.

---

## ADR 016, u is estimated from the candidate marginals and held fixed

**Status** accepted, Phase 2

**Context.** With both m and u free, expectation maximisation converged on a
solution that defines a match as an identical name string. It fitted the match
proportion at 0.038 against a true 0.0032, drove m for lexical agreement to 1.0
and u to 4e-7, and produced weights above fourteen.

**This is not an implementation bug.** The candidate set contains roughly 120,000
pairs of distinct people who share an identical folded name, because those
collisions were planted deliberately. "Same name" is a larger and tighter cluster
than "same person", and unsupervised EM has no way to prefer the smaller one.

**Decision.** Estimate u once from the marginal distribution of the candidate set
and hold it fixed. Fit only m and the match proportion.

**Reasoning.** Matches are roughly three in a thousand candidate pairs, so the
candidate marginals are the non match marginals to three decimal places. This is
standard practice in modern record linkage and it removes the degree of freedom
that the collisions exploit.

**Cost.** It does not solve the problem, only reduces it. See ADR 018.

---

## ADR 017, lexical and phonetic are modelled as one composite name channel

**Status** accepted, Phase 2. Resolves the violation flagged in ADR 006.

**Context.** ADR 006 recorded that Fellegi Sunter assumes conditional
independence and that lexical and phonetic agreement are correlated by
construction. Measured, that correlation is **0.686**.

Fitted separately, lexical agreement scored 3.276 and phonetic agreement 4.011.
A pair with an identical name therefore collected **7.287 before any other
evidence was consulted**, against a decision threshold of 4.032. The four
remaining signals contributed a mean of 1.38 to a true pair, so they could never
overturn it.

The measured consequence was exact. The set of pairs above threshold was 57,872.
The set of pairs where both name signals were at top level was also 57,872. **The
model had become `GROUP BY AccusedName`, which is the baseline this project
exists to beat.** Pairwise precision 0.0896.

**Decision.** Layer 4 models five features, not six. Lexical and phonetic are two
readings of one string and are combined into one `name` channel with six levels
cut where the data separates. Both are still computed and reported individually
in the Layer 3 report, because the brief asks for six signals and because their
individual coverage and AUC are worth knowing.

**Two things the levels capture that the obvious encoding does not.** Agreeing on
a full name is twelve times stronger evidence than agreeing on a given name alone,
measured, so those are separate levels. And a pair recorded as initials on both
sides has no phonetic tokens, is reachable only through the territorial blocking
key, and is measurably purer than a generic partial match, so it gets its own
level rather than being folded into "not computable".

---

## ADR 018, open problem, unsupervised EM does not reach the model ceiling

**Status** open. Recorded rather than resolved, because it is the live blocker.

**The measurement.** Fitting m and u from ground truth, which is a diagnostic and
never part of the engine, this model form reaches pairwise **F1 0.5870, precision
0.7128, recall 0.4989**. Expectation maximisation fitted without labels reaches
**F1 0.1269 at its best possible cut**, and 0.0024 at the threshold it derives for
itself.

So the features are adequate and the fit is not. Those are different problems and
a single F1 cannot tell them apart, which is why the oracle diagnostic is
computed and reported alongside every run.

**What is known.** EM fits the match proportion at 0.038 against a true 0.0032,
between eleven and twenty four times too high depending on configuration. It is
absorbing a large diffuse class rather than the small tight one. Fixing u helps
and does not fix it.

**Two results that survive regardless, because both are measured on the oracle
fit and are therefore independent of the EM failure.**

The frequency adjustment works. It moves oracle precision from 0.5474 to 0.7128
and F1 from 0.5690 to 0.5870. Weighting name agreement by inverse frequency is
doing exactly what the theory says it should.

The relational signal currently hurts. Dropping it raises oracle F1 from 0.5870 to
0.6176. Its fitted weight for a shared arresting officer is +4.52, which is
implausible, and the cause is almost certainly another conditional dependence,
since a shared officer implies a shared station and the spatial signal already
counts that. This is ADR 017 repeating itself on a different pair of signals.

**Candidate directions, none yet chosen.** Seeding m from pairs that agree on a
rare name, which are near pure matches and need no labels. Constraining m to be
monotone in agreement level. Modelling the spatial and relational dependence
explicitly. Accepting a semi supervised fit and stating plainly that it uses
labels, which changes what the deck may claim.

## ADR 022, one canonical headline, written by the run, read by everything

**Status.** Accepted, 28 July 2026.

**Context.** Four different F1 figures were live at once and all four were true.

| Figure | What it was |
|---|---|
| 0.5117 | the shipped system at the cut it derives for itself |
| 0.5504 | the same system at the F1 optimal cut, chosen by looking at the answer |
| 0.6326 | the same system with a 3,000 form name vocabulary |
| 0.5870 | the same model family fitted from ground truth |

A reader could not tell which was the result. Worse, each was correct in its own
sentence, so nothing looked wrong on any single page. That is the failure mode
that matters, because it does not announce itself.

**Decision.** `eval/report.py` writes `eval/canonical.json`. It holds one
headline, the definition that produced it, the three other roles with their
qualifiers, and the rule. Everything else reads it. The README, the screens, the
status table and the leaderboard all resolve their figures from exported JSON at
build or render time, and nothing is typed by hand anywhere.

The canonical headline is **the fixture corpus at the threshold the engine
derives for itself**, which is the conservative reading and is what the deployed
system actually does. It is not the best figure available. It is the one an
officer would get.

**The qualifier travels with the figure.** Not in a footnote, not in a caption
further down, inline in the same sentence. "At the F1 optimal cut, which we do
not deploy." "With a realistic name vocabulary." The leaderboard states corpus
and cut on every row, because a figure without those two is not comparable to
anything.

**Consequence.** `web/src/screens/Status.tsx` used to type sixteen metrics into
its claim strings. They are now `{tokens}` resolved from the reports at render,
with `scripts/build_status_md.py` doing the same substitution from the same
files for the markdown mirror. A test walks every `.tsx` in the repository and
fails on a four decimal literal, so the next one cannot land quietly.

**What this costs.** The headline is now the least flattering of the four
figures, and it is the one on the front page. That is the point. The three
better numbers are all still published, each with the reason it is not the
answer.

## ADR 023, Kannada is an interface translation and is labelled as one

**Status.** Accepted, 28 July 2026.

**Context.** A Karnataka police product that renders only in English is
incomplete. A Karnataka police product that claims Kannada support and delivers
machine translated technical prose is worse, because it invites a reader to
trust an argument they are reading in a degraded form.

**Decision.** The masthead carries an English and ಕನ್ನಡ toggle, remembered in
localStorage. It translates **interface chrome**: navigation, panel titles,
table column headers, status words, button text and the audit strip keys. The
dictionary is `web/src/i18n/strings.ts`, keyed by the exact English string, and a
string with no entry falls through to English rather than to a placeholder, so
the coverage is visible on the page rather than asserted in a document.

**What is deliberately not translated.**

Explanatory prose. Those notes carry the argument of this product and a
rendering of a technical argument into Kannada without a Kannada speaking domain
reviewer would be worse than English for a reader who has both. That review has
not happened, so the claim is not made.

Anything numeric or identifying. Crime numbers, AMIDs, identity ids, metrics,
thresholds, SQL and file paths, all of which come out of the engine.
`scripts/check-kannada.mjs` requires every digit in a dictionary entry to survive
translation unchanged and in Latin numerals, and `scripts/smoke-render.mjs`
renders all nine screens in both languages and fails if any digit run differs. A
crime number half in Kannada numerals is not a crime number anyone can type back
into a search box.

**Kannada natural language querying and Kannada speech remain NOT BUILT**, and
`/status` says so on the same screen as the toggle. Neither is started. Querying
is structured and parameterised, there is no language model anywhere in this
system, and Zia speech is not wired.

**The Kannada that changes a result is in Layer 1**, where a name written in
Kannada is transliterated and folded so it reaches the same blocking key as its
Latin spellings. 116 of 118 name pairs fold together across scripts. That is the
part of this problem that recovers identities, and it works whichever way the
toggle is set.

**Typography.** Noto Sans Kannada was already vendored. It is appended to the
interface stack rather than replacing it, because identifiers and metrics never
translate and both faces therefore have to coexist inside one sentence. Latin
glyphs still come from Inter Tight and Kannada falls through to Noto, so no
element needs per string markup. Leading is opened to between 1.45 and 1.7
wherever translated chrome renders, because matras sit above and below the
baseline and conjuncts stack, and a line box tuned for Latin clips them. The
type scale, the palette and the density are unchanged. Contrast is unchanged
too, since Kannada is set in the same tokens at the same sizes, and the two
language buttons on the navy masthead are now checked explicitly by
`check-contrast.mjs`.

## ADR 024, victims and complainants have the same gap, and the estimator does not survive it

**Status.** Accepted, 29 July 2026.

**Context.** `Victim` and `ComplainantDetails` carry a person with no key that
survives across FIRs, exactly as `Accused` does. The deck asserted this in one
line and it had never been measured.

It could not have been measured. The generator drew every victim and every
complainant independently per case, so no repeat person existed, there was no
ground truth, and a resolver run over those tables would have scored near zero
precision by construction while measuring nothing at all.

**Decision, part one, the corpus.** Victims and complainants now have true
person identities with repeat appearances, at 18 and 22 per cent respectively,
below the accused recurrence rate because a person who offends repeatedly is by
definition a repeat visitor to the record and a victim usually is not. Names are
rendered through the same variant machinery, so the same cross script and
spelling problem exists on all three tables.

This runs as a post pass from its own random stream, seeded at `SEED + 90210`.
The main generator's draws are untouched, and `Accused.csv` and `CaseMaster.csv`
are byte identical to the run before this change. The published headline
therefore still reproduces, which was verified rather than assumed.

**Decision, part two, the engine.** `engine/resolve_other.py` imports Layers 1
to 5 from the modules the accused pipeline uses. It is not a second
implementation, so a figure on one table is comparable to a figure on another by
construction.

**The policy guard is demonstrated here, not merely called.** `Victim` carries
`CasteID`, `ReligionID` and `OccupationID`, and this is the first table where
protected columns sit beside a person we are actively trying to identify. The
run asserts the raw header is rejected, projects the permitted columns, then
asserts the projection passes. If the projection were removed the first
assertion would still fail the run. A control never seen to trip cannot be
distinguished from one that does not work.

**Result.**

| Table | Rows | People | Hidden | Unsupervised F1 | Oracle F1 |
|---|---|---|---|---|---|
| Accused | 7,611 | 3,840 | 3,771 | **0.5117** | 0.5870 |
| Victim | 688 | 544 | 144 | **0.0000** | 0.4824 |
| ComplainantDetails | 5,000 | 3,884 | 1,116 | **0.0000** | 0.3328 |

Across all three, 13,299 person bearing rows collapse to 8,268 people, and
5,651 same person relationships exist that no join on the raw schema can see.

**The finding, and it is a failure.** On both new tables the shipped engine
resolves nothing. Not poorly, nothing. Precision, recall and F1 are all zero,
and every row stays a singleton.

The oracle diagnostic separates the two possible causes and the answer is
unambiguous. The features are adequate: with m and u fitted from labels the same
model form reaches F1 0.4824 on victims and 0.3328 on complainants. The
unsupervised estimator recovers none of it.

**Why.** Layer 4 estimates m from leave one out seeds, where each signal's
parameters come from pairs that agree strongly on the *other* signals. That
needs several independent channels to corroborate one another. Accused has five
modelled channels. These tables have four, because the relational signal has
nothing to compute from: neither has an arresting officer, and a FIR names at
most one complainant, so there are no co accused to share. Of the four that
remain, modus operandi is a property of the case rather than of the person,
which for a victim carries almost nothing about who they are.

So the seed is not pure enough, m is estimated badly, and the fitted weight for
top level name agreement comes out at +1.89 against a derived threshold of
+3.44. Nothing clears the bar. **The estimator does not degrade gracefully below
its minimum evidence; it fails outright.** That is a sharper statement of the
ADR 018 and ADR 019 problem than the accused corpus could produce, because there
the fit was merely worse than the oracle rather than absent.

**What this is not.** It is not a reason to lower the threshold until something
merges. The threshold is derived from the fitted prior and moving it by hand
would be tuning against an answer we are only allowed to look at afterwards.

**What we do not claim.** Victim and complainant resolution is **NOT BUILT**.
The tables are measured, the gap in them is quantified, and the engine's failure
on them is published with its diagnosis. The counts of rows, people and hidden
repeats stand on their own, because they come from ground truth rather than from
the engine.

**The asymmetry worth noting.** `ComplainantDetails` carries an `Address` and a
`PhoneNumber`; `Accused` carries neither, and the schema file comments on that
itself. Those two columns are not yet features, which is why the complainant
oracle is the *lowest* of the three rather than the highest. Using them is the
obvious next move and it is not done.

## ADR 025, best partition selection does not rescue Layer 6, and Layer 6 is now closed

**Status.** Accepted, 29 July 2026. Supersedes nothing. Closes the question
opened by ADR 021.

**Context.** Layer 6 does not converge. ADR 021 established that damping made
the oscillation worse rather than better, and diagnosed the cause as the
coupling of a continuous score to a hard partition through step functions rather
than as a step size problem.

The remaining idea was to stop trying to converge. A non convergent search that
visits good states is still useful if you can tell which state was good. So
score every iteration's partition on the engine's own objective and return the
best scoring one instead of the last.

**The objective.** `engine.cluster.collective.objective`. Total retained edge
weight, the sum of `score - threshold` over every candidate pair placed in one
cluster, minus one log likelihood ratio unit per edge cut to repair a cannot
link violation. Pairs in different clusters contribute nothing, which makes the
sum well defined without enumerating non edges. **It reads no ground truth**,
which is the only condition under which selection would have been honest.

**Method.** `scripts/layer6_selection_study.py`. Three corpus seeds at 3,000
cases each, a full resolve per seed, eight iterations per run. Success required
two things: the selected partition beats the last iteration, and it does so on
every seed. A rule that gains on two corpora and loses on the third is a coin
toss with extra steps.

**Result.**

| Seed | Selected | of | F1 last | F1 selected | Delta |
|---|---|---|---|---|---|
| 4471 | 2 | 8 | 0.5379 | 0.5400 | **+0.0021** |
| 20260729 | 5 | 8 | 0.5716 | 0.5702 | **-0.0014** |
| 815623 | 3 | 8 | 0.5579 | 0.5571 | **-0.0008** |

Improved on one seed of three, made it worse on two, mean change **-0.0000**.

**Decision.** Selection is rejected. The objective is close to uncorrelated with
F1 across the narrow band of partitions this loop actually visits. Every
iteration scores between 9,085 and 9,154 on a corpus where F1 moves by 0.003,
so the objective is discriminating between partitions that are, for practical
purposes, the same partition. Picking the argmax of noise is picking noise.

The objective and the per iteration scores are kept and reported, because a
measurement that answered the question is worth keeping. `best_labels` is
returned as a diagnostic and is never used to choose. **Layer 6 ships the last
iteration, exactly as before.** Nothing about the published headline changes.

**Layer 6 stays PARTIAL and remains reported as non convergent.**

**Layer 6 is closed.** Damping was the first mechanism and it failed. Selection
was the second and it failed. The brief that authorised this work set two
attempts as the limit and that limit is reached. No further work on Layer 6.

**What would actually be needed, recorded so the next person does not repeat
us.** The problem is not the search and not the selection. It is that Layer 5
emits a hard partition, Layer 3f consumes it through a step function, and the
composition has no fixed point to find. A soft assignment carried between
iterations, so that relational evidence is weighted by how confident the
partition is rather than by which side of a cut it fell, would change the object
being iterated. That is a different Layer 5 and a different Layer 6, not a
parameter on this one.

## ADR 026, the sparse tables, three methods, one works and it is the boring one

**Status.** Accepted, 29 July 2026. Extends ADR 024.

**Context.** ADR 024 recorded that the engine resolves nothing on `Victim` and
`ComplainantDetails`, F1 0.0000 on both, while the oracle diagnostic showed the
features were adequate. The estimator was the failure. Three remedies were
specified and all three were tried.

**Result.** Every attempt, including the failures.

| Method | Victim F1 | Complainant F1 |
|---|---|---|
| Baseline, the table's own leave one out seeds | 0.0000 | 0.0000 |
| **a.** Transfer m from `Accused`, re estimate the mixing proportion | 0.0000 | 0.0000 |
| **a2.** Transfer m *and* the threshold, as a diagnosis of a | 0.0294 | 0.1310 |
| **b.** One parameter set pooled over all three tables | 0.0000 | 0.0000 |
| **c.** Use the address and phone columns the table already has | not applicable | **0.3706** |

**Method a fails, and the diagnosis is precise and worth more than the
attempt.** Transferring m produces a *better ranking*: the best cut reachable on
victims rises from F1 0.0450 to 0.2993. The weights are fine. What breaks is the
step the brief named, re estimating the mixing proportion. EM drives p to
0.000000 on both tables, the threshold is `log((1-p)/p)`, and it lands at 20.72
while the highest score the model can produce is 8.10. Nothing can clear it.

The cause is that a transferred m and a locally estimated u are not calibrated
to each other. m came from a table where matches are relatively easy; u
describes this table's candidate set. The mixing proportion is the only free
parameter left, so it absorbs the whole mismatch and collapses.

**a2 confirms that diagnosis and is not proposed as a method.** Taking the
threshold from the source table as well produces the first non zero victim
result, F1 0.0294 at precision 0.7500, which is three true pairs of 200. That is
a demonstration that the weights were never the problem, not a working resolver.
Transferring the base rate is a much weaker assumption than transferring m,
because the match proportion among candidate pairs depends on the blocking
output and on how often a person recurs, and both differ per table.

**Method b fails for the same reason as a**, which is unsurprising, because
pooling produces a parameter set dominated by `Accused`. It contributes 3.19
million of the 3.83 million pooled pairs.

**Method c works and it is shipped.** `ComplainantDetails` carries an `Address`
and a `PhoneNumber`. `Accused` carries neither, the schema file comments on that
asymmetry itself, and both columns were sitting unused while the resolver failed
on the one table that has them. Phone is modelled as binary equality, because a
partial match on a phone number means nothing. Address is graded: exact string,
shared locality stem, neither.

**F1 0.0000 to 0.3706, precision 0.6107, recall 0.2661.** Fitted weights: phone
agreement +1.06, exact address +1.40, differing address -0.80. No transfer, no
pooling, the table's own estimation over its own channels. The estimator was
never broken in a way that needed a clever fix. It needed one more independent
channel, and the column was already in the schema.

**Neither is a protected attribute.** Caste, religion and occupation are on
`Victim`, and they are not read here or anywhere. `engine/policy.py` still
rejects the raw `Victim` header on every run.

**The finding that matters most is the ceiling, not the result.** Once the phone
column is a feature, the oracle ceiling for `ComplainantDetails` moves from
0.3328 to **0.9781**. The complainant table is very nearly perfectly resolvable,
because it has a near identifier on it. `Accused` has no such column, and its
ceiling is 0.5870.

That comparison is the whole argument of this project in one line. **The
difference between a resolvable person and an unresolvable one is not the
algorithm, it is whether the form had a field for a phone number.** The KSP
schema collects contact details for the person reporting the crime and none for
the person accused of it.

**Victim stays NOT BUILT.** All three specified methods return exactly zero.
`Victim` has no address, no phone, no arresting officer and no co accused, and
the only columns it carries beyond a name are the three that are excluded. There
is nothing left to add. This is not an estimator problem that more work would
fix; it is a table with a name, an age and nothing else.

**What changed in the code.** The signal set became a parameter of
`engine.linkage.fellegi_sunter` rather than a module constant, so a table can
opt into channels the accused pipeline does not have. `FittedModel` carries its
own signal list, so `weights()` and `score()` cannot disagree. `fit_em` gained
`m_prior`, which is what made a and b testable at all. Defaults are unchanged
and the accused headline is unchanged at F1 0.5117, which was verified rather
than assumed.

## ADR 027, two operating points, and the sentence we had the evidence for

**Status.** Accepted, 29 July 2026.

**Context.** SUTRA had one headline, precision 0.5770 at recall 0.4596, and it
led every screen. Precision 0.9539 at recall 0.1440 had been measured since the
precision recall curve was built and was sitting on row four of a table.

For criminal identity that ordering is backwards. A precision of 0.5770 means
roughly two in five automatic merges are wrong. Nobody would write that to a
record. The figure a department would actually deploy on was already known and
was presented as a footnote to the figure it would not.

**Decision, part one. Two canonical figures, not one.** `eval/canonical.json`
now carries a `products` block with both, and both are read from it.

| | Precision | Recall | F1 | Cut | Merges | For |
|---|---|---|---|---|---|---|
| **Deployable** | **0.9539** | 0.1440 | 0.2502 | 10.14 | 1,585 | automatic merging |
| **Investigative** | 0.5770 | 0.4596 | 0.5117 | 5.27 | 8,365 | generating review candidates |

The deployable point is defined as **the highest recall that holds precision at
or above 0.95**. That definition matters: unlike the F1 optimal cut, it is
chosen against a policy a department can state in advance rather than against
the answer, which is what makes it deployable at all.

They are two different products from one model. At the deployable cut a merge
can be written to the record unattended and one merge in twenty is still wrong.
At the investigative cut there is roughly three times the recall and a human has
to sit between the result and the record.

**Which one to run at is a policy choice for the department**, about the cost of
a wrong merge against the cost of a missed one. It is not a property of the
method and this project does not get to make it. Both are presented side by
side, equally weighted, and neither is called *the* answer.

The investigative point remains what the shipped engine derives for itself and
therefore remains the canonical headline for reproducibility purposes. ADR 022
is unchanged.

**Decision, part two. State the bound.**

With m and u fitted from ground truth this model form caps at **F1 0.5870**, so
no linkage method can do much better on the fields this schema provides. SUTRA
reaches **87%** of it. The remaining gap is not a modelling problem, it is a
data collection problem, and it is the argument for adding a person key to the
record.

This is now on `/evaluation`, on `/status` and in the README. It is the most
useful thing this repository has to say to the Karnataka State Police and it had
been sitting unstated in an `oracle_diagnostic` field for several sessions.

**Why the bound is credible rather than convenient, and exactly what it bounds.**
The oracle fits m and u from the labels, so it is not a target any deployed
system can reach without them. It is an upper bound on **this model family**:
Fellegi Sunter over these discretised agreement levels, with conditional
independence assumed between channels.

**Corrected, 29 July 2026.** An earlier version of this ADR said a different
linkage family "could not move past it". That is false and it was the one
overclaim in this repository. A model that does not discretise, that scores name
similarity continuously, or that models the dependence between channels rather
than assuming it away, is **not** bounded by this oracle and could exceed it.
What the oracle bounds is the method we shipped, not the problem.

The honest form of the claim is narrower and still worth making. On these
fields, a well fitted Fellegi Sunter model reaches 0.5997, and we reach 88% of
that without labels. The remaining headroom inside this family is small. Whether
a different family could do materially better on the same columns is **not
measured here** and we do not assert either way.

**The second caveat, which the earlier version also omitted.** This ceiling is
measured on one synthetic corpus at an 86 form name vocabulary, generated by
`data/generator` with difficulty parameters we chose. The vocabulary sweep
already shows the figure moves when that parameter moves. It is a property of
this fixture, not of the KSP schema in the world.

**The demonstration that makes it concrete**, and it arrived by accident from
ADR 026. Give the same model a phone number and the ceiling moves from 0.5870 to
**0.9781**. That is `ComplainantDetails`, resolved by the same code on the same
corpus, and the only difference is two columns.

The KSP schema records an address and a phone number for the person **reporting**
a crime, and neither for the person **accused** of one. The person the record
most needs to identify across cases is the one it collects least about.

So the argument is not "our F1 is low, please add a field". It is: **the same
engine reaches 0.98 on the table that has a contact column and caps at 0.59 on
the table that does not.** Closing the gap is a records design decision. Nothing
in the algorithm can substitute for it.

## ADR 028, the column we never read, and making the engine argue what the report argues

**Status.** Accepted, 29 July 2026.

**Context.** An end to end audit asked a blunt question: why is the result 0.51
when the project has been careful about everything else. Two answers came back,
and both were embarrassing because both were free.

### One. `Accused.GenderID` was never read.

The engine read four columns off the accused row: the id, the case id, the name
and the age. `GenderID` sat beside them for the whole project and no layer
touched it.

**Corrected by ADR 030, 29 July 2026. Read that before this paragraph.** The
original text said: of 3,840 true people, zero have two rows that disagree on
gender, so a disagreement is a deterministic non match. That figure was
guaranteed by the generator, which copied each person's gender onto every one of
their rows verbatim. It was published as a measurement and it was not one. The
corpus now models a recording error rate and the honest figures are in ADR 030.
The table below is therefore the value of this channel **on a field that cannot
be wrong**, which is an upper bound and not a result.

The effect on the candidate set:

| | Pairs | True pairs | Purity |
|---|---|---|---|
| gender agrees | 2,920,886 | 10,306 | 0.003528 |
| **gender disagrees** | **273,335** | **0** | **0.000000** |

**273,335 false pairs eliminated, zero true pairs lost.** 8.6% of the candidate
set, removed by a column that was already on the row.

It is modelled as a three level channel rather than a boolean, so that a blank
gender is NOT_COMPUTABLE and never scored as a disagreement. Absence of a
measurement is never evidence, the same rule ADR 020 applied to unobserved
levels.

**On whether this is a protected attribute.** It is not, and the distinction is
worth stating rather than assuming. Caste, religion and occupation are excluded
because using them to decide anything about a person reproduces a historical
harm, and `engine/policy.py` still raises on all three. Sex here is a
descriptive fact recorded about a person the police have already identified in
that case, used only to ask whether two rows can be the same individual. It
scores no risk, ranks nobody, and predicts nothing about anyone. If it were used
to rank people or to score a person's likelihood of offending, it would belong
on the excluded list.

### Two. The engine did not implement the argument the report was making.

Since the operating point work, this project has argued that F beta at 0.5 is
the correct objective for criminal identity, because a false merge asserts two
people are one and propagates, while a missed merge leaves the record where it
already was.

The decision threshold sat at posterior 0.5. **That is the threshold for a model
that believes the two errors cost the same.** The argument was in the report and
not in the engine.

F beta at 0.5 is exactly the statement that recall is worth beta squared, a
quarter, of precision. The implied cost ratio is `1 / 0.5**2 = 4`. Under a cost
ratio `c` the decision boundary sits at posterior `c / (1 + c)`, which is where
the expected cost of merging equals the expected cost of not merging. At c = 4
that is posterior 0.8.

`FALSE_MERGE_COST_RATIO = 4.0` in `engine/linkage/fellegi_sunter.py`. It reads no
labels. It is a policy constant derived from a stated position about harm, and a
department that weighs the two errors differently changes one number.

### Result

| | Before | After, clean field | **After, 1.2% gender error** |
|---|---|---|---|
| Precision | 0.5770 | 0.7983 | **0.7901** |
| Recall | 0.4596 | 0.3686 | **0.3692** |
| F1 | 0.5117 | 0.5043 | **0.5033** |
| **F0.5, the stated objective** | 0.5490 | 0.6473 | **0.6434** |
| False merge rate | 0.0458 | 0.0401 | **0.0392** |
| Oracle ceiling | 0.5870 | 0.5997 | **0.5937** |

The third column is what ships. The second is the figure this ADR originally
published and is kept so the size of the overstatement is visible.

**F1 went down and that is not a defeat.** F1 weights the two errors equally and
this project has argued for two sessions that they are not equal. On the
objective we chose and justified *before* running this change, the result
improved by 0.0983, a 17.9% relative gain. Reporting the F1 drop beside it is
the point: a team that only published F0.5 here would be hiding the trade.

Precision moved from 0.58 to 0.80. At 0.58, two in five automatic merges are
wrong and no records officer would accept the output. At 0.80 it becomes
arguable. That is the difference between a demonstration and a tool.

**A third defect fixed itself.** The relational signal previously had a positive
ablation delta of +0.0316, meaning removing it improved F1, which ADR 017
diagnosed as correlated evidence counted twice. It is now **-0.0809**: removing
it hurts. Adding an independent channel and correcting the threshold resolved a
conditional dependence problem that two earlier sessions had failed to fix
directly.

**What this does not fix.** Recall is 0.3686. The system finds a third of the
true pairs, and at the deployable cut it finds a seventh. The ceiling moved by
0.0127, so the headroom inside this model family remains small. Both facts are
unchanged by this work and are reported unchanged.

## ADR 029, the cost policy helps one table and silences another

**Status.** Accepted, 29 July 2026. Amends ADR 026 and ADR 028.

**Context.** ADR 028 put the false merge cost ratio into the decision threshold,
which is where this project's stated objective always implied it belonged. On
`Accused` that was clearly right: F0.5 from 0.5490 to 0.6473, precision from
0.5770 to 0.7983.

Re-running the full chain showed it had a second effect nobody looked for.

| Table | Cost weighted, what ships | Equal cost cut |
|---|---|---|
| Accused | **F1 0.5043**, F0.5 0.6473 | F1 0.5302, F0.5 0.5780 |
| ComplainantDetails | **F1 0.0036** | F1 0.3696 |
| Victim | 0.0000 | 0.0000 |

**The complainant result from ADR 026 is almost entirely gone at the shipped
threshold.** F1 0.3706 became 0.0036. Precision is 0.7500 and recall is 0.0018,
which is nine merges.

**This is not a bug and it was not fixed.** The threshold moved by `log(4)`,
about 1.39 in log likelihood ratio units, from 2.963 to 4.363. The complainant
model's scores are compressed: the phone and address channels carry real
evidence, weights around +1.06 and +1.40, and that is not enough to reach four
to one odds on many pairs. The engine is doing exactly what it was told. It is
refusing to merge people it is not confident about, and on that table it is
rarely confident.

**Decision.** Both figures are reported, on the screen and in the JSON, in
adjacent columns. Neither is presented alone.

The alternative was to give each table its own cost ratio, which would be
choosing a policy per table to make each table look good. That is tuning against
the answer with extra steps, and the cost ratio is supposed to be a statement
about harm rather than a knob.

**What this actually tells a department.** The phone number is worth a great
deal, the oracle for that table is 0.9781, and the unsupervised estimator
extracts only part of it. At a standard strict enough to write to a record
unattended, the current fit on complainants does not qualify. That is a fair
description of where the work stands and it is more useful than a headline of
0.3706 that would only hold under a cost model this project has argued against.

**What would fix it properly.** Not a different threshold. A better fit on that
table, so the scores separate widely enough to clear a strict bar. The oracle
says the information is there.

## ADR 030, the gender field was made incapable of being wrong, and we measured that

**Status.** Accepted, 29 July 2026. Corrects ADR 028.

**What happened.** ADR 028 added a gender channel and reported that it removed
273,335 false pairs while contradicting **zero** true pairs, citing that of 3,840
true people, none had two rows disagreeing on gender. The prose around it said
station writers get names wrong constantly "and they do not get this wrong".

That sentence is a claim about real police records. The evidence offered for it
was a synthetic corpus in which `generate.py` copied `person["GenderID"]` onto
every row of that person verbatim. **The field could not disagree with itself.**
The zero was arithmetic, not a finding, and the strength of the channel was a
property of the fixture.

This is the third time this project has caught itself measuring what the
generator makes true. The pattern is worth naming: a corpus built to test one
thing will be silently perfect about everything else, and every new signal has
to be checked against whether the generator ever makes it wrong.

**The fix, in two parts.**

*The corpus.* `GENDER_ERROR_RATE = 0.012`, applied as a post pass from its own
random stream so names, cases, dates and ages are untouched and only the one
field moves. 149 of 13,299 rows across the three person tables now carry a wrong
gender, and 60 of 3,840 true people have rows that contradict each other.

The rate is a parameter, not a discovery. A binary coded field is genuinely much
cleaner than a transliterated name, and it is not clean: mis-keyed codes, rows
copied from a previous FIR, and a recorder guessing from a name they cannot
gender.

*The measurement.* `scripts/gender_noise_study.py` sweeps it. One corpus, one
feature extraction, and only the gender channel recomputed per rate, so a
difference between two rows is that channel and nothing else.

| Error rate | Rows flipped | People split | F0.5 with | F0.5 without | Gain | True pairs contradicted |
|---|---|---|---|---|---|---|
| **0.000**, the original claim | 0 | 0 | 0.6473 | 0.6381 | **+0.0092** | **0** |
| 0.005 | 48 | 34 | 0.6453 | 0.6381 | +0.0072 | 140 |
| **0.012**, shipped | 89 | 60 | 0.6434 | 0.6381 | **+0.0053** | **255** |
| 0.020 | 141 | 93 | 0.6433 | 0.6381 | +0.0052 | 398 |
| 0.050 | 348 | 222 | 0.6426 | 0.6381 | +0.0045 | 929 |
| 0.100 | 752 | 415 | 0.6360 | 0.6381 | **-0.0021** | 1,834 |

**What the sweep actually says.**

The channel is worth roughly **half** what ADR 028 claimed. +0.0092 F0.5 on a
field that cannot be wrong, +0.0053 at a realistic rate. Reporting the first
without the second overstates it by about 74 per cent.

It contradicts **255 true pairs** at the shipped rate. ADR 028 said zero.

**It goes negative at 10 per cent.** Past that point the channel does more harm
than good and should be removed. That is a real operating limit and it is the
sort of thing this project should be able to tell a department: if your gender
field is wrong more than about one row in twelve, do not use it for matching.

**Why it survives realistic noise at all**, since the honest version is less
impressive than the original: the asymmetry. A wrong gender on one row costs
only the true pairs involving that row, of which there are a handful. A right
gender on every other row rejects false pairs across the entire candidate set,
and false pairs outnumber true ones roughly three hundred to one. The channel is
robust because it is mostly doing rejection, and rejection is where the volume
is.

**What ships.** The 1.2% corpus. Headline precision 0.7901, recall 0.3692,
F0.5 0.6434, false merge rate 0.0392. Every figure in the repository is now from
a corpus whose gender field can be wrong.

**The general lesson, recorded because it will recur.** Before claiming a signal
is strong, check whether the generator ever makes it weak. If it cannot, the
measurement is of the generator. Any future channel added to Layer 3 gets a
noise parameter and a sweep before it gets an ADR.
