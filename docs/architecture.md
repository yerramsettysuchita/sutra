# Architecture

## 1. The problem is a missing entity, not a missing model

Read the KSP entity relationship diagram and look for the person.

`CaseMaster` has a case. `Accused` hangs off it with `AccusedMasterID` as its
own key and `CaseMasterID` as its parent. `PersonID` holds A1, A2, A3, which is
an ordering label inside one FIR and carries no meaning across FIRs. There is no
father's name column, no address column, no phone column, no biometric
reference. `Victim` and `ComplainantDetails` have the same shape.

So the schema models cases and roles within cases. It does not model people.

The problem statement asks for criminal network analysis and repeat offender
tracking. Both are person level questions. Neither is answerable by any query,
however clever, over the tables as supplied, because the join key those
questions need does not exist in the data.

This is the whole project. Everything below is the consequence.

### Why the obvious workaround fails

The obvious workaround is `GROUP BY AccusedName`. It fails in both directions at
once, and the two failures compound.

It over splits. The same offender appears as `ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ` at one station,
`Ramesh S/o Krishnappa` at the next, `R. Krishnappa` in a hurried entry, and
`Kadu Ramesha` where the writer used the locality moniker the man is actually
known by. Four rows, one man, zero edges between his cases. Every co offending
relationship he has is invisible.

It over merges. Manjunath, Basappa, Shivakumar and Ramesh are extremely common
given names in Karnataka, and `-appa` and `-gowda` patronymics are common in
turn. Grouping by string collapses genuinely different people into one node and
manufactures a criminal network that does not exist. An analyst acting on that
network acts on a fabrication.

Over splitting loses true edges. Over merging invents false ones. A system that
does both and reports neither is worse than no system, because it is confident.

## 2. Split compute, and why

Resolution is a nightly batch job. The deployed surface is read only.

The reasoning is not that serverless is inconvenient. It is that entity
resolution is inherently a global, iterative, all pairs computation and the
online path is inherently a single request with a latency budget. Those are
different machines.

Layer 6 iterates the entire corpus to a fixed point, because merging two records
creates new co offending edges, which change the relational evidence for other
pairs, which changes their scores. You cannot do that per request. Layer 4 fits
m and u probabilities by expectation maximisation across every comparison vector
in the corpus. That is a corpus level estimate, not a pair level one. Layer 3
needs sentence embeddings over `BriefFacts`, which means a model in memory.

Therefore:

- The engine runs locally on the full corpus and writes JSON artefacts, the
  resolved identity table, the co offender graph, community assignments, profile
  records, undetected case candidates, and the evaluation report.
- Catalyst serves those artefacts and answers queries against them.
- Nothing heavy is shipped into a function. No torch, no transformers, no
  scikit-learn in the deployed bundle.
- Re resolution is scheduled with Catalyst Job Scheduling, not triggered by user
  traffic.

This is the correct architecture for entity resolution regardless of the hosting
constraint. The hosting constraint just makes it non optional, which is
convenient, because it means we get to argue the point rather than assert it.

The honest cost of this decision is staleness. A FIR filed at 14:00 is not in
the resolved graph until the batch runs. We state that in the interface rather
than hiding it, and the audit strip carries the resolution timestamp on every
panel.

## 3. Catalyst service mapping

The organisers state that reaching for a third party service where a Catalyst
service exists may invalidate the submission. The mapping we hold to:

| Need | Service | Not |
|---|---|---|
| LLM, natural language to SQL | Catalyst QuickML | OpenAI, Anthropic |
| Embeddings for MO similarity | Catalyst QuickML | any hosted embedding API |
| Speech, Kannada and English | Catalyst Zia | Google STT, hosted Whisper |
| Structured storage | Catalyst Data Store | Postgres elsewhere |
| Document and artefact storage | Catalyst Stratus | S3, Firebase |
| Identity | Catalyst Authentication | Auth0, Firebase Auth |
| Scheduled resolution | Catalyst Job Scheduling, Cron | GitHub Actions cron |
| Static hosting | Catalyst Web Client Hosting | Vercel, Netlify |

Python libraries running inside our own process are not third party services.
`jellyfish`, `networkx`, `scikit-learn` and `sentence-transformers` run in the
local batch job and ship nothing to anyone. The line is a hosted API call
leaving our process, and we do not cross it.

## 4. The nine layers

### Layer 0, synthetic corpus

We cannot evaluate identity resolution without ground truth, and the real KSP
corpus has none, which is precisely the problem we are solving. So we generate a
corpus on KSP's exact schema where identity is known by construction.

Every accused row is emitted by a known synthetic person. The generator writes
the map. Every name variant applied, cross script rendering, patronymic form,
initialisation, spelling perturbation, locality moniker, is recorded per row, so
evaluation can slice performance by the exact corruption that caused a failure.

The generator plants the signals the engine is supposed to find. Each person has
a true birth year, so implied age is consistent within noise. Each person has a
home district and station, so the spatial prior is real. Each person has a modus
operandi family, so `BriefFacts` embeddings have something to cluster. Gangs
recur, so relational evidence exists.

It also plants the traps. Distinct people share exact names in the same
district. Given names follow a Zipf like frequency skew, so a match on a common
name genuinely carries less information than a match on a rare one, which is
what Layer 4 exists to exploit. Some pairs are given no surviving signal at all,
and the audit reports them as an honest recall ceiling rather than hiding them.

Seed fixed at 4471. Ships standalone, pure standard library, no dependencies.

### Layer 1, Indic normalisation

Cross script folding of Kannada to a Latin phonetic space, token reordering to a
canonical order, whitespace and punctuation handling, initial expansion and
contraction, honorific and relationship token stripping, `S/o`, `bin`, `ತಂದೆ`,
`ಬಿನ್`, `@`, `alias`.

English Soundex is not used anywhere in this system. It was designed in 1918 for
American census surnames and it destroys exactly the distinctions Kannada needs,
retroflex against dental, aspirated against unaspirated, and it treats vowels as
noise when Kannada vowel length is phonemic. It appears in the evaluation only
as a baseline to beat.

### Layer 2, blocking

All pairs over the accused table is quadratic and pointless. Blocking generates
candidate pairs cheaply.

Two key families, unioned. An Indic phonetic key on the normalised name, and a
territorial key on district plus station circle. Union rather than intersection,
because an offender who travels breaks the territorial key and an offender
written in a different script breaks the phonetic key, and we would rather score
extra pairs than lose true ones.

Blocking is reported honestly with two numbers, reduction ratio, how much work we
avoided, and pairs completeness, what fraction of true matching pairs survived
into the candidate set. Pairs completeness is a hard ceiling on recall for
everything downstream. Both numbers go in the evaluation report.

### Layer 3, six signal feature extraction

Six independent evidence channels per candidate pair.

a. **Lexical.** Jaro Winkler and token set ratio on the normalised `AccusedName`.

b. **Phonetic.** Agreement of the Indic phonetic code from Layer 1.

c. **Temporal.** Birth year consistency. Implied birth year is
   `year(CaseMaster.CrimeRegisteredDate) - Accused.AgeYear`. The same person must
   agree within plus or minus two years. Station recorded ages are estimates, so
   the tolerance is real, and disagreement beyond it is strong negative evidence.

d. **Spatial.** Haversine distance over `CaseMaster` latitude and longitude, plus
   hierarchy distance through `Unit.ParentUnit`. Two signals, because physical
   proximity and administrative proximity are different things and a case can be
   near in one and far in the other.

e. **Modus operandi.** Embedding similarity over `CaseMaster.BriefFacts`.
   Offenders repeat method. This is the channel that links a man across
   districts when the name rendering has diverged completely.

f. **Relational.** Shared co accused and shared arresting officer. This is the
   only channel that does not look at the person at all, and it is the one that
   makes Layer 6 necessary.

### Layer 4, frequency adjusted Fellegi Sunter linkage

Classical probabilistic record linkage. For each feature we estimate `m`, the
probability of agreement given the pair is a true match, and `u`, the probability
of agreement given it is not. The log likelihood ratio of the comparison vector
is the match weight, and it is additive across features under conditional
independence.

`m` and `u` are fitted by expectation maximisation over the unlabelled candidate
set, so the model calibrates itself to this corpus rather than to constants
someone chose.

The correction most implementations skip is frequency adjustment. Under plain
Fellegi Sunter, agreeing on `Manjunath` scores identically to agreeing on
`Yellappa Nagarajaiah`. That is information theoretically wrong. Agreement on a
value of frequency `f` carries roughly `-log2(f)` bits, so the name agreement
weight is scaled by inverse name frequency computed over the corpus. A match on a
rare name is worth far more than a match on a common one, and in a jurisdiction
where the top twenty given names cover a large share of the population, this is
the difference between a usable system and a false merge generator.

Conditional independence between the six channels is an assumption and it is not
strictly true. Phonetic agreement and lexical agreement are correlated by
construction. We record this as a known limitation in `decisions.md` and mitigate
it at Layer 7, where isotonic calibration absorbs systematic miscalibration
without us having to model the dependence structure explicitly.

### Layer 5, constrained correlation clustering

Pairwise scores must become entities. Pairwise decisions are not transitive, A
matches B, B matches C, A contradicts C, so a clustering step has to arbitrate.

The schema hands us a hard constraint for free. Two `Accused` rows sharing one
`CaseMasterID` are A1 and A2 of the same FIR. They are provably different people.
That is a cannot link edge derived from the data itself rather than from a
heuristic, and it is the single most valuable structural fact available to us.

Correlation clustering with cannot link constraints is NP hard. We do not pretend
otherwise. The relaxation is connected components over the auto merge threshold
followed by local search that repairs constraint violations by splitting on the
weakest internal edge, iterated until no cluster violates a cannot link. The
relaxation, its failure modes and the alternatives considered are documented in
`decisions.md`. A cluster that cannot be repaired is not silently split, it is
escalated to the review queue as a conflict, and the interface shows that case
explicitly.

### Layer 6, collective iteration

Layer 3f makes resolution self referential. Merging two records creates new co
offending edges. New edges change relational evidence for other pairs. Changed
evidence changes scores, which changes merges.

So we iterate. Score, cluster, rebuild the graph, rescore, until the assignment
stops moving. F1 against the gold set is logged per iteration and the convergence
curve goes in the evaluation report, because a claim of convergence without a
curve is a claim, not a result.

The iteration is not guaranteed to converge in theory. In practice it does, and
we cap it and report the cap.

### Layer 7, calibration and routing

A Fellegi Sunter weight is not a probability. Isotonic regression maps scores to
calibrated probabilities against the gold set, chosen over Platt scaling because
it assumes only monotonicity and the score to probability relationship here is
not sigmoid shaped.

Routing on the calibrated probability:

- above 0.92, automatic merge
- 0.65 to 0.92, human review queue with full evidence
- below 0.65, reject

Nothing merges silently. Every merge carries the evidence that produced it, the
calibrated probability, the route taken, and a timestamp. Every merge is
reversible, and reversal is a first class operation, not a database fix.

The thresholds are a policy choice, not a mathematical one, and they encode a
deliberate asymmetry. A false merge tells an investigator that two people are one
person, which is an error that propagates into every downstream product and can
put the wrong name in front of someone. A missed merge leaves the record where it
already was. So the automatic band is set conservatively and the review band is
wide.

### Layer 8, downstream products

Everything the problem statement actually asked for, now computable because the
person entity exists.

Resolved identity table. Co offender graph with people as nodes and shared cases
as edges. Leiden community detection, chosen over Louvain because Louvain can
produce internally disconnected communities and Leiden guarantees it cannot.
Repeat offender profiles. Candidate suspect ranking for undetected cases, those
with `ChargesheetDetails.cstype` equal to `C`, scored on modus operandi
similarity, territorial plausibility and temporal availability.

The candidate ranking is an investigative aid that surfaces existing records for
human attention. It is not a prediction about a person, and the distinction is
argued in `ethics.md`.

### Layer 9, IPC to BNS reconciliation

`Act.Active` and `Section.Active` mark the July 2024 transition from the Indian
Penal Code to the Bharatiya Nyaya Sanhita. A murder before the transition is IPC
302 and after it is BNS 103.

Any trend query crossing 1 July 2024 that does not reconcile the two returns a
cliff at the transition date that is an artefact of legislation rather than a
fact about crime. Layer 9 holds the mapping both ways and applies it inside query
planning, so a question about murder over five years returns five years of
murder.

## 5. Query path

Natural language or Kannada question, to intent and entity extraction, to SQL
against the resolved views, to execution, to answer with the generated SQL always
visible.

Two rules govern the path.

The generated SQL is never hidden. An analyst who cannot see the query cannot
audit the answer, and an unauditable answer has no evidential standing.

Refusal is a first class outcome. A question the system cannot answer correctly
gets a stated reason, not a plausible number. The refusal rate is reported in the
evaluation and it is one of the most valuable figures in the project, because a
system that answers everything is a system that is guessing.

## 6. What is deployed

A static bundle whose contents sit at the archive root, plus the JSON artefacts
from the batch. No engine code is deployed. The read layer is thin by
construction and this is checked at package time.
