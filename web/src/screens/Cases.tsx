/**
 * Undetected case matcher, Layer 8.
 *
 * For cases closed as cstype C, true but the offender not traced, rank
 * resolved identities by how well the case fits what that person is already
 * on record for.
 *
 * The accuracy panel is not decoration. This is the one screen where a
 * plausible looking ranking could be entirely wrong and no reader would know,
 * so the measured hit rate against ground truth sits beside the list rather
 * than in a report nobody opens.
 */

import { useMemo, useState } from 'react'

import {
  Bar,
  DataTable,
  Metric,
  MetricRow,
  Panel,
  Rule,
  StatusPill,
  type Column,
} from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import { HeroFigure, MethodBars, SubHeader } from '../components/hero'
import { n, pct } from '../data/useReports'
import type { Accuracy, Candidate, Reports, UndetectedCase } from '../data/types'

export function Cases({ reports }: { reports: Reports }) {
  const feed = reports.cases
  const [selected, setSelected] = useState<string | null>(null)

  const current = useMemo(() => {
    if (!feed) return null
    return feed.cases.find((c) => c.case_id === selected) ?? feed.cases[0] ?? null
  }, [feed, selected])

  if (!feed) {
    return (
      <NotBuilt
        title="Undetected case matcher"
        what="Ranks resolved identities against an unsolved case by modus operandi, territory and time."
        why="The Layer 8 export has not been produced."
        command={'make resolve\nmake downstream\nmake export'}
      />
    )
  }

  const acc = feed.accuracy.combined
  const lift = acc.hit_at_10 / Math.max(acc.random_baseline_hit_at_10, 1e-9)

  const accuracyRows = (
    [
      ['combined', feed.accuracy.combined],
      ['modus operandi only', feed.accuracy.modus_only],
      ['spatial only', feed.accuracy.spatial_only],
      ['temporal only', feed.accuracy.temporal_only],
    ] as Array<[string, Accuracy]>
  ).map(([ranking, a]) => ({ ranking, ...a }))

  const accuracyColumns: Column<(typeof accuracyRows)[number]>[] = [
    {
      key: 'ranking',
      header: 'Ranking',
      render: (r) =>
        r.ranking === 'combined' ? (
          <strong>
            {r.ranking} <StatusPill label="shipped" tone="resolved" />
          </strong>
        ) : (
          r.ranking
        ),
    },
    { key: 'h1', header: 'Hit at 1', numeric: true, render: (r) => r.hit_at_1.toFixed(4) },
    { key: 'h3', header: 'Hit at 3', numeric: true, render: (r) => r.hit_at_3.toFixed(4) },
    { key: 'h10', header: 'Hit at 10', numeric: true, render: (r) => r.hit_at_10.toFixed(4) },
    { key: 'h50', header: 'Hit at 50', numeric: true, render: (r) => r.hit_at_50.toFixed(4) },
    {
      key: 'mrr',
      header: 'MRR',
      numeric: true,
      render: (r) => r.mean_reciprocal_rank.toFixed(4),
    },
    {
      key: 'bar',
      header: 'Hit at 10',
      width: '8rem',
      render: (r) => (
        <Bar
          fraction={r.hit_at_10}
          tone={r.ranking === 'combined' ? 'resolved' : 'dim'}
        />
      ),
    },
  ]

  return (
    <>
      <SubHeader
        title="Undetected cases"
        stats={[
          { label: 'Hit at 1', value: acc.hit_at_1.toFixed(4), tone: 'resolved' },
          { label: 'Hit at 10', value: acc.hit_at_10.toFixed(4), tone: 'resolved' },
          { label: 'MRR', value: acc.mean_reciprocal_rank.toFixed(4) },
          { label: 'Cases', value: n(feed.total_undetected_cases) },
        ]}
      />

      {/* The hero for this route. Ranking accuracy, stated before the list. */}
      <section className="panel" aria-labelledby="cases-hero-title">
        <div className="panel__eyebrow panel__eyebrow--resolved" aria-hidden="true" />
        <h2 className="visually-hidden" id="cases-hero-title">
          Undetected case ranking accuracy
        </h2>
        <div className="hero">
          <MethodBars
            methods={[
              { name: 'Temporal only', value: feed.accuracy.temporal_only.hit_at_10 },
              { name: 'Modus only', value: feed.accuracy.modus_only.hit_at_10 },
              { name: 'Spatial only', value: feed.accuracy.spatial_only.hit_at_10 },
              { name: 'Combined', value: acc.hit_at_10, lead: true },
            ]}
            caption={`Hit rate at rank 10 by signal. Combined ${acc.hit_at_10.toFixed(4)}, spatial only ${feed.accuracy.spatial_only.hit_at_10.toFixed(4)}, modus only ${feed.accuracy.modus_only.hit_at_10.toFixed(4)}, temporal only ${feed.accuracy.temporal_only.hit_at_10.toFixed(4)}.`}
          />
          <HeroFigure
            label="True offender in the top ten"
            value={acc.hit_at_10.toFixed(2)}
            tone="resolved"
            caption={
              <>
                of {n(acc.cases_measured)} undetected cases, from a pool of{' '}
                {n(acc.candidate_pool)} identities. Random selection reaches{' '}
                {acc.random_baseline_hit_at_10.toFixed(5)}.
              </>
            }
          />
        </div>
      </section>

      <Panel
        id="matcher-accuracy"
        title="Measured accuracy"
        eyebrow="resolved"
        aside={<StatusPill label="against ground truth" tone="official" />}
        note={
          <>
            The generator recorded who actually committed every undetected case,
            so this ranking can be scored rather than asserted. A hit at rank k
            means a resolved identity holding that person's records appears in
            the top k of {n(feed.candidate_pool)} candidates.
          </>
        }
      >
        <MetricRow>
          <Metric
            label="Hit at rank 1"
            value={acc.hit_at_1.toFixed(4)}
            tone="resolved"
            caption={<>the true offender ranked first</>}
          />
          <Metric label="Hit at rank 3" value={acc.hit_at_3.toFixed(4)} tone="resolved" />
          <Metric label="Hit at rank 10" value={acc.hit_at_10.toFixed(4)} tone="resolved" />
          <Metric
            label="Mean reciprocal rank"
            value={acc.mean_reciprocal_rank.toFixed(4)}
            tone="resolved"
          />
          <Metric
            label="Against random"
            value={`${Math.round(lift)}x`}
            small
            caption={
              <>
                random selection reaches{' '}
                {acc.random_baseline_hit_at_10.toFixed(6)} at rank 10 from a pool
                of {n(acc.candidate_pool)}
              </>
            }
          />
        </MetricRow>
        <Rule />
        <DataTable
          caption="Each signal ranked on its own alongside the combination, so it is visible which one is doing the work. Weights were fixed before measurement and are not tuned against ground truth."
          columns={accuracyColumns}
          rows={accuracyRows}
          rowKey={(r) => r.ranking}
        />
        <div style={{ padding: 'var(--s-4) 0 0' }}>
          <p className="note">
            <strong>Read this honestly.</strong> Spatial proximity carries most
            of the result on its own, at {feed.accuracy.spatial_only.hit_at_10.toFixed(4)}{' '}
            against {acc.hit_at_10.toFixed(4)} combined. Modus operandi
            similarity contributes{' '}
            {feed.accuracy.modus_only.hit_at_10.toFixed(4)} alone and temporal
            availability {feed.accuracy.temporal_only.hit_at_10.toFixed(4)}. The
            combination beats every single signal, but this is substantially a
            geography model with method as a secondary filter, not the other way
            round.
          </p>
        </div>
      </Panel>

      <Panel id="not-prediction" title="What this is not" eyebrow="conflict">
        <p className="note">
          This ranks <strong>people already on record</strong> against a case
          that has already happened. It scores a pair of cases, not a person.
        </p>
        <p className="note">
          It produces no persistent attribute of anybody, it does not rank the
          population, and asked about a named individual it has nothing to say.
          It is a retrieval index over records an investigator could have found
          by hand with unlimited time.
        </p>
        <p className="note">
          It is <strong>not a prediction of future offending</strong>. SUTRA
          does not do individual risk scoring or behavioural profiling, and{' '}
          <span className="mono">CasteID</span>,{' '}
          <span className="mono">ReligionID</span> and{' '}
          <span className="mono">OccupationID</span> are never read by any model
          here. The precedent behind that refusal, Chicago's Strategic Subject
          List and the LAPD LASER programme, is set out in docs/ethics.md.
        </p>
        <p className="note">
          Every result below is an investigative lead requiring independent
          corroboration. Nothing here is evidence.
        </p>
      </Panel>

      <div className="profile">
        <Panel id="case-list" title="Undetected cases" eyebrow="review" flush>
          <ul className="idlist" aria-label="Cases closed as true but undetected">
            {feed.cases.map((entry) => (
              <li key={entry.case_id}>
                <button
                  type="button"
                  className={`idlist__item${
                    current?.case_id === entry.case_id ? ' idlist__item--active' : ''
                  }`}
                  aria-current={current?.case_id === entry.case_id}
                  onClick={() => setSelected(entry.case_id)}
                >
                  <span className="idlist__key mono">{entry.crime_no}</span>
                  <span className="idlist__name">{entry.subhead}</span>
                  <span className="idlist__meta mono">
                    {entry.station}, {entry.registered}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="note" style={{ padding: 'var(--s-3) var(--s-4)' }}>
            {n(feed.shown)} of {n(feed.total_undetected_cases)} undetected cases,
            strongest top candidate first. The accuracy above is measured over
            all {n(feed.total_undetected_cases)}.
          </p>
        </Panel>

        <div className="stack">{current && <CaseDetail entry={current} feed={feed} />}</div>
      </div>
    </>
  )
}

function CaseDetail({
  entry,
  feed,
}: {
  entry: UndetectedCase
  feed: NonNullable<Reports['cases']>
}) {
  const top = entry.candidates[0]

  const columns: Column<Candidate>[] = [
    { key: 'rank', header: 'Rank', numeric: true, render: (r) => String(r.rank) },
    {
      key: 'identity',
      header: 'Identity',
      code: true,
      render: (r) => r.identity,
    },
    {
      key: 'label',
      header: 'On record as',
      render: (r) => (
        <span className={r.script === 'kannada' ? 'kn' : 'mono'}>{r.label}</span>
      ),
    },
    {
      key: 'cases',
      header: 'Known cases',
      numeric: true,
      render: (r) => String(r.known_cases),
    },
    { key: 'score', header: 'Score', numeric: true, render: (r) => r.score.toFixed(4) },
    {
      key: 'km',
      header: 'Nearest case',
      numeric: true,
      render: (r) => `${r.signals.nearest_km.toFixed(1)} km`,
    },
    {
      key: 'bar',
      header: 'Score',
      width: '8rem',
      render: (r) => (
        <Bar fraction={r.score / Math.max(entry.candidates[0]?.score ?? 1, 1e-9)} tone="signal" />
      ),
    },
  ]

  return (
    <>
      <Panel
        id="case-detail"
        title={entry.crime_no}
        eyebrow="review"
        aside={<StatusPill label="cstype C, undetected" tone="review" />}
        note={
          <>
            {entry.subhead}, {entry.station}, {entry.district}. Registered{' '}
            {entry.registered}. No accused was ever traced, so this FIR carries
            no Accused row at all.
          </>
        }
      >
        <p className="note brief">{entry.brief_facts}</p>
      </Panel>

      <Panel id="candidates" title="Ranked candidates" eyebrow="signal" flush>
        <DataTable
          caption={`Resolved identities ranked against this case. Weights are modus ${feed.weights.modus}, spatial ${feed.weights.spatial}, temporal ${feed.weights.temporal}, fixed before measurement. Spatial falls to zero beyond ${feed.spatial_horizon_km} km and temporal beyond ${feed.temporal_horizon_days} days outside the identity's known active window.`}
          columns={columns}
          rows={entry.candidates}
          rowKey={(r) => r.identity}
        />
      </Panel>

      {top && (
        <Panel
          id="top-evidence"
          title={`Why ${top.identity} ranks first`}
          eyebrow="official"
          note="The three signals behind the top ranked candidate, shown separately so the score can be argued with rather than accepted."
        >
          <MetricRow>
            <Metric
              label="Modus operandi"
              value={top.signals.modus.toFixed(4)}
              small
              caption={
                <>
                  cosine between this narrative and the identity's centroid over
                  its own BriefFacts
                </>
              }
            />
            <Metric
              label="Spatial"
              value={top.signals.spatial.toFixed(4)}
              small
              caption={
                <>
                  nearest known case {top.signals.nearest_km.toFixed(1)} km away,
                  Haversine over CaseMaster coordinates
                </>
              }
            />
            <Metric
              label="Temporal"
              value={top.signals.temporal.toFixed(4)}
              small
              caption={
                top.signals.days_outside_window === 0 ? (
                  <>the case falls inside this identity's known active window</>
                ) : (
                  <>
                    {n(top.signals.days_outside_window)} days outside the known
                    active window
                  </>
                )
              }
            />
            <Metric
              label="Combined"
              value={top.score.toFixed(4)}
              small
              tone="signal"
              caption={<>weighted sum, not a probability</>}
            />
          </MetricRow>
          <Rule />
          <p className="note">
            This score is <strong>not calibrated</strong>. Unlike the merge
            probability in the review queue, it has not been passed through
            isotonic regression, so {pct(top.score * 100, 1)} is a rank position
            and not a chance that this person did it.
          </p>
        </Panel>
      )}
    </>
  )
}
