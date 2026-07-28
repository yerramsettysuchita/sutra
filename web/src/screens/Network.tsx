/**
 * Offender profile and co offender network.
 *
 * The graph is the one place three dimensions would be tempting and is not
 * used, because a co offender neighbourhood at this size is a flat graph and
 * adding a third axis would be decoration. See CLAUDE.md on earned depth.
 *
 * Accessibility. Cytoscape renders to a canvas and is invisible to a screen
 * reader, so the same edges are available as a table behind a toggle and the
 * toggle is a real control rather than a hidden fallback.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'

import { HeroFigure, SubHeader } from '../components/hero'
import type { ScopeEffect } from '../scope/filter'

import {
  DataTable,
  Metric,
  MetricRow,
  Panel,
  Rule,
  StatusPill,
  type Column,
} from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import { n } from '../data/useReports'
import type { Identity, NetworkEdge, Reports } from '../data/types'

const TOKENS = {
  resolved: '#2E9E6B',
  resolvedDeep: '#0F5D3C',
  line: '#CFCBC1',
  ink: '#14171C',
  ink3: '#656C75',
  navy: '#16305C',
  surface: '#FFFFFF',
  sunken: '#F4F2EE',
}

/** Kannada block, U+0C80 to U+0CFF. Tested by code point rather than by a
 *  literal character range, so the source stays ASCII safe. */
function hasKannada(text: string): boolean {
  for (const ch of text) {
    const point = ch.codePointAt(0) ?? 0
    if (point >= 0x0c80 && point <= 0x0cff) return true
  }
  return false
}

export function Network({
  reports,
  effect,
}: {
  reports: Reports
  effect?: ScopeEffect | null
}) {
  const { identities, network, profiles } = reports
  // A search result arrives as #/network?identity=R000412.
  //
  // Read off the hash rather than through useSearchParams, because
  // react-router-dom resolves as CommonJS under server side rendering and a
  // named hook import fails there while working in the browser. The hook would
  // parse exactly this string, so nothing is lost and the screen stays
  // renderable outside a router, which is what the smoke test needs.
  const requested = useMemo(() => {
    if (typeof window === 'undefined') return null
    const hash = window.location.hash
    const q = hash.indexOf('?')
    if (q === -1) return null
    return new URLSearchParams(hash.slice(q + 1)).get('identity')
  }, [])

  const [selected, setSelected] = useState<string | null>(requested)

  useEffect(() => {
    if (requested) setSelected(requested)
  }, [requested])
  const [showTable, setShowTable] = useState(false)
  const [phase, setPhase] = useState<'before' | 'after'>('after')

  const list = identities?.identities ?? []
  const current = useMemo(
    () => list.find((i) => i.identity === selected) ?? list[0] ?? null,
    [list, selected],
  )

  if (!identities || !network) {
    return (
      <NotBuilt
        title="Offender network"
        what="Resolved identities, their name variants across scripts, and the co offender edges resolution recovered."
        why="The identity and network exports have not been produced."
        command={'make resolve\npython scripts/export_web.py'}
      />
    )
  }

  const boundaryCut = effect && effect.edges.cutAtBoundary > 0 ? (
    <Panel
      id="network-scope"
      title="This network is cut at the district boundary"
      eyebrow="signal"
      aside={<StatusPill label="view filter, not enforcement" tone="signal" />}
    >
      <p className="note">
        Showing {n(effect.edges.after)} of {n(effect.edges.before)} co offender
        edges. A further {n(effect.edges.cutAtBoundary)}{' '}
        {effect.edges.cutAtBoundary === 1 ? 'edge has' : 'edges have'} one end
        inside this jurisdiction and one outside, so the relationship exists and
        the other end is not shown. That is a real cost of scoping a network by
        place, and it is stated rather than hidden by drawing a shorter graph.
      </p>
      <p className="note">
        This is a client side view filter demonstrating the access model. The
        underlying JSON is served in full, Catalyst Authentication is not built
        and server side enforcement is not built. See /status.
      </p>
    </Panel>
  ) : null

  const neighbourEdges = current
    ? network.edges.filter(
        (e) => e.source === current.identity || e.target === current.identity,
      )
    : []
  const recoveredHere = neighbourEdges.filter((e) => e.recovered).length

  // Corpus wide figures from Layer 8, distinct from the exported subgraph.
  const graph = profiles?.graph
  const corpusEdges = Number(graph?.edges ?? 0)
  const corpusRecovered = Number(graph?.edges_recovered_by_resolution ?? 0)
  const corpusShare = corpusEdges ? (corpusRecovered / corpusEdges) * 100 : 0

  return (
    <>
      <SubHeader
        title="Offender network"
        stats={[
          { label: 'Edges', value: n(corpusEdges) },
          {
            label: 'Recovered',
            value: n(corpusRecovered),
            tone: 'resolved',
          },
          { label: 'Share', value: `${corpusShare.toFixed(1)}%`, tone: 'resolved' },
        ]}
      />

      {boundaryCut}

      {/* The second loud moment. One toggle, the whole thesis. */}
      <section className="panel" aria-labelledby="swap-title">
        <div className="panel__eyebrow panel__eyebrow--resolved" aria-hidden="true" />
        <h2 className="visually-hidden" id="swap-title">
          Relationships recovered by resolution
        </h2>
        <div className="hero">
          <div>
            <span className="hero__label">Before and after resolution</span>
            <div className="swap" role="group" aria-label="Show the network before or after resolution">
              <button
                type="button"
                className={`swap__btn${phase === 'before' ? ' swap__btn--on' : ''}`}
                aria-pressed={phase === 'before'}
                onClick={() => setPhase('before')}
              >
                Before
              </button>
              <button
                type="button"
                className={`swap__btn swap__btn--after${phase === 'after' ? ' swap__btn--on' : ''}`}
                aria-pressed={phase === 'after'}
                onClick={() => setPhase('after')}
              >
                After
              </button>
            </div>
            <p className="swap-count" aria-live="polite">
              {phase === 'after' ? (
                <>
                  <strong>{n(corpusRecovered)}</strong> of {n(corpusEdges)}{' '}
                  relationships exist only after resolution,{' '}
                  <strong>{corpusShare.toFixed(1)}%</strong>
                </>
              ) : (
                <>
                  <strong>{n(corpusEdges - corpusRecovered)}</strong> of{' '}
                  {n(corpusEdges)} relationships a naive join would already have
                  found
                </>
              )}
            </p>
            <p className="note" style={{ marginTop: 'var(--s-3)' }}>
              The toggle changes the graph below. These counts are corpus wide,
              from Layer 8 over all {n(Number(graph?.nodes ?? 0))} resolved
              identities. The graph shows the exported neighbourhood only.
            </p>
          </div>
          <HeroFigure
            label="Relationships recovered"
            value={`${corpusShare.toFixed(1)}%`}
            tone="resolved"
            caption={
              <>
                of the co offender network was invisible while one man was
                {' '}{identities.identities[0]?.distinct_renderings ?? 'several'}{' '}
                different apparent people
              </>
            }
          />
        </div>
      </section>

      <Panel
        id="network-summary"
        title="Exported neighbourhood"
        eyebrow="signal"
        note={
          <>
            Edges join two resolved identities that appear on the same FIR. An
            edge is <strong>recovered</strong> when it attaches through a name
            rendering that a naive join would have treated as a different
            person, so it was invisible before resolution.
          </>
        }
      >
        <MetricRow>
          <Metric
            label="Identities shown"
            value={identities.shown}
            small
            caption={<>of {n(identities.total_identities)} resolved</>}
          />
          <Metric label="Edges here" value={network.edges.length} small />
          <Metric
            label="Recovered here"
            value={network.recovered_edges}
            small
            tone="resolved"
          />
          <Metric
            label="Visible before"
            value={network.pre_existing_edges}
            small
            caption={<>a naive join would already have found these</>}
          />
        </MetricRow>
      </Panel>

      <div className="profile">
        <Panel id="identity-list" title="Resolved identities" eyebrow="navy" flush>
          <ul className="idlist" aria-label="Resolved identities by record count">
            {list.map((identity) => (
              <li key={identity.identity}>
                <button
                  type="button"
                  className={`idlist__item${
                    current?.identity === identity.identity
                      ? ' idlist__item--active'
                      : ''
                  }`}
                  aria-current={current?.identity === identity.identity}
                  onClick={() => setSelected(identity.identity)}
                >
                  <span className="idlist__key mono">{identity.identity}</span>
                  <span
                    className={`idlist__name${
                      identity.variants[0]?.script === 'kannada' ? ' kn' : ''
                    }`}
                  >
                    {identity.variants[0]?.name ?? identity.identity}
                  </span>
                  <span className="idlist__meta mono">
                    {identity.record_count} records, {identity.case_count} cases,{' '}
                    {identity.distinct_renderings} renderings
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="stack">
          {current && (
            <>
              <IdentityHeader identity={current} recovered={recoveredHere} />
              <GraphPanel
                identity={current}
                edges={network.edges}
                nodes={network.nodes}
                onSelect={setSelected}
                showTable={showTable}
                onToggleTable={() => setShowTable((v) => !v)}
                phase={phase}
              />
              <CaseHistory identity={current} />
            </>
          )}
        </div>
      </div>
    </>
  )
}

function IdentityHeader({
  identity,
  recovered,
}: {
  identity: Identity
  recovered: number
}) {
  const birth = identity.implied_birth_year
  const birthLabel =
    birth.min === null
      ? 'not recorded'
      : birth.min === birth.max
        ? String(birth.min)
        : `${birth.min} to ${birth.max}`

  return (
    <Panel
      id="identity-header"
      title={identity.identity}
      eyebrow="resolved"
      aside={
        <StatusPill
          label={`merged from ${identity.record_count} records`}
          tone={identity.record_count > 1 ? 'resolved' : 'neutral'}
        />
      }
      note={
        identity.record_count > 1 ? (
          <>
            The KSP record held these as {identity.record_count} unconnected
            accused rows across {identity.case_count} FIRs, written{' '}
            {identity.distinct_renderings} different ways
            {identity.scripts.length > 1 ? ' in two scripts' : ''}. Nothing in
            the schema connects them.
          </>
        ) : (
          <>A single record. Nothing was merged into this identity.</>
        )
      }
    >
      <div className="variants">
        {identity.variants.map((variant) => (
          <span
            key={variant.amid}
            className={`variant${variant.script === 'kannada' ? ' kn' : ''}`}
          >
            <span className="variant__name">{variant.name}</span>
            <span className="variant__amid mono">{variant.amid}</span>
          </span>
        ))}
      </div>
      <Rule />
      <MetricRow>
        <Metric label="Records merged" value={identity.record_count} small />
        <Metric label="Cases" value={identity.case_count} small />
        <Metric
          label="Implied birth year"
          value={birthLabel}
          small
          caption={<>from CrimeRegisteredDate minus AgeYear</>}
        />
        <Metric
          label="Station circle"
          value={identity.primary_circle ?? 'unknown'}
          small
          caption={
            identity.circles.length > 1 ? (
              <>{identity.circles.length} stations in total</>
            ) : undefined
          }
        />
        <Metric
          label="Merge confidence"
          value={
            identity.merge_confidence.mean === null
              ? 'n/a'
              : identity.merge_confidence.mean.toFixed(3)
          }
          small
          tone="resolved"
          caption={
            identity.merge_confidence.edges ? (
              <>
                mean calibrated probability over{' '}
                {identity.merge_confidence.edges} internal edges, weakest{' '}
                {identity.merge_confidence.min?.toFixed(3)}
              </>
            ) : (
              <>no internal edges, single record</>
            )
          }
        />
        <Metric
          label="Recovered edges"
          value={recovered}
          small
          tone="resolved"
          caption={<>co offender links invisible before resolution</>}
        />
      </MetricRow>
    </Panel>
  )
}

function GraphPanel({
  identity,
  edges,
  nodes,
  onSelect,
  showTable,
  onToggleTable,
  phase,
}: {
  identity: Identity
  edges: NetworkEdge[]
  nodes: Reports['network'] extends null ? never : { identity: string; label: string }[]
  onSelect: (id: string) => void
  showTable: boolean
  onToggleTable: () => void
  phase: 'before' | 'after'
}) {
  const container = useRef<HTMLDivElement>(null)
  const [swapping, setSwapping] = useState(false)

  // Cross fade on the phase change. The duration token collapses to almost
  // nothing under prefers-reduced-motion, so the swap becomes instant rather
  // than animated, which is the correct behaviour rather than a lesser one.
  useEffect(() => {
    setSwapping(true)
    const timer = window.setTimeout(() => setSwapping(false), 260)
    return () => window.clearTimeout(timer)
  }, [phase, identity.identity])

  const neighbourhood = useMemo(() => {
    const visible = phase === 'before' ? edges.filter((e) => !e.recovered) : edges
    const touching = visible.filter(
      (e) => e.source === identity.identity || e.target === identity.identity,
    )
    const ids = new Set<string>([identity.identity])
    touching.forEach((e) => {
      ids.add(e.source)
      ids.add(e.target)
    })
    // Second ring, so the shape of the group is visible rather than a star.
    const second = visible.filter((e) => ids.has(e.source) && ids.has(e.target))
    return { ids, edges: second }
  }, [edges, identity.identity, phase])

  const labelOf = useMemo(() => {
    const map = new Map<string, string>()
    nodes.forEach((node) => map.set(node.identity, node.label))
    return map
  }, [nodes])

  useEffect(() => {
    if (!container.current || showTable) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const cy = cytoscape({
      container: container.current,
      elements: [
        ...[...neighbourhood.ids].map((id) => ({
          data: {
            id,
            label: labelOf.get(id) ?? id,
            focus: id === identity.identity ? 1 : 0,
          },
        })),
        ...neighbourhood.edges.map((edge) => ({
          data: {
            id: `${edge.source}|${edge.target}`,
            source: edge.source,
            target: edge.target,
            recovered: edge.recovered ? 1 : 0,
            weight: edge.shared_cases,
          },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': TOKENS.sunken,
            'border-width': 1,
            'border-color': TOKENS.line,
            label: 'data(label)',
            'font-size': 9,
            'font-family': 'Inter Tight, system-ui, sans-serif',
            color: TOKENS.ink,
            'text-valign': 'bottom',
            'text-margin-y': 4,
            width: 18,
            height: 18,
          },
        },
        {
          selector: 'node[focus = 1]',
          style: {
            'background-color': TOKENS.navy,
            'border-color': TOKENS.navy,
            width: 26,
            height: 26,
            'font-weight': 600,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'mapData(weight, 1, 4, 1, 4)',
            'line-color': TOKENS.line,
            'curve-style': 'bezier',
          },
        },
        {
          selector: 'edge[recovered = 1]',
          style: { 'line-color': TOKENS.resolved, width: 2.5 },
        },
      ],
      layout: { name: 'cose', animate: !reduced, animationDuration: 400 },
      wheelSensitivity: 0.2,
    })

    cy.on('tap', 'node', (event) => onSelect(event.target.id()))
    return () => cy.destroy()
  }, [neighbourhood, labelOf, identity.identity, onSelect, showTable])

  const tableRows = neighbourhood.edges.map((edge) => ({
    ...edge,
    other: edge.source === identity.identity ? edge.target : edge.source,
  }))

  const columns: Column<(typeof tableRows)[number]>[] = [
    { key: 'source', header: 'From', code: true, render: (r) => r.source },
    { key: 'target', header: 'To', code: true, render: (r) => r.target },
    {
      key: 'shared',
      header: 'Shared cases',
      numeric: true,
      render: (r) => String(r.shared_cases),
    },
    {
      key: 'crime',
      header: 'Crime numbers',
      code: true,
      render: (r) => r.cases.map((c) => c.crime_no).join(', '),
    },
    {
      key: 'recovered',
      header: 'Status',
      render: (r) =>
        r.recovered ? (
          <StatusPill label="recovered" tone="resolved" />
        ) : (
          <StatusPill label="visible before" tone="neutral" />
        ),
    },
  ]

  return (
    <Panel
      id="graph"
      title="Co offender neighbourhood"
      eyebrow="resolved"
      aside={
        <button
          type="button"
          className="btn"
          aria-pressed={showTable}
          onClick={onToggleTable}
        >
          {showTable ? 'Show graph' : 'Show as table'}
        </button>
      }
      note={
        <>
          Edges in <span className="legend-swatch legend-swatch--resolved" />{' '}
          green were recovered by resolution. Grey edges a naive join would
          already have found. The graph is a canvas and cannot be read by
          assistive technology, so the same edges are available as a table.
        </>
      }
    >
      {showTable ? (
        <DataTable
          caption={`Co offender edges in the neighbourhood of ${identity.identity}. The table equivalent of the graph.`}
          columns={columns}
          rows={tableRows}
          rowKey={(r, i) => `${r.source}-${r.target}-${i}`}
        />
      ) : tableRows.length === 0 ? (
        <p className="note">
          This identity shares no FIR with any other identity in the exported
          set, so it has no co offender edges.
        </p>
      ) : (
        <div className={`graph-wrap${swapping ? ' graph-wrap--swapping' : ''}`}>
          <div
            ref={container}
            className="graph"
            role="img"
            aria-label={`Co offender network around ${identity.identity} ${phase} resolution, ${neighbourhood.ids.size} identities and ${tableRows.length} edges. Use the show as table control for an accessible equivalent.`}
          />
        </div>
      )}
    </Panel>
  )
}

function CaseHistory({ identity }: { identity: Identity }) {
  const columns: Column<Identity['cases'][number]>[] = [
    { key: 'crime_no', header: 'Crime number', code: true, render: (r) => r.crime_no },
    { key: 'registered', header: 'Registered', code: true, render: (r) => r.registered },
    { key: 'subhead', header: 'Offence', render: (r) => r.subhead },
    { key: 'station', header: 'Station', render: (r) => r.station },
    {
      key: 'name',
      header: 'Written as',
      render: (r) => (
        <span className={hasKannada(r.name) ? 'kn' : 'mono'}>{r.name}</span>
      ),
    },
    { key: 'amid', header: 'AMID', code: true, render: (r) => r.amid },
  ]

  return (
    <Panel id="history" title="Case history" eyebrow="official" flush>
      <DataTable
        caption={`Every case this identity appears in, oldest first, with the name as the station wrote it. Before resolution these ${identity.case_count} cases belonged to ${identity.distinct_renderings} apparently different people.`}
        columns={columns}
        rows={identity.cases}
        rowKey={(r, i) => `${r.amid}-${i}`}
      />
    </Panel>
  )
}
