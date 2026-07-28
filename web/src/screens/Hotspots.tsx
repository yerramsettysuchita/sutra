/**
 * Hotspots and trends, Layer 8.
 *
 * Two surfaces, not one. Case density is what every crime map shows. Offender
 * density needs a person entity, and computing it is only possible after
 * Layers 1 to 7. That distinction leads the screen because it is the reason
 * this is not another heatmap.
 *
 * Rendered as inline SVG. MapLibre is not installed and a scatter plus a bar
 * chart plus a trend line needs no dependency.
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
import { Details, HeroFigure, SubHeader } from '../components/hero'
import { n, pct } from '../data/useReports'
import type { DistrictRow, HotspotsFeed, Reports } from '../data/types'

const RESOLVED_MID = '#2E9E6B'
const CONFLICT_MID = '#D9534A'
const REVIEW_MID = '#B57F14'
const LINE = '#CFCBC1'
const SUNKEN = '#F4F2EE'
const INK3 = '#656C75'

export function Hotspots({ reports }: { reports: Reports }) {
  const feed = reports.hotspots
  const [district, setDistrict] = useState<string | null>(null)

  const selected = useMemo(() => {
    if (!feed) return null
    return (
      feed.trends.find((t) => t.district === district) ?? feed.trends[0] ?? null
    )
  }, [feed, district])

  if (!feed) {
    return (
      <NotBuilt
        title="Hotspots and trends"
        what="Case density and offender density over the case coordinates, district aggregates, and a monthly trend per district with an anomaly flag."
        why="The Layer 8 export has not been produced."
        command={'make resolve\nmake downstream\nmake export'}
      />
    )
  }

  const t = feed.totals

  const districtColumns: Column<DistrictRow>[] = [
    { key: 'district', header: 'District', render: (r) => r.district },
    { key: 'cases', header: 'Cases', numeric: true, render: (r) => n(r.cases) },
    {
      key: 'offenders',
      header: 'Offenders',
      numeric: true,
      render: (r) => <span className="value--resolved">{n(r.offenders)}</span>,
    },
    {
      key: 'before',
      header: 'Apparent before',
      numeric: true,
      render: (r) => (
        <span className="value--conflict">
          {n(r.apparent_offenders_before_resolution)}
        </span>
      ),
    },
    {
      key: 'repeat',
      header: 'Repeat',
      numeric: true,
      render: (r) => n(r.repeat_offenders),
    },
    {
      key: 'ratio',
      header: 'Cases each',
      numeric: true,
      render: (r) => r.cases_per_offender.toFixed(2),
    },
    { key: 'offence', header: 'Most common', render: (r) => r.top_offence ?? '' },
    {
      key: 'bar',
      header: 'Cases',
      width: '8rem',
      render: (r) => (
        <Bar fraction={r.cases / (feed.districts[0]?.cases ?? 1)} tone="signal" />
      ),
    },
  ]

  return (
    <>
      <SubHeader
        title="Hotspots"
        stats={[
          { label: 'Districts', value: String(feed.districts.length) },
          { label: 'Grid cells', value: String(feed.cells) },
          {
            label: 'Inflation removed',
            value: pct(t.inflation_pct, 1),
            tone: 'resolved',
          },
          {
            label: 'Anomalies',
            value: String(feed.anomalous_district_months),
            tone: 'review',
          },
        ]}
      />

      <section className="panel" aria-labelledby="hot-hero">
        <div className="panel__eyebrow panel__eyebrow--resolved" aria-hidden="true" />
        <h2 className="visually-hidden" id="hot-hero">
          Offender density against case density
        </h2>
        <div className="hero">
          <div>
            <p className="note">
              <strong>
                A case density map shows where offences are recorded. Every
                district already has one.
              </strong>{' '}
              Offender density needs a person entity, and without one the same
              man working three stations under three renderings counts as three
              offenders. An area with one busy repeat offender and an area with
              three occasional ones look identical, and they need different
              responses.
            </p>
            <p className="note" style={{ marginTop: 'var(--s-3)' }}>
              Summed over grid cells, this corpus holds{' '}
              <span className="mono">{n(t.offenders)}</span> offender
              occupancies. Counted the way the raw schema forces, it holds{' '}
              <span className="mono">
                {n(t.apparent_offenders_before_resolution)}
              </span>
              . Both rows are summed identically, so the ratio holds.
            </p>
          </div>
          <HeroFigure
            label="Offender inflation removed"
            value={pct(t.inflation_pct, 1)}
            tone="resolved"
            caption={
              <>
                {n(t.inflation_removed)} apparent offenders that were the same
                people written differently
              </>
            }
          />
        </div>
      </section>

      <div className="split--two-thirds">
        <Panel
          id="scatter"
          title="Case coordinates"
          eyebrow="signal"
          note={`Every case placed on its CaseMaster latitude and longitude, binned to ${feed.cell_degrees} degree cells, about 25 km. Circle area is case count. Colour is cases per offender, so a dark cell is a small group working an area repeatedly rather than simply a busy one.`}
        >
          <Scatter feed={feed} />
        </Panel>

        <Panel id="scatter-key" title="Reading the map" eyebrow="official">
          <MetricRow>
            <Metric
              label="Cases placed"
              value={t.cases_placed}
              small
              caption={<>across {feed.cells} occupied cells</>}
            />
            <Metric
              label="Anomalous district months"
              value={feed.anomalous_district_months}
              small
              tone="review"
              caption={
                <>
                  above {feed.anomaly_multiple}x the trailing{' '}
                  {feed.trailing_months} month median, with at least{' '}
                  {feed.min_cases_to_flag} cases
                </>
              }
            />
          </MetricRow>
          <Rule />
          <p className="note">
            The multiple was fixed at{' '}
            <span className="mono">{feed.anomaly_multiple}</span> before any
            measurement and has not been adjusted since. A twelve month
            trailing window is used so the baseline sees through seasonality
            rather than tracking it.
          </p>
        </Panel>
      </div>

      <Panel id="districts" title="By district" eyebrow="navy" flush>
        <DataTable
          caption="District aggregates through the Unit hierarchy. Apparent before is what a join on AccusedName would have counted."
          columns={districtColumns}
          rows={feed.districts}
          rowKey={(r) => r.district}
        />
      </Panel>

      <Panel
        id="trend"
        title="Monthly trend"
        eyebrow={selected && selected.anomalous_months ? 'review' : 'signal'}
        aside={
          <label className="field" style={{ minWidth: '12rem' }}>
            <span className="visually-hidden">District</span>
            <select
              className="field__control"
              value={selected?.district ?? ''}
              onChange={(e) => setDistrict(e.target.value)}
            >
              {feed.trends.map((row) => (
                <option key={row.district} value={row.district}>
                  {row.district}
                </option>
              ))}
            </select>
          </label>
        }
        note={
          selected
            ? `${selected.district}, ${n(selected.total_cases)} cases across ${feed.months.length} months, ${selected.anomalous_months} of them flagged.`
            : undefined
        }
      >
        {selected && <Trend feed={feed} series={selected.series} />}
      </Panel>
    </>
  )
}

/* -------------------------------------------------------------- scatter */

function Scatter({ feed }: { feed: HotspotsFeed }) {
  const lats = feed.grid.map((c) => c.lat)
  const lons = feed.grid.map((c) => c.lon)
  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)
  const maxCases = Math.max(...feed.grid.map((c) => c.cases))
  const maxRatio = Math.max(...feed.grid.map((c) => c.cases_per_offender))

  const W = 520
  const H = 400
  const pad = 18

  // Latitude increases northward, so y is inverted to put north at the top.
  const x = (lon: number) => pad + ((lon - minLon) / (maxLon - minLon || 1)) * (W - pad * 2)
  const y = (lat: number) => H - pad - ((lat - minLat) / (maxLat - minLat || 1)) * (H - pad * 2)

  // An SVG scatter is invisible to a screen reader whatever its aria-label
  // says, because the label can state the shape and not the values. CLAUDE.md
  // requires a table equivalent behind a toggle and this chart did not have
  // one. The twenty densest cells, which is what a reader would look at.
  const densest = [...feed.grid].sort((a, b) => b.cases - a.cases).slice(0, 20)

  return (
    <>
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="gapfig"
      role="img"
      aria-label={`Scatter of ${feed.cells} occupied grid cells across Karnataka. Circle area is case count, colour intensity is cases per offender. The densest cell holds ${maxCases} cases.`}
    >
      <rect width={W} height={H} fill={SUNKEN} />
      {feed.grid.map((cell) => {
        const r = 3 + Math.sqrt(cell.cases / maxCases) * 16
        const intensity = maxRatio ? cell.cases_per_offender / maxRatio : 0
        return (
          <circle
            key={`${cell.lat},${cell.lon}`}
            cx={x(cell.lon)}
            cy={y(cell.lat)}
            r={r}
            fill={RESOLVED_MID}
            fillOpacity={0.18 + intensity * 0.62}
            stroke={RESOLVED_MID}
            strokeOpacity={0.55}
            strokeWidth="0.75"
          />
        )
      })}
      <text x={pad} y={14} fontSize="10" fill={INK3} fontFamily="Inter Tight, sans-serif">
        north
      </text>
      <text
        x={W - pad}
        y={H - 4}
        fontSize="10"
        fill={INK3}
        textAnchor="end"
        fontFamily="Inter Tight, sans-serif"
      >
        east
      </text>
    </svg>
    <Details summary="Grid cells as a table" open={false}>
      <DataTable
        caption="The twenty densest grid cells, the same data the scatter plots. Latitude and longitude are the cell centre."
        columns={[
          { key: 'lat', header: 'Latitude', numeric: true,
            render: (r) => r.lat.toFixed(2) },
          { key: 'lon', header: 'Longitude', numeric: true,
            render: (r) => r.lon.toFixed(2) },
          { key: 'cases', header: 'Cases', numeric: true,
            render: (r) => n(r.cases) },
          { key: 'offenders', header: 'Offenders', numeric: true,
            render: (r) => n(r.offenders) },
          { key: 'ratio', header: 'Cases each', numeric: true,
            render: (r) => r.cases_per_offender.toFixed(2) },
        ]}
        rows={densest}
        rowKey={(r) => `${r.lat},${r.lon}`}
      />
    </Details>
    </>
  )
}

/* ---------------------------------------------------------------- trend */

function Trend({
  feed,
  series,
}: {
  feed: HotspotsFeed
  series: HotspotsFeed['trends'][number]['series']
}) {
  const W = 900
  const H = 220
  const pad = 30
  const max = Math.max(...series.map((p) => Math.max(p.cases, p.trailing_median)), 1)

  const x = (i: number) => pad + (i / Math.max(series.length - 1, 1)) * (W - pad * 2)
  const y = (v: number) => H - pad - (v / max) * (H - pad * 2)

  const line = series.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.cases)}`).join(' ')
  const median = series
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.trailing_median)}`)
    .join(' ')
  const flagged = series.filter((p) => p.anomaly)

  return (
    <>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="gapfig"
        role="img"
        aria-label={`Monthly case counts over ${series.length} months, peak ${max}. ${flagged.length} months exceed ${feed.anomaly_multiple} times the trailing median and are flagged.`}
      >
        <rect width={W} height={H} fill={SUNKEN} />
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} stroke={LINE} />
        <path d={median} fill="none" stroke={REVIEW_MID} strokeWidth="1.25"
              strokeDasharray="4 3" />
        <path d={line} fill="none" stroke={RESOLVED_MID} strokeWidth="2" />
        {flagged.map((p) => {
          const i = series.indexOf(p)
          return (
            <circle key={p.month} cx={x(i)} cy={y(p.cases)} r="4.5"
                    fill={CONFLICT_MID} />
          )
        })}
        <text x={pad} y={H - 10} fontSize="9" fill={INK3}
              fontFamily="JetBrains Mono, monospace">
          {series[0]?.month}
        </text>
        <text x={W - pad} y={H - 10} fontSize="9" fill={INK3} textAnchor="end"
              fontFamily="JetBrains Mono, monospace">
          {series[series.length - 1]?.month}
        </text>
      </svg>
      <div className="gap-bar__legend" style={{ marginTop: 'var(--s-3)' }}>
        <span>
          <i className="swatch swatch--resolved" aria-hidden="true" />
          monthly cases
        </span>
        <span>
          <i
            className="swatch"
            style={{ background: REVIEW_MID }}
            aria-hidden="true"
          />
          trailing {feed.trailing_months} month median
        </span>
        <span>
          <i className="swatch swatch--conflict" aria-hidden="true" />
          flagged, above {feed.anomaly_multiple}x the median
        </span>
      </div>
      {/* The line chart is invisible to assistive technology. Same data. */}
      <Details summary="Monthly trend as a table" open={false}>
        <DataTable
          caption="Every month in the series, its case count, the trailing median it is compared against, and whether it was flagged as anomalous."
          columns={[
            { key: 'month', header: 'Month', code: true, render: (r) => r.month },
            { key: 'cases', header: 'Cases', numeric: true,
              render: (r) => n(r.cases) },
            { key: 'median', header: 'Trailing median', numeric: true,
              render: (r) => r.trailing_median.toFixed(1) },
            { key: 'flag', header: 'Status',
              render: (r) => (
                <StatusPill
                  label={r.anomaly ? 'flagged' : 'within range'}
                  tone={r.anomaly ? 'conflict' : 'resolved'}
                />
              ) },
          ]}
          rows={series}
          rowKey={(r) => r.month}
        />
      </Details>
    </>
  )
}
