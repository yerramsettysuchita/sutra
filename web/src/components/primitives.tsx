/**
 * SUTRA component primitives.
 *
 * Six pieces. Panel, Rule, Metric, DataTable, StatusPill, AuditStrip. Every
 * screen is built from these and nothing else, so the visual language is
 * settled in one file rather than negotiated per screen.
 *
 * Two rules are enforced here rather than left to discipline.
 *
 * Every number renders in JetBrains Mono with tabular figures. `Metric` and the
 * `num` cell type apply it, so a number cannot reach the page in the interface
 * face by accident.
 *
 * Status never travels as colour alone. `StatusPill` requires a `label`, and
 * that word is what assistive technology reads. The colour is redundant
 * reinforcement, never the carrier.
 *
 * Interface language is applied here too. Panel titles, column headers, status
 * words and metric labels pass through `t`, so a screen writes English and the
 * Kannada rendering follows without the screen knowing. Everything that arrives
 * as a `ReactNode`, which is every explanatory note, is left exactly as written,
 * and so is every value, because values come from the engine.
 */

import type { ReactNode, TdHTMLAttributes } from 'react'

import { useT } from '../i18n/useLanguage'

export type Tone =
  | 'resolved'
  | 'review'
  | 'conflict'
  | 'signal'
  | 'official'
  | 'neutral'

/** Eyebrow tones. `navy` is structural rather than semantic, for panels that
 *  carry no single meaning. */
export type Eyebrow = Exclude<Tone, 'neutral'> | 'navy'

/* ------------------------------------------------------------------ Panel */

export function Panel({
  title,
  note,
  aside,
  eyebrow = 'navy',
  flush = false,
  children,
  id,
}: {
  title?: string
  note?: ReactNode
  /** The one line saying what the number means and why it matters. Not
   *  optional in practice, it is the strongest thing on the page. */
  aside?: ReactNode
  /** Colour enters the page here and nowhere else. Panel bodies stay white. */
  eyebrow?: Eyebrow
  flush?: boolean
  children: ReactNode
  id?: string
}) {
  const t = useT()
  const headingId = id ? `${id}-title` : undefined
  return (
    <section className="panel" aria-labelledby={headingId} id={id}>
      <div className={`panel__eyebrow panel__eyebrow--${eyebrow}`} aria-hidden="true" />
      {title && (
        <header className="panel__head">
          <h2 className="panel__title" id={headingId}>
            {t(title)}
          </h2>
          {aside}
        </header>
      )}
      <div className={`panel__body${flush ? ' panel__body--flush' : ''}`}>
        {note && <p className="panel__note">{note}</p>}
        {note && !flush && <Rule tight />}
        {children}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ StaleNotice */

/**
 * A study measured against an earlier corpus.
 *
 * Some studies cost many minutes to re-run and are deliberately not part of
 * `make all`. That is a reasonable trade and it created a real failure: two of
 * them were rendered as current while describing a corpus that no longer
 * existed. The fix is not to force a re-run, it is to make staleness visible.
 *
 * `scripts/check_freshness.py` writes the `stale` block into the report. This
 * renders it. A figure a reader cannot tell is stale is worse than no figure.
 */
export function StaleNotice({
  stale,
}: {
  stale?: { is_stale: boolean; report_generated_at: string;
            corpus_generated_at: string; refresh_with: string } | null
}) {
  if (!stale?.is_stale) return null
  return (
    <p className="stale" role="note">
      <strong>Measured on an earlier corpus.</strong> This study ran at{' '}
      <span className="mono">{stale.report_generated_at}</span>, and the corpus
      behind every other figure on this page was generated at{' '}
      <span className="mono">{stale.corpus_generated_at}</span>. The figures
      below are not from the run that produced the headline. Refresh with{' '}
      <span className="mono">{stale.refresh_with}</span>.
    </p>
  )
}

/* ------------------------------------------------------------------- Rule */

export function Rule({ tight = false }: { tight?: boolean }) {
  return <hr className={`rule${tight ? ' rule--tight' : ''}`} />
}

/* ----------------------------------------------------------------- Metric */

export function Metric({
  label,
  value,
  unit,
  caption,
  tone,
  small = false,
}: {
  label: string
  value: string | number
  unit?: string
  caption?: ReactNode
  tone?: Tone
  small?: boolean
}) {
  const t = useT()
  return (
    <div className={`metric${tone ? ` metric--${tone}` : ''}`}>
      <span className="metric__label">{t(label)}</span>
      <span className={`metric__value${small ? ' metric__value--sm' : ''}`}>
        {typeof value === 'number' ? value.toLocaleString('en-IN') : value}
        {unit && <span className="metric__unit">{unit}</span>}
      </span>
      {caption && <span className="metric__caption">{caption}</span>}
    </div>
  )
}

export function MetricRow({ children }: { children: ReactNode }) {
  return <div className="metric-row">{children}</div>
}

/* ------------------------------------------------------------- StatusPill */

export function StatusPill({
  label,
  tone = 'neutral',
}: {
  label: string
  tone?: Tone
}) {
  const t = useT()
  return (
    <span className={`pill pill--${tone}`}>
      <span className="pill__dot" aria-hidden="true" />
      {t(label)}
    </span>
  )
}

/* -------------------------------------------------------------- DataTable */

export type Column<T> = {
  key: string
  header: string
  /** Right aligned and monospaced. Every numeric column must set this. */
  numeric?: boolean
  /** Monospaced but left aligned, for identifiers and names. */
  code?: boolean
  render: (row: T) => ReactNode
  width?: string
}

export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
}: {
  caption: string
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string
}) {
  const t = useT()
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={caption}>
      <table className="table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                style={{
                  width: c.width,
                  textAlign: c.numeric ? 'right' : 'left',
                }}
              >
                {t(c.header)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey(row, i)}>
              {columns.map((c, j) => {
                const Cell = (j === 0 ? 'th' : 'td') as 'th' | 'td'
                const props: TdHTMLAttributes<HTMLTableCellElement> = {
                  className: c.numeric ? 'num' : c.code ? 'name' : undefined,
                }
                return (
                  <Cell
                    key={c.key}
                    {...props}
                    {...(j === 0 ? { scope: 'row' as const } : {})}
                  >
                    {c.render(row)}
                  </Cell>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Proportion rendered inline. Hidden from assistive technology, because the
 *  neighbouring cell already states the number it depicts. */
export function Bar({
  fraction,
  tone = 'signal',
}: {
  fraction: number
  tone?: 'signal' | 'resolved' | 'official' | 'review' | 'dim'
}) {
  const width = `${Math.max(1, Math.min(100, fraction * 100))}%`
  const modifier = tone === 'signal' ? '' : ` table__bar--${tone}`
  return (
    <span
      className={`table__bar${modifier}`}
      style={{ width }}
      aria-hidden="true"
    />
  )
}

/* ---------------------------------------------------- Provenance and audit */

export type AuditEntry = { key: string; value: string }

/**
 * The full provenance record, sitting directly under the masthead in official
 * tint. Seed, corpus timestamp, blocking timestamp and every file read.
 *
 * This is the primary copy. A printed sheet leaves the building without its
 * context, so provenance has to be on the page rather than in a footer, and
 * the print sheet keeps it while dropping the pinned strip.
 */
export function ProvenanceBar({ entries }: { entries: AuditEntry[] }) {
  const t = useT()
  return (
    <div className="provenance" aria-label="Provenance of every figure on this screen">
      {entries.map((entry, i) => (
        <span className="provenance__item" key={`${entry.key}-${i}`}>
          <span className="provenance__key">{t(entry.key)}</span>
          <span className="provenance__value mono">{entry.value}</span>
        </span>
      ))}
    </div>
  )
}

/** Compact copy pinned to the bottom, so provenance stays visible after the
 *  masthead has scrolled away. Hidden in print, where the bar above serves. */
export function AuditStrip({ entries }: { entries: AuditEntry[] }) {
  const t = useT()
  return (
    <div
      className="audit-strip"
      role="status"
      aria-live="polite"
      aria-label="Provenance summary"
    >
      {entries.map((entry, i) => (
        <span className="audit-strip__item" key={`${entry.key}-${i}`}>
          {i > 0 && (
            <span className="audit-strip__sep" aria-hidden="true">
              /
            </span>
          )}
          <span className="audit-strip__key">{t(entry.key)}</span>
          <span className="audit-strip__value">{entry.value}</span>
        </span>
      ))}
    </div>
  )
}
