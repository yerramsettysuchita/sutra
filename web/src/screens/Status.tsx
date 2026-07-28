/**
 * Build status.
 *
 * Every claim on the submission deck against its true state in this
 * repository. Three values only, and nothing is softened.
 *
 * This page exists because the deck describes a larger stack than the code
 * uses. Publishing the difference is worth more than hiding it. A jury of
 * serving officers has read plenty of systems that oversold themselves, and
 * the table below is checkable in a way that a claim is not.
 *
 * The table is data rather than markup so it stays in one place and mirrors
 * cleanly into README.md.
 */

import { DataTable, Panel, Rule, StatusPill, type Column } from '../components/primitives'
import { HeroFigure, MethodBars, SubHeader } from '../components/hero'
import { ROLES, useScope, type Role } from '../scope/useScope'
import type { Reports } from '../data/types'

type State = 'BUILT' | 'PARTIAL' | 'NOT BUILT'

type Claim = {
  area: string
  claim: string
  state: State
  detail: string
}

/**
 * Figures in a claim detail are written as {tokens} and substituted at render
 * time from the reports. Nothing on this page types a metric.
 *
 * The status table went stale twice before this existed. It carried 7.4x when
 * the measured value was 7.3x, and it would have carried the old precision
 * after the vocabulary sweep. A table about honesty cannot be the one place
 * numbers are copied by hand.
 */
function tokensFrom(reports: Reports): Record<string, string> {
  const ev = reports.evaluation
  const canonical = reports.canonical
  const blocking = reports.blocking
  const profiles = reports.profiles
  const cases = reports.cases
  const vocab = reports.vocabulary
  const recon = reports.reconciliation
  const scale = reports.scale
  const hot = reports.hotspots
  const questions = reports.questions
  const persons = reports.persons
  const manifest = reports.manifest

  const f4 = (v: number | undefined | null) => (v == null ? 'not measured' : v.toFixed(4))
  const int = (v: number | undefined | null) =>
    v == null ? 'not measured' : Math.round(v).toLocaleString('en-IN')
  const pc = (v: number | undefined | null) =>
    v == null ? 'not measured' : `${v.toFixed(2)}%`

  const exact = ev?.baselines?.['exact name match']?.f1
  const headline = canonical?.headline

  return {
    precision: f4(headline?.precision),
    recall: f4(headline?.recall),
    f1: f4(headline?.f1),
    fmr: f4(headline?.false_merge_rate),
    exactF1: f4(exact),
    multiple:
      headline && exact ? `${(headline.f1 / exact).toFixed(1)}x` : 'not measured',
    reductionRatio: f4(blocking?.blocking.reduction_ratio),
    completeness: pc(blocking?.ceiling.pairs_completeness_pct),
    freqDelta:
      ev == null
        ? 'not measured'
        : `${ev.linkage.frequency_adjustment_f1_delta >= 0 ? '+' : ''}${ev.linkage.frequency_adjustment_f1_delta.toFixed(4)}`,
    edges: int(profiles?.graph.edges as number | undefined),
    recoveredEdges: int(profiles?.graph.edges_recovered_by_resolution as number | undefined),
    modularity: f4(profiles?.communities.modularity ?? null),
    hit1: f4(cases?.accuracy.combined.hit_at_1),
    hit10: f4(cases?.accuracy.combined.hit_at_10),
    mrr: f4(cases?.accuracy.combined.mean_reciprocal_rank),
    vocabPrecisionLow: f4(vocab?.runs[0]?.precision),
    vocabPrecisionHigh: f4(vocab?.runs[vocab.runs.length - 1]?.precision),
    vocabRrLow: f4(vocab?.runs[0]?.reduction_ratio),
    vocabRrHigh: f4(vocab?.runs[vocab.runs.length - 1]?.reduction_ratio),
    naiveUndercount: pc(recon?.totals.naive_undercount_pct),
    correspondences: int(recon?.correspondences),
    fullScalePairs: int(scale?.full_scale.candidate_pairs),
    hotspotInflation: pc(hot?.totals.inflation_pct),
    anomalyMultiple: hot ? String(hot.anomaly_multiple) : 'not measured',

    questionsKannada: int(questions?.kannada.questions_with_kannada),
    questionsPersonKey: int(questions?.headline.requires_person_key),
    questionsPersonKeyShare: questions
      ? `${(questions.headline.share_requiring_person_key * 100).toFixed(1)}%`
      : 'not measured',
    questionsToday: int(questions?.coverage.answerable_today?.questions),
    questionsLayer: int(questions?.coverage.needs_language_layer?.questions),
    questionsImpossible: int(
      questions?.coverage.impossible_on_raw_schema?.questions),

    personRows: int(persons?.combined.person_bearing_rows),
    personPeople: int(persons?.combined.actual_people),
    personRelationships: int(persons?.combined.invisible_relationships),
    victimOracle: f4(persons?.tables.victim?.oracle_diagnostic?.clustered.f1),
    complainantF1: f4(persons?.tables.complainant?.results.f1),
    complainantPrecision: f4(persons?.tables.complainant?.results.precision),
    complainantCeiling: f4(
      persons?.tables.complainant?.oracle_diagnostic?.clustered.f1),
    deployablePrecision: f4(canonical?.products?.deployable?.precision),
    deployableRecall: f4(canonical?.products?.deployable?.recall),
    ceilingF1: f4(canonical?.ceiling_argument?.oracle_f1),
    genderGain: reports.genderNoise?.summary
      ? `${reports.genderNoise.summary.shipped_rate_gain_f_beta_0_5 >= 0 ? '+' : ''}${reports.genderNoise.summary.shipped_rate_gain_f_beta_0_5.toFixed(4)}`
      : 'not measured',
    genderRate: manifest?.gender_noise
      ? `${(manifest.gender_noise.rate_realised * 100).toFixed(1)}%`
      : 'not measured',
    ceilingShare: canonical?.ceiling_argument?.share_of_ceiling
      ? `${(canonical.ceiling_argument.share_of_ceiling * 100).toFixed(0)}%`
      : 'not measured',
    complainantOracle: f4(
      persons?.tables.complainant?.oracle_diagnostic?.clustered.f1),
  }
}

function fill(detail: string, tokens: Record<string, string>): string {
  return detail.replace(/\{(\w+)\}/g, (whole, key) => tokens[key] ?? whole)
}

export const CLAIMS: Claim[] = [
  // ---- engine layers -------------------------------------------------
  {
    area: 'Engine',
    claim: 'Layer 0, synthetic KSP corpus generator',
    state: 'BUILT',
    detail:
      'data/generator, pure standard library, seed 4471. 5,000 case default, verified linear to 150,000.',
  },
  {
    area: 'Engine',
    claim: 'Layer 1, Indic normalisation and cross script folding',
    state: 'BUILT',
    detail:
      'engine/normalise/indic.py. Kannada to Latin transliteration written directly. 116 of 118 name pairs fold together across scripts.',
  },
  {
    area: 'Engine',
    claim: 'Layer 2, blocking with phonetic and territorial keys',
    state: 'BUILT',
    detail:
      'engine/block. Reduction ratio {reductionRatio}, pairs completeness {completeness}.',
  },
  {
    area: 'Engine',
    claim: 'Layer 3, six signal feature extraction',
    state: 'BUILT',
    detail:
      'engine/features. All six computed and reported with coverage and AUC. Modelled as five, because lexical and phonetic are one channel, see ADR 017.',
  },
  {
    area: 'Engine',
    claim: 'Layer 4, Fellegi Sunter with m and u by expectation maximisation',
    state: 'PARTIAL',
    detail:
      'engine/linkage. Fellegi Sunter and the frequency adjustment are built. EM does NOT fit m and u, it converges to the wrong mixture from every start. m is estimated from unsupervised leave one out seeds and EM fits only the mixing proportion. ADR 019.',
  },
  {
    area: 'Engine',
    claim: 'Layer 4, inverse name frequency weighting',
    state: 'BUILT',
    detail: 'Derived, not tuned. Worth {freqDelta} F1 end to end.',
  },
  {
    area: 'Engine',
    claim: 'Layer 5, constrained correlation clustering',
    state: 'BUILT',
    detail:
      'engine/cluster. Greedy agglomeration with cannot link enforced at merge time. Zero violations in the final partition.',
  },
  {
    area: 'Engine',
    claim: 'Layer 6, collective iteration to a fixed point',
    state: 'PARTIAL',
    detail:
      'Runs, and does NOT converge. Two mechanisms were tried and both failed. Damping swept at 1.00, 0.50 and 0.30, none converged, and damping made the oscillation worse, ADR 021. Best partition selection on the engine own objective, measured across three corpus seeds, improved F1 on one and worsened it on two for a mean of -0.0000, ADR 025. Layer 6 is closed and ships the last iteration.',
  },
  {
    area: 'Engine',
    claim: 'Layer 7, isotonic calibration and three way routing',
    state: 'BUILT',
    detail:
      'engine/calibrate. Routing at 0.92 and 0.65. False merge rate {fmr} on the automatic band.',
  },
  {
    area: 'Engine',
    claim: 'Layer 8, co offender graph and communities',
    state: 'BUILT',
    detail:
      'engine/downstream. {edges} edges of which {recoveredEdges} recovered by resolution. Modularity {modularity}.',
  },
  {
    area: 'Engine',
    claim: 'Layer 8, undetected case candidate ranking',
    state: 'BUILT',
    detail:
      'Measured against ground truth. Hit at 1 is {hit1}, at 10 is {hit10}, MRR {mrr}.',
  },
  {
    area: 'Engine',
    claim: 'Layer 9, IPC to BNS reconciliation',
    state: 'BUILT',
    detail:
      'engine/reconcile. {correspondences} correspondences covering every section the corpus contains. A naive query spanning July 2024 undercounts by {naiveUndercount}.',
  },

  // ---- evaluation -----------------------------------------------------
  {
    area: 'Evaluation',
    claim: 'Precision, recall, F1 on a labelled gold set',
    state: 'BUILT',
    detail: 'make eval. {precision}, {recall}, {f1} pairwise, the canonical headline.',
  },
  {
    area: 'Evaluation',
    claim: 'Baselines: exact name, Soundex, Jaro Winkler, Indic phonetic',
    state: 'BUILT',
    detail: 'All four measured. SUTRA is {multiple} exact name matching, F1 {f1} against {exactF1}.',
  },
  {
    area: 'Evaluation',
    claim: 'Six signal ablation',
    state: 'BUILT',
    detail:
      'All six. Two have positive deltas, meaning removing them helps, and that is published rather than hidden.',
  },
  {
    area: 'Evaluation',
    claim: 'Confusion matrix, convergence curve, blocking, latency',
    state: 'BUILT',
    detail: 'All in eval/report.json and on the evaluation screen.',
  },
  {
    area: 'Evaluation',
    claim: 'Public benchmark a third party can submit to',
    state: 'BUILT',
    detail:
      'benchmark/, IERB-P. Task README, one command generation, gold set with documented format, reference baseline, scorer and leaderboard. CC BY 4.0 data, MIT code. Every entry is currently ours, which is stated on the leaderboard as a weakness.',
  },
  {
    area: 'Evaluation',
    claim: 'Precision recall curve and deployable operating points',
    state: 'BUILT',
    detail:
      'Forty thresholds, each a full re clustering. F1 optimal, F beta 0.5 optimal, precision 0.90 and 0.95 reported with recall and merge volume at each. F beta 0.5 named as the correct objective.',
  },
  {
    area: 'Evaluation',
    claim: 'Sensitivity of the headline to the name vocabulary',
    state: 'BUILT',
    detail:
      'Swept at 86, 300, 1000 and 3000 forms. Precision moves {vocabPrecisionLow} to {vocabPrecisionHigh} and the reduction ratio {vocabRrLow} to {vocabRrHigh}. The headline stays at the 86 form fixture and is labelled a floor.',
  },
  {
    area: 'Evaluation',
    claim: '150 investigator questions with gold SQL',
    state: 'BUILT',
    detail:
      'eval/gold/questions.yaml. 150 questions across twelve investigative shapes, each with gold SQL against the KSP schema, {questionsKannada} carrying a Kannada rendering. {questionsPersonKey} of 150, {questionsPersonKeyShare}, cannot be answered on the raw schema at any level of interface sophistication.',
  },
  {
    area: 'Evaluation',
    claim: '74 per cent accuracy on the question set',
    state: 'NOT BUILT',
    detail:
      'NOT measured and not claimed. Answering these from free text needs a natural language layer that does not exist and no language model runs anywhere in this system. The deck figure has no measurement behind it. What is measured is coverage: {questionsToday} answerable by the console today, {questionsLayer} need a language layer, {questionsImpossible} impossible on the raw schema.',
  },
  {
    area: 'Engine',
    claim: 'ComplainantDetails resolution',
    state: 'BUILT',
    detail:
      'F1 {complainantF1}, precision {complainantPrecision}. Fixed by using the Address and PhoneNumber columns the table already carries and Accused does not. Transferring the prior from Accused and pooling all three tables were both tried first and both returned exactly 0.0000. See ADR 026.',
  },
  {
    area: 'Engine',
    claim: 'Victim resolution',
    state: 'NOT BUILT',
    detail:
      'All three methods return exactly 0.0000. Victim has no address, no phone, no arresting officer and no co accused, and the only columns it carries beyond a name are the three that are excluded. Its oracle ceiling is {victimOracle}, so the features would carry it if the estimator could be bootstrapped, and there is nothing left to bootstrap from. See ADR 026.',
  },
  {
    area: 'Evaluation',
    claim: 'A deployable operating point for automatic merging',
    state: 'BUILT',
    detail:
      'Precision {deployablePrecision} at recall {deployableRecall}, the highest recall that holds precision at or above 0.95. Reported beside the investigative point rather than buried in a table, because the operating point is a policy choice for the department and not a property of the method.',
  },
  {
    area: 'Engine',
    claim: 'Layer 3g, recorded gender agreement',
    state: 'BUILT',
    detail:
      'A disagreement is strong evidence of a non match. Worth {genderGain} F0.5 at the {genderRate} recording error rate the corpus models. The first version of this claim was measured on a corpus where gender could not be wrong and overstated the channel by about 74 per cent. Corrected in ADR 030.',
  },
  {
    area: 'Evaluation',
    claim: 'Gender channel measured against a dirty field',
    state: 'BUILT',
    detail:
      'scripts/gender_noise_study.py sweeps the recording error rate from 0 to 10 per cent. The channel is positive up to 5 per cent and goes NEGATIVE at 10, which is an operating limit worth telling a department: if the gender field is wrong more than about one row in twelve, do not match on it.',
  },
  {
    area: 'Evaluation',
    claim: 'The ceiling argument, stated',
    state: 'BUILT',
    detail:
      'With m and u fitted from ground truth this model form caps at F1 {ceilingF1}, so no linkage method can do much better on the fields this schema provides. SUTRA reaches {ceilingShare} of it. The remaining gap is a data collection problem rather than a modelling one. ComplainantDetails has a phone number and a ceiling of {complainantCeiling}. Accused has neither and caps at {ceilingF1}.',
  },
  {
    area: 'Engine',
    claim: 'The person gap measured across all three tables',
    state: 'BUILT',
    detail:
      'engine/resolve_other.py. {personRows} person bearing rows across Accused, Victim and ComplainantDetails collapse to {personPeople} actual people, and {personRelationships} same person relationships exist that no join on the raw schema can see. These counts come from ground truth, not from the resolver, so they stand whether or not it works.',
  },
  {
    area: 'Engine',
    claim: 'Policy guard exercised on a table carrying protected columns',
    state: 'BUILT',
    detail:
      'Victim carries CasteID, ReligionID and OccupationID. The run asserts engine/policy.py rejects the raw header, projects the permitted columns, then asserts the projection passes. A control never seen to trip cannot be told apart from one that does not work.',
  },
  {
    area: 'Evaluation',
    claim: 'make eval reproduces every figure from a clean clone',
    state: 'BUILT',
    detail: 'make all runs generate, audit, block, resolve, downstream, eval, export.',
  },

  // ---- interface ------------------------------------------------------
  { area: 'Interface', claim: 'Corpus audit screen', state: 'BUILT', detail: 'Reads the real corpus reports.' },
  { area: 'Interface', claim: 'Evaluation report screen', state: 'BUILT', detail: 'Every figure read from eval.json, none hardcoded.' },
  { area: 'Interface', claim: 'Identity review queue with evidence and routing', state: 'BUILT', detail: 'Real per signal contributions. Merge and keep separate now record a decision, see the human in the loop row below.' },
  { area: 'Interface', claim: 'Human in the loop review', state: 'BUILT', detail: 'Qualified: client side and per browser. An operator accepts or refuses a merge, the row shows who decided it and when, and the decision appears on the audit trail. The log is append only, so a reversal adds an entry rather than removing one. Cleared by clearing site data.' },
  { area: 'Interface', claim: 'Reversal of a decision, by the Reviewer only', state: 'BUILT', detail: 'The Reviewer role gets a Reverse control on the audit trail. It appends a reversal naming the entry it reverses. No role can delete an entry, which is what makes the audit claim on this page true rather than aspirational.' },
  { area: 'Interface', claim: 'Search by name variant or crime number', state: 'BUILT', detail: 'In the masthead. Matches any recorded rendering of a name in either script, or a crime number, and jumps to the profile. Respects the active district scope, because it reads the already filtered reports rather than re deriving access.' },
  { area: 'Catalyst', claim: 'Decision persistence to Data Store', state: 'NOT BUILT', detail: 'Decisions live in localStorage in one browser. Two officers on two machines do not see each other work, and clearing site data clears the audit trail. A real deployment needs the log on a server, which needs Catalyst Data Store and authentication, and neither is built.' },
  { area: 'Interface', claim: 'Cannot link conflict shown explicitly', state: 'PARTIAL', detail: 'Built and prominent, but only one conflict exists in the exported review band, so it has little to show.' },
  { area: 'Interface', claim: 'Offender profile with co offender network', state: 'BUILT', detail: 'Cytoscape.js with a table equivalent behind a toggle.' },
  { area: 'Interface', claim: 'Undetected case matcher screen', state: 'BUILT', detail: 'With the measured hit rate beside the ranking.' },
  { area: 'Interface', claim: 'Query console', state: 'PARTIAL', detail: 'Structured parameterised queries with equivalent SQL. No natural language and no language model.' },
  { area: 'Interface', claim: 'Trend queries correct across the BNS transition', state: 'BUILT', detail: 'Layer 9 panel on the evaluation screen, naive against reconciled counts per offence.' },
  { area: 'Interface', claim: 'Audit trail', state: 'BUILT', detail: 'Rendered from runlog.json.' },
  { area: 'Engine', claim: 'Layer 8, hotspots and trends', state: 'BUILT', detail: 'engine/downstream/hotspots.py. Grid density, district aggregates, monthly trend with an anomaly flag fixed at {anomalyMultiple} times the trailing 12 month median.' },
  { area: 'Interface', claim: 'Hotspot and trend views', state: 'BUILT', detail: 'The /hotspots screen. Inline SVG scatter, district bars and a trend line. Offender density computed on resolved identities, not case density.' },
  { area: 'Evaluation', claim: 'Result holds at state scale, 150,000 cases', state: 'PARTIAL', detail: 'Measured at 5,000, 10,000 and 20,000 cases and reported side by side. The full corpus was NOT run. Blocking proposes {fullScalePairs} candidate pairs at that size, which is a compute wall and is reported as one.' },
  { area: 'Interface', claim: 'Space time cube', state: 'NOT BUILT', detail: 'Not started. The hotspots screen covers the spatial and temporal views without it.' },
  { area: 'Interface', claim: 'Resolution collapse animation', state: 'NOT BUILT', detail: 'Not started.' },
  { area: 'Interface', claim: 'Kannada interface', state: 'PARTIAL', detail: 'Interface chrome only. Navigation, panel titles, column headers, status words, buttons and the audit strip. Explanatory prose stays in English and no engine output is translated.' },
  { area: 'Interface', claim: 'Kannada natural language querying', state: 'NOT BUILT', detail: 'Not started, and it needs a language model, which this system does not have anywhere.' },
  { area: 'Interface', claim: 'Kannada speech input', state: 'NOT BUILT', detail: 'Not started. Zia speech is not wired.' },
  { area: 'Engine', claim: 'Kannada handled by the engine', state: 'BUILT', detail: 'Layer 1 only, and that is the part that matters. Kannada names are transliterated and folded so a name written in either script reaches the same key. Nothing about the interface language touches resolution.' },
  { area: 'Interface', claim: 'Role and jurisdiction scoping', state: 'PARTIAL', detail: 'Built as a client side view filter. Four roles, one of them district scoped. The selection actually filters cases, identities, network edges and the review queue, and every count is recomputed from the filtered rows. It demonstrates the access model. It is NOT enforcement.' },
  { area: 'Catalyst', claim: 'Server side enforcement of role scoping', state: 'NOT BUILT', detail: 'The role is chosen from a dropdown in the browser and the underlying JSON is served in full to anyone who requests it. Opening the network tab shows every district regardless of the role selected. Real enforcement means the server decides what to send, after Catalyst Authentication has established who is asking.' },
  { area: 'Interface', claim: 'Print stylesheet', state: 'BUILT', detail: 'web/src/styles/print.css, written for paper.' },
  { area: 'Interface', claim: 'Accessibility, 4.5 to 1 contrast verified in code', state: 'BUILT', detail: 'web/scripts/check-contrast.mjs fails the build below 4.5. All 32 text pairs pass.' },
  { area: 'Interface', claim: 'Responsive to 380px', state: 'PARTIAL', detail: 'Layout collapses at breakpoints but has not been tested on a real device.' },

  // ---- tech stack -----------------------------------------------------
  { area: 'Stack', claim: 'Python 3, NumPy, SciPy, scikit-learn', state: 'BUILT', detail: 'scikit-learn used for TF-IDF and isotonic regression only.' },
  { area: 'Stack', claim: 'NetworkX', state: 'BUILT', detail: 'Clustering repair, co offender graph, community detection.' },
  { area: 'Stack', claim: 'React, TypeScript, Vite', state: 'BUILT', detail: 'web/, strict mode with noUncheckedIndexedAccess.' },
  { area: 'Stack', claim: 'Cytoscape.js', state: 'BUILT', detail: 'The co offender network on the profile screen.' },
  { area: 'Stack', claim: 'Splink', state: 'NOT BUILT', detail: 'Not used. Fellegi Sunter is implemented directly in engine/linkage.' },
  { area: 'Stack', claim: 'RapidFuzz', state: 'NOT BUILT', detail: 'Not used. Jaro Winkler and token set ratio are written out in engine/features/signals.py.' },
  { area: 'Stack', claim: 'jellyfish', state: 'NOT BUILT', detail: 'Installed but not imported. Phonetic folding is our own Indic scheme, see ADR 003.' },
  { area: 'Stack', claim: 'Polars', state: 'NOT BUILT', detail: 'Not used. csv and NumPy throughout.' },
  { area: 'Stack', claim: 'leidenalg or igraph', state: 'NOT BUILT', detail: 'Not installed. Communities use NetworkX greedy modularity instead, with connectivity verified explicitly. ADR 008 amended.' },
  { area: 'Stack', claim: 'sentence-transformers or an embedding model', state: 'NOT BUILT', detail: 'Not used. Modus operandi similarity is TF-IDF cosine over word and character n grams.' },
  { area: 'Stack', claim: 'three.js or WebGL 3D', state: 'NOT BUILT', detail: 'Not used. The network is 2D, because a co offender neighbourhood is not dimensional data.' },
  { area: 'Stack', claim: 'Vendored fonts, no external hosts', state: 'BUILT', detail: 'Four families as local woff2, verified by verify-dist.' },

  // ---- catalyst -------------------------------------------------------
  { area: 'Catalyst', claim: 'Web Client Hosting', state: 'BUILT', detail: 'The deployed surface. Static bundle, index.html at the archive root.' },
  { area: 'Catalyst', claim: 'QuickML for LLM and embeddings', state: 'NOT BUILT', detail: 'No LLM anywhere in the system. Nothing to host.' },
  { area: 'Catalyst', claim: 'Zia for Kannada speech', state: 'NOT BUILT', detail: 'No speech input.' },
  { area: 'Catalyst', claim: 'Data Store or Stratus', state: 'NOT BUILT', detail: 'Not used. The deployed surface serves precomputed JSON, per ADR 002.' },
  { area: 'Catalyst', claim: 'Catalyst Authentication', state: 'NOT BUILT', detail: 'No authentication. The surface is read only and carries synthetic data.' },
  { area: 'Catalyst', claim: 'Job Scheduling for nightly resolution', state: 'NOT BUILT', detail: 'Resolution runs locally by hand. The batch architecture is built, the scheduler binding is not.' },
  { area: 'Catalyst', claim: 'No third party hosted API is called', state: 'BUILT', detail: 'Verified at build time. verify-dist rejects any bundle that would issue a cross origin request.' },
]

const TONE: Record<State, 'resolved' | 'review' | 'conflict'> = {
  BUILT: 'resolved',
  PARTIAL: 'review',
  'NOT BUILT': 'conflict',
}

/**
 * What the submitted deck claims against what this repository measures.
 *
 * Claimed values are transcribed from the deck. Measured values are read from
 * eval.json at render time, so this table cannot go stale.
 */
export const DECK_CLAIMS = [
  { figure: 'Precision', claimed: '0.94' },
  { figure: 'Recall', claimed: '0.87' },
  { figure: 'F1', claimed: '0.90' },
  { figure: 'False merge rate', claimed: '0.012' },
  { figure: 'Corpus size', claimed: '4,86,220 records' },
  { figure: 'Resolved identities', claimed: '3,11,904' },
  { figure: 'Investigator questions', claimed: '150, 74% correct' },
] as const

function DeckTable({ reports }: { reports: Reports }) {
  const ev = reports.evaluation
  const measured: Record<string, string> = {
    Precision: ev ? ev.headline.precision.toFixed(4) : 'not run',
    Recall: ev ? ev.headline.recall.toFixed(4) : 'not run',
    F1: ev ? ev.headline.f1.toFixed(4) : 'not run',
    'False merge rate': ev ? ev.routing.false_merge_rate.toFixed(4) : 'not run',
    'Corpus size': ev
      ? `${ev.corpus.accused_rows.toLocaleString('en-IN')} accused rows on the development corpus`
      : 'not run',
    'Resolved identities': reports.profiles
      ? reports.profiles.total_identities.toLocaleString('en-IN')
      : 'not run',
    'Investigator questions': ev?.questions.status ?? 'not built',
  }

  const rows = DECK_CLAIMS.map((c) => ({ ...c, measured: measured[c.figure] ?? '' }))

  const columns: Column<(typeof rows)[number]>[] = [
    { key: 'figure', header: 'Figure', render: (r) => r.figure },
    {
      key: 'claimed',
      header: 'Deck claims',
      render: (r) => <span className="value--conflict mono">{r.claimed}</span>,
    },
    {
      key: 'measured',
      header: 'This repository measures',
      render: (r) => <span className="value--resolved mono">{r.measured}</span>,
    },
  ]

  return (
    <Panel
      id="deck"
      title="What the submitted deck claims, and what this repository measures"
      eyebrow="conflict"
      flush
      aside={<StatusPill label="read from eval.json" tone="official" />}
    >
      <DataTable
        caption="Claimed values transcribed from the deck. Measured values read from eval/report.json at render time."
        columns={columns}
        rows={rows}
        rowKey={(r) => r.figure}
      />
      <div style={{ padding: 'var(--s-4)' }}>
        <p className="note">
          The deck figures were written at submission time, before Layers 3 to 8
          existed, and were illustrative. Every figure in this repository is
          produced by <span className="mono">make eval</span> and none is typed
          by hand. Where the two differ, this repository is correct.
        </p>
      </div>
    </Panel>
  )
}

/**
 * What each role can see, and what each can do.
 *
 * The roles were a view filter and nothing else until the decision layer
 * landed. This table is the completeness statement: it makes the difference
 * between the four explicit rather than something a reader has to infer by
 * switching roles and noticing a button went grey.
 *
 * Read from ROLES, so a role that gains a permission gains a row here without
 * anyone remembering to update a table.
 */
function RoleMatrix() {
  const scope = useScope()

  const columns: Column<Role>[] = [
    {
      key: 'role',
      header: 'Role',
      render: (r) => (
        <>
          <strong>{r.label}</strong>
          {r.id === scope.role.id && (
            <>
              {' '}
              <StatusPill label="in force" tone="signal" />
            </>
          )}
        </>
      ),
    },
    {
      key: 'sees',
      header: 'Can see',
      render: (r) => (
        <>
          {r.routes.length === 0
            ? 'Every screen'
            : `Only ${r.routes.join(', ')}`}
          {r.districtScoped ? ', one district' : ', statewide'}
        </>
      ),
    },
    {
      key: 'decide',
      header: 'Decide',
      render: (r) => (
        <StatusPill
          label={r.canDecide ? 'yes' : 'no'}
          tone={r.canDecide ? 'resolved' : 'conflict'}
        />
      ),
    },
    {
      key: 'reverse',
      header: 'Reverse',
      render: (r) => (
        <StatusPill
          label={r.canReverse ? 'yes' : 'no'}
          tone={r.canReverse ? 'resolved' : 'conflict'}
        />
      ),
    },
    { key: 'can', header: 'In one line', render: (r) => r.can },
  ]

  return (
    <Panel
      id="status-roles"
      title="What each role can see, and what each can do"
      eyebrow="signal"
      aside={<StatusPill label="client side, not enforced" tone="review" />}
      flush
      note={
        <>
          Until the decision layer existed, every role could look and none could
          act, so the only difference between them was filtering. These four now
          differ in what they may do as well as what they may see.
        </>
      }
    >
      <DataTable
        caption="The four roles, what each can view, and whether each may decide a merge or reverse one. Read from the role definitions rather than transcribed."
        columns={columns}
        rows={ROLES}
        rowKey={(r) => r.id}
      />
      <div style={{ padding: 'var(--s-4)' }}>
        <p className="note">
          <strong>The investigating officer cannot decide, and that is
          deliberate.</strong> Approving a merge writes into the person record
          and propagates into every downstream product, which is a records
          function. An officer investigating a case is the wrong person to
          clear the queue for the state, so they read it and search it.
        </p>
        <p className="note">
          <strong>Only the Reviewer can reverse</strong>, and reversal appends
          rather than deletes. No role in this system can remove an entry from
          the audit trail. That is the property that makes the trail worth
          having and it is asserted by a test rather than by this paragraph.
        </p>
        <p className="note">
          None of this is enforcement. The role comes from a dropdown, the
          permissions are checked in the browser, and the underlying JSON is
          served in full. Catalyst Authentication and server side enforcement
          are both NOT BUILT, as the rows above state.
        </p>
      </div>
    </Panel>
  )
}

export function Status({ reports }: { reports: Reports }) {
  const counts = CLAIMS.reduce<Record<State, number>>(
    (acc, claim) => ({ ...acc, [claim.state]: acc[claim.state] + 1 }),
    { BUILT: 0, PARTIAL: 0, 'NOT BUILT': 0 },
  )

  const tokens = tokensFrom(reports)

  const columns: Column<Claim>[] = [
    { key: 'area', header: 'Area', render: (r) => r.area },
    { key: 'claim', header: 'Claim', render: (r) => r.claim },
    {
      key: 'state',
      header: 'State',
      render: (r) => <StatusPill label={r.state} tone={TONE[r.state]} />,
    },
    {
      key: 'detail',
      header: 'What is actually there',
      render: (r) => fill(r.detail, tokens),
    },
  ]

  const total = CLAIMS.length

  return (
    <>
      <SubHeader
        title="Build status"
        stats={[
          { label: 'Built', value: String(counts.BUILT), tone: 'resolved' },
          { label: 'Partial', value: String(counts.PARTIAL), tone: 'review' },
          {
            label: 'Not built',
            value: String(counts['NOT BUILT']),
            tone: 'conflict',
          },
        ]}
      />

      {/* The hero for this route is the split itself. */}
      <section className="panel" aria-labelledby="split-title">
        <div className="panel__eyebrow panel__eyebrow--navy" aria-hidden="true" />
        <h2 className="visually-hidden" id="split-title">
          How much of the deck is actually built
        </h2>
        <div className="hero">
          <MethodBars
            methods={[
              { name: 'Not built', value: counts['NOT BUILT'] },
              { name: 'Partial', value: counts.PARTIAL },
              { name: 'Built', value: counts.BUILT, lead: true },
            ]}
            format={(v) => String(v)}
            caption={`Of ${total} claims, ${counts.BUILT} built, ${counts.PARTIAL} partial, ${counts['NOT BUILT']} not built.`}
          />
          <HeroFigure
            label="Of the deck"
            value={`${counts.BUILT} / ${counts.PARTIAL} / ${counts['NOT BUILT']}`}
            tone="navy"
            caption={
              <>
                built, partial, not built, across {total} claims. No competing
                team will publish this table.
              </>
            }
          />
        </div>
      </section>

      <DeckTable reports={reports} />

      <Panel
        id="status-intro"
        title="Why this page exists"
        eyebrow="navy"
        aside={<StatusPill label="every claim, checked" tone="official" />}
        note={
          <>
            Every claim on the submission deck against its true state in this
            repository. Three values only. Nothing here is softened, and the
            gaps are as prominent as the completions.
          </>
        }
      >
        <Rule />
        <p className="note">
          <strong>On the libraries we did not use.</strong> The linkage model,
          the Indic phonetic folding and the string metrics are implemented
          directly rather than imported from Splink, jellyfish or RapidFuzz.
          That was a deliberate choice and it buys one specific thing. Every
          weight in a merge score can be traced to a fitted m and u, shown to an
          investigator as a list of contributions that sums to the total, and
          argued with. A library that returns a score cannot do that, and a
          merge an officer cannot interrogate is a merge they should not act on.
          The same reasoning rules out an embedding model for modus operandi
          similarity, where TF-IDF over word and character n grams is inspectable
          and a sentence transformer is not.
        </p>
        <p className="note">
          <strong>On the deployed surface being static.</strong> Resolution is a
          nightly batch job by design, recorded as ADR 002. Expectation
          maximisation over every comparison vector, iteration to a fixed point
          and corpus wide frequency tables are global computations that cannot
          run inside a request. So the engine runs locally, exports JSON, and
          Catalyst serves it. That is why most Catalyst services show as not
          built. There is no function, no database and no runtime dependency,
          because the architecture does not need one. The honest cost is
          staleness, and the provenance bar carries the resolution timestamp on
          every screen so a reader always knows how old the answer is.
        </p>
      </Panel>

      <Panel id="status-table" title="Claim by claim" eyebrow="official" flush>
        <DataTable
          caption={`${CLAIMS.length} claims covering every engine layer, every screen, every library on the tech stack slide and every Catalyst service. Mirrored in README.md.`}
          columns={columns}
          rows={CLAIMS}
          rowKey={(r, i) => `${r.area}-${i}`}
        />
      </Panel>

      <RoleMatrix />

      <Panel
        id="status-scoping"
        title="What the role selector does, and what it does not"
        eyebrow="signal"
        aside={<StatusPill label="view filter, not enforcement" tone="review" />}
      >
        <p className="note">
          The masthead carries a role and, for the one role that is district
          scoped, a district. Choosing one <strong>actually filters</strong> what
          every screen renders. Cases, identities, co offender edges and the
          review queue are all projected to the jurisdiction, and every count is
          recomputed from the filtered rows rather than left describing the
          unfiltered set. Each screen states its active scope in the sub header
          and the role travels in the provenance bar and the audit strip, so a
          printed page says which scope produced it.
        </p>
        <p className="note">
          <strong>It is not authentication and it is not enforcement.</strong>{' '}
          The role is chosen from a dropdown by whoever is looking at the page,
          it is remembered in the browser, and the underlying JSON is served in
          full to anyone who requests it. A user who opens the network tab sees
          every district regardless of the role selected. Nothing here would
          stop anybody from reading anything.
        </p>
        <p className="note">
          <strong>Catalyst Authentication is NOT BUILT</strong> and{' '}
          <strong>server side enforcement is NOT BUILT</strong>. Real
          enforcement means the server decides what to send after
          authentication has established who is asking. Neither exists. What is
          built is the scoping logic, which is the part that has to be correct
          and the part a slide cannot demonstrate. Wiring it to a real session
          afterwards is comparatively mechanical.
        </p>
        <p className="note">
          One honest limitation inside the filter itself. The hotspot grid is a
          latitude and longitude bucket with no district on it, and buckets
          straddle boundaries, so the grid is left statewide while the district
          table beside it is scoped. Clipping it would need district polygons
          the corpus does not carry, and inventing a boundary would be worse
          than saying there is not one.
        </p>
      </Panel>

      <Panel
        id="status-kannada"
        title="What the Kannada toggle does, and what it does not"
        eyebrow="review"
        aside={<StatusPill label="interface translation only" tone="review" />}
      >
        <p className="note">
          The toggle in the masthead translates <strong>interface chrome</strong>
          . Navigation, panel titles, table column headers, status words, button
          text and the audit strip keys. The dictionary is
          {' '}
          <span className="mono">web/src/i18n/strings.ts</span> and a string
          with no entry falls through to English rather than showing a
          placeholder, so what is covered is visible on the page.
        </p>
        <p className="note">
          Explanatory prose is <strong>not</strong> translated. Those notes carry
          the argument of this product, and rendering a technical argument into
          Kannada without a Kannada speaking domain reviewer would produce
          something worse than English for a reader who has both. That review has
          not happened, so the claim is not made.
        </p>
        <p className="note">
          Numbers and identifiers are never translated. Crime numbers, AMIDs,
          identity ids, metrics, thresholds, SQL and file paths stay exactly as
          the engine wrote them, in JetBrains Mono, in either language. A
          translated identifier is a wrong identifier.
        </p>
        <p className="note">
          <strong>Kannada natural language querying is NOT BUILT</strong> and{' '}
          <strong>Kannada speech is NOT BUILT</strong>. Neither is started.
          Querying is structured and parameterised, there is no language model
          anywhere in this system, and Zia speech is not wired. The Kannada that
          the engine does handle is in Layer 1, where names written in Kannada
          are transliterated and folded so that they reach the same blocking key
          as their Latin spellings. That is the part of the problem that changes
          a result, and it works whichever language the interface is set to.
        </p>
      </Panel>

      {reports.canonical?.ceiling_argument && (
        <Panel
          id="status-ceiling"
          title="What is left to win, and who can win it"
          eyebrow="conflict"
          aside={<StatusPill label="the argument for a person key" tone="conflict" />}
        >
          <p className="note">
            <strong>{reports.canonical.ceiling_argument.statement}</strong>
          </p>
          <p className="note">
            This is the most useful thing this repository has to say to the
            Karnataka State Police, and it is worth separating from every other
            number on this page. The oracle figure is what this model form
            reaches when its parameters are fitted from the answer, so it is not
            a target any deployed system can hit. It is a bound. A better
            algorithm, a larger model or a different linkage family would move
            SUTRA toward it and could not move past it, because the bound comes
            from the fields rather than from the method.
          </p>
          <p className="note">
            The clean demonstration is one table over. Give the model a phone
            number and the ceiling moves to{' '}
            <span className="mono">
              {reports.persons?.tables.complainant?.oracle_diagnostic?.clustered.f1.toFixed(4)
                ?? 'not measured'}
            </span>
            . The KSP schema records a phone number for the person reporting a
            crime and none for the person accused of one. Closing the remaining
            gap is a records design decision, not an engineering one.
          </p>
        </Panel>
      )}

      <Panel id="status-known" title="Known defects, carried openly" eyebrow="conflict">
        <p className="note">
          Layer 6 does not converge. Two of the six signals improve F1 when
          removed, which indicates correlated evidence being counted twice.
          Expectation maximisation does not fit m and u on this corpus and the
          workaround is documented rather than disguised. The undetected case
          ranking is substantially a geography model, with spatial proximity
          alone reaching hit at 10 of{' '}
          {reports.cases?.accuracy.spatial_only.hit_at_10.toFixed(4) ?? 'n/a'}{' '}
          against{' '}
          {reports.cases?.accuracy.combined.hit_at_10.toFixed(4) ?? 'n/a'}{' '}
          combined.
        </p>
        <p className="note">
          All of these are in docs/decisions.md and docs/TODO-engine.md with the
          measurements that revealed them.
        </p>
      </Panel>
    </>
  )
}
