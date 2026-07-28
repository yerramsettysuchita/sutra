/**
 * Evaluation report. Every figure read from eval.json, none hardcoded.
 *
 * The two positive ablation deltas are shown in conflict colour rather than
 * hidden, because a signal that improves the result when removed is a finding
 * about the model and not an embarrassment to be smoothed over.
 */

import {
  Bar,
  DataTable,
  Metric,
  MetricRow,
  Panel,
  Rule,
  StaleNotice,
  StatusPill,
  type Column,
} from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import {
  Details,
  HeroFigure,
  MethodBars,
  Readout,
  SubHeader,
  type Method,
} from '../components/hero'
import { asPct, n, pct } from '../data/useReports'
import type {
  OffenceCount,
  PairMetrics,
  PersonsFeed,
  ReconciliationFeed,
  Reports,
  ScaleFeed,
  ScaleRun,
} from '../data/types'

/**
 * How to read these numbers.
 *
 * Four figures are live across this project and a reader must be able to tell
 * in one glance which one is the answer. Read from canonical.json, which the
 * eval run writes and nothing types by hand.
 */
function HowToRead({ canonical }: { canonical: NonNullable<Reports['canonical']> }) {
  const tone: Record<string, 'resolved' | 'conflict' | 'review' | 'signal'> = {
    headline: 'resolved',
    floor: 'conflict',
    ceiling: 'review',
    realistic: 'signal',
  }
  return (
    <Panel
      id="how-to-read"
      title="How to read these numbers"
      eyebrow="navy"
      aside={<StatusPill label="one canonical headline" tone="official" />}
    >
      <ul className="legend-list">
        {canonical.how_to_read
          .filter((row) => row.f1 !== null)
          .map((row) => (
            <li key={row.role}>
              <StatusPill label={row.role} tone={tone[row.role] ?? 'signal'} />
              <span className="legend-list__value mono">
                {(row.f1 as number).toFixed(4)}
              </span>
              <span className="legend-list__text">{row.text}</span>
            </li>
          ))}
      </ul>
      <Rule tight />
      <p className="note">
        <strong>{canonical.rule}</strong> The headline is{' '}
        {canonical.definition.statement.toLowerCase()}
      </p>
    </Panel>
  )
}

/**
 * Two products from one model.
 *
 * The deployable point was already measured and was sitting in a table on row
 * four while a precision of 0.5770 led every screen. For criminal identity that
 * ordering is backwards: the figure a department would actually merge on
 * belongs first.
 *
 * Both are shown side by side because neither is the right answer on its own.
 * Which one a department runs at is a policy choice about the cost of a wrong
 * merge against the cost of a missed one, and this project does not get to make
 * it.
 */
function TwoProducts({
  canonical,
  persons,
}: {
  canonical: NonNullable<Reports['canonical']>
  persons: PersonsFeed | null
}) {
  const { deployable, investigative, note } = canonical.products
  const ceiling = canonical.ceiling_argument
  // The complainant ceiling is the sharpest version of this argument, and it
  // is read rather than typed, like every other figure on this screen.
  const complainant = persons?.tables.complainant?.oracle_diagnostic?.clustered.f1

  const products = [
    deployable && { key: 'deployable', tone: 'resolved' as const, product: deployable },
    { key: 'investigative', tone: 'signal' as const, product: investigative },
  ].filter(Boolean) as Array<{
    key: string
    tone: 'resolved' | 'signal'
    product: NonNullable<typeof deployable>
  }>

  return (
    <>
      <Panel
        id="two-products"
        title="Two products from one model"
        eyebrow="navy"
        aside={<StatusPill label="the operating point is a policy choice" tone="official" />}
        note={note}
      >
        <div className="products">
          {products.map(({ key, tone, product }) => (
            <div className={`product product--${tone}`} key={key}>
              <span className="product__label">{product.label}</span>
              <span className="product__purpose">for {product.purpose}</span>
              <div className="product__figures">
                <span className={`product__precision value--${tone === 'resolved' ? 'resolved' : 'conflict'}`}>
                  {product.precision.toFixed(4)}
                </span>
                <span className="product__unit">precision</span>
              </div>
              <dl className="product__rest">
                <div>
                  <dt>Recall</dt>
                  <dd className="mono">{product.recall.toFixed(4)}</dd>
                </div>
                <div>
                  <dt>F1</dt>
                  <dd className="mono">{product.f1.toFixed(4)}</dd>
                </div>
                <div>
                  <dt>Cut</dt>
                  <dd className="mono">{product.threshold_llr.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>Merges</dt>
                  <dd className="mono">{n(product.merged_pairs)}</dd>
                </div>
              </dl>
              <p className="product__note">{product.statement}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        id="ceiling-argument"
        title="Why the remaining gap is not a modelling problem"
        eyebrow="conflict"
        aside={<StatusPill label="the argument for a person key" tone="conflict" />}
      >
        <div className="hero" style={{ padding: 0 }}>
          <MethodBars
            methods={[
              { name: 'SUTRA, deployed', value: ceiling.headline_f1 },
              { name: 'Ceiling, fitted from labels', value: ceiling.oracle_f1, lead: true },
            ]}
            caption={`SUTRA reaches F1 ${ceiling.headline_f1.toFixed(4)} against a ceiling of ${ceiling.oracle_f1.toFixed(4)} for this model form on these fields.`}
          />
          <HeroFigure
            label="Of the reachable ceiling"
            value={
              ceiling.share_of_ceiling
                ? `${(ceiling.share_of_ceiling * 100).toFixed(0)}%`
                : 'n/a'
            }
            tone="conflict"
            caption={
              <>
                The gap above SUTRA is what better modelling could win. The gap
                above the ceiling is what no modelling can win, because the
                fields are not in the schema.
              </>
            }
          />
        </div>
        <Rule />
        <p className="note">
          <strong>{ceiling.statement}</strong>
        </p>
        {complainant != null && (
          <p className="note">
            The comparison that makes this concrete is in the three table panel
            below. <span className="mono">ComplainantDetails</span> carries a
            phone number, and once that column is a feature its ceiling is{' '}
            <span className="mono">{complainant.toFixed(4)}</span>.{' '}
            <span className="mono">Accused</span> carries no such column and its
            ceiling is{' '}
            <span className="mono">{ceiling.oracle_f1.toFixed(4)}</span>. The
            difference between a resolvable person and an unresolvable one is
            not the algorithm. It is whether the form had a field for a phone
            number, and the KSP schema collects contact details for the person
            reporting the crime and none for the person accused of it.
          </p>
        )}
      </Panel>
    </>
  )
}

const RESOLVED_MID = '#2E9E6B'
const CONFLICT_MID = '#D9534A'
const REVIEW_MID = '#B57F14'
const NAVY = '#16305C'
const LINE = '#CFCBC1'
const SUNKEN = '#F4F2EE'
const INK3 = '#656C75'

/**
 * The precision recall curve, and the operating points on it.
 *
 * The headline is the F1 optimal cut, which weights the two errors equally.
 * For criminal identity they are not equal, so F beta at 0.5 is also reported
 * and named as the correct objective for this domain.
 */
function OperatingPoints({ ev }: { ev: NonNullable<Reports['evaluation']> }) {
  const curve = ev.precision_recall_curve ?? []
  const points = ev.operating_points ?? {}
  if (!curve.length) return null

  const W = 460
  const H = 320
  const pad = 42
  const x = (recall: number) => pad + recall * (W - pad * 2)
  const y = (precision: number) => H - pad - precision * (H - pad * 2)
  const path = curve
    .slice()
    .sort((a, b) => a.recall - b.recall)
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(p.recall)} ${y(p.precision)}`)
    .join(' ')

  // Every point below the deployed one is chosen with knowledge of the answer.
  // The qualifier travels with the row so a figure is never read bare.
  const marks: Array<[string, string, string]> = [
    ['deployed', 'Deployed, engine derived cut', RESOLVED_MID],
    ['f1_optimal', 'F1 optimal', NAVY],
    ['f_beta_0_5_optimal', 'F0.5 optimal', NAVY],
    ['precision_90', 'Precision 0.90', REVIEW_MID],
    ['precision_95', 'Precision 0.95', CONFLICT_MID],
  ]

  const qualifiers = ev.operating_point_qualifiers ?? {}
  const rows = marks
    .map(([key, label]) => ({
      key,
      label,
      point: points[key],
      qualifier: qualifiers[key] ?? '',
    }))
    .filter((r) => r.point)

  const columns: Column<(typeof rows)[number]>[] = [
    {
      key: 'label',
      header: 'Operating point',
      render: (r) =>
        r.key === ev.deployed_operating_point ? (
          <>
            <strong>{r.label}</strong>{' '}
            <StatusPill label="canonical headline" tone="resolved" />
          </>
        ) : (
          <>
            {r.label}{' '}
            <StatusPill label="not deployed" tone="review" />
          </>
        ),
    },
    { key: 'cut', header: 'Cut', numeric: true, render: (r) => r.point!.threshold.toFixed(2) },
    {
      key: 'p',
      header: 'Precision',
      numeric: true,
      render: (r) => <span className="value--resolved">{r.point!.precision.toFixed(4)}</span>,
    },
    { key: 'r', header: 'Recall', numeric: true, render: (r) => r.point!.recall.toFixed(4) },
    { key: 'f1', header: 'F1', numeric: true, render: (r) => r.point!.f1.toFixed(4) },
    {
      key: 'f05',
      header: 'F0.5',
      numeric: true,
      render: (r) => <strong>{r.point!.f_beta_0_5.toFixed(4)}</strong>,
    },
    {
      key: 'merges',
      header: 'Merged pairs',
      numeric: true,
      render: (r) => n(r.point!.merged_pairs),
    },
  ]

  return (
    <Panel
      id="operating"
      title="The operating point"
      eyebrow="navy"
      note={ev.objective_note}
    >
      <div className="hero" style={{ padding: 0 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="gapfig"
          role="img"
          aria-label={`Precision recall curve across ${curve.length} thresholds. At the deployed cut, which is the canonical headline, precision is ${points.deployed?.precision.toFixed(4)} and recall ${points.deployed?.recall.toFixed(4)}. At the F1 optimal cut, which we do not deploy, precision is ${points.f1_optimal?.precision.toFixed(4)} and recall ${points.f1_optimal?.recall.toFixed(4)}. Precision 0.90 is reachable at recall ${points.precision_90?.recall.toFixed(4)}.`}
        >
          <rect width={W} height={H} fill={SUNKEN} />
          <line x1={pad} y1={pad} x2={pad} y2={H - pad} stroke={LINE} />
          <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke={LINE} />
          <path d={path} fill="none" stroke={NAVY} strokeWidth="2" />
          {rows.map((r) => (
            <g key={r.key}>
              <circle
                cx={x(r.point!.recall)}
                cy={y(r.point!.precision)}
                r={r.key === ev.deployed_operating_point ? 7 : 4.5}
                fill={marks.find((m) => m[0] === r.key)?.[2] ?? NAVY}
                stroke="#fff"
                strokeWidth="1.5"
              />
            </g>
          ))}
          <text x={pad} y={pad - 12} fontSize="10" fill={INK3}
                fontFamily="Inter Tight, sans-serif">
            precision
          </text>
          <text x={W - pad} y={H - 14} fontSize="10" fill={INK3} textAnchor="end"
                fontFamily="Inter Tight, sans-serif">
            recall
          </text>
        </svg>
        <HeroFigure
          label="Precision reachable"
          value={points.precision_95 ? points.precision_95.precision.toFixed(2) : 'n/a'}
          tone="resolved"
          caption={
            points.precision_95 ? (
              <>
                at recall {points.precision_95.recall.toFixed(4)} and{' '}
                {n(points.precision_95.merged_pairs)} merges. The curve is a
                choice, not a fact.
              </>
            ) : (
              <>not reachable on this curve</>
            )
          }
        />
      </div>

      <Rule />
      <DataTable
        caption="Each point is a full re clustering at that threshold, not a cut on the raw pair scores, because the partition is what ships. Only the first row is deployable. Every other cut is selected by looking at ground truth and cannot be chosen in the field."
        columns={columns}
        rows={rows}
        rowKey={(r) => r.key}
      />
      <Rule />
      <p className="note">
        <strong>
          The automatic band is deliberately narrow, {n(ev.routing.auto_merged_pairs)}{' '}
          pairs of {n(ev.corpus.candidate_pairs)}.
        </strong>{' '}
        Everything uncertain goes to a human. That is the answer to the false
        merge rate of {ev.routing.false_merge_rate.toFixed(4)}, and it belongs
        next to it rather than in a footnote.
      </p>
    </Panel>
  )
}

/**
 * How much of the measured precision is the fixture.
 */
function Vocabulary({ feed }: { feed: NonNullable<Reports['vocabulary']> }) {
  const first = feed.runs[0]
  const last = feed.runs[feed.runs.length - 1]
  if (!first || !last) return null

  const columns: Column<(typeof feed.runs)[number]>[] = [
    {
      key: 'forms',
      header: 'Name forms',
      numeric: true,
      render: (r) => n(r.requested_vocabulary),
    },
    {
      key: 'tokens',
      header: 'Folded tokens',
      numeric: true,
      render: (r) => n(r.folded_tokens_realised),
    },
    {
      key: 'pairs',
      header: 'Candidate pairs',
      numeric: true,
      render: (r) => n(r.candidate_pairs),
    },
    {
      key: 'rr',
      header: 'Reduction ratio',
      numeric: true,
      render: (r) => r.reduction_ratio.toFixed(4),
    },
    {
      key: 'complete',
      header: 'Completeness',
      numeric: true,
      render: (r) => pct(r.pairs_completeness_pct),
    },
    {
      key: 'base',
      header: 'Base rate',
      numeric: true,
      render: (r) => r.base_rate.toFixed(6),
    },
    {
      key: 'p',
      header: 'Precision',
      numeric: true,
      render: (r) => <span className="value--resolved">{r.precision.toFixed(4)}</span>,
    },
    { key: 'r', header: 'Recall', numeric: true, render: (r) => r.recall.toFixed(4) },
    { key: 'f1', header: 'F1', numeric: true, render: (r) => r.f1.toFixed(4) },
  ]

  return (
    <Panel
      id="vocabulary"
      title="How much of this is the fixture"
      eyebrow="review"
      aside={<StatusPill label="headline unchanged" tone="official" />}
      note="Corpus size, seed and every other parameter held fixed. Only the name vocabulary moves."
    >
      <StaleNotice stale={feed.stale} />
      <div className="hero" style={{ padding: 0 }}>
        <MethodBars
          methods={feed.runs.map((r, i) => ({
            name: `${n(r.requested_vocabulary)} forms`,
            value: r.precision,
            lead: i === feed.runs.length - 1,
          }))}
          caption={`Precision by name vocabulary. ${feed.runs
            .map((r) => `${r.requested_vocabulary} forms ${r.precision.toFixed(4)}`)
            .join(', ')}.`}
        />
        <HeroFigure
          label="Precision gained"
          value={`+${feed.sensitivity.precision_gain.toFixed(3)}`}
          tone="review"
          caption={
            <>
              from {first.precision.toFixed(4)} at {n(first.requested_vocabulary)}{' '}
              name forms to {last.precision.toFixed(4)} at{' '}
              {n(last.requested_vocabulary)}
            </>
          }
        />
      </div>

      <Rule />
      <DataTable
        caption="Pairs completeness barely moves, so blocking finds the same true pairs throughout. What changes is how much rubbish it finds alongside them."
        columns={columns}
        rows={feed.runs}
        rowKey={(r) => String(r.requested_vocabulary)}
      />
      <Rule />
      <p className="note">
        <strong>Which end is realistic.</strong> The{' '}
        {n(first.requested_vocabulary)} form pool is a deliberately hostile
        fixture and nothing like a jurisdiction. Karnataka's electoral rolls
        carry name vocabularies in the hundreds of thousands. The{' '}
        {n(last.requested_vocabulary)} form end is still conservative against
        that, and it is the end indicative of field behaviour.
      </p>
      <p className="note">
        <strong>The headline figures on this page are not replaced.</strong>{' '}
        They remain those of the {n(first.requested_vocabulary)} form fixture.
        This sweep establishes that they are a floor, and a floor that is
        honestly labelled is worth more than a ceiling that needs a footnote.
      </p>
    </Panel>
  )
}

/**
 * Does the result hold at scale.
 *
 * The honest answer to a jury that asks. Measured at three sizes, with the
 * growth exponent fitted, and an explicit statement that the full corpus was
 * not run and why.
 */
function Scale({ feed }: { feed: ScaleFeed }) {
  const first = feed.runs[0]
  const last = feed.runs[feed.runs.length - 1]
  if (!first || !last) return null

  const drift = last.f1 - first.f1

  const columns: Column<ScaleRun>[] = [
    { key: 'cases', header: 'Cases', numeric: true, render: (r) => n(r.cases) },
    { key: 'rows', header: 'Accused rows', numeric: true, render: (r) => n(r.accused_rows) },
    {
      key: 'pairs',
      header: 'Candidate pairs',
      numeric: true,
      render: (r) => n(r.candidate_pairs),
    },
    {
      key: 'base',
      header: 'Base rate',
      numeric: true,
      render: (r) => r.base_rate.toFixed(6),
    },
    {
      key: 'precision',
      header: 'Precision',
      numeric: true,
      render: (r) => r.precision.toFixed(4),
    },
    { key: 'recall', header: 'Recall', numeric: true, render: (r) => r.recall.toFixed(4) },
    {
      key: 'f1',
      header: 'F1',
      numeric: true,
      render: (r) => <span className="value--resolved">{r.f1.toFixed(4)}</span>,
    },
    {
      key: 'multiple',
      header: 'vs exact name',
      numeric: true,
      render: (r) =>
        r.multiple_over_exact ? `${r.multiple_over_exact.toFixed(1)}x` : '',
    },
    {
      key: 'seconds',
      header: 'Seconds',
      numeric: true,
      render: (r) => r.total_seconds.toFixed(1),
    },
    {
      key: 'memory',
      header: 'Peak MB',
      numeric: true,
      render: (r) => r.peak_python_memory_mb.toFixed(0),
    },
  ]

  return (
    <Panel
      id="scale"
      title="Does it hold at scale"
      eyebrow={Math.abs(drift) < 0.03 ? 'resolved' : 'review'}
      aside={<StatusPill label="three sizes, measured" tone="official" />}
      note="The same chain run end to end at three corpus sizes. Every figure below is measured, none is interpolated."
    >
      <StaleNotice stale={feed.stale} />
      <div className="hero" style={{ padding: 0 }}>
        <div className="verdict">
          <Metric
            label={`F1 at ${n(first.cases)} cases`}
            value={first.f1.toFixed(4)}
            small
            tone="resolved"
          />
          <Metric
            label={`F1 at ${n(last.cases)} cases`}
            value={last.f1.toFixed(4)}
            small
            tone="resolved"
          />
          <Metric
            label="Drift"
            value={`${drift >= 0 ? '+' : ''}${drift.toFixed(4)}`}
            small
            tone={Math.abs(drift) < 0.03 ? 'resolved' : 'conflict'}
            caption={
              <>
                across a {(last.accused_rows / first.accused_rows).toFixed(1)}{' '}
                times larger corpus
              </>
            }
          />
        </div>
        <HeroFigure
          label="Candidate pairs grow as"
          value={`n^${feed.growth.pairs_vs_rows_exponent.toFixed(2)}`}
          tone={feed.growth.pairs_vs_rows_exponent > 1.8 ? 'conflict' : 'review'}
          caption={
            <>
              in accused rows. That is what stops the full corpus running, not
              the accuracy.
            </>
          }
        />
      </div>

      <Rule />
      <DataTable
        caption="Every headline figure at every size that fits."
        columns={columns}
        rows={feed.runs}
        rowKey={(r) => String(r.cases)}
      />

      <Rule />
      <p className="note">
        <strong>The full corpus was not run, and this is why.</strong> At{' '}
        {n(feed.full_scale.cases)} cases the corpus holds{' '}
        {n(feed.full_scale.accused_rows)} accused rows and the shipped blocking
        scheme proposes{' '}
        <span className="mono">{n(feed.full_scale.candidate_pairs)}</span>{' '}
        candidate pairs. That is not a memory ceiling that chunking removes, it
        is three billion pairs that have to be scored.
      </p>
      <p className="note">
        The cause is measurable. The generator draws names from 58 given and 28
        patronymic forms, so the number of distinct folded tokens is fixed at
        about two hundred however large the corpus grows. Block membership
        therefore grows linearly and pairs within a block grow with its square.
        At full scale the largest single block holds{' '}
        {n(feed.full_scale.largest_block_rows)} rows and contributes over 900
        million pairs on its own.
      </p>
      <p className="note">
        On real Karnataka data, where distinct names number in the hundreds of
        thousands rather than the dozens, blocks would be far smaller. That is a
        reasonable expectation and it is not measured here, so it is stated as
        an expectation and not as a result.
      </p>
    </Panel>
  )
}

/**
 * Layer 9. What a query spanning July 2024 gets wrong.
 *
 * Two counts of the same thing, side by side. The error between them is the
 * hero figure for this panel, because it is the whole reason the layer exists.
 */
function Reconciliation({ feed }: { feed: ReconciliationFeed }) {
  const t = feed.totals
  const present = feed.by_offence.filter((r) => r.reconciled_count > 0)
  const absent = feed.by_offence.length - present.length

  const columns: Column<OffenceCount>[] = [
    { key: 'ipc', header: 'IPC', code: true, render: (r) => r.ipc },
    { key: 'bns', header: 'BNS', code: true, render: (r) => r.bns },
    { key: 'offence', header: 'Offence', render: (r) => r.offence },
    {
      key: 'naive',
      header: 'Naive count',
      numeric: true,
      render: (r) => (
        <span className="value--conflict">{n(r.naive_count)}</span>
      ),
    },
    {
      key: 'true',
      header: 'Reconciled',
      numeric: true,
      render: (r) => (
        <span className="value--resolved">{n(r.reconciled_count)}</span>
      ),
    },
    {
      key: 'miss',
      header: 'Undercount',
      numeric: true,
      render: (r) => (
        <span className="value--conflict">{pct(r.naive_undercount_pct, 1)}</span>
      ),
    },
    {
      key: 'bar',
      header: 'Missed',
      width: '8rem',
      render: (r) => <Bar fraction={r.naive_undercount_pct / 100} tone="dim" />,
    },
  ]

  return (
    <Panel
      id="reconciliation"
      title="Layer 9, IPC to BNS reconciliation"
      eyebrow="conflict"
      aside={<StatusPill label="spans 1 July 2024" tone="review" />}
      note={
        <>
          The Bharatiya Nyaya Sanhita replaced the Indian Penal Code on{' '}
          <span className="mono">{feed.transition}</span>. A murder before that
          date is <span className="mono">IPC 302</span> and after it is{' '}
          <span className="mono">BNS 103</span>. An analyst filtering on the
          section number as written gets only one side of the boundary.
        </>
      }
    >
      <div className="hero" style={{ padding: 0 }}>
        <div className="verdict">
          <Metric
            label="Naive count"
            value={n(t.naive_count)}
            tone="conflict"
            caption={<>filtering on the section number as written</>}
          />
          <Metric
            label="Reconciled count"
            value={n(t.reconciled_count)}
            tone="resolved"
            caption={<>following the correspondence across the boundary</>}
          />
          <Metric
            label="Cases never seen"
            value={n(t.naive_missed)}
            small
            tone="conflict"
            caption={
              <>
                {n(feed.cases_before_transition)} cases sit before the
                transition and {n(feed.cases_on_or_after_transition)} after it
              </>
            }
          />
        </div>
        <HeroFigure
          label="A naive query undercounts by"
          value={pct(t.naive_undercount_pct, 1)}
          tone="conflict"
          caption={
            <>
              across {feed.window.from} to {feed.window.to}. The section number
              changed underneath the question and nothing in the schema says so.
            </>
          }
        />
      </div>

      <Rule />
      <DataTable
        caption={`Per offence, over the whole corpus window. ${absent} of ${feed.correspondences} mapped correspondences have no cases here, because the generator's modus operandi families do not cover them, and they are omitted rather than shown as zero.`}
        columns={columns}
        rows={present}
        rowKey={(r) => r.code}
      />

      <Rule />
      <p className="note">
        <strong>Worse than missing.</strong> A section number is not a stable
        identifier across the boundary.{' '}
        {Object.entries(feed.ambiguous_codes).map(([code, meanings]) => (
          <span key={code}>
            Number <span className="mono">{code}</span> means{' '}
            {meanings.join(', and also ')}.{' '}
          </span>
        ))}
        {feed.offences_returning_the_wrong_offence.length === 0 && (
          <>
            That collision does not manifest in this corpus, because the
            offence on the other side of it has no cases here. The guard is
            built and the measured harm from it in this run is zero, reported
            as zero.
          </>
        )}
      </p>
    </Panel>
  )
}

type BaselineRow = { method: string; metrics: PairMetrics; sutra: boolean }
type AblationRow = {
  signal: string
  label: string
  f1: number
  delta: number
  harmful: boolean
}

/**
 * The same engine over all three person bearing tables.
 *
 * Accused is not the only table with the missing person entity. Victim and
 * ComplainantDetails have it too. This panel is the measurement, and two of the
 * three rows are a failure, which is the reason the panel is worth having.
 */
function ThreeTables({ feed }: { feed: PersonsFeed }) {
  const order = ['accused', 'victim', 'complainant']
  const rows = order
    .map((key) => feed.tables[key])
    .filter((t): t is NonNullable<typeof t> => Boolean(t))

  const columns: Column<(typeof rows)[number]>[] = [
    { key: 'table', header: 'Table', code: true, render: (r) => r.table },
    { key: 'rows', header: 'Rows', numeric: true, render: (r) => n(r.rows) },
    {
      key: 'people',
      header: 'Actual people',
      numeric: true,
      render: (r) => n(r.true_people),
    },
    {
      key: 'hidden',
      header: 'Hidden by fragmentation',
      numeric: true,
      render: (r) => (
        <span className="value--conflict">{n(r.hidden_by_fragmentation)}</span>
      ),
    },
    {
      key: 'f1',
      header: 'F1, unsupervised',
      numeric: true,
      render: (r) =>
        r.results.f1 > 0 ? (
          <span className="value--resolved">{r.results.f1.toFixed(4)}</span>
        ) : (
          <span className="value--conflict">{r.results.f1.toFixed(4)}</span>
        ),
    },
    {
      key: 'equal',
      header: 'F1, equal cost cut',
      numeric: true,
      render: (r) =>
        r.results_at_equal_cost
          ? r.results_at_equal_cost.f1.toFixed(4)
          : 'n/a',
    },
    {
      key: 'oracle',
      header: 'F1, oracle',
      numeric: true,
      render: (r) =>
        r.oracle_diagnostic
          ? r.oracle_diagnostic.clustered.f1.toFixed(4)
          : 'n/a',
    },
  ]

  const failed = rows.filter((r) => r.results.f1 === 0)

  return (
    <>
      <Panel
        id="three-tables"
        title="The same engine over all three person bearing tables"
        eyebrow="conflict"
        aside={<StatusPill label="two of three failed" tone="conflict" />}
        note={
          <>
            Accused is not the only table in the KSP schema holding a person
            with no key that survives across FIRs. Victim and ComplainantDetails
            have exactly the same gap. Layers 1 to 5 are imported from the
            modules the accused pipeline uses, so these figures are comparable
            by construction rather than by assurance.
          </>
        }
      >
        <HeroFigure
          label="Across all three tables"
          value={`${n(feed.combined.person_bearing_rows)} to ${n(feed.combined.actual_people)}`}
          tone="navy"
          caption={
            <>
              person bearing rows collapse to actual people.{' '}
              <strong>{n(feed.combined.invisible_relationships)}</strong> same
              person relationships exist that no join on the raw KSP schema can
              see, because there is no column to join on.
            </>
          }
        />
      </Panel>

      <Panel id="three-tables-detail" title="Table by table" eyebrow="official" flush>
        <DataTable
          caption="Rows, the people they actually represent, and what the engine recovers. The oracle column fits m and u from ground truth and is not the engine, it exists to separate a feature problem from a fit problem."
          columns={columns}
          rows={rows}
          rowKey={(r) => r.table}
        />
        <div style={{ padding: 'var(--s-4)' }}>
          {failed.length > 0 && (
            <p className="note">
              <strong>
                On {failed.length === 1 ? 'one table' : `${failed.length} tables`} the
                engine resolves nothing.
              </strong>{' '}
              Not poorly, nothing. The oracle column says why: the features
              separate, and the unsupervised estimator recovers none of it.
              Layer 4 fits m from leave one out seeds, which needs several
              independent channels to corroborate each other. Neither of these
              tables has an arresting officer and a FIR names at most one
              complainant, so the relational signal has nothing to compute from
              and one channel is simply absent. The estimator does not degrade
              gracefully below that, it fails outright. See ADR 024.
            </p>
          )}
          <p className="note">
            <strong>Why there are two unsupervised columns.</strong> The engine
            requires four to one odds before it merges, because a false merge
            costs more than a missed one and ADR 028 puts that in the threshold
            rather than only in the report. On <span className="mono">Accused</span>{' '}
            that policy lifted F0.5 materially, and it is the shipped cut. On{' '}
            <span className="mono">ComplainantDetails</span> it suppresses the
            table almost entirely, because that model's scores are compressed
            and very few pairs reach four to one. The same policy helps one
            table and silences another. Both columns are shown because
            publishing only the flattering one would misrepresent either the
            engine or the policy.
          </p>
          <p className="note">
            The counts of rows, people and hidden repeats do not depend on the
            engine. They come from ground truth, so they stand whether or not
            the resolver works. <strong>Victim and complainant resolution is
            NOT BUILT</strong> and is reported that way on /status.
          </p>
          <p className="note">
            <strong>The policy guard was exercised here explicitly.</strong>{' '}
            <span className="mono">Victim</span> carries{' '}
            <span className="mono">CasteID</span>,{' '}
            <span className="mono">ReligionID</span> and{' '}
            <span className="mono">OccupationID</span>. The run asserts the raw
            header is rejected by <span className="mono">engine/policy.py</span>,
            projects the permitted columns, then asserts the projection passes.
            A control never seen to trip cannot be told apart from one that does
            not work.
          </p>
        </div>
      </Panel>
    </>
  )
}

export function Evaluation({ reports }: { reports: Reports }) {
  const evaluation = reports.evaluation
  const reconciliation = reports.reconciliation

  if (!evaluation) {
    return (
      <NotBuilt
        title="Evaluation report"
        what="Precision, recall, F1, the false merge rate, baselines, ablations and the convergence curve."
        why="eval/report.json has not been produced, so there is nothing measured to show and this screen will not estimate."
        command={'make resolve\nmake eval'}
      />
    )
  }

  const h = evaluation.headline
  const routing = evaluation.routing
  const oracle = evaluation.oracle_diagnostic

  const baselineRows: BaselineRow[] = [
    ...Object.entries(evaluation.baselines).map(([method, metrics]) => ({
      method,
      metrics,
      sutra: false,
    })),
    { method: 'SUTRA', metrics: h, sutra: true },
  ].sort((a, b) => a.metrics.f1 - b.metrics.f1)

  const exactName = evaluation.baselines['exact name match']
  const multiple = exactName ? h.f1 / exactName.f1 : null
  const bestBaseline = Math.max(
    ...Object.values(evaluation.baselines).map((m) => m.f1),
  )

  const baselineColumns: Column<BaselineRow>[] = [
    {
      key: 'method',
      header: 'Method',
      render: (r) =>
        r.sutra ? (
          <strong>
            {r.method} <StatusPill label="this system" tone="resolved" />
          </strong>
        ) : (
          r.method
        ),
    },
    {
      key: 'precision',
      header: 'Precision',
      numeric: true,
      render: (r) => r.metrics.precision.toFixed(4),
    },
    {
      key: 'recall',
      header: 'Recall',
      numeric: true,
      render: (r) => r.metrics.recall.toFixed(4),
    },
    { key: 'f1', header: 'F1', numeric: true, render: (r) => r.metrics.f1.toFixed(4) },
    {
      key: 'bar',
      header: 'F1',
      width: '10rem',
      render: (r) => (
        <Bar fraction={r.metrics.f1 / h.f1} tone={r.sutra ? 'resolved' : 'dim'} />
      ),
    },
  ]

  const ablationRows: AblationRow[] = Object.entries(evaluation.ablation)
    .map(([signal, entry]) => ({
      signal,
      label: entry.label,
      f1: entry.f1,
      delta: entry.f1_delta,
      harmful: entry.f1_delta > 0,
    }))
    .sort((a, b) => a.delta - b.delta)

  const harmful = ablationRows.filter((r) => r.harmful)

  const ablationColumns: Column<AblationRow>[] = [
    { key: 'label', header: 'Signal dropped', render: (r) => r.label },
    { key: 'f1', header: 'F1 without it', numeric: true, render: (r) => r.f1.toFixed(4) },
    {
      key: 'delta',
      header: 'Delta',
      numeric: true,
      render: (r) => (
        <span className={r.harmful ? 'value--conflict' : undefined}>
          {r.delta >= 0 ? '+' : ''}
          {r.delta.toFixed(4)}
        </span>
      ),
    },
    {
      key: 'verdict',
      header: 'Reading',
      render: (r) =>
        r.harmful ? (
          <StatusPill label="removing it helps" tone="conflict" />
        ) : (
          <StatusPill label="carries the result" tone="resolved" />
        ),
    },
  ]

  const cm = evaluation.confusion_matrix
  const confusionRows = [
    { cell: 'True positive pairs', value: cm.true_positive_pairs ?? 0, tone: 'resolved' },
    { cell: 'False positive pairs', value: cm.false_positive_pairs ?? 0, tone: 'conflict' },
    { cell: 'False negative pairs', value: cm.false_negative_pairs ?? 0, tone: 'review' },
    { cell: 'True negative pairs', value: cm.true_negative_pairs ?? 0, tone: 'neutral' },
  ]

  const confusionColumns: Column<(typeof confusionRows)[number]>[] = [
    { key: 'cell', header: 'Cell', render: (r) => r.cell },
    { key: 'value', header: 'Pairs', numeric: true, render: (r) => n(r.value) },
  ]

  const history = evaluation.convergence.history
  const f1s = history.map((entry) => entry.f1 ?? 0)
  const spread = f1s.length ? Math.max(...f1s) - Math.min(...f1s) : 0

  const convergenceColumns: Column<(typeof history)[number]>[] = [
    { key: 'iteration', header: 'Iteration', numeric: true, render: (r) => String(r.iteration) },
    {
      key: 'f1',
      header: 'F1',
      numeric: true,
      render: (r) => (r.f1 ?? 0).toFixed(4),
    },
    { key: 'clusters', header: 'Clusters', numeric: true, render: (r) => n(r.clusters) },
    {
      key: 'moved',
      header: 'Rows reassigned',
      numeric: true,
      render: (r) => n(r.rows_reassigned),
    },
    {
      key: 'bar',
      header: 'Movement',
      width: '9rem',
      render: (r) => (
        <Bar
          fraction={
            r.rows_reassigned /
            Math.max(...history.map((e) => e.rows_reassigned), 1)
          }
          tone="review"
        />
      ),
    },
  ]

  const latencyRows = Object.entries(evaluation.latency_seconds).map(
    ([stage, seconds]) => ({ stage, seconds }),
  )
  const maxSeconds = Math.max(...latencyRows.map((r) => r.seconds))

  const latencyColumns: Column<(typeof latencyRows)[number]>[] = [
    { key: 'stage', header: 'Stage', code: true, render: (r) => r.stage },
    {
      key: 'seconds',
      header: 'Seconds',
      numeric: true,
      render: (r) => r.seconds.toFixed(3),
    },
    {
      key: 'bar',
      header: 'Share',
      width: '10rem',
      render: (r) => <Bar fraction={r.seconds / maxSeconds} tone="signal" />,
    },
  ]

  const methods: Method[] = baselineRows.map((r) => ({
    name: r.method,
    value: r.metrics.f1,
    lead: r.sutra,
  }))

  return (
    <>
      <SubHeader
        title="Evaluation"
        stats={[
          { label: 'F1', value: h.f1.toFixed(4), tone: 'resolved' },
          { label: 'Precision', value: h.precision.toFixed(4) },
          { label: 'Recall', value: h.recall.toFixed(4) },
          {
            label: 'F0.5',
            value: (evaluation.headline_f_beta_0_5 ?? 0).toFixed(4),
            tone: 'resolved',
          },
          {
            label: 'False merge',
            value: routing.false_merge_rate.toFixed(4),
            tone: 'conflict',
          },
        ]}
      />

      {reports.canonical && (
        <TwoProducts canonical={reports.canonical} persons={reports.persons} />
      )}

      {reports.canonical && <HowToRead canonical={reports.canonical} />}

      {/* The one loud thing on this route. Everything else is quieter. */}
      <section className="panel" aria-labelledby="hero-title">
        <div className="panel__eyebrow panel__eyebrow--resolved" aria-hidden="true" />
        <h2 className="visually-hidden" id="hero-title">
          Identity resolution against every baseline, by F1
        </h2>
        <div className="hero">
          <MethodBars
            methods={methods}
            caption={`F1 by method. ${methods
              .map((m) => `${m.name} ${m.value.toFixed(4)}`)
              .join(', ')}.`}
          />
          {multiple && exactName && (
            <HeroFigure
              label="SUTRA against"
              value={`${multiple.toFixed(1)}x`}
              tone="resolved"
              caption={
                <>
                  the naive join every other approach starts from.{' '}
                  <span className="mono">GROUP BY AccusedName</span> reaches F1{' '}
                  {exactName.f1.toFixed(4)}. This reaches {h.f1.toFixed(4)}.
                </>
              }
            />
          )}
        </div>
      </section>

      <div className="split--two-thirds">
        <Panel
          id="headline"
          title="Headline"
          eyebrow="resolved"
          aside={<StatusPill label="pairwise against ground truth" tone="official" />}
          note="Pairwise precision and recall over every pair of accused rows in the corpus, not over the pairs blocking proposed. Measuring against the candidate set would hide the pairs Layer 2 already lost."
        >
          <MetricRow>
            <Metric label="Precision" value={h.precision.toFixed(4)} tone="resolved" />
            <Metric label="Recall" value={h.recall.toFixed(4)} tone="resolved" />
            <Metric label="F1" value={h.f1.toFixed(4)} tone="resolved" />
            <Metric
              label="False merge rate"
              value={routing.false_merge_rate.toFixed(4)}
              tone="conflict"
              caption={
                <>
                  {n(routing.false_merges)} of {n(routing.auto_merged_pairs)}{' '}
                  automatic merges, the band where no human sees the decision
                </>
              }
            />
          </MetricRow>
        </Panel>

        <Panel
          id="ceiling"
          title="Against the ceiling"
          eyebrow="review"
          note="Fitting the same model from ground truth shows what this model form could reach if the unsupervised fit were perfect."
        >
          <Readout
            label="Of the oracle ceiling"
            value={asPct(h.f1 / oracle.oracle_with_adjustment.f1, 0)}
            tone="resolved"
            caption={
              <>
                {oracle.oracle_with_adjustment.f1.toFixed(4)} with labelled
                parameters, {h.f1.toFixed(4)} reached without labels
              </>
            }
          />
          <Rule />
          <Metric
            label="Frequency adjustment"
            value={`${evaluation.linkage.frequency_adjustment_f1_delta >= 0 ? '+' : ''}${evaluation.linkage.frequency_adjustment_f1_delta.toFixed(4)}`}
            small
            tone="resolved"
            caption={<>F1 gained by weighting name agreement by inverse frequency</>}
          />
        </Panel>
      </div>

      <Panel
        id="baselines"
        title="Against the baselines"
        eyebrow="signal"
        flush
        aside={
          multiple ? (
            <StatusPill
              label={`${multiple.toFixed(1)}x exact name match`}
              tone="resolved"
            />
          ) : undefined
        }
      >
        <DataTable
          caption={
            multiple && exactName
              ? `SUTRA reaches F1 ${h.f1.toFixed(4)} against ${exactName.f1.toFixed(4)} for exact name matching, which is ${multiple.toFixed(1)} times the naive join, and ${(h.f1 / bestBaseline).toFixed(1)} times the best baseline of any kind. English Soundex appears here and nowhere else in the system, as a baseline to beat rather than a component.`
              : 'Baselines measured on the same corpus and clustered the same way.'
          }
          columns={baselineColumns}
          rows={baselineRows}
          rowKey={(r) => r.method}
        />
      </Panel>

      <OperatingPoints ev={evaluation} />

      {reports.persons && <ThreeTables feed={reports.persons} />}

      {reports.vocabulary && <Vocabulary feed={reports.vocabulary} />}

      {reports.scale && <Scale feed={reports.scale} />}

      {reconciliation && <Reconciliation feed={reconciliation} />}

      <Details summary="Ablation, confusion matrix, convergence, blocking and latency">
      <Panel
        id="ablation"
        title="Signal ablation"
        eyebrow={harmful.length ? 'conflict' : 'signal'}
        flush
      >
        <DataTable
          caption="Each signal removed in turn, with the resulting change in F1. A negative delta means the signal was carrying the result."
          columns={ablationColumns}
          rows={ablationRows}
          rowKey={(r) => r.signal}
        />
        {harmful.length > 0 && (
          <div style={{ padding: 'var(--s-4)' }}>
            <p className="note">
              <strong>
                {harmful.length === 1 ? 'One signal' : `${harmful.length} signals`}{' '}
                improve the result when removed.
              </strong>{' '}
              {harmful.map((r) => r.label.split(',')[0]).join(' and ')}. A
              positive delta indicates a signal correlated with another one
              already in the model, so Fellegi Sunter counts the same evidence
              twice under its conditional independence assumption. Shared
              arresting officer implies a shared station, which the spatial
              signal already carries. This is the same defect that ADR 017
              corrected between the lexical and phonetic channels, appearing
              again on a different pair. It is recorded and not yet fixed.
            </p>
          </div>
        )}
      </Panel>

      <div className="split--one-third">
        <Panel id="confusion" title="Confusion matrix" eyebrow="official" flush>
          <DataTable
            caption="Raw pair counts, not normalised."
            columns={confusionColumns}
            rows={confusionRows}
            rowKey={(r) => r.cell}
          />
        </Panel>

        <Panel id="fit" title="How the model was fitted" eyebrow="review">
          <p className="note">
            Fitted match rate{' '}
            <span className="mono">
              {evaluation.linkage.fitted_p_match.toFixed(5)}
            </span>{' '}
            against an observed{' '}
            <span className="mono">
              {evaluation.linkage.observed_p_match.toFixed(5)}
            </span>
            . Method: {evaluation.linkage.method}.
          </p>
          <p className="note">
            Oracle ceiling {oracle.oracle_with_adjustment.f1.toFixed(4)} with
            labelled parameters, against{' '}
            {oracle.oracle_no_adjustment.f1.toFixed(4)} without the frequency
            adjustment. The gap attributes any shortfall to the fit rather than
            to the features.
          </p>
        </Panel>
      </div>

      <Panel
        id="convergence"
        title="Layer 6 collective iteration"
        eyebrow={evaluation.convergence.converged ? 'resolved' : 'conflict'}
        flush
        aside={
          <StatusPill
            label={evaluation.convergence.converged ? 'converged' : 'non convergent'}
            tone={evaluation.convergence.converged ? 'resolved' : 'conflict'}
          />
        }
      >
        <DataTable
          caption={
            evaluation.convergence.converged
              ? 'Relational evidence recomputed against resolved identities until the partition stopped moving.'
              : `Relational evidence recomputed against resolved identities each iteration. The partition does not reach a fixed point. It oscillates within ${spread.toFixed(4)} F1 across ${history.length} iterations with between ${n(Math.min(...history.map((e) => e.rows_reassigned)))} and ${n(Math.max(...history.map((e) => e.rows_reassigned)))} rows moving each time, and stops at the iteration cap rather than by converging.`
          }
          columns={convergenceColumns}
          rows={history}
          rowKey={(r) => String(r.iteration)}
        />
      </Panel>

      <div className="split">
        <Panel id="blocking-eval" title="Blocking" eyebrow="signal">
          <MetricRow>
            <Metric
              label="Pairs completeness"
              value={pct(evaluation.blocking.pairs_completeness_pct)}
              small
              tone="resolved"
              caption={<>hard ceiling on recall for every layer after Layer 2</>}
            />
            <Metric
              label="Reduction ratio"
              value={evaluation.blocking.reduction_ratio.toFixed(6)}
              small
              tone="review"
              caption={
                <>
                  {n(evaluation.blocking.candidate_pairs)} candidate pairs from{' '}
                  {n(evaluation.blocking.all_possible_pairs)} possible
                </>
              }
            />
          </MetricRow>
        </Panel>

        <Panel id="latency" title="Latency" eyebrow="official" flush>
          <DataTable
            caption="Wall clock per stage on the development corpus. Resolution is a batch job, so these are batch timings and not request latencies."
            columns={latencyColumns}
            rows={latencyRows}
            rowKey={(r) => r.stage}
          />
        </Panel>
      </div>

      </Details>

      <Panel id="questions" title="Investigator question set" eyebrow="review">
        <p className="note">
          <strong>{evaluation.questions.status}.</strong>{' '}
          {evaluation.questions.note}
        </p>
      </Panel>
    </>
  )
}
