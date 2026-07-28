/**
 * Identity review queue.
 *
 * Every row is a real candidate pair from the review band, with the real per
 * signal contributions that produced its score. Nothing is illustrative.
 *
 * Cannot link conflicts are sorted to the top. A pair the model scores highly
 * but the schema proves cannot be one person is the single most persuasive
 * artefact this product has, because it shows the system refusing a merge it
 * would otherwise have wanted to make.
 */

import { useMemo, useState } from 'react'

import { Metric, MetricRow, Panel, Rule, StatusPill } from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import { SubHeader } from '../components/hero'
import { n } from '../data/useReports'
import { useT } from '../i18n/useLanguage'
import { useDecisions } from '../decisions/useDecisions'
import { useScope } from '../scope/useScope'
import type { Evidence, PairSide, ReviewPair, Reports } from '../data/types'
import type { ScopeEffect } from '../scope/filter'

type Filter = 'all' | 'conflict'

export function ReviewQueue({
  reports,
  effect,
}: {
  reports: Reports
  effect?: ScopeEffect | null
}) {
  const routing = reports.routing
  const t = useT()
  const scope = useScope()
  const { summary, reset, log } = useDecisions()
  const [filter, setFilter] = useState<Filter>('all')
  const [open, setOpen] = useState<string | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)

  const pairs = useMemo(() => {
    if (!routing) return []
    const sorted = [...routing.pairs].sort((a, b) => {
      if (a.cannot_link_conflict !== b.cannot_link_conflict) {
        return a.cannot_link_conflict ? -1 : 1
      }
      return b.probability - a.probability
    })
    return filter === 'conflict'
      ? sorted.filter((p) => p.cannot_link_conflict)
      : sorted
  }, [routing, filter])

  if (!routing) {
    return (
      <NotBuilt
        title="Identity review queue"
        what="Candidate merges the engine will not decide alone, with the evidence that produced each score."
        why="The routing export has not been produced, so there is no queue to show."
        command={'make resolve\nmake eval\npython scripts/export_web.py'}
      />
    )
  }

  const conflicts = routing.pairs.filter((p) => p.cannot_link_conflict).length
  const counts = summary(routing.pairs.length)

  return (
    <>
      <SubHeader
        title="Review queue"
        stats={[
          {
            label: 'Pending',
            value: n(counts.pending),
            tone: counts.pending ? 'review' : 'resolved',
          },
          { label: 'Decided', value: n(counts.decided), tone: 'resolved' },
          {
            label: 'Conflicts',
            value: String(conflicts),
            tone: conflicts ? 'conflict' : undefined,
          },
        ]}
      />

      {!scope.role.canDecide && (
        <Panel
          id="queue-readonly"
          title="This queue is read only for your role"
          eyebrow="review"
          aside={<StatusPill label="cannot decide" tone="review" />}
        >
          <p className="note">
            <strong>{scope.role.label}</strong> may read the queue and may not
            clear it. Approving a merge writes into the person record, which is
            a records function rather than an investigative one, so it belongs
            to the Records operator, the SCRB analyst or the Reviewer.
          </p>
          <p className="note">
            Change the role in the masthead to act on these pairs. That is a
            demonstration of the access model. It is not enforcement, and
            /status says so.
          </p>
        </Panel>
      )}

      {counts.decided > 0 && (
        <Panel
          id="queue-progress"
          title="Decisions taken in this browser"
          eyebrow="official"
          aside={<StatusPill label="per browser, not persisted" tone="review" />}
        >
          <MetricRow>
            <Metric label="Merged" value={counts.merged} tone="resolved" small
                    caption={<>accepted as one person</>} />
            <Metric label="Kept separate" value={counts.keptSeparate} tone="review" small
                    caption={<>refused as two people</>} />
            <Metric label="Reversed" value={counts.reversed} small
                    tone={counts.reversed ? 'conflict' : 'neutral'}
                    caption={<>appended, never deleted</>} />
            <Metric label="Still pending" value={counts.pending} small
                    caption={<>of {n(routing.pairs.length)} shown</>} />
          </MetricRow>
          <Rule />
          <div className="chip-row">
            {confirmReset ? (
              <>
                <button type="button" className="btn btn--primary"
                        onClick={() => { reset(); setConfirmReset(false) }}>
                  Yes, clear {n(log.length)} local decisions
                </button>
                <button type="button" className="btn"
                        onClick={() => setConfirmReset(false)}>
                  Cancel
                </button>
              </>
            ) : (
              <button type="button" className="btn"
                      onClick={() => setConfirmReset(true)}>
                Clear local decisions
              </button>
            )}
          </div>
          <p className="note">
            Clearing removes every decision from this browser, including the
            audit trail of them. It does not touch the engine, because nothing
            here ever reached it. Real deployments would not offer this control
            and would not need it, since the log would live on a server.
          </p>
        </Panel>
      )}

      {effect && effect.reviewPairs.after < effect.reviewPairs.before && (
        <Panel
          id="queue-scope"
          title="This queue is scoped"
          eyebrow="signal"
          aside={<StatusPill label="view filter, not enforcement" tone="signal" />}
        >
          <p className="note">
            Showing {effect.reviewPairs.after} of{' '}
            {effect.reviewPairs.before} review band pairs. The rest touch
            districts outside this jurisdiction. This is a client side view
            filter for demonstration. The underlying JSON is served in full and
            server side enforcement is not built, which /status states plainly.
          </p>
        </Panel>
      )}

      <Panel
        id="queue-summary"
        title="Review queue"
        eyebrow="review"
        aside={<StatusPill label="no merge is automatic here" tone="review" />}
        note={
          <>
            Pairs whose calibrated probability falls between{' '}
            <span className="mono">{routing.review_band.floor}</span> and{' '}
            <span className="mono">{routing.review_band.ceiling}</span>. Above
            the ceiling the engine merges without asking. Below the floor it
            rejects. This band is everything it will not decide alone, and the
            band is deliberately wide because a false merge is the harm this
            system exists to avoid.
          </>
        }
      >
        <MetricRow>
          <Metric
            label="In the review band"
            value={routing.total_in_review_band}
            tone="review"
          />
          <Metric
            label="Shown here"
            value={routing.shown}
            small
            caption={<>highest probability first, conflicts before everything else</>}
          />
          <Metric
            label="Cannot link conflicts"
            value={conflicts}
            tone={conflicts ? 'conflict' : 'neutral'}
            small
            caption={<>merges the schema proves are wrong</>}
          />
        </MetricRow>
        <Rule />
        <div className="chip-row" role="group" aria-label="Filter the queue">
          <button
            type="button"
            className={`filter${filter === 'all' ? ' filter--on' : ''}`}
            aria-pressed={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            {t('All')} {routing.shown}
          </button>
          <button
            type="button"
            className={`filter${filter === 'conflict' ? ' filter--on' : ''}`}
            aria-pressed={filter === 'conflict'}
            onClick={() => setFilter('conflict')}
          >
            {t('Conflicts only')} {conflicts}
          </button>
        </div>
      </Panel>

      <ul className="ledger" aria-label="Candidate merges awaiting a decision">
        {pairs.map((pair) => (
          <LedgerRow
            key={pair.pair_id}
            pair={pair}
            expanded={open === pair.pair_id}
            onToggle={() =>
              setOpen(open === pair.pair_id ? null : pair.pair_id)
            }
          />
        ))}
      </ul>

      {pairs.length === 0 && (
        <Panel id="empty" title="Nothing matches that filter" eyebrow="review">
          <p className="note">
            The export carries {n(routing.shown)} review band pairs, of which{' '}
            {conflicts} are cannot link conflicts.
          </p>
        </Panel>
      )}
    </>
  )
}

/** UTC to the minute. An audit stamp does not need seconds and the extra
 *  digits make a long list harder to scan. */
export function stamp(iso: string): string {
  if (!iso) return 'unknown'
  return iso.replace('T', ' ').replace(/:[0-9][0-9]\.[0-9]+Z$/, ' UTC')
    .replace(/Z$/, ' UTC')
}

function LedgerRow({
  pair,
  expanded,
  onToggle,
}: {
  pair: ReviewPair
  expanded: boolean
  onToggle: () => void
}) {
  const t = useT()
  const scope = useScope()
  const { record, outcomeOf } = useDecisions()
  const outcome = outcomeOf(pair.pair_id)
  const decided = outcome?.action ?? null
  const conflict = pair.cannot_link_conflict
  const panelId = `${pair.pair_id}-evidence`

  const decide = (action: 'merge' | 'keep separate') => {
    if (!scope.role.canDecide) return
    if (action === 'merge' && conflict) return
    record({
      pair_id: pair.pair_id,
      amid_left: pair.left.amid,
      amid_right: pair.right.amid,
      action,
      role: scope.role.id,
      role_label: scope.role.label,
      district: scope.district,
      probability: pair.probability,
    })
  }

  return (
    <li className={`ledger__row${conflict ? ' ledger__row--conflict' : ''}`}>
      <div
        className={`panel__eyebrow panel__eyebrow--${conflict ? 'conflict' : 'review'}`}
        aria-hidden="true"
      />

      <div className="ledger__head">
        <div className="ledger__candidates">
          <Candidate side={pair.left} />
          <span className="ledger__join" aria-hidden="true">
            against
          </span>
          <Candidate side={pair.right} />
        </div>

        <div className="ledger__verdict">
          <span className="ledger__prob mono">
            {pair.probability.toFixed(3)}
          </span>
          <span className="ledger__band">
            <StatusPill
              label={conflict ? 'cannot link' : 'human decision'}
              tone={conflict ? 'conflict' : 'review'}
            />
          </span>
          <span className="ledger__llr mono">
            llr {pair.score_llr >= 0 ? '+' : ''}
            {pair.score_llr.toFixed(2)}
          </span>
        </div>
      </div>

      {conflict && pair.conflict_reason && (
        <p className="ledger__conflict" role="note">
          <strong>Merge refused.</strong> {pair.conflict_reason}
        </p>
      )}

      <div className="ledger__evidence">
        {pair.evidence.slice(0, expanded ? undefined : 4).map((item) => (
          <EvidenceChip key={item.signal} item={item} />
        ))}
        {!expanded && pair.evidence.length > 4 && (
          <span className="evidence evidence--more">
            +{pair.evidence.length - 4} more
          </span>
        )}
      </div>

      {expanded && (
        <table className="table ledger__table">
          <caption>
            Every signal contributing to this score, as log likelihood ratio.
            They sum to {pair.score_llr.toFixed(2)}.
          </caption>
          <thead>
            <tr>
              <th scope="col">Signal</th>
              <th scope="col">Level</th>
              <th scope="col" style={{ textAlign: 'right' }}>
                Weight
              </th>
            </tr>
          </thead>
          <tbody>
            {pair.evidence.map((item) => (
              <tr key={item.signal}>
                <th scope="row">{item.label}</th>
                <td className="num">{item.level ?? 'n/a'}</td>
                <td className="num">
                  <span
                    className={
                      item.weight >= 0 ? 'value--resolved' : 'value--conflict'
                    }
                  >
                    {item.weight >= 0 ? '+' : ''}
                    {item.weight.toFixed(3)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {outcome?.decision && outcome.action && (
        <p className="ledger__outcome" role="status">
          <StatusPill
            label={outcome.action === 'merge' ? 'merged' : 'kept separate'}
            tone={outcome.action === 'merge' ? 'resolved' : 'review'}
          />{' '}
          by {outcome.decision.role_label}
          {outcome.decision.district ? `, ${outcome.decision.district}` : ''}
          {' at '}
          <span className="mono">{stamp(outcome.decision.at)}</span>
        </p>
      )}
      {outcome?.reversed && (
        <p className="ledger__outcome" role="status">
          <StatusPill label="reversed, back in the queue" tone="conflict" />{' '}
          by {outcome.decision?.role_label} at{' '}
          <span className="mono">{stamp(outcome.decision?.at ?? '')}</span>
        </p>
      )}

      <div className="ledger__actions">
        <button
          type="button"
          className="btn"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={onToggle}
        >
          {t(expanded ? 'Hide evidence' : 'Show all evidence')}
        </button>
        <span className="ledger__spacer" />
        <button
          type="button"
          className="btn btn--primary"
          disabled={conflict || !scope.role.canDecide}
          title={
            conflict
              ? 'Refused. The schema proves these are different people.'
              : !scope.role.canDecide
                ? scope.role.label + ' may read this queue and not clear it.'
                : 'Records the decision in this browser. Nothing is written to the engine.'
          }
          onClick={() => decide('merge')}
        >
          {t(decided === 'merge' ? 'Merged' : 'Merge')}
        </button>
        <button
          type="button"
          className="btn"
          disabled={!scope.role.canDecide}
          title={
            scope.role.canDecide
              ? 'Records the decision in this browser. Nothing is written to the engine.'
              : scope.role.label + ' may read this queue and not clear it.'
          }
          onClick={() => decide('keep separate')}
        >
          {t(decided === 'keep separate' ? 'Kept separate' : 'Keep separate')}
        </button>
      </div>
      <p className="ledger__note" id={panelId}>
        {scope.role.canDecide
          ? 'A decision is recorded in this browser and appears on the audit trail. It is not written to the resolved identity table, because resolution is a nightly batch job and this surface is read only. See ADR 002.'
          : scope.role.label + ' sees this queue read only. Deciding a merge writes to the person record, which is a records function.'}
      </p>
    </li>
  )
}

function Candidate({ side }: { side: PairSide }) {
  return (
    <div className="candidate">
      <span
        className={`candidate__name${side.script === 'kannada' ? ' kn' : ' mono'}`}
      >
        {side.name}
      </span>
      <span className="candidate__meta mono">
        {side.amid} / {side.person_label} / {side.crime_no}
      </span>
      <span className="candidate__meta">
        {side.station}, {side.district}, {side.registered}
        {side.age ? `, age ${side.age}` : ', age not recorded'}
      </span>
    </div>
  )
}

function EvidenceChip({ item }: { item: Evidence }) {
  const tone = item.weight >= 0 ? 'resolved' : 'conflict'
  return (
    <span className={`evidence evidence--${tone}`}>
      <span className="evidence__label">{item.signal}</span>
      <span className="evidence__weight mono">
        {item.weight >= 0 ? '+' : ''}
        {item.weight.toFixed(2)}
      </span>
    </span>
  )
}
