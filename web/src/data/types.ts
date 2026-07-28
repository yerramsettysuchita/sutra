/**
 * Shapes of the JSON the client reads.
 *
 * Three files come from the corpus and the engine reports directly. Five come
 * from scripts/export_web.py. All are hand written to mirror what the Python
 * writes, so a shape change is caught at runtime by the guards in useReports
 * rather than silently rendering blanks.
 */

/* ------------------------------------------------------- corpus and layer 2 */

export type Manifest = {
  generator: string
  seed: number
  generated_at?: string
  co_offending_preset?: string
  dyad_recurrence?: { dyads: number; recurring: number; rate_pct: number }
  /** Share of rows whose recorded gender is wrong. ADR 030. */
  gender_noise?: {
    rate_requested: number
    total_flipped: number
    total_rows: number
    rate_realised: number
  }
  corpus_start: string
  corpus_end: string
  bns_transition: string
  requested_cases: number
  counts: Record<string, number>
  excluded_from_features: string[]
}

export type CorpusStats = {
  counts: Record<string, number>
  script: Record<string, number>
  variants: Record<string, number>
  appearances_per_person: Record<string, number>
  name_frequency_top10: Record<string, number>
  recoverability: {
    true_pairs: number
    cross_script_pairs: number
    channels: Record<string, number>
    tiers: Record<string, number>
    recall_ceiling_pct: number
    unrecoverable_pct: number
    exact_match_pct: number
  }
  hard_negatives: {
    collision_groups: number
    tight_age_groups: number
    ambiguous_name_strings: number
    cross_person_exact_name_pairs: number
  }
  relational: { gangs: number; cannot_link_cases: number; undetected_cases: number }
}

export type FamilyResult = {
  candidate_pairs: number
  pairs_completeness_pct: number
  reduction_ratio: number
}

export type BlockingReport = {
  generated_at: string
  corpus_seed: number
  cases: number
  accused_rows: number
  normalisation: {
    script_counts: Record<string, number>
    empty_after_folding: number
    cross_script_true_pairs: number
    cross_script_shared_token: number
    cross_script_shared_token_pct: number
    cross_script_blocked: number
    cross_script_blocked_pct: number
  }
  blocking: {
    shipped_families: string[]
    all_possible_pairs: number
    candidate_pairs: number
    cannot_link_dropped: number
    reduction_ratio: number
    total_blocks: number
    largest_block: number
    by_family: Record<string, FamilyResult>
    by_combination: Array<{
      families: string
      candidate_pairs: number
      reduction_ratio: number
      pairs_completeness_pct: number
    }>
  }
  ceiling: {
    true_pairs: number
    blocked: number
    lost: number
    pairs_completeness_pct: number
    revised_recall_ceiling_pct: number
    prior_ceiling_pct: number
    exact_name_match_pct: number
  }
}

/* --------------------------------------------------------------- evaluation */

export type PairMetrics = {
  true_positive_pairs: number
  false_positive_pairs: number
  false_negative_pairs: number
  predicted_pairs: number
  actual_pairs: number
  precision: number
  recall: number
  f1: number
}

export type EvalReport = {
  generated_at: string
  corpus: {
    cases: number
    accused_rows: number
    true_persons: number
    candidate_pairs: number
  }
  headline: PairMetrics
  headline_f_beta_0_5: number
  precision_recall_curve: Array<{
    threshold: number
    precision: number
    recall: number
    f1: number
    f_beta_0_5: number
    merged_pairs: number
    false_positive_pairs: number
  }>
  operating_points: Record<
    string,
    {
      threshold: number
      precision: number
      recall: number
      f1: number
      f_beta_0_5: number
      merged_pairs: number
    } | null
  >
  deployed_operating_point: string
  /** The sentence that must travel with every non deployed point, keyed the
   *  same way as operating_points. Written by eval/report.py. */
  operating_point_qualifiers: Record<string, string>
  objective_note: string
  confusion_matrix: Record<string, number>
  routing: {
    thresholds: { auto_merge: number; review_floor: number }
    auto_merge: { pairs: number; precision?: number }
    review: { pairs: number; precision?: number }
    reject: { pairs: number; precision?: number }
    false_merge_rate: number
    false_merges: number
    auto_merged_pairs: number
  }
  baselines: Record<string, PairMetrics>
  ablation: Record<
    string,
    PairMetrics & { label: string; f1_delta: number }
  >
  convergence: {
    iterations: number
    converged: boolean
    history: Array<{
      iteration: number
      rows_reassigned: number
      clusters: number
      violations: number
      precision?: number
      recall?: number
      f1?: number
    }>
  }
  blocking: {
    reduction_ratio: number
    pairs_completeness_pct: number
    candidate_pairs: number
    all_possible_pairs: number
  }
  signals: Record<
    string,
    { label: string; coverage: number; auc: number; lift_at_top_level: number | null }
  >
  linkage: {
    method: string
    fitted_p_match: number
    observed_p_match: number
    threshold_llr: number
    frequency_adjustment_f1_delta: number
  }
  oracle_diagnostic: {
    oracle_no_adjustment: { f1: number; precision: number; recall: number }
    oracle_with_adjustment: { f1: number; precision: number; recall: number }
    em_fitted_best_cut: { f1: number; precision: number; recall: number }
  }
  latency_seconds: Record<string, number>
  questions: { status: string; note: string }
}

/* ------------------------------------------------------------------ routing */

export type PairSide = {
  amid: string
  name: string
  script: string
  person_label: string
  age: string | null
  case_id: string
  crime_no: string
  registered: string
  district: string
  station: string
  identity: string
}

export type Evidence = {
  signal: string
  label: string
  level: number | null
  weight: number
}

export type ReviewPair = {
  pair_id: string
  left: PairSide
  right: PairSide
  score_llr: number
  probability: number
  route: string
  evidence: Evidence[]
  cannot_link_conflict: boolean
  conflict_reason: string | null
}

export type RoutingFeed = {
  generated_at: string
  review_band: { floor: number; ceiling: number }
  total_in_review_band: number
  shown: number
  pairs: ReviewPair[]
}

/* --------------------------------------------------------------- identities */

export type Identity = {
  identity: string
  record_count: number
  case_count: number
  source_amids: string[]
  variants: Array<{ name: string; script: string; amid: string }>
  distinct_renderings: number
  scripts: string[]
  implied_birth_year: { min: number | null; max: number | null; values: number[] }
  primary_circle: string | null
  circles: Array<{ station: string; cases: number }>
  cases: Array<{
    case_id: string
    crime_no: string
    registered: string
    district: string
    station: string
    subhead: string
    amid: string
    name: string
  }>
  merge_confidence: { mean: number | null; min: number | null; edges: number }
}

export type IdentityFeed = {
  generated_at: string
  total_identities: number
  shown: number
  identities: Identity[]
}

/* ------------------------------------------------------------------ network */

export type NetworkNode = {
  identity: string
  label: string
  record_count: number
  case_count: number
  merged: boolean
  degree: number
  circle: string | null
}

export type NetworkEdge = {
  source: string
  target: string
  shared_cases: number
  cases: Array<{ case_id: string; crime_no: string; registered: string }>
  visible_before_resolution: boolean
  recovered: boolean
}

export type NetworkFeed = {
  generated_at: string
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  recovered_edges: number
  pre_existing_edges: number
}

/* --------------------------------------------------- layer 8, undetected */

export type Candidate = {
  rank: number
  identity: string
  label: string
  script: string
  score: number
  known_cases: number
  signals: {
    modus: number
    spatial: number
    temporal: number
    nearest_km: number
    days_outside_window: number
  }
}

export type UndetectedCase = {
  case_id: string
  crime_no: string
  registered: string
  district: string
  station: string
  subhead: string
  brief_facts: string
  candidates: Candidate[]
}

export type Accuracy = {
  cases_measured: number
  culprit_unreachable: number
  hit_at_1: number
  hit_at_3: number
  hit_at_10: number
  hit_at_50: number
  mean_reciprocal_rank: number
  median_rank_when_found: number | null
  candidate_pool: number
  random_baseline_hit_at_10: number
}

export type CasesFeed = {
  generated_at: string
  weights: Record<string, number>
  spatial_horizon_km: number
  temporal_horizon_days: number
  candidate_pool: number
  total_undetected_cases: number
  shown: number
  accuracy: {
    combined: Accuracy
    modus_only: Accuracy
    spatial_only: Accuracy
    temporal_only: Accuracy
  }
  cases: UndetectedCase[]
}

/* ----------------------------------------------------- layer 8, profiles */

export type Profile = {
  identity: string
  label: string
  script: string
  records: number
  cases: number
  distinct_renderings: number
  renderings: Array<{ name: string; times: number }>
  districts_touched: number
  districts: Array<{ district: string; cases: number }>
  stations: Array<{ station: string; cases: number }>
  primary_circle: string | null
  circles_touched: number
  mo_signature: Array<{ offence: string; cases: number; share: number }>
  co_accused_circle: Array<{
    identity: string
    label: string
    shared_cases: number
    recovered: boolean
  }>
  co_accused_count: number
  recovered_relationships: number
  first_case: string | null
  last_case: string | null
  active_days: number
  before_resolution: { apparent_people: number; largest_fragment_cases: number }
  after_resolution: { people: number; cases: number }
}

export type ProfilesFeed = {
  generated_at: string
  total_identities: number
  shown: number
  graph: Record<string, number>
  communities: Record<string, unknown> & {
    algorithm: string
    communities: number
    modularity: number | null
    internally_disconnected_communities: number
    connectivity_guarantee_held: boolean
  }
  summary: Record<string, number>
  profiles: Profile[]
}

/* ------------------------------------------------ layer 9, reconciliation */

export type OffenceCount = {
  code: string
  offence: string
  head: string
  ipc: string
  bns: string
  naive_count: number
  reconciled_count: number
  naive_missed: number
  naive_wrong_offence: number
  naive_undercount_pct: number
}

export type ReconciliationFeed = {
  generated_at: string
  window: { from: string; to: string; spans_transition: boolean }
  transition: string
  cases_before_transition: number
  cases_on_or_after_transition: number
  correspondences: number
  totals: {
    naive_count: number
    reconciled_count: number
    naive_missed: number
    naive_undercount_pct: number
  }
  ambiguous_codes: Record<string, string[]>
  offences_returning_the_wrong_offence: Array<{
    code: string
    offence: string
    wrong_offence_rows: number
  }>
  by_offence: OffenceCount[]
}

/* -------------------------------------------------- layer 8, hotspots */

export type GridCell = {
  lat: number
  lon: number
  cases: number
  offenders: number
  repeat_offenders: number
  apparent_offenders_before_resolution: number
  cases_per_offender: number
}

export type DistrictRow = {
  district: string
  cases: number
  offenders: number
  repeat_offenders: number
  apparent_offenders_before_resolution: number
  cases_per_offender: number
  top_offence: string | null
}

export type TrendPoint = {
  month: string
  cases: number
  trailing_median: number
  anomaly: boolean
}

export type HotspotsFeed = {
  generated_at: string
  cell_degrees: number
  anomaly_multiple: number
  trailing_months: number
  min_cases_to_flag: number
  cells: number
  totals: {
    cases_placed: number
    offenders: number
    apparent_offenders_before_resolution: number
    inflation_removed: number
    inflation_pct: number
  }
  anomalous_district_months: number
  months: string[]
  grid: GridCell[]
  districts: DistrictRow[]
  trends: Array<{
    district: string
    total_cases: number
    anomalous_months: number
    series: TrendPoint[]
  }>
}

/* -------------------------------------------------------- canonical */

/** Written by scripts/check_freshness.py onto any study older than the corpus. */
export type Stale = {
  is_stale: boolean
  report_generated_at: string
  corpus_generated_at: string
  refresh_with: string
  note: string
}

export type Product = {
  label: string
  purpose: string
  precision: number
  recall: number
  f1: number
  f_beta_0_5: number
  threshold_llr: number
  merged_pairs: number
  statement: string
}

export type Canonical = {
  generated_at: string
  headline: {
    precision: number
    recall: number
    f1: number
    f_beta_0_5: number
    false_merge_rate: number
  }
  definition: {
    corpus: string
    cases: number
    accused_rows: number
    name_vocabulary: number
    seed: number
    operating_point: string
    threshold_llr: number
    statement: string
  }
  how_to_read: Array<{ role: string; f1: number | null; text: string }>
  /** One model, two operating points, two different products. */
  products: {
    note: string
    deployable: Product | null
    investigative: Product
  }
  /** What no linkage method can exceed on the fields this schema provides. */
  ceiling_argument: {
    oracle_f1: number
    headline_f1: number
    share_of_ceiling: number | null
    statement: string
  }
  qualifiers: Record<string, string>
  rule: string
}

/* ----------------------------------------------------- vocabulary study */

export type VocabRun = {
  requested_vocabulary: number
  folded_tokens_realised: number
  candidate_pairs: number
  reduction_ratio: number
  pairs_completeness_pct: number
  base_rate: number
  precision: number
  recall: number
  f1: number
  multiple_over_exact: number | null
}

export type VocabFeed = {
  stale?: Stale
  generated_at: string
  cases: number
  runs: VocabRun[]
  fixture: { vocabulary: number; precision: number; f1: number; note: string }
  realistic: { vocabulary: number; precision: number; f1: number; note: string }
  sensitivity: {
    precision_gain: number
    f1_gain: number
    reduction_ratio_gain: number
    base_rate_ratio: number | null
  }
  headline_unchanged: string
}

/* ---------------------------------------------------------- scale study */

export type ScaleRun = {
  cases: number
  accused_rows: number
  candidate_pairs: number
  reduction_ratio: number
  base_rate: number
  precision: number
  recall: number
  f1: number
  clusters: number
  exact_name_f1: number
  multiple_over_exact: number | null
  total_seconds: number
  peak_python_memory_mb: number
  stages_seconds: Record<string, number>
}

export type ScaleFeed = {
  stale?: Stale
  generated_at: string
  runs: ScaleRun[]
  growth: {
    pairs_vs_rows_exponent: number
    interpretation: string
    projected_pairs_at_full_scale: number
  }
  full_scale: {
    cases: number
    accused_rows: number
    candidate_pairs: number
    largest_block_rows: number
    reduction_ratio: number
    note: string
  }
  not_run_at_full_scale: string
}

/* ------------------------------------------------------------------- runlog */

export type RunLog = {
  run_id: string
  exported_at: string
  seed: number
  corpus_generated_at?: string
  co_offending_preset?: string
  stages: Array<{ stage: string; seconds: number }>
  route_counts: Record<string, number>
  counts: Record<string, number>
  files_read: string[]
  engine: {
    linkage_method: string
    threshold_llr: number
    blocking_families: string[]
    collective_iterations: number
    collective_converged: boolean
  }
}

/* --------------------------------------------------------------------- bag */

/* ------------------------------------------- the 150 question gold set */

export type GoldQuestion = {
  id: string
  shape: string
  difficulty: 'simple' | 'moderate' | 'complex'
  question: string
  question_kn: string | null
  tables: string[]
  answerable_today: boolean
  requires_person_key: boolean
  band: 'answerable_today' | 'needs_language_layer' | 'impossible_on_raw_schema'
  sql: string
}

export type QuestionsFeed = {
  generated_at: string
  version: string
  status: string
  total_questions: number
  headline: {
    requires_person_key: number
    share_requiring_person_key: number
    statement: string
  }
  coverage: Record<string, { questions: number; share: number; meaning: string }>
  accuracy: { status: string; why: string }
  kannada: { questions_with_kannada: number; share: number; why_not_all: string }
  by_shape: Record<string, {
    questions: number
    requires_person_key: number
    answerable_today: number
    share_needing_person_key: number
  }>
  by_difficulty: Record<string, {
    questions: number
    requires_person_key: number
    answerable_today: number
  }>
  questions: GoldQuestion[]
}

/* ------------------------- the other two person bearing tables, ADR 024 */

export type PersonTable = {
  spec: string
  table: string
  note: string
  rows: number
  true_people: number
  hidden_by_fragmentation: number
  true_pairs_in_table?: number
  candidate_pairs?: number
  reduction_ratio?: number
  pairs_completeness_pct?: number
  identities_found?: number
  results: { precision: number; recall: number; f1: number }
  results_at_equal_cost?: {
    precision: number
    recall: number
    f1: number
    threshold_llr: number
    note: string
  }
  oracle_diagnostic?: {
    note: string
    clustered: { precision: number; recall: number; f1: number }
  }
  verdict?: string
  guard?: {
    table_carries_protected_columns: boolean
    protected_columns_present?: string[]
    raw_header_rejected: boolean | null
    projected_header_accepted: boolean
    columns_permitted_into_features?: string[]
  }
}

export type PersonsFeed = {
  generated_at: string
  tables: Record<string, PersonTable>
  combined: {
    person_bearing_rows: number
    actual_people: number
    rows_that_are_a_repeat: number
    invisible_relationships: number
    statement: string
  }
  method: string
}

export type GenderNoiseFeed = {
  generated_at: string
  correction: string
  runs: Array<{
    error_rate: number
    rows_flipped: number
    true_pairs_contradicted: number
    f_beta_0_5_gain: number
  }>
  summary: {
    clean_field_true_pairs_contradicted: number
    shipped_rate_true_pairs_contradicted: number
    shipped_rate_gain_f_beta_0_5: number
    highest_rate_still_positive: number | null
  }
}

export type Reports = {
  manifest: Manifest
  corpus: CorpusStats
  blocking: BlockingReport | null
  evaluation: EvalReport | null
  canonical: Canonical | null
  routing: RoutingFeed | null
  identities: IdentityFeed | null
  network: NetworkFeed | null
  cases: CasesFeed | null
  profiles: ProfilesFeed | null
  reconciliation: ReconciliationFeed | null
  hotspots: HotspotsFeed | null
  scale: ScaleFeed | null
  vocabulary: VocabFeed | null
  questions: QuestionsFeed | null
  persons: PersonsFeed | null
  genderNoise: GenderNoiseFeed | null
  runlog: RunLog | null
}
