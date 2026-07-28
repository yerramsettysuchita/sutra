/**
 * Corpus audit. What the synthetic corpus contains and what any system could
 * recover from it. The chrome lives in Shell, so this file is panels only.
 */

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
import { HeroFigure, SubHeader } from '../components/hero'
import { SchemaGap } from '../components/SchemaGap'
import { n, pct } from '../data/useReports'
import type { PersonsFeed, Reports } from '../data/types'

/**
 * The gap is not one table, it is three.
 *
 * The diagram above draws Accused because that is the table the project is
 * about. Victim and ComplainantDetails carry the same missing person entity,
 * and until it was measured that was a sentence on a slide rather than a
 * number. This panel is the number, across all three.
 */
function ThreeTableGap({ feed }: { feed: PersonsFeed }) {
  const order = ['accused', 'victim', 'complainant']
  const rows = order
    .map((key) => feed.tables[key])
    .filter((t): t is NonNullable<typeof t> => Boolean(t))

  const columns: Column<(typeof rows)[number]>[] = [
    { key: 'table', header: 'Table', code: true, render: (r) => r.table },
    { key: 'rows', header: 'Rows on file', numeric: true, render: (r) => n(r.rows) },
    {
      key: 'people',
      header: 'Actual people',
      numeric: true,
      render: (r) => n(r.true_people),
    },
    {
      key: 'hidden',
      header: 'Rows that are a repeat',
      numeric: true,
      render: (r) => (
        <>
          <span className="value--conflict">{n(r.hidden_by_fragmentation)}</span>
          <Bar fraction={r.hidden_by_fragmentation / Math.max(r.rows, 1)} tone="review" />
        </>
      ),
    },
    {
      key: 'share',
      header: 'Share inflated',
      numeric: true,
      render: (r) =>
        `${((r.hidden_by_fragmentation / Math.max(r.rows, 1)) * 100).toFixed(1)}%`,
    },
  ]

  return (
    <Panel
      id="three-table-gap"
      title="The same gap, in all three person bearing tables"
      eyebrow="conflict"
      aside={<StatusPill label="measured, not asserted" tone="official" />}
      note={
        <>
          The diagram above draws <span className="mono">Accused</span> because
          that is the table this project is about. It is not the only one.{' '}
          <span className="mono">Victim</span> and{' '}
          <span className="mono">ComplainantDetails</span> hold a person with no
          key that survives across FIRs either, and the counts below come from
          ground truth rather than from the resolver, so they stand whether or
          not the engine works on them.
        </>
      }
      flush
    >
      <DataTable
        caption="Every person bearing table in the KSP schema, the rows it holds, and how many distinct people those rows actually are."
        columns={columns}
        rows={rows}
        rowKey={(r) => r.table}
      />
      <div style={{ padding: 'var(--s-4)' }}>
        <p className="note">
          <strong>{feed.combined.statement}</strong>
        </p>
        <p className="note">
          The asymmetry is worth naming.{' '}
          <span className="mono">ComplainantDetails</span> carries an address
          and a phone number. <span className="mono">Accused</span> carries
          neither, and the schema file comments on that itself. The person the
          record most needs to identify is the one it collects least about.
        </p>
      </div>
    </Panel>
  )
}

export function CorpusAudit({ reports }: { reports: Reports }) {
  const { manifest, corpus, blocking } = reports
  const rec = corpus.recoverability
  const countOf = (key: string) => manifest.counts[key] ?? 0
  const accusedRows = countOf('accused_rows')

  const ceiling = blocking?.ceiling.revised_recall_ceiling_pct ?? rec.recall_ceiling_pct
  const exact = rec.exact_match_pct
  const mergeable = corpus.hard_negatives.cross_person_exact_name_pairs

  const repeatOffenders = Object.entries(corpus.appearances_per_person ?? {})
    .filter(([appearances]) => Number(appearances) >= 2)
    .reduce((total, [, people]) => total + people, 0)

  const scriptTotal = Object.values(corpus.script).reduce((a, b) => a + b, 0)
  const kannada = corpus.script.kannada ?? 0
  const crossScriptShare = (rec.cross_script_pairs / rec.true_pairs) * 100

  const nameRows = Object.entries(corpus.name_frequency_top10).map(([name, count]) => ({
    name,
    count,
    share: (count / Math.max(1, accusedRows)) * 100,
  }))
  const topShare = nameRows.reduce((a, r) => a + r.share, 0)
  const maxName = Math.max(...nameRows.map((r) => r.count))

  const nameColumns: Column<(typeof nameRows)[number]>[] = [
    { key: 'name', header: 'Canonical name', code: true, render: (r) => r.name },
    { key: 'count', header: 'Rows', numeric: true, width: '5rem', render: (r) => n(r.count) },
    { key: 'share', header: 'Share', numeric: true, width: '5rem', render: (r) => pct(r.share) },
    {
      key: 'bar',
      header: 'Frequency',
      width: '9rem',
      render: (r) => <Bar fraction={r.count / maxName} tone="official" />,
    },
  ]

  const familyRows = blocking
    ? blocking.blocking.by_combination.map((row) => ({
        ...row,
        shipped: row.families === blocking.blocking.shipped_families.join('+'),
      }))
    : []

  const familyColumns: Column<(typeof familyRows)[number]>[] = [
    {
      key: 'families',
      header: 'Key families',
      code: true,
      render: (r) => (
        <>
          {r.families}
          {r.shipped && (
            <>
              {' '}
              <StatusPill label="shipped" tone="resolved" />
            </>
          )}
        </>
      ),
    },
    { key: 'pairs', header: 'Candidate pairs', numeric: true, render: (r) => n(r.candidate_pairs) },
    {
      key: 'reduction',
      header: 'Reduction ratio',
      numeric: true,
      render: (r) => r.reduction_ratio.toFixed(4),
    },
    {
      key: 'completeness',
      header: 'Pairs completeness',
      numeric: true,
      render: (r) => pct(r.pairs_completeness_pct),
    },
  ]

  return (
    <>
      <SubHeader
        title="Corpus audit"
        stats={[
          { label: 'Cases', value: n(countOf('cases')) },
          { label: 'Accused rows', value: n(accusedRows) },
          { label: 'Ceiling', value: pct(ceiling), tone: 'resolved' },
          { label: 'Naive join', value: pct(exact), tone: 'conflict' },
        ]}
      />

      {/* The hero for this route. The gap is the argument. */}
      <Panel
        id="verdict"
        title="Recoverability verdict"
        eyebrow="resolved"
        note={
          <>
            The gap between these two numbers is the whole argument. A system
            joining on <span className="mono">AccusedName</span> reaches the
            lower one. Everything Layers 1 to 7 do is spent closing the distance
            to the upper one.
          </>
        }
        aside={<StatusPill label="measured" tone="resolved" />}
      >
        <div className="hero" style={{ padding: 0 }}>
          <div>
            <div
              className="gap-bar__track"
              style={{ height: '2.5rem' }}
              role="img"
              aria-label={`Exact name matching reaches ${pct(exact)} of true pairs. The measured ceiling is ${pct(ceiling)}.`}
            >
              <span className="gap-bar__ceiling" style={{ width: `${ceiling}%` }} />
              <span className="gap-bar__exact" style={{ width: `${exact}%` }} />
            </div>
            <div className="gap-bar__legend" style={{ marginTop: 'var(--s-3)' }}>
              <span>
                <i className="swatch swatch--conflict" aria-hidden="true" />
                exact name match <b>{pct(exact)}</b>
              </span>
              <span>
                <i className="swatch swatch--resolved" aria-hidden="true" />
                measured ceiling <b>{pct(ceiling)}</b>
              </span>
            </div>
          </div>
          <HeroFigure
            label="Ground to cover"
            value={pct(ceiling - exact, 1)}
            tone="resolved"
            caption={
              <>
                of true matching pairs sit between what a name join finds and
                what the data allows. That distance is the project.
              </>
            }
          />
        </div>
      </Panel>

      <Panel id="framing" title="What this is" eyebrow="navy">
        <p className="note">
          SUTRA builds the missing person entity in the Karnataka State Police
          crime record. <strong>The finding, drawn.</strong>
        </p>
        <SchemaGap />
        <Rule tight />
        <p className="note">
          <span className="mono">Accused.AccusedMasterID</span> is scoped to a
          single FIR and <span className="mono">PersonID</span> is a within case
          sort label. The row carries no father's name, no address and no
          biometric key, so criminal network analysis and repeat offender
          tracking, both named in problem statement 01, cannot be computed from
          the data as supplied.
        </p>
        <div className="chip-row">
          <StatusPill label="Layers 1 to 8 measured" tone="resolved" />
          <StatusPill label="Layer 9 not built" tone="review" />
        </div>
      </Panel>

      {reports.persons && <ThreeTableGap feed={reports.persons} />}

      <Panel
        id="volumes"
        title="Corpus volume"
        eyebrow="navy"
        note="Generated on the KSP schema with identity known by construction. Ground truth is written by the generator and never read by the engine."
      >
        <MetricRow>
          <Metric label="Cases" value={countOf('cases')} />
          <Metric label="Accused rows" value={accusedRows} />
          <Metric label="True persons" value={countOf('true_persons_appearing')} />
          <Metric label="True matching pairs" value={rec.true_pairs} />
          <Metric
            label="Repeat offenders"
            value={repeatOffenders}
            small
            caption={
              <>
                people appearing twice or more.{' '}
                {n(corpus.relational.cannot_link_cases)} cases carry two or more
                accused, which are the cannot link edges Layer 5 relies on
              </>
            }
          />
        </MetricRow>
      </Panel>

      <Panel id="verdict-detail" title="What the ceiling means" eyebrow="review">
        <div className="verdict">
          <Metric
            label="Recall ceiling"
            value={pct(ceiling)}
            tone="resolved"
            caption={
              blocking ? (
                <>
                  after Layer 2 blocking. {n(blocking.ceiling.lost)} true pairs
                  are lost before scoring begins and cannot be recovered by
                  anything downstream
                </>
              ) : (
                <>before blocking, which is not yet measured</>
              )
            }
          />
          <Metric
            label="Exact name match reaches"
            value={pct(exact)}
            tone="conflict"
            caption={<>the baseline a naive system achieves</>}
          />
          <Metric
            label="Wrongly mergeable pairs"
            value={mergeable}
            tone="conflict"
            caption={
              <>
                cross person pairs sharing an identical name string. A name
                based system merges these and reports success
              </>
            }
          />
          <Metric
            label="Planted collisions"
            value={corpus.hard_negatives.collision_groups}
            small
            caption={
              <>
                groups of distinct people forced onto one name in one district,{' '}
                {n(corpus.hard_negatives.tight_age_groups)} of them with birth
                years within a year
              </>
            }
          />
        </div>

        {blocking && (
          <>
            <Rule />
            <p className="note">
              Phase 0 reported a ceiling of{' '}
              <span className="mono">{pct(blocking.ceiling.prior_ceiling_pct)}</span>{' '}
              on the assumption that blocking loses nothing. It does.{' '}
              <strong>
                That figure is superseded by {pct(ceiling)}, and the lower number
                is the real one.
              </strong>
            </p>
          </>
        )}
      </Panel>

      {blocking && (
        <Panel
          id="layer2"
          title="Layer 1 normalisation and Layer 2 blocking"
          eyebrow="signal"
          note="Pairs completeness is a hard ceiling on recall for every layer after this one, because a pair blocking never proposes can never be resolved at any cost."
        >
          <MetricRow>
            <Metric
              label="Pairs completeness"
              value={pct(blocking.ceiling.pairs_completeness_pct)}
              tone="resolved"
            />
            <Metric
              label="Reduction ratio"
              value={blocking.blocking.reduction_ratio.toFixed(4)}
              tone="review"
            />
            <Metric
              label="Candidate pairs"
              value={blocking.blocking.candidate_pairs}
              small
              caption={<>from {n(blocking.blocking.all_possible_pairs)} possible</>}
            />
            <Metric
              label="Cross script folded"
              value={pct(blocking.normalisation.cross_script_shared_token_pct, 1)}
              small
              caption={
                <>
                  of {n(blocking.normalisation.cross_script_true_pairs)} cross
                  script true pairs share a folded token after Layer 1,{' '}
                  {pct(blocking.normalisation.cross_script_blocked_pct, 1)}{' '}
                  survive into the candidate set
                </>
              }
            />
          </MetricRow>
          <Rule />
          <DataTable
            caption="Every key family combination, so the choice is a measurement and not an assertion. PH is the full folded token, P4 its first four characters, TR the station circle paired with an initial."
            columns={familyColumns}
            rows={familyRows}
            rowKey={(r) => r.families}
          />
        </Panel>
      )}

      <div className="split split--wide-left">
        <Panel
          id="frequency"
          title="Name frequency skew"
          eyebrow="conflict"
          flush
          aside={<StatusPill label="drives Layer 4" tone="signal" />}
        >
          <DataTable
            caption={`The ten most common canonical names cover ${pct(topShare, 1)} of all accused rows. Agreement on a common name is weaker evidence than agreement on a rare one, which is what inverse name frequency weighting in Layer 4 exists to exploit.`}
            columns={nameColumns}
            rows={nameRows}
            rowKey={(r) => r.name}
          />
        </Panel>

        <Panel id="script" title="Script as written" eyebrow="signal">
          <MetricRow>
            <Metric
              label="Kannada script"
              value={pct((kannada / scriptTotal) * 100, 1)}
              small
              caption={<>of {n(scriptTotal)} accused names</>}
            />
            <Metric
              label="Cross script true pairs"
              value={pct(crossScriptShare, 1)}
              small
              tone="review"
              caption={
                <>
                  {n(rec.cross_script_pairs)} pairs where one appearance is
                  Kannada and the other Latin
                </>
              }
            />
          </MetricRow>
          <div className="script-sample" aria-hidden="true">
            <span className="kn">ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ</span>
            <span className="mono">Ramesh S/o Krishnappa</span>
            <span className="mono">R. Krishnappa</span>
          </div>
          <p className="note" style={{ marginTop: 'var(--s-3)' }}>
            One man, three renderings, no key connecting them. Layer 1 folds all
            three to the same phonetic form. The samples above are illustrative,
            the percentages are measured.
          </p>
        </Panel>
      </div>

      <Panel
        id="calibration"
        title="Co offending calibration"
        eyebrow="official"
        aside={
          <StatusPill label={manifest.co_offending_preset ?? 'unknown'} tone="signal" />
        }
        note="Layer 3f relational evidence only exists if offenders reappear together. That rate is a parameter calibrated against the literature rather than a constant we chose, because tuning it until the signal looks useful would measure our own configuration."
      >
        <MetricRow>
          <Metric
            label="Dyad recurrence"
            value={pct(manifest.dyad_recurrence?.rate_pct ?? 0)}
            small
            caption={
              <>
                of {n(manifest.dyad_recurrence?.dyads ?? 0)} co offending pairs
                appear together more than once
              </>
            }
          />
          <Metric
            label="Literature anchor"
            value="2.5%"
            small
            tone="review"
            caption={
              <>
                Sarnecki, Stockholm, share of co offending relationships
                persisting beyond six months
              </>
            }
          />
          <Metric label="Co offending groups" value={corpus.relational.gangs} small />
          <Metric
            label="Undetected cases"
            value={corpus.relational.undetected_cases}
            small
            caption={<>cstype C, input to the Layer 8 candidate matcher</>}
          />
        </MetricRow>
      </Panel>
    </>
  )
}
