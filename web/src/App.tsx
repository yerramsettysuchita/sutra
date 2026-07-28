import { useMemo } from 'react'
import { HashRouter, Route, Routes } from 'react-router-dom'

import { NotBuilt } from './components/NotBuilt'
import { Shell } from './components/Shell'
import { Panel, StatusPill } from './components/primitives'
import { Skeleton, SkeletonBars } from './components/hero'
import { useReports } from './data/useReports'
import { useT } from './i18n/useLanguage'
import { applyScope } from './scope/filter'
import { ScopeProvider, useScope } from './scope/useScope'
import type { Reports } from './data/types'
import { Ask } from './screens/Ask'
import { AuditTrail } from './screens/AuditTrail'
import { Cases } from './screens/Cases'
import { CorpusAudit } from './screens/CorpusAudit'
import { Evaluation } from './screens/Evaluation'
import { Hotspots } from './screens/Hotspots'
import { Network } from './screens/Network'
import { ReviewQueue } from './screens/ReviewQueue'
import { Status } from './screens/Status'

export default function App() {
  const state = useReports()
  const t = useT()

  if (state.status === 'loading') {
    return (
      <div className="shell">
        <p className="visually-hidden" role="status" aria-live="polite">
          Reading the engine output.
        </p>
        <div className="masthead-block">
          <div className="masthead">
            <div style={{ width: '100%' }}>
              <Skeleton lines={3} figure />
            </div>
          </div>
        </div>
        <div className="stack">
          <Panel title="Loading" eyebrow="navy">
            <SkeletonBars rows={5} />
          </Panel>
          <div className="split--two-thirds">
            <Panel title=" " eyebrow="navy">
              <Skeleton lines={4} figure />
            </Panel>
            <Panel title=" " eyebrow="navy">
              <Skeleton lines={3} />
            </Panel>
          </div>
        </div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="shell">
        <div className="state">
          <Panel
            title="No corpus to read"
            eyebrow="conflict"
            aside={<StatusPill label="not generated" tone="conflict" />}
          >
            <p className="note" role="alert">
              Every screen reads real engine output rather than a fixture, so
              there is nothing to show until the corpus exists.
            </p>
            <p className="note">
              <span className="mono">{state.message}</span>
            </p>
            <code className="state__cmd">
              {'make gen\nmake stats\nmake block\nmake resolve\nmake eval'}
            </code>
          </Panel>
        </div>
      </div>
    )
  }

  const { reports } = state

  return <Scoped reports={reports} t={t} />
}

/**
 * The scope has to sit inside a component that already has the reports, because
 * the district picker offers the districts the corpus actually contains rather
 * than a hardcoded list, and the filter needs the reports to project.
 */
function Scoped({
  reports,
  t,
}: {
  reports: Reports
  t: (text: string) => string
}) {
  const districts = useMemo(() => {
    const names = new Set<string>()
    for (const row of reports.hotspots?.districts ?? []) names.add(row.district)
    for (const c of reports.cases?.cases ?? []) names.add(c.district)
    for (const i of reports.identities?.identities ?? []) {
      for (const c of i.cases) names.add(c.district)
    }
    return [...names].sort()
  }, [reports])

  return (
    <ScopeProvider districts={districts}>
      <ScopedRoutes reports={reports} districts={districts} t={t} />
    </ScopeProvider>
  )
}

function ScopedRoutes({
  reports: unscoped,
  districts,
  t,
}: {
  reports: Reports
  districts: string[]
  t: (text: string) => string
}) {
  const scope = useScope()
  const { reports, effect } = useMemo(
    () => applyScope(unscoped, scope.district),
    [unscoped, scope.district],
  )

  return (
    /* Hash routing, because Catalyst Web Client Hosting serves static files
       with no rewrite rule, so a deep link under browser history routing would
       return 404 on refresh. */
    <HashRouter>
      <a className="skip-link" href="#main">
        {t('Skip to main content')}
      </a>
      <Routes>
        <Route element={<Shell reports={reports} districts={districts} />}>
          <Route index element={<CorpusAudit reports={reports} />} />
          <Route path="evaluation" element={<Evaluation reports={unscoped} />} />
          <Route
            path="identities"
            element={<ReviewQueue reports={reports} effect={effect} />}
          />
          <Route path="network" element={<Network reports={reports} effect={effect} />} />
          <Route path="audit" element={<AuditTrail reports={reports} />} />
          <Route path="cases" element={<Cases reports={reports} />} />
          <Route path="hotspots" element={<Hotspots reports={reports} />} />
          <Route path="ask" element={<Ask reports={reports} />} />
          <Route path="status" element={<Status reports={unscoped} />} />
          <Route
            path="*"
            element={
              <NotBuilt
                title="No such screen"
                what="This route does not exist."
                why="Use the rail on the left."
              />
            }
          />
        </Route>
      </Routes>
    </HashRouter>
  )
}
