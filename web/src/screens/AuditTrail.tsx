/**
 * Audit trail. What the run actually did, from runlog.json.
 *
 * Append only in intent. Nothing here is editable and nothing is derived in
 * the browser. Every row is a fact the engine recorded about its own
 * execution, which is what makes the explainability claim checkable rather
 * than asserted.
 */

import {
  Bar,
  DataTable,
  Metric,
  MetricRow,
  Panel,
  StatusPill,
  type Column,
} from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import { n, timestamp } from '../data/useReports'
import { useDecisions } from '../decisions/useDecisions'
import { useScope } from '../scope/useScope'
import { stamp } from './ReviewQueue'
import type { Reports } from '../data/types'

export function AuditTrail({ reports }: { reports: Reports }) {
  const runlog = reports.runlog

  if (!runlog) {
    return (
      <NotBuilt
        title="Audit trail"
        what="Run identifier, stage timings, routing counts, seed and every file read."
        why="The run log has not been exported."
        command={'python scripts/export_web.py'}
      />
    )
  }

  const maxSeconds = Math.max(...runlog.stages.map((s) => s.seconds), 1)

  const stageColumns: Column<(typeof runlog.stages)[number]>[] = [
    { key: 'stage', header: 'Stage', code: true, render: (r) => r.stage },
    {
      key: 'seconds',
      header: 'Seconds',
      numeric: true,
      render: (r) => r.seconds.toFixed(3),
    },
    {
      key: 'bar',
      header: 'Share of run',
      width: '12rem',
      render: (r) => <Bar fraction={r.seconds / maxSeconds} tone="signal" />,
    },
  ]

  const routeRows = Object.entries(runlog.route_counts).map(([route, count]) => ({
    route,
    count,
  }))
  const totalRouted = routeRows.reduce((a, r) => a + r.count, 0)

  const routeColumns: Column<(typeof routeRows)[number]>[] = [
    {
      key: 'route',
      header: 'Route',
      render: (r) => (
        <StatusPill
          label={r.route.replace('_', ' ')}
          tone={
            r.route === 'auto_merge'
              ? 'resolved'
              : r.route === 'review'
                ? 'review'
                : 'neutral'
          }
        />
      ),
    },
    { key: 'count', header: 'Pairs', numeric: true, render: (r) => n(r.count) },
    {
      key: 'share',
      header: 'Share',
      numeric: true,
      render: (r) => `${((r.count / totalRouted) * 100).toFixed(4)}%`,
    },
  ]

  const countRows = Object.entries(runlog.counts).map(([key, value]) => ({
    key,
    value,
  }))
  const countColumns: Column<(typeof countRows)[number]>[] = [
    { key: 'key', header: 'Quantity', code: true, render: (r) => r.key },
    { key: 'value', header: 'Count', numeric: true, render: (r) => n(r.value) },
  ]

  const fileRows = runlog.files_read.map((path) => ({ path }))
  const fileColumns: Column<{ path: string }>[] = [
    { key: 'path', header: 'File read', code: true, render: (r) => r.path },
  ]

  return (
    <section aria-label="Audit trail of the resolution run and of operator decisions">
      <Panel
        id="audit-sections"
        title="Two logs, kept apart"
        eyebrow="navy"
        aside={<StatusPill label="pipeline, then people" tone="official" />}
      >
        <p className="note">
          <strong>The pipeline run</strong> below is what the engine did. It is
          reproducible from a seed and it is the provenance of every figure in
          this application.
        </p>
        <p className="note">
          <strong>Operator decisions</strong> is what people did afterwards.
          Those two are different kinds of record and mixing them would let a
          human judgement look like a computed result, so they are separated
          here and never summed.
        </p>
      </Panel>

      <Panel
        id="run"
        title="Pipeline run"
        eyebrow="official"
        aside={<StatusPill label={`run ${runlog.run_id}`} tone="official" />}
        note="Every figure on every screen in this application came from one execution of the pipeline. This is that execution."
      >
        <MetricRow>
          <Metric label="Run id" value={runlog.run_id} small />
          <Metric label="Seed" value={String(runlog.seed)} small />
          <Metric
            label="Exported"
            value={timestamp(runlog.exported_at)}
            small
          />
          <Metric
            label="Corpus generated"
            value={timestamp(runlog.corpus_generated_at)}
            small
          />
          <Metric
            label="Co offending preset"
            value={runlog.co_offending_preset ?? 'unknown'}
            small
          />
        </MetricRow>
      </Panel>

      <Panel
        id="engine-config"
        title="Engine configuration"
        eyebrow="signal"
        note="The parameters that produced this run, recorded rather than described."
      >
        <MetricRow>
          <Metric
            label="Linkage method"
            value={runlog.engine.linkage_method.split(',')[0] ?? 'unknown'}
            small
            caption={<>{runlog.engine.linkage_method}</>}
          />
          <Metric
            label="Merge threshold"
            value={runlog.engine.threshold_llr.toFixed(3)}
            small
            caption={<>log likelihood ratio at the cost weighted boundary</>}
          />
          <Metric
            label="Blocking families"
            value={runlog.engine.blocking_families.join(' + ')}
            small
          />
          <Metric
            label="Collective iterations"
            value={String(runlog.engine.collective_iterations)}
            small
            tone={runlog.engine.collective_converged ? 'resolved' : 'conflict'}
            caption={
              runlog.engine.collective_converged ? (
                <>converged</>
              ) : (
                <>stopped at the cap without reaching a fixed point</>
              )
            }
          />
        </MetricRow>
      </Panel>

      <div className="split">
        <Panel id="stages" title="Stage timings" eyebrow="official" flush>
          <DataTable
            caption="Wall clock per pipeline stage. Resolution is a batch job, so these are batch timings and not request latencies."
            columns={stageColumns}
            rows={runlog.stages}
            rowKey={(r) => r.stage}
          />
        </Panel>

        <Panel id="routes" title="Routing outcome" eyebrow="review" flush>
          <DataTable
            caption="Where every scored candidate pair was sent. Nothing merges silently, and the reject band is the overwhelming majority because the candidate set is deliberately wide."
            columns={routeColumns}
            rows={routeRows}
            rowKey={(r) => r.route}
          />
        </Panel>
      </div>

      <div className="split">
        <Panel id="counts" title="Volumes" eyebrow="navy" flush>
          <DataTable
            caption="What the run processed."
            columns={countColumns}
            rows={countRows}
            rowKey={(r) => r.key}
          />
        </Panel>

        <Panel id="files" title="Provenance" eyebrow="official" flush>
          <DataTable
            caption="Every file this export read. Nothing else contributed to any figure shown in this application."
            columns={fileColumns}
            rows={fileRows}
            rowKey={(r) => r.path}
          />
        </Panel>
      </div>

      <OperatorDecisions />
    </section>
  )
}

/**
 * What people did, as opposed to what the pipeline did.
 *
 * Newest first, because an auditor reads the most recent action and works
 * backwards. Every row carries the role and the scope in force, since a
 * decision without those is anonymous and an anonymous audit entry is not one.
 *
 * The reviewer gets a Reverse control. It appends a reversal and leaves the
 * original entry where it is, so the log only ever grows. Every other role sees
 * the same log without the control.
 */
function OperatorDecisions() {
  const scope = useScope()
  const { log, reverse } = useDecisions()

  const rows = [...log].reverse()

  const columns: Column<(typeof rows)[number]>[] = [
    {
      key: 'action',
      header: 'Action',
      render: (r) => (
        <StatusPill
          label={r.action}
          tone={
            r.action === 'merge'
              ? 'resolved'
              : r.action === 'keep separate'
                ? 'review'
                : 'conflict'
          }
        />
      ),
    },
    {
      key: 'pair',
      header: 'Pair',
      code: true,
      render: (r) => `${r.amid_left} / ${r.amid_right}`,
    },
    {
      key: 'probability',
      header: 'Probability',
      numeric: true,
      render: (r) => r.probability.toFixed(3),
    },
    { key: 'role', header: 'Role', render: (r) => r.role_label },
    {
      key: 'scope',
      header: 'Scope',
      render: (r) => r.district ?? 'statewide',
    },
    {
      key: 'at',
      header: 'When',
      code: true,
      render: (r) => stamp(r.at),
    },
    ...(scope.role.canReverse
      ? [{
          key: 'reverse',
          header: 'Reverse',
          render: (r: (typeof rows)[number]) =>
            r.action === 'merge' ? (
              <button
                type="button"
                className="btn"
                onClick={() =>
                  reverse(r.pair_id, {
                    role: scope.role.id,
                    role_label: scope.role.label,
                    district: scope.district,
                  })
                }
                title="Appends a reversal. The entry above stays in the log."
              >
                Reverse
              </button>
            ) : null,
        }]
      : []),
  ]

  if (!rows.length) {
    return (
      <Panel
        id="decisions"
        title="Operator decisions"
        eyebrow="review"
        aside={<StatusPill label="nothing decided yet" tone="review" />}
      >
        <p className="note">
          <strong>No decisions have been taken in this browser.</strong> The
          review queue at <span className="mono">/identities</span> is where
          they are made, and the Records operator, the SCRB analyst and the
          Reviewer may make them.
        </p>
        <p className="note">
          An empty table would suggest the log failed to load. It did not.
          There is nothing in it.
        </p>
      </Panel>
    )
  }

  return (
    <Panel
      id="decisions"
      title="Operator decisions"
      eyebrow="review"
      aside={
        <StatusPill
          label={scope.role.canReverse ? 'reversal available' : 'append only'}
          tone="official"
        />
      }
      flush
      note={
        <>
          What people did, newest first. This log is append only: a reversal
          adds an entry and never removes the one it reverses, so an auditor can
          always see that a merge was made before it was undone.{' '}
          {scope.role.canReverse
            ? 'Your role may reverse a merge.'
            : `${scope.role.label} sees this log and cannot reverse an entry.`}
        </>
      }
    >
      <DataTable
        caption="Every decision taken in this browser, newest first, with the role and jurisdiction in force at the time."
        columns={columns}
        rows={rows}
        rowKey={(r, i) => `${r.pair_id}-${r.at}-${i}`}
      />
    </Panel>
  )
}
